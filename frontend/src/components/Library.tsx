import { createSignal, For, Show, Index } from "solid-js";
import { uploadPDF, deleteDocument } from "../api";
import type { DocumentInfo } from "../api";

function formatBytes(bytes: number | null | undefined) {
  if (typeof bytes !== "number" || !Number.isFinite(bytes)) return "Unknown size";
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

interface Props {
  docs: DocumentInfo[];
  refetch: () => void;
}

export default function Library(props: Props) {
  const [dragging, setDragging] = createSignal(false);
  const [uploading, setUploading] = createSignal<string[]>([]);
  const [uploadErrors, setUploadErrors] = createSignal<string[]>([]);

  const totalChunks = () => props.docs.reduce((s, d) => s + d.chunk_count, 0);

  async function handleFiles(files: FileList | null) {
    if (!files) return;
    const pdfs = Array.from(files).filter((f) => f.name.endsWith(".pdf"));
    setUploading(pdfs.map((f) => f.name));
    setUploadErrors([]);

    const results = await Promise.all(
      pdfs.map((f) => uploadPDF(f).then(() => null).catch((e: Error) => `${f.name}: ${e.message}`))
    );
    const errors = results.filter((r): r is string => r !== null);

    setUploading([]);
    setUploadErrors(errors);
    props.refetch();
  }

  async function handleDelete(doc_id: string) {
    await deleteDocument(doc_id);
    props.refetch();
  }

  return (
    <div class="page">
      <h1 class="page-title">Upload Documents</h1>
      <p class="page-sub">PDFs are chunked and embedded into your local vector store.</p>

      {/* Drop zone */}
      <div
        class={`dropzone${dragging() ? " dropzone--active" : ""}`}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); handleFiles(e.dataTransfer?.files ?? null); }}
      >
        <div class="dropzone-icon">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
            <polyline points="17 8 12 3 7 8"/>
            <line x1="12" y1="3" x2="12" y2="15"/>
          </svg>
        </div>
        <p class="dropzone-label">
          Drop PDFs here or{" "}
          <label class="dropzone-browse">
            browse
            <input type="file" accept=".pdf" multiple style="display:none" onChange={(e) => handleFiles(e.currentTarget.files)} />
          </label>
        </p>
        <p class="dropzone-hint">.pdf · multiple files supported</p>
      </div>

      {/* Uploading state */}
      <Show when={uploading().length > 0}>
        <div class="upload-progress">
          <For each={uploading()}>
            {(name) => <div class="upload-item"><span class="upload-spinner" />{name}</div>}
          </For>
        </div>
      </Show>

      {/* Upload errors */}
      <Show when={uploadErrors().length > 0}>
        <div class="upload-errors">
          <Index each={uploadErrors()}>
            {(msg) => <div class="upload-error">{msg()}</div>}
          </Index>
        </div>
      </Show>

      {/* Library */}
      <Show when={props.docs.length > 0}>
        <div class="library-header">
          <span class="label-caps">Library — {props.docs.length} document{props.docs.length !== 1 ? "s" : ""}</span>
          <span class="meta">{totalChunks()} chunks indexed</span>
        </div>
        <div class="doc-list">
          <For each={props.docs}>
            {(doc) => (
              <div class="doc-card">
                <div class="doc-icon">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                    <polyline points="14 2 14 8 20 8"/>
                  </svg>
                </div>
                <div class="doc-info">
                  <span class="doc-name">{doc.filename}</span>
                  <span class="meta">{formatBytes(doc.file_size)} · {doc.chunk_count} chunks</span>
                </div>
                <button class="doc-delete" title="Remove" onClick={() => handleDelete(doc.doc_id)}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
                  </svg>
                </button>
              </div>
            )}
          </For>
        </div>
      </Show>
    </div>
  );
}
