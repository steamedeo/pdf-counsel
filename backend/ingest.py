import hashlib
import json
import os
import re
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import numpy as np
from filelock import FileLock
from pypdf import PdfReader
from openai import OpenAI

from .logging_config import get_logger

log = get_logger(__name__)

INDEXES_DIR = Path(__file__).parent.parent / "indexes"
META_FILE = INDEXES_DIR / "documents.json"

# Legal clause markers: "Article 5", "Section 3.1", "§ 12", "1.", "(a)", "CHAPTER"
_LEGAL_BOUNDARY = re.compile(
    r"(?m)^(?:"
    r"(?:Article|ARTICLE|Section|SECTION|Clause|CLAUSE|Chapter|CHAPTER)\s+[\dA-Z]"
    r"|§\s*\d"
    r"|\d+\.\s+[A-Z]"       # "1. Definitions"
    r"|\([a-z]\)\s+[A-Z]"   # "(a) The party"
    r"|WHEREAS"
    r"|DEFINITIONS"
    r"|RECITALS"
    r")"
)

EMBED_MODEL = "text-embedding-3-small"
EMBED_BATCH = 100  # OpenAI allows up to 2048 inputs per call; 100 is safe


def _load_meta() -> dict:
    if META_FILE.exists():
        return json.loads(META_FILE.read_text())
    return {}


_META_LOCK = FileLock(str(META_FILE) + ".lock")


def _save_meta(meta: dict) -> None:
    INDEXES_DIR.mkdir(exist_ok=True)
    with _META_LOCK:
        META_FILE.write_text(json.dumps(meta, indent=2), encoding="utf-8")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_pages(pdf_bytes: bytes) -> list[dict]:
    """Return list of {page: int, text: str} for each page."""
    reader = PdfReader(BytesIO(pdf_bytes))
    pages = []
    for i, page in enumerate(reader.pages, 1):
        text = page.extract_text() or ""
        text = text.strip()
        if text:
            pages.append({"page": i, "text": text})
    return pages


def _split_into_chunks(pages: list[dict]) -> list[dict]:
    """
    Structure-aware splitting for legal documents.

    Strategy:
    1. Concatenate all page text, preserving page-number metadata per character range.
    2. Find legal clause boundaries using regex (Article, Section, §, numbered lists…).
    3. Split at those boundaries first — each clause becomes a candidate chunk.
    4. If a clause is too long (> MAX_TOKENS chars proxy), fall back to sentence splitting
       within that clause so no chunk exceeds the limit.
    5. If a clause is very short, merge it with the next one (avoids micro-chunks on
       sub-clauses like "(i) see above").

    Why this beats fixed-size chunking for legal text:
    - A contract clause is the natural unit of meaning. Splitting mid-clause loses
      the subject ("The Licensee shall…") or the condition ("…unless Article 3 applies").
    - Retrieval precision is higher because each chunk is a complete legal thought.
    - Citations are more trustworthy — the returned passage is the actual clause,
      not an arbitrary window that starts mid-sentence.
    """
    MAX_CHARS = 3000   # ~750 tokens, safe for text-embedding-3-small (8191 token limit)
    MIN_CHARS = 120    # merge chunks shorter than this with the next

    # Build a flat list of (page_number, line) tuples
    lines_with_pages: list[tuple[int, str]] = []
    for p in pages:
        for line in p["text"].splitlines():
            lines_with_pages.append((p["page"], line))

    # Group lines into clause segments by detecting legal boundaries
    segments: list[dict] = []  # {text, start_page}
    current_lines: list[str] = []
    current_page = lines_with_pages[0][0] if lines_with_pages else 1

    for page_num, line in lines_with_pages:
        if _LEGAL_BOUNDARY.match(line) and current_lines:
            segments.append(
                {"text": "\n".join(current_lines), "page": current_page})
            current_lines = [line]
            current_page = page_num
        else:
            if not current_lines:
                current_page = page_num
            current_lines.append(line)

    if current_lines:
        segments.append(
            {"text": "\n".join(current_lines), "page": current_page})

    # Post-process: split oversized segments, merge undersized ones
    chunks: list[dict] = []
    for seg in segments:
        text = seg["text"].strip()
        if not text:
            continue

        if len(text) <= MAX_CHARS:
            chunks.append({"text": text, "page": seg["page"]})
        else:
            # Fall back to sentence-boundary splitting within the clause
            sentences = re.split(r"(?<=[.;])\s+", text)
            current = ""
            for sentence in sentences:
                if len(current) + len(sentence) + 1 > MAX_CHARS and current:
                    chunks.append(
                        {"text": current.strip(), "page": seg["page"]})
                    current = sentence
                else:
                    current = (current + " " +
                               sentence).strip() if current else sentence
            if current:
                chunks.append({"text": current.strip(), "page": seg["page"]})

    # Merge micro-chunks forward
    merged: list[dict] = []
    for chunk in chunks:
        if merged and len(merged[-1]["text"]) < MIN_CHARS:
            merged[-1]["text"] += "\n" + chunk["text"]
        else:
            merged.append(chunk)

    return merged


def _embed_chunks(chunks: list[dict], filename: str) -> tuple[np.ndarray, list[dict]]:
    """Call OpenAI embeddings in batches, return (matrix, enriched_chunks)."""
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], timeout=30.0)
    texts = [c["text"] for c in chunks]
    vectors = []

    for i in range(0, len(texts), EMBED_BATCH):
        batch = texts[i: i + EMBED_BATCH]
        response = client.embeddings.create(model=EMBED_MODEL, input=batch)
        usage = getattr(response, "usage", None)
        if usage:
            log.info("llm call=ingest_embed batch_start=%d total_tokens=%s", i, getattr(usage, "total_tokens", "?"))
        # Response items are ordered by index
        batch_vecs = [item.embedding for item in sorted(
            response.data, key=lambda x: x.index)]
        vectors.extend(batch_vecs)

    matrix = np.array(vectors, dtype=np.float32)
    # L2-normalise so cosine similarity = dot product at query time
    norms = np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-9
    matrix = matrix / norms

    enriched = [
        {"text": c["text"], "page": c["page"], "filename": filename}
        for c in chunks
    ]
    return matrix, enriched


def _sanitize_filename(filename: str) -> str:
    name = Path(filename).name  # strip any directory components
    name = re.sub(r"[^\w\s\-.]", "", name)  # allow only word chars, spaces, hyphens, dots
    return name[:200] or "unnamed.pdf"


def process_pdf(pdf_bytes: bytes, filename: str) -> dict:
    filename = _sanitize_filename(filename)
    doc_id = hashlib.sha256(pdf_bytes).hexdigest()[:16]
    meta = _load_meta()

    if doc_id in meta:
        return {
            "doc_id": doc_id,
            "filename": meta[doc_id]["filename"],
            "chunk_count": meta[doc_id]["chunk_count"],
            "status": "already_exists",
        }

    pages = _extract_pages(pdf_bytes)
    chunks = _split_into_chunks(pages)
    matrix, enriched_chunks = _embed_chunks(chunks, filename)

    index_dir = INDEXES_DIR / doc_id
    index_dir.mkdir(parents=True, exist_ok=True)
    np.save(str(index_dir / "vectors.npy"), matrix)
    (index_dir / "chunks.json").write_text(json.dumps(enriched_chunks,
                                                      ensure_ascii=False), encoding="utf-8")

    reader = PdfReader(BytesIO(pdf_bytes))
    page_count = len(reader.pages)

    meta[doc_id] = {
        "filename": filename,
        "chunk_count": len(chunks),
        "page_count": page_count,
        "file_size": len(pdf_bytes),
        "indexed_at": _now_iso(),
        "status": "indexed",
    }
    _save_meta(meta)

    return {
        "doc_id": doc_id,
        "filename": filename,
        "chunk_count": len(chunks),
        "status": "indexed",
    }
