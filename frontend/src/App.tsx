import { createSignal, createResource, Switch, Match, Show, onMount } from "solid-js";
import Library from "./components/Library";
import Chat from "./components/Chat";
import Settings from "./components/Settings";
import { getDocuments, checkHealth } from "./api";
import "./app.css";

type Page = "upload" | "chat" | "settings";

export default function App() {
  const [page, setPage] = createSignal<Page>("upload");
  const [collapsed, setCollapsed] = createSignal(false);
  const [docs, { refetch: refetchDocs }] = createResource(getDocuments, { initialValue: [] });

  const docCount = () => (docs() ?? []).length;
  const hasDocs = () => docCount() > 0;
  const [noApiKey, setNoApiKey] = createSignal(false);

  onMount(async () => {
    try {
      const { api_key_set } = await checkHealth();
      setNoApiKey(!api_key_set);
    } catch {
      // backend not yet up — ignore, user will see errors naturally
    }
  });

  function navigate(id: Page) {
    if (id === "chat" && !hasDocs()) return;
    setPage(id);
    // Auto-collapse on mobile after navigation
    if (window.innerWidth < 640) setCollapsed(true);
  }

  function NavItem(props: { id: Page; icon: string; label: string; badge?: () => number }) {
    const active = () => page() === props.id;
    const disabled = () => props.id === "chat" && !hasDocs();
    return (
      <button
        class={`nav-item${active() ? " nav-item--active" : ""}${disabled() ? " nav-item--disabled" : ""}`}
        onClick={() => navigate(props.id)}
        title={disabled() ? "Upload a document first" : props.label}
      >
        <span class="nav-icon" innerHTML={props.icon} />
        <Show when={!collapsed()}>
          <span class="nav-label">{props.label}</span>
          <Show when={props.badge && props.badge()! > 0}>
            <span class="nav-badge">{props.badge!()}</span>
          </Show>
        </Show>
        <Show when={collapsed() && props.badge && props.badge()! > 0}>
          <span class="nav-badge nav-badge--dot" />
        </Show>
      </button>
    );
  }

  const uploadIcon = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>`;
  const chatIcon = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>`;
  const settingsIcon = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>`;
  const collapseIcon = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>`;
  const expandIcon = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>`;

  return (
    <div class={`app-shell${collapsed() ? " sidebar-collapsed" : ""}`}>
      {/* Sidebar */}
      <aside class="sidebar">
        <div class="sidebar-top">
          <div class="sidebar-logo">
            <div class="logo-icon">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/>
                <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>
              </svg>
            </div>
            <Show when={!collapsed()}>
              <div class="logo-text">
                <span class="logo-name">PDF Counsel</span>
                <span class="logo-sub">local · v0.1</span>
              </div>
            </Show>
          </div>

          <button
            class="sidebar-toggle"
            onClick={() => setCollapsed((v) => !v)}
            title={collapsed() ? "Expand sidebar" : "Collapse sidebar"}
            innerHTML={collapsed() ? expandIcon : collapseIcon}
          />
        </div>

        <nav class="sidebar-nav">
          <NavItem id="upload" icon={uploadIcon} label="Upload" badge={docCount} />
          <NavItem id="chat" icon={chatIcon} label="Chat" />
          <NavItem id="settings" icon={settingsIcon} label="Settings" />
        </nav>
      </aside>

      {/* Mobile overlay */}
      <Show when={!collapsed()}>
        <div class="sidebar-overlay" onClick={() => setCollapsed(true)} />
      </Show>

      {/* Main */}
      <main class="main">
        {/* Mobile menu button — only visible on small screens when sidebar is hidden */}
        <Show when={collapsed()}>
          <button
            class="mobile-menu-btn"
            onClick={() => setCollapsed(false)}
            title="Open menu"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/>
            </svg>
          </button>
        </Show>
        <Show when={noApiKey()}>
          <div class="api-key-banner">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
            No OpenAI API key detected. Add <code>OPENAI_API_KEY</code> to your <code>.env</code> file and restart the app.
          </div>
        </Show>
        <Switch>
          <Match when={page() === "upload"}><Library docs={docs() ?? []} refetch={refetchDocs} /></Match>
          <Match when={page() === "chat"}><Chat /></Match>
          <Match when={page() === "settings"}><Settings onApiKeySaved={() => setNoApiKey(false)} /></Match>
        </Switch>
      </main>
    </div>
  );
}
