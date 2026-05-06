import asyncio
import os
import time
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, File, Request, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from .logging_config import get_logger
from .models import (
    IngestResponse,
    DocumentInfo,
    ChatRequest,
    DeleteResponse,
    ChatHistoryResponse,
    ChatHistoryMessage,
    SaveChatMessageRequest,
)
from . import ingest
from . import retrieval
from . import chat
from . import history

_env_path = os.getenv("ENV_FILE_PATH", os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv(_env_path)

log = get_logger(__name__)
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not os.getenv("OPENAI_API_KEY"):
        log.warning("OPENAI_API_KEY not set — configure it via the Settings page")
    else:
        log.info("pdfcounsel starting up")
    yield
    log.info("pdfcounsel shut down")


app = FastAPI(title="pdfcounsel", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    log.info("%s %s %d %.1fms", request.method, request.url.path, response.status_code, duration_ms)
    return response

_cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return JSONResponse({"status": "ok", "api_key_set": bool(os.getenv("OPENAI_API_KEY"))})


@app.post("/api/ingest", response_model=IngestResponse)
@limiter.limit("5/minute")
async def ingest_document(request: Request, file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
    pdf_bytes = await file.read()
    result = await asyncio.to_thread(ingest.process_pdf, pdf_bytes, file.filename)
    return result


@app.get("/api/documents", response_model=list[DocumentInfo])
def list_documents():
    return retrieval.list_documents()


@app.delete("/api/documents/{doc_id}", response_model=DeleteResponse)
def delete_document(doc_id: str):
    return retrieval.delete_document(doc_id)


@app.post("/api/chat")
@limiter.limit("30/minute")
async def chat_endpoint(request: Request, body: ChatRequest):
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=400, detail="OPENAI_API_KEY not configured.")

    return StreamingResponse(
        chat.stream_answer(body.question, body.doc_ids, body.top_k),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/chat/history", response_model=ChatHistoryResponse)
def get_chat_history():
    return {"messages": history.list_messages()}


@app.post("/api/chat/history/messages", response_model=ChatHistoryMessage)
def save_chat_history_message(payload: SaveChatMessageRequest):
    if payload.role not in {"user", "assistant"}:
        raise HTTPException(status_code=400, detail="Invalid message role.")
    return history.save_message(
        payload.role,
        payload.content,
        [citation.model_dump() for citation in payload.citations],
    )


@app.delete("/api/chat/history", response_model=DeleteResponse)
def clear_chat_history():
    history.clear_messages()
    return {"doc_id": "chat", "status": "deleted"}


@app.post("/api/settings/apikey")
def set_api_key(payload: dict):
    key = payload.get("api_key", "").strip()
    if not key.startswith("sk-"):
        raise HTTPException(status_code=400, detail="Invalid API key format.")
    env_path = os.getenv("ENV_FILE_PATH", os.path.join(os.path.dirname(__file__), "..", ".env"))
    with open(env_path, "w") as f:
        f.write(f"OPENAI_API_KEY={key}\n")
    os.environ["OPENAI_API_KEY"] = key
    return {"status": "saved"}


