const BASE = "";

export interface DocumentInfo {
  doc_id: string;
  filename: string;
  chunk_count: number;
  page_count: number;
  file_size: number;
  indexed_at: string;
  status: string;
}

export interface IngestResponse {
  doc_id: string;
  filename: string;
  chunk_count: number;
  status: string;
}

export interface Citation {
  filename: string;
  page: number;
}

export interface ChatHistoryMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: Citation[];
  created_at: string;
}

export async function uploadPDF(file: File): Promise<IngestResponse> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE}/api/ingest`, { method: "POST", body: form });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getDocuments(): Promise<DocumentInfo[]> {
  const res = await fetch(`${BASE}/api/documents`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function deleteDocument(doc_id: string): Promise<void> {
  const res = await fetch(`${BASE}/api/documents/${doc_id}`, { method: "DELETE" });
  if (!res.ok) throw new Error(await res.text());
}

export async function checkHealth(): Promise<{ api_key_set: boolean }> {
  const res = await fetch(`${BASE}/health`);
  if (!res.ok) throw new Error("Backend unreachable");
  return res.json();
}

export async function saveApiKey(api_key: string): Promise<void> {
  const res = await fetch(`${BASE}/api/settings/apikey`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ api_key }),
  });
  if (!res.ok) throw new Error(await res.text());
}

export async function getChatHistory(): Promise<ChatHistoryMessage[]> {
  const res = await fetch(`${BASE}/api/chat/history`);
  if (!res.ok) throw new Error(await res.text());
  const payload = await res.json();
  return payload.messages;
}

export async function saveChatMessage(message: {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
}): Promise<ChatHistoryMessage> {
  const res = await fetch(`${BASE}/api/chat/history/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...message, citations: message.citations ?? [] }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function clearChatHistory(): Promise<void> {
  const res = await fetch(`${BASE}/api/chat/history`, { method: "DELETE" });
  if (!res.ok) throw new Error(await res.text());
}

export interface SSEHandlers {
  onToken: (text: string) => void;
  onCitations: (citations: Citation[]) => void;
  onDone: () => void;
  onError: (err: Error) => void;
}

// POST /api/chat and parse the SSE stream manually.
// EventSource only supports GET — we use fetch + ReadableStream instead.
export async function streamChat(
  question: string,
  doc_ids: string[] | null,
  handlers: SSEHandlers,
  top_k: number = 5
): Promise<void> {
  const res = await fetch(`${BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, doc_ids, top_k }),
  });

  if (!res.ok || !res.body) {
    handlers.onError(new Error(await res.text()));
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split("\n\n");
    buffer = events.pop() ?? "";

    for (const raw of events) {
      const lines = raw.split("\n");
      let eventType = "message";
      let data = "";
      for (const line of lines) {
        const cleanLine = line.endsWith("\r") ? line.slice(0, -1) : line;
        if (cleanLine.startsWith("event: ")) eventType = cleanLine.slice(7);
        if (cleanLine.startsWith("data: ")) data = cleanLine.slice(6);
      }
      if (eventType === "token") handlers.onToken(data.replace(/\\n/g, "\n"));
      if (eventType === "citations") handlers.onCitations(JSON.parse(data));
      if (eventType === "error") { handlers.onError(new Error(data)); return; }
      if (eventType === "done") { handlers.onDone(); return; }
    }
  }
}
