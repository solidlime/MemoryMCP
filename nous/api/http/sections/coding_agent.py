"""Coding Agent Floating Panel for Nous Dashboard."""

from pathlib import Path


def render_coding_agent_panel() -> str:
    """Return HTML+CSS+JS for the Coding Agent floating panel."""
    return _CA_HTML + "\n<script>\n" + _JS + "\n</script>"


def render_coding_agent_css() -> str:
    return ""  # embedded in panel HTML


_JS = (Path(__file__).resolve().parent.parent / "static" / "coding_agent.js").read_text(encoding="utf-8")


def render_coding_agent_js() -> str:
    """Return all JavaScript for the Coding Agent panel."""
    return _JS


_CA_HTML = """\
<style>
/* === Coding Agent Floating Panel === */
#ca-panel {
  position: fixed;
  bottom: 80px;
  right: 20px;
  width: 640px;
  height: 440px;
  min-width: 280px;
  min-height: 220px;
  z-index: 8000;
  display: none;
  flex-direction: column;
  background: rgba(13,13,26,0.97);
  border: 1px solid var(--glass-border, rgba(96,165,250,0.20));
  border-radius: 10px;
  box-shadow: 0 8px 40px rgba(0,0,0,0.60), 0 0 0 1px rgba(96,165,250,0.08);
  overflow: hidden;
  animation: caSlideIn 0.18s ease;
}
#ca-panel.ca-open { display: flex; }
@keyframes caSlideIn {
  from { opacity:0; transform: translateY(14px); }
  to   { opacity:1; transform: translateY(0); }
}

/* Header */
#ca-header {
  height: 40px;
  min-height: 40px;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 0 10px;
  background: #0d0d1a;
  border-bottom: 1px solid var(--glass-border, rgba(96,165,250,0.16));
  cursor: grab;
  user-select: none;
  flex-shrink: 0;
}
#ca-header:active { cursor: grabbing; }
.ca-title {
  font-size: 12px;
  font-weight: 700;
  color: var(--accent-blue, #60a5fa);
  letter-spacing: 0.4px;
  white-space: nowrap;
  margin-right: 6px;
}
.ca-tab-btn {
  background: transparent;
  border: 1px solid transparent;
  color: #64748b;
  border-radius: 5px;
  padding: 3px 10px;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}
.ca-tab-btn:hover { color: #94a3b8; border-color: rgba(96,165,250,0.20); }
.ca-tab-btn.ca-tab-active {
  color: var(--accent-blue, #60a5fa);
  background: rgba(96,165,250,0.10);
  border-color: rgba(96,165,250,0.30);
}
#ca-close-btn {
  margin-left: auto;
  background: transparent;
  border: 1px solid transparent;
  color: #64748b;
  border-radius: 5px;
  width: 26px;
  height: 26px;
  font-size: 14px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
  flex-shrink: 0;
}
#ca-close-btn:hover { color: #fca5a5; border-color: rgba(248,113,113,0.30); background: rgba(248,113,113,0.10); }

/* Body */
#ca-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
}
.ca-tab-pane { display: none; flex-direction: column; flex: 1; min-height: 0; overflow: hidden; }
.ca-tab-pane.ca-pane-active { display: flex; }

/* === Terminal Tab === */
#ca-tab-terminal { padding: 8px; gap: 6px; }
.ca-lang-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.ca-lang-row label { font-size: 11px; color: #64748b; }
#ca-lang-select {
  background: rgba(96,165,250,0.07);
  border: 1px solid rgba(96,165,250,0.20);
  color: #e2e8f0;
  border-radius: 5px;
  padding: 3px 8px;
  font-size: 11px;
  font-family: 'Fira Code', 'Noto Sans Mono CJK JP', monospace;
  cursor: pointer;
  outline: none;
}
#ca-lang-select option { background: #0d0d1a; color: #e2e8f0; }
#ca-run-btn {
  background: rgba(16,185,129,0.12);
  border: 1px solid rgba(16,185,129,0.28);
  color: #4ade80;
  border-radius: 5px;
  padding: 3px 12px;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.15s;
}
#ca-run-btn:hover { background: rgba(16,185,129,0.22); border-color: rgba(16,185,129,0.50); }
#ca-run-btn:disabled { opacity: 0.45; cursor: not-allowed; }
#ca-code-area {
  flex-shrink: 0;
  width: 100%;
  height: 130px;
  resize: none;
  background: rgba(0,0,0,0.35);
  border: 1px solid rgba(96,165,250,0.15);
  border-radius: 6px;
  color: #e2e8f0;
  font-family: 'Fira Code', 'Cascadia Code', 'Noto Sans Mono CJK JP', monospace;
  font-size: 12px;
  line-height: 1.55;
  padding: 8px 10px;
  outline: none;
  box-sizing: border-box;
  transition: border-color 0.2s;
}
#ca-code-area:focus { border-color: rgba(96,165,250,0.38); }
#ca-output-area {
  flex: 1;
  overflow-y: auto;
  background: rgba(0,0,0,0.30);
  border: 1px solid rgba(96,165,250,0.10);
  border-radius: 6px;
  padding: 8px 10px;
  font-family: 'Fira Code', 'Cascadia Code', 'Noto Sans Mono CJK JP', monospace;
  font-size: 11px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
  min-height: 60px;
}
.ca-out-stdout { color: #d1fae5; }
.ca-out-stderr { color: #fca5a5; }
.ca-out-info   { color: #94a3b8; }
.ca-out-error  { color: #f87171; font-weight: 600; }
.ca-artifacts  { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; flex-shrink: 0; }
.ca-artifacts img { max-width: 100%; max-height: 200px; border-radius: 4px; border: 1px solid rgba(96,165,250,0.15); }

/* === Files Tab === */
#ca-tab-files { padding: 8px; gap: 6px; }
.ca-files-toolbar {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}
.ca-files-toolbar span { font-size: 11px; color: #64748b; flex: 1; }
.ca-icon-btn {
  background: rgba(96,165,250,0.07);
  border: 1px solid rgba(96,165,250,0.18);
  color: #94a3b8;
  border-radius: 5px;
  padding: 3px 8px;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.15s;
}
.ca-icon-btn:hover { background: rgba(96,165,250,0.15); color: #e2e8f0; }
#ca-file-list {
  flex: 1;
  overflow-y: auto;
  background: rgba(0,0,0,0.25);
  border: 1px solid rgba(96,165,250,0.10);
  border-radius: 6px;
  padding: 4px;
  min-height: 60px;
}
.ca-file-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.12s;
  font-size: 11px;
  color: #cbd5e1;
}
.ca-file-item:hover { background: rgba(96,165,250,0.08); }
.ca-file-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ca-file-size { color: #475569; font-size: 10px; flex-shrink: 0; }
.ca-del-btn {
  background: transparent;
  border: none;
  color: #475569;
  cursor: pointer;
  font-size: 12px;
  padding: 0 2px;
  line-height: 1;
  transition: color 0.15s;
  flex-shrink: 0;
}
.ca-del-btn:hover { color: #f87171; }
.ca-drop-zone {
  border: 1px dashed rgba(96,165,250,0.22);
  border-radius: 6px;
  padding: 10px;
  text-align: center;
  font-size: 11px;
  color: #475569;
  transition: all 0.2s;
  flex-shrink: 0;
  cursor: pointer;
}
.ca-drop-zone.ca-drag-over {
  border-color: var(--accent-blue, #60a5fa);
  background: rgba(96,165,250,0.07);
  color: #94a3b8;
}
.ca-empty { color: #475569; font-size: 11px; padding: 12px; text-align: center; }

/* Resize handle */
#ca-resize-handle {
  position: absolute;
  bottom: 0;
  right: 0;
  width: 16px;
  height: 16px;
  cursor: se-resize;
  opacity: 0.45;
}
#ca-resize-handle::after {
  content: '';
  position: absolute;
  bottom: 4px;
  right: 4px;
  width: 8px;
  height: 8px;
  border-right: 2px solid var(--accent-blue, #60a5fa);
  border-bottom: 2px solid var(--accent-blue, #60a5fa);
  border-radius: 1px;
}
</style>

<div id="ca-panel">
  <div id="ca-header">
    <span class="ca-title"><i data-lucide="zap"></i> Coding Agent</span>
    <button class="ca-tab-btn ca-tab-active" data-tab="terminal"><i data-lucide="monitor"></i> Terminal</button>
    <button class="ca-tab-btn" data-tab="files"><i data-lucide="folder"></i> Files</button>
    <button id="ca-close-btn" title="Close"><i data-lucide="x"></i></button>
  </div>

  <div id="ca-body">
    <!-- Terminal Tab -->
    <div id="ca-tab-terminal" class="ca-tab-pane ca-pane-active">
      <div class="ca-lang-row">
        <label>Lang:</label>
        <select id="ca-lang-select">
          <option value="python" selected>Python</option>
          <option value="bash">Bash</option>
        </select>
        <button id="ca-run-btn"><i data-lucide="play"></i> Run</button>
      </div>
      <textarea id="ca-code-area" spellcheck="false" placeholder="# Enter code here&#10;# Ctrl+Enter to run"></textarea>
      <div id="ca-output-area"><span class="ca-out-info">Ready.</span></div>
      <div class="ca-artifacts" id="ca-artifacts"></div>
    </div>

    <!-- Files Tab -->
    <div id="ca-tab-files" class="ca-tab-pane">
      <div class="ca-files-toolbar">
        <span><i data-lucide="folder-open"></i> Workspace files</span>
        <button class="ca-icon-btn" id="ca-files-refresh"><i data-lucide="refresh-cw"></i> Reload</button>
      </div>
      <div id="ca-file-list"><div class="ca-empty">Loading...</div></div>
      <div class="ca-drop-zone" id="ca-drop-zone">
        <i data-lucide="upload"></i> Drop files here to upload
        <input type="file" id="ca-file-input" multiple style="display:none">
      </div>
    </div>
  </div>

  <div id="ca-resize-handle"></div>
</div>

"""
