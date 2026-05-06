import json
from typing import Optional

import numpy as np

from .ingest import _load_meta, _save_meta, INDEXES_DIR

CANDIDATES_PER_QUERY = 20


def list_documents() -> list[dict]:
    meta = _load_meta()
    return [{"doc_id": doc_id, **info} for doc_id, info in meta.items()]


def delete_document(doc_id: str) -> dict:
    meta = _load_meta()
    if doc_id not in meta:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Document not found.")

    # Remove index files from disk
    index_dir = INDEXES_DIR / doc_id
    if index_dir.exists():
        for f in index_dir.iterdir():
            f.unlink()
        index_dir.rmdir()

    del meta[doc_id]
    _save_meta(meta)
    return {"doc_id": doc_id, "status": "deleted"}


def _normalise_embedding(embedding: list[float]) -> np.ndarray:
    q = np.array(embedding, dtype=np.float32)
    return q / (np.linalg.norm(q) + 1e-9)


def _dedupe_results(results: list[dict]) -> list[dict]:
    deduped: list[dict] = []
    seen = set()
    for result in results:
        key = (result["doc_id"], result["page"], result["text"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(result)
    return deduped


def _load_active_indexes(doc_ids: Optional[list[str]]) -> list[tuple[str, np.ndarray, list[dict]]]:
    meta = _load_meta()
    active_ids = doc_ids if doc_ids else list(meta.keys())
    indexes = []

    for doc_id in active_ids:
        if doc_id not in meta:
            continue

        index_dir = INDEXES_DIR / doc_id
        vectors_path = index_dir / "vectors.npy"
        chunks_path = index_dir / "chunks.json"

        if not vectors_path.exists() or not chunks_path.exists():
            continue

        vectors = np.load(str(vectors_path))
        chunks = json.loads(chunks_path.read_text(encoding="utf-8"))
        indexes.append((doc_id, vectors, chunks))

    return indexes


def query_documents(question_embedding: list[float], doc_ids: Optional[list[str]], top_k: int = 5) -> list[dict]:
    """
    Search all active numpy indexes and return the top-k chunks
    merged and ranked by cosine similarity score.

    Each returned chunk dict has: text, filename, page, doc_id, score.
    """
    q = _normalise_embedding(question_embedding)

    all_results: list[dict] = []

    for doc_id, vectors, chunks in _load_active_indexes(doc_ids):
        scores = vectors @ q
        for idx, score in enumerate(scores.tolist()):
            all_results.append({
                "text": chunks[idx]["text"],
                "filename": chunks[idx]["filename"],
                "page": chunks[idx]["page"],
                "doc_id": doc_id,
                "score": score,
            })

    all_results.sort(key=lambda r: r["score"], reverse=True)
    return all_results[:top_k]


def query_documents_multi(
    query_embeddings: list[list[float]],
    doc_ids: Optional[list[str]],
    candidates_per_query: int = CANDIDATES_PER_QUERY,
) -> list[dict]:
    """
    Search active indexes with multiple query embeddings.

    Results are ranked by their best score across query variants and deduped by
    document, page, and exact chunk text.
    """
    indexes = _load_active_indexes(doc_ids)
    all_results: list[dict] = []

    for query_index, embedding in enumerate(query_embeddings):
        q = _normalise_embedding(embedding)
        query_results: list[dict] = []

        for doc_id, vectors, chunks in indexes:
            scores = vectors @ q
            for idx, score in enumerate(scores.tolist()):
                query_results.append({
                    "text": chunks[idx]["text"],
                    "filename": chunks[idx]["filename"],
                    "page": chunks[idx]["page"],
                    "doc_id": doc_id,
                    "score": score,
                    "query_index": query_index,
                })

        query_results.sort(key=lambda r: r["score"], reverse=True)
        all_results.extend(query_results[:candidates_per_query])

    all_results.sort(key=lambda r: r["score"], reverse=True)
    return _dedupe_results(all_results)
