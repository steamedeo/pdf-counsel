from pydantic import BaseModel
from typing import Optional


class IngestResponse(BaseModel):
    doc_id: str
    filename: str
    chunk_count: int
    status: str  # "indexed" | "already_exists"


class DocumentInfo(BaseModel):
    doc_id: str
    filename: str
    chunk_count: int
    file_size: int | None = None
    status: str


class ChatRequest(BaseModel):
    question: str
    doc_ids: Optional[list[str]] = None
    top_k: int = 5


class Citation(BaseModel):
    filename: str
    page: int


class ChatHistoryMessage(BaseModel):
    id: str
    role: str
    content: str
    citations: list[Citation] = []
    created_at: str


class SaveChatMessageRequest(BaseModel):
    role: str
    content: str
    citations: list[Citation] = []


class ChatHistoryResponse(BaseModel):
    messages: list[ChatHistoryMessage]


class DeleteResponse(BaseModel):
    doc_id: str
    status: str
