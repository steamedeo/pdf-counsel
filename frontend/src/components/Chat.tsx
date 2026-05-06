import { createSignal, createResource, createMemo, For, Show, onMount } from "solid-js";
import { getChatHistory, getDocuments, saveChatMessage, streamChat } from "../api";
import { topK } from "../store";
import type { DocumentInfo } from "../api";

interface Citation {
  filename: string;
  page: number;
}

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  created_at: string;
}

type ChatItem =
  | { type: "date"; id: string; label: string }
  | { type: "message"; id: string; message: Message };

function newId() {
  return crypto.randomUUID?.() ?? `${Date.now()}-${Math.random()}`;
}

function formatSources(citations: Citation[] | undefined) {
  if (!citations?.length) return "";

  const seen = new Set<string>();
  const sources = citations.filter((citation) => {
    const key = `${citation.filename}:${citation.page}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });

  return sources
    .map((source) => `${source.filename}, page ${source.page}`)
    .join("; ");
}

function cleanAnswer(content: string) {
  return content
    .replace(/\s*\(\s*\[?Source\s*\d+\]?\s*(?:,\s*page\s*\d+)?\s*\)/gi, "")
    .replace(/\s*\[\s*Source\s*\d+\s*\]/gi, "")
    .trim();
}

function dayKey(value: string) {
  const date = new Date(value);
  return `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`;
}

function dateLabel(value: string) {
  const date = new Date(value);
  const today = new Date();
  const yesterday = new Date();
  yesterday.setDate(today.getDate() - 1);

  if (dayKey(value) === dayKey(today.toISOString())) return "Today";
  if (dayKey(value) === dayKey(yesterday.toISOString())) return "Yesterday";

  return date.toLocaleDateString(undefined, {
    month: "long",
    day: "numeric",
    year: "numeric",
  });
}

export default function Chat() {
  const [docs] = createResource<DocumentInfo[]>(getDocuments, { initialValue: [] });
  const [messages, setMessages] = createSignal<Message[]>([]);
  const [input, setInput] = createSignal("");
  const [streaming, setStreaming] = createSignal(false);
  let inputRef: HTMLTextAreaElement | undefined;
  let bottomRef: HTMLDivElement | undefined;

  const totalChunks = () => (docs() ?? []).reduce((s, d) => s + d.chunk_count, 0);
  const items = createMemo<ChatItem[]>(() => {
    const result: ChatItem[] = [];
    let currentDay = "";

    for (const message of messages()) {
      const key = dayKey(message.created_at);
      if (key !== currentDay) {
        currentDay = key;
        result.push({ type: "date", id: `date-${key}`, label: dateLabel(message.created_at) });
      }
      result.push({ type: "message", id: message.id, message });
    }

    return result;
  });

  onMount(async () => {
    try {
      const history = await getChatHistory();
      setMessages(history);
      queueMicrotask(() => bottomRef?.scrollIntoView());
    } catch {
      setMessages([]);
    }
  });

  async function send() {
    const q = input().trim();
    if (!q || streaming()) return;

    const createdAt = new Date().toISOString();
    const userMessage: Message = {
      id: newId(),
      role: "user",
      content: q,
      citations: [],
      created_at: createdAt,
    };

    setMessages((m) => [...m, userMessage]);
    void saveChatMessage({ role: "user", content: q, citations: [] });
    setInput("");
    setStreaming(true);
    queueMicrotask(() => bottomRef?.scrollIntoView({ behavior: "smooth" }));

    let assistantIdx!: number;
    let assistantContent = "";
    let assistantCitations: Citation[] = [];
    setMessages((m) => {
      assistantIdx = m.length;
      return [...m, {
        id: newId(),
        role: "assistant",
        content: "",
        citations: [],
        created_at: new Date().toISOString(),
      }];
    });

    await streamChat(q, null, {
      onToken: (text) => {
        assistantContent += text;
        setMessages((m) => m.map((msg, i) =>
          i === assistantIdx ? { ...msg, content: msg.content + text } : msg
        ));
        bottomRef?.scrollIntoView({ behavior: "smooth" });
      },
      onCitations: (cits) => {
        assistantCitations = cits;
        setMessages((m) => m.map((msg, i) =>
          i === assistantIdx ? { ...msg, citations: cits } : msg
        ));
      },
      onDone: () => finishStreaming(assistantContent, assistantCitations),
      onError: (err) => {
        const msg = err.message.includes("429")
          ? "Too many requests — please wait a moment before asking again."
          : `Something went wrong: ${err.message}`;
        setMessages((m) => m.map((msg2, i) =>
          i === assistantIdx ? { ...msg2, content: msg } : msg2
        ));
        finishStreaming();
      },
    }, topK());
  }

  function onKeyDown(e: KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  function finishStreaming(content?: string, citations: Citation[] = []) {
    setStreaming(false);
    if (content?.trim()) {
      void saveChatMessage({ role: "assistant", content, citations });
    }
    queueMicrotask(() => inputRef?.focus());
  }

  return (
    <div class="chat-shell">
      {/* Header */}
      <div class="chat-header">
        <div class="chat-header-left">
          <span class="chat-title">Chat</span>
          <span class="meta">{(docs() ?? []).length} documents · {totalChunks()} chunks</span>
        </div>
      </div>

      {/* Messages */}
      <div class="chat-messages">
        <Show when={messages().length === 0}>
          <div class="chat-empty">Ask a question about your documents.</div>
        </Show>
        <For each={items()}>
          {(item) => (
            <Show
              when={item.type === "message"}
              fallback={<div class="date-separator">{item.type === "date" ? item.label : ""}</div>}
            >
              <Show
                when={item.type === "message" && item.message.role === "assistant"}
                fallback={
                  <div class="msg-row msg-row--user">
                    <div class="bubble-user">{item.type === "message" ? item.message.content : ""}</div>
                    <div class="avatar-user">you</div>
                  </div>
                }
              >
                <div class="msg-row msg-row--assistant">
                  <div class="avatar-assistant">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>
                  </div>
                  <div class="msg-body">
                    <div class="bubble-assistant">
                      <Show
                        when={item.type === "message" && item.message.content}
                        fallback={
                          <span class="thinking">
                            <span class="thinking-spinner" />
                            Thinking
                          </span>
                        }
                      >
                        {item.type === "message" ? cleanAnswer(item.message.content) : ""}
                      </Show>
                      <Show when={item.type === "message" ? formatSources(item.message.citations) : ""}>
                        {(sources) => <div class="answer-source">Source: {sources()}</div>}
                      </Show>
                    </div>
                  </div>
                </div>
              </Show>
            </Show>
          )}
        </For>
        <div ref={bottomRef} />
      </div>

      {/* Input area */}
      <div class="chat-input-area">
        <div class="chat-input-wrap">
          <textarea
            ref={inputRef}
            class="chat-input"
            placeholder="Ask a question about your documents…"
            rows={1}
            value={input()}
            onInput={(e) => setInput(e.currentTarget.value)}
            onKeyDown={onKeyDown}
            disabled={streaming()}
          />
          <button class="chat-send" onClick={send} disabled={streaming() || !input().trim()}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
            </svg>
          </button>
        </div>
        <p class="chat-hint">Enter to send · Shift+Enter for newline · retrieval-augmented with citations</p>
      </div>

    </div>
  );
}
