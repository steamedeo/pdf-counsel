import json
import os
import re
from typing import Optional, AsyncGenerator

from openai import AsyncOpenAI

from . import retrieval
from .logging_config import get_logger

log = get_logger(__name__)


def _log_usage(call: str, response) -> None:
    usage = getattr(response, "usage", None)
    if usage is None:
        return
    parts = [f"call={call}"]
    for attr in ("input_tokens", "output_tokens", "total_tokens",
                 "prompt_tokens", "completion_tokens"):
        val = getattr(usage, attr, None)
        if val is not None:
            parts.append(f"{attr}={val}")
    log.info("llm %s", " ".join(parts))

QUERY_VARIANT_COUNT = 3
CANDIDATES_PER_QUERY = 20
RERANK_MAX_CHUNKS = 6
EMBED_MODEL = "text-embedding-3-small"

SYSTEM_PROMPT = """You are a document analysis assistant. You answer questions strictly and only based on the source passages provided to you below.

Rules you must never break:
1. Only make claims that are directly supported by the provided passages.
2. Quote source text verbatim — never paraphrase a source passage when citing it.
3. Keep the answer text focused on the answer. The app displays document names and page numbers below your response, so do not add a separate source list or trailing source sentence.
4. When you use a passage, add its source marker in parentheses, for example: (Source 1). Do not mention filenames or page numbers.
5. If the answer cannot be found in any provided passage, say exactly: "I could not find an answer to this question in the loaded documents."
6. Never infer, extrapolate, or answer from general knowledge.
"""

NOT_FOUND_ANSWER = "I could not find an answer to this question in the loaded documents."


def _build_context(chunks: list[dict]) -> str:
    parts = []
    for i, chunk in enumerate(chunks, 1):
        parts.append(
            f"[Source {i}] {chunk['filename']}, page {chunk['page']}:\n\"{chunk['text']}\""
        )
    return "\n\n".join(parts)


def _extract_response_text(response) -> str:
    text = getattr(response, "output_text", None)
    if isinstance(text, str):
        return text

    parts = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            content_text = getattr(content, "text", None)
            if content_text:
                parts.append(content_text)
    return "".join(parts)


def _fallback_query_variants(question: str) -> list[str]:
    variants = [question]
    lowered = question.lower()

    aliases = []
    if "ai act" in lowered or "regolamento sull" in lowered or "intelligenza artificiale" in lowered:
        aliases.append(
            "AI Act regolamento sull'intelligenza artificiale regolamento sull'IA artificial intelligence act"
        )
    if "vigore" in lowered or "force" in lowered:
        aliases.append("entrata in vigore entra in vigore applicazione data effetto ventesimo giorno")
    if "anno" in lowered or "year" in lowered:
        aliases.append("anno data del regolamento adottato pubblicato entrato in vigore")

    if aliases:
        variants.append(f"{question} {' '.join(aliases)}")

    keywords = re.sub(r"[^\w\s']", " ", question, flags=re.UNICODE)
    keywords = re.sub(r"\s+", " ", keywords).strip()
    if keywords and keywords not in variants:
        variants.append(keywords)

    while len(variants) < QUERY_VARIANT_COUNT:
        variants.append(question)

    return variants[:QUERY_VARIANT_COUNT]


def _parse_query_variants(raw: str, question: str) -> list[str]:
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            parsed = parsed.get("queries", [])
        if not isinstance(parsed, list):
            raise ValueError("query rewrite response was not a list")

        variants = [str(item).strip() for item in parsed if str(item).strip()]
    except Exception:
        variants = []

    result = [question]
    for variant in variants:
        if variant not in result:
            result.append(variant)
        if len(result) >= QUERY_VARIANT_COUNT:
            break

    if len(result) < QUERY_VARIANT_COUNT:
        for variant in _fallback_query_variants(question):
            if variant not in result:
                result.append(variant)
            if len(result) >= QUERY_VARIANT_COUNT:
                break

    return result[:QUERY_VARIANT_COUNT]


async def _build_query_variants(client: AsyncOpenAI, question: str) -> list[str]:
    prompt = f"""Generate exactly {QUERY_VARIANT_COUNT} search queries for retrieving legal-document passages.

Rules:
- Return only a JSON array of strings.
- The first query must be the user's original question unchanged.
- Preserve the user's language where possible.
- Include one legal phrasing variant.
- Include one keyword-focused variant.
- Expand aliases such as AI Act, regolamento sull'IA, regolamento sull'intelligenza artificiale.

User question: {question}
"""
    try:
        response = await client.responses.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            input=prompt,
        )
        _log_usage("query_rewrite", response)
        return _parse_query_variants(_extract_response_text(response), question)
    except Exception:
        return _fallback_query_variants(question)


def _build_rerank_context(chunks: list[dict]) -> str:
    parts = []
    for i, chunk in enumerate(chunks, 1):
        text = chunk["text"]
        if len(text) > 1800:
            text = text[:1800] + "..."
        parts.append(
            f"[Candidate {i}] {chunk['filename']}, page {chunk['page']}:\n{text}"
        )
    return "\n\n".join(parts)


def _parse_rerank_indices(raw: str, limit: int, max_items: int = RERANK_MAX_CHUNKS) -> list[int]:
    match = re.search(r"\[[\s\d,]*\]", raw)
    if not match:
        return []

    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []

    indices: list[int] = []
    seen = set()
    for item in parsed:
        if not isinstance(item, int):
            continue
        if item < 1 or item > limit or item in seen:
            continue
        seen.add(item)
        indices.append(item)
        if len(indices) >= max_items:
            break

    return indices


async def _rerank_chunks(client: AsyncOpenAI, question: str, chunks: list[dict], top_k: int) -> list[dict]:
    if not chunks:
        return []

    max_items = min(top_k, RERANK_MAX_CHUNKS)
    prompt = f"""Select the candidate passages that can directly answer the user's question.

Return only a JSON array of candidate numbers, for example [1, 4].
Return [] if none of the candidates directly answer the question.
Select at most {max_items} candidates.

Question: {question}

Candidates:
{_build_rerank_context(chunks)}
"""
    try:
        response = await client.responses.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            input=prompt,
        )
        _log_usage("rerank", response)
        indices = _parse_rerank_indices(
            _extract_response_text(response),
            limit=len(chunks),
            max_items=max_items,
        )
    except Exception:
        indices = []

    return [chunks[index - 1] for index in indices]


def _citations_for_answer(answer: str, chunks: list[dict]) -> list[dict]:
    if NOT_FOUND_ANSWER.lower() in answer.lower():
        return []

    source_numbers = {
        int(match)
        for match in re.findall(r"\bSource\s*(\d+)\b", answer, flags=re.IGNORECASE)
    }

    if source_numbers:
        selected = [
            chunks[index - 1]
            for index in sorted(source_numbers)
            if 1 <= index <= len(chunks)
        ]
    else:
        selected = []

    citations = []
    seen = set()
    for chunk in selected:
        key = (chunk["filename"], chunk["page"])
        if key in seen:
            continue
        seen.add(key)
        citations.append({"filename": chunk["filename"], "page": chunk["page"]})
    return citations


async def stream_answer(question: str, doc_ids: Optional[list[str]], top_k: int = 5) -> AsyncGenerator[str, None]:
    try:
        client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"], timeout=30.0)

        query_variants = await _build_query_variants(client, question)

        embed_response = await client.embeddings.create(
            model=EMBED_MODEL,
            input=query_variants,
        )
        _log_usage("query_embed", embed_response)
        query_embeddings = [
            item.embedding
            for item in sorted(embed_response.data, key=lambda x: x.index)
        ]

        candidates = retrieval.query_documents_multi(
            query_embeddings,
            doc_ids,
            candidates_per_query=CANDIDATES_PER_QUERY,
        )
        chunks = await _rerank_chunks(client, question, candidates, top_k=top_k)

        if not chunks:
            safe = NOT_FOUND_ANSWER.replace("\n", "\\n")
            yield f"event: token\ndata: {safe}\n\n"
            yield f"event: citations\ndata: []\n\n"
            yield "event: done\ndata: \n\n"
            return

        context = _build_context(chunks)
        user_message = f"Source passages:\n\n{context}\n\nQuestion: {question}"

        async with client.responses.stream(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
        ) as stream:
            answer_parts = []
            async for event in stream:
                if event.type == "response.output_text.delta":
                    delta = event.delta
                    if delta:
                        answer_parts.append(delta)
                        safe = delta.replace("\n", "\\n")
                        yield f"event: token\ndata: {safe}\n\n"
            _log_usage("answer_stream", await stream.get_final_response())

        citations = _citations_for_answer("".join(answer_parts), chunks)
        yield f"event: citations\ndata: {json.dumps(citations)}\n\n"
        yield "event: done\ndata: \n\n"

    except Exception as e:
        log.exception("stream_answer failed: %s", e)
        yield f"event: error\ndata: {str(e)}\n\n"
        yield "event: done\ndata: \n\n"
