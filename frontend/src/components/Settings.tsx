import { createSignal } from "solid-js";
import { clearChatHistory, saveApiKey } from "../api";

export default function Settings(props: { onApiKeySaved: () => void }) {
  const [apiKey, setApiKey] = createSignal("");
  const [showKey, setShowKey] = createSignal(false);
  const [saving, setSaving] = createSignal(false);
  const [saved, setSaved] = createSignal(false);
  const [saveError, setSaveError] = createSignal("");
  const [clearingHistory, setClearingHistory] = createSignal(false);
  const [historyCleared, setHistoryCleared] = createSignal(false);

  async function handleSave() {
    setSaving(true);
    setSaveError("");
    try {
      await saveApiKey(apiKey());
      setSaved(true);
      props.onApiKeySaved();
      setTimeout(() => setSaved(false), 2000);
    } catch (e: any) {
      setSaveError(e.message ?? "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  async function handleClearHistory() {
    setClearingHistory(true);
    try {
      await clearChatHistory();
      setHistoryCleared(true);
      setTimeout(() => setHistoryCleared(false), 2000);
    } finally {
      setClearingHistory(false);
    }
  }

  return (
    <div class="page">
      <h1 class="page-title">Settings</h1>
      <p class="page-sub">Configuration is saved to <code class="inline-code">.env</code> on disk.</p>

      <form class="settings-section" onSubmit={(e) => { e.preventDefault(); handleSave(); }}>
        <span class="label-caps">OpenAI API</span>
        <div class="settings-card">
          <div class="field-group">
            <label class="field-label">API Key</label>
            <div class="input-icon-wrap">
              <input
                class="field-input"
                type={showKey() ? "text" : "password"}
                placeholder="sk-…"
                value={apiKey()}
                onInput={(e) => setApiKey(e.currentTarget.value)}
                autocomplete="current-password"
              />
              <button type="button" class="input-icon-btn" onClick={() => setShowKey((v) => !v)} title={showKey() ? "Hide" : "Show"}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  {showKey()
                    ? <><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/><path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/><line x1="1" y1="1" x2="23" y2="23"/></>
                    : <><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></>
                  }
                </svg>
              </button>
            </div>
            <p class="field-hint">Stored in <code class="inline-code">OPENAI_API_KEY</code> in your .env file. Never logged.</p>
            {saveError() && <p class="field-error">{saveError()}</p>}
          </div>
        </div>

        <button class="btn-primary" type="submit" disabled={saving() || !apiKey().trim()}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/>
          </svg>
          {saved() ? "Saved!" : saving() ? "Saving…" : "Save API key"}
        </button>
      </form>

      <div class="settings-section">
        <span class="label-caps">Privacy</span>
        <div class="settings-card">
          <div class="field-group">
            <label class="field-label">Chat history</label>
            <p class="field-hint">Stored locally for 30 days in the history folder.</p>
          </div>
          <button class="btn-secondary danger" onClick={handleClearHistory} disabled={clearingHistory()}>
            {historyCleared() ? "History cleared" : clearingHistory() ? "Clearing..." : "Clear chat history"}
          </button>
        </div>
      </div>
    </div>
  );
}
