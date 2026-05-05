"""Coding Agent IDE panel for MemoryMCP Dashboard."""


def render_coding_agent_panel() -> str:
    """Return HTML for the Coding Agent overlay panel."""
    return _CA_HTML


def render_coding_agent_css() -> str:
    """Return CSS for the Coding Agent panel (also included in panel HTML)."""
    return ""  # CSS is already embedded in render_coding_agent_panel


def render_coding_agent_js() -> str:
    """Return JS for the Coding Agent panel (also included in panel HTML)."""
    return ""  # JS is already embedded in render_coding_agent_panel


_CA_HTML = """\
<style>
/* ================================================================
   Coding Agent — Full-Screen IDE Overlay
   Dark theme · Glass morphism · Monaco Editor
   ================================================================ */

#coding-agent-overlay {
  position: fixed;
  inset: 0;
  z-index: 9000;
  display: none;
  background: rgba(0, 0, 0, 0.80);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  animation: caFadeIn 0.18s ease;
}
#coding-agent-overlay.ca-visible {
  display: flex;
}
@keyframes caFadeIn {
  from { opacity: 0; }
  to   { opacity: 1; }
}

/* ── Panel ── */
#coding-agent-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: rgba(13, 13, 26, 0.97);
  border: 1px solid rgba(96, 165, 250, 0.20);
  overflow: hidden;
  animation: caSlideIn 0.22s ease;
}
@keyframes caSlideIn {
  from { transform: translateY(18px); opacity: 0.6; }
  to   { transform: translateY(0);    opacity: 1;   }
}

/* ── Toolbar ── */
#ca-toolbar {
  height: 44px;
  min-height: 44px;
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 0 14px;
  background: linear-gradient(90deg,
    rgba(124, 58, 237, 0.14) 0%,
    rgba(13, 13, 26, 0.96) 60%);
  border-bottom: 1px solid rgba(96, 165, 250, 0.16);
  flex-shrink: 0;
}
.ca-title {
  font-size: 14px;
  font-weight: 700;
  color: #60a5fa;
  letter-spacing: 0.4px;
  white-space: nowrap;
  margin-right: 4px;
}
#ca-lang-select {
  background: rgba(96, 165, 250, 0.08);
  border: 1px solid rgba(96, 165, 250, 0.20);
  color: #e2e8f0;
  border-radius: 6px;
  padding: 4px 9px;
  font-size: 12px;
  font-family: 'Fira Code', 'Cascadia Code', monospace;
  cursor: pointer;
  outline: none;
  transition: border-color 0.2s, background 0.2s;
}
#ca-lang-select:hover,
#ca-lang-select:focus {
  border-color: rgba(96, 165, 250, 0.45);
  background: rgba(96, 165, 250, 0.13);
}
#ca-lang-select option {
  background: #0d0d1a;
  color: #e2e8f0;
}
#ca-toolbar button {
  background: rgba(96, 165, 250, 0.09);
  border: 1px solid rgba(96, 165, 250, 0.20);
  color: #e2e8f0;
  border-radius: 6px;
  padding: 5px 13px;
  font-size: 12px;
  font-family: 'Fira Code', 'Cascadia Code', monospace;
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;
}
#ca-toolbar button:hover {
  background: rgba(96, 165, 250, 0.20);
  border-color: rgba(96, 165, 250, 0.45);
  transform: translateY(-1px);
  box-shadow: 0 3px 10px rgba(96, 165, 250, 0.14);
}
#ca-toolbar button:active { transform: translateY(0); }
#ca-run-btn {
  background: rgba(16, 185, 129, 0.12) !important;
  border-color: rgba(16, 185, 129, 0.28) !important;
  color: #4ade80 !important;
}
#ca-run-btn:hover {
  background: rgba(16, 185, 129, 0.24) !important;
  border-color: rgba(16, 185, 129, 0.55) !important;
  box-shadow: 0 3px 12px rgba(16, 185, 129, 0.18) !important;
}
#ca-run-btn:disabled {
  opacity: 0.50;
  cursor: not-allowed;
  transform: none !important;
  box-shadow: none !important;
}
#ca-save-btn {
  background: rgba(96, 165, 250, 0.11) !important;
  border-color: rgba(96, 165, 250, 0.24) !important;
}
#ca-close-btn {
  background: rgba(248, 113, 113, 0.10) !important;
  border-color: rgba(248, 113, 113, 0.24) !important;
  color: #fca5a5 !important;
  margin-left: auto !important;
}
#ca-close-btn:hover {
  background: rgba(248, 113, 113, 0.22) !important;
  border-color: rgba(248, 113, 113, 0.52) !important;
  box-shadow: 0 3px 12px rgba(248, 113, 113, 0.16) !important;
}

/* ── Body ── */
#ca-body {
  flex: 1;
  display: flex;
  overflow: hidden;
  min-height: 0;
}

/* ── Sidebar ── */
#ca-sidebar {
  width: 210px;
  min-width: 150px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: rgba(10, 10, 22, 0.65);
  border-right: 1px solid rgba(96, 165, 250, 0.12);
  overflow: hidden;
}
#ca-sidebar-header {
  padding: 7px 9px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid rgba(96, 165, 250, 0.12);
  background: rgba(96, 165, 250, 0.04);
  flex-shrink: 0;
}
.ca-sidebar-title {
  font-size: 10px;
  font-weight: 700;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.9px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ca-sidebar-btns {
  display: flex;
  gap: 2px;
}
.ca-sidebar-btns button {
  background: transparent;
  border: 1px solid transparent;
  color: #64748b;
  border-radius: 4px;
  width: 22px;
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  font-size: 13px;
  padding: 0;
  transition: all 0.14s;
}
.ca-sidebar-btns button:hover {
  background: rgba(96, 165, 250, 0.10);
  border-color: rgba(96, 165, 250, 0.22);
  color: #60a5fa;
  transform: scale(1.12);
}
#ca-file-tree {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 4px 0;
  scrollbar-width: thin;
  scrollbar-color: rgba(96, 165, 250, 0.18) transparent;
}
#ca-file-tree::-webkit-scrollbar { width: 4px; }
#ca-file-tree::-webkit-scrollbar-thumb {
  background: rgba(96, 165, 250, 0.18);
  border-radius: 2px;
}
.ca-tree-item {
  display: flex;
  align-items: center;
  gap: 3px;
  padding: 3px 6px 3px 0;
  cursor: pointer;
  transition: background 0.10s;
  user-select: none;
  font-size: 13px;
  color: #e2e8f0;
  white-space: nowrap;
  overflow: hidden;
  border-left: 2px solid transparent;
}
.ca-tree-item:hover  { background: rgba(96, 165, 250, 0.07); }
.ca-tree-item.ca-tree-active {
  background: rgba(96, 165, 250, 0.13);
  color: #93c5fd;
  border-left-color: #60a5fa;
}
.ca-tree-item.ca-tree-dir { color: #93c5fd; font-weight: 500; }
.ca-tree-toggle {
  width: 14px;
  font-size: 9px;
  color: #64748b;
  flex-shrink: 0;
  text-align: center;
}
.ca-tree-icon { font-size: 12px; flex-shrink: 0; }
.ca-tree-name { overflow: hidden; text-overflow: ellipsis; flex: 1; font-size: 12px; }

/* ── Editor Section ── */
#ca-editor-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
}

/* ── Tab Bar ── */
#ca-tabbar {
  height: 35px;
  min-height: 35px;
  display: flex;
  align-items: flex-end;
  background: rgba(10, 10, 22, 0.85);
  border-bottom: 1px solid rgba(96, 165, 250, 0.13);
  overflow-x: auto;
  overflow-y: hidden;
  flex-shrink: 0;
  scrollbar-width: none;
}
#ca-tabbar::-webkit-scrollbar { display: none; }
.ca-tab {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 0 10px;
  height: 31px;
  background: rgba(255, 255, 255, 0.025);
  border-right: 1px solid rgba(96, 165, 250, 0.10);
  border-top: 2px solid transparent;
  cursor: pointer;
  transition: background 0.12s;
  white-space: nowrap;
  font-size: 12px;
  color: #94a3b8;
  min-width: 80px;
  max-width: 190px;
  flex-shrink: 0;
}
.ca-tab:hover { background: rgba(255, 255, 255, 0.055); color: #e2e8f0; }
.ca-tab.ca-tab-active {
  background: rgba(96, 165, 250, 0.09);
  border-top-color: #60a5fa;
  color: #e2e8f0;
}
.ca-tab-icon  { font-size: 12px; }
.ca-tab-name  {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  font-family: 'Fira Code', 'Cascadia Code', monospace;
  font-size: 12px;
}
.ca-tab-close {
  background: transparent;
  border: none;
  color: #64748b;
  cursor: pointer;
  width: 16px;
  height: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 3px;
  font-size: 10px;
  flex-shrink: 0;
  padding: 0;
  transition: all 0.11s;
}
.ca-tab-close:hover { background: rgba(248, 113, 113, 0.22); color: #f87171; }
.ca-tab-empty {
  color: #475569;
  font-size: 12px;
  padding: 0 14px;
  display: flex;
  align-items: center;
  height: 100%;
  font-style: italic;
}

/* ── Monaco Container ── */
#ca-editor-container {
  flex: 1;
  overflow: hidden;
  min-height: 0;
  background: #1e1e2e;
  position: relative;
}
#ca-editor-loading {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 14px;
  color: #475569;
  font-family: 'Fira Code', monospace;
  font-size: 14px;
  background: #1e1e2e;
  z-index: 1;
}
.ca-loading-icon {
  font-size: 34px;
  animation: caLoadPulse 2s ease infinite;
}
@keyframes caLoadPulse {
  0%, 100% { transform: scale(1)    rotate(0deg);   opacity: 0.55; }
  50%       { transform: scale(1.18) rotate(180deg); opacity: 1;    }
}

/* ── Resize Handle ── */
#ca-resize-handle {
  height: 5px;
  min-height: 5px;
  background: rgba(96, 165, 250, 0.05);
  cursor: ns-resize;
  flex-shrink: 0;
  transition: background 0.18s;
  display: flex;
  align-items: center;
  justify-content: center;
}
#ca-resize-handle::after {
  content: '';
  display: block;
  width: 42px;
  height: 2px;
  background: rgba(96, 165, 250, 0.20);
  border-radius: 1px;
  transition: background 0.18s;
}
#ca-resize-handle:hover                { background: rgba(96, 165, 250, 0.14); }
#ca-resize-handle:hover::after         { background: rgba(96, 165, 250, 0.50); }
#ca-resize-handle.ca-resizing::after   { background: rgba(96, 165, 250, 0.70); }

/* ── Output Panel ── */
#ca-output-panel {
  height: 220px;
  min-height: 120px;
  display: flex;
  flex-direction: column;
  background: rgba(10, 10, 22, 0.94);
  flex-shrink: 0;
}
#ca-output-tabs {
  display: flex;
  align-items: center;
  height: 30px;
  min-height: 30px;
  background: rgba(10, 10, 22, 0.80);
  border-bottom: 1px solid rgba(96, 165, 250, 0.12);
  flex-shrink: 0;
  padding: 0 6px;
  gap: 2px;
}
.ca-out-tab {
  padding: 0 13px;
  height: 26px;
  display: flex;
  align-items: center;
  cursor: pointer;
  font-size: 11px;
  color: #64748b;
  border-radius: 4px 4px 0 0;
  border: 1px solid transparent;
  transition: all 0.13s;
  user-select: none;
  white-space: nowrap;
}
.ca-out-tab:hover { background: rgba(96, 165, 250, 0.08); color: #e2e8f0; }
.ca-out-tab.ca-out-tab-active {
  background: rgba(96, 165, 250, 0.13);
  color: #60a5fa;
  border-color: rgba(96, 165, 250, 0.18);
  border-bottom-color: transparent;
}
.ca-clear-btn {
  margin-left: auto;
  background: transparent;
  border: 1px solid transparent;
  color: #475569;
  cursor: pointer;
  font-size: 13px;
  padding: 2px 6px;
  border-radius: 4px;
  transition: all 0.13s;
}
.ca-clear-btn:hover {
  background: rgba(248, 113, 113, 0.12);
  border-color: rgba(248, 113, 113, 0.30);
  color: #f87171;
}

/* ── Output Content Areas ── */
.ca-out-content {
  flex: 1;
  overflow-y: auto;
  overflow-x: auto;
  padding: 7px 12px;
  font-family: 'Fira Code', 'Cascadia Code', monospace;
  font-size: 12px;
  line-height: 1.65;
  color: #e2e8f0;
  display: none;
  scrollbar-width: thin;
  scrollbar-color: rgba(96, 165, 250, 0.18) transparent;
}
.ca-out-content::-webkit-scrollbar       { width: 5px; height: 5px; }
.ca-out-content::-webkit-scrollbar-thumb { background: rgba(96,165,250,0.18); border-radius: 3px; }
.ca-out-content.ca-out-active            { display: block; }
.ca-out-stdout { white-space: pre-wrap; word-break: break-all; }
.ca-out-stderr { white-space: pre-wrap; word-break: break-all; color: #f87171; }

/* Artifacts grid */
#ca-out-content-artifacts        { display: none !important; }
#ca-out-content-artifacts.ca-out-active {
  display: grid !important;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 10px;
  align-content: start;
  padding: 10px;
}
.ca-artifacts-empty {
  grid-column: 1 / -1;
  text-align: center;
  color: #475569;
  padding: 22px;
  font-size: 13px;
  line-height: 1.9;
}
.ca-artifact-item {
  border: 1px solid rgba(96, 165, 250, 0.18);
  border-radius: 7px;
  overflow: hidden;
  cursor: pointer;
  transition: all 0.18s;
  aspect-ratio: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.03);
}
.ca-artifact-item:hover {
  border-color: rgba(96, 165, 250, 0.45);
  transform: scale(1.03);
  box-shadow: 0 5px 18px rgba(96, 165, 250, 0.14);
}
.ca-artifact-img { width: 100%; height: 100%; object-fit: contain; }

/* Pip panel */
#ca-out-content-pip              { display: none !important; flex-direction: column; }
#ca-out-content-pip.ca-out-active { display: flex !important; }
.ca-pip-row {
  display: flex;
  gap: 6px;
  padding: 8px 10px;
  align-items: center;
  border-bottom: 1px solid rgba(96, 165, 250, 0.12);
  flex-shrink: 0;
}
#ca-pip-input {
  flex: 1;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(96, 165, 250, 0.18);
  color: #e2e8f0;
  border-radius: 6px;
  padding: 5px 10px;
  font-family: 'Fira Code', monospace;
  font-size: 12px;
  outline: none;
  transition: border-color 0.18s;
}
#ca-pip-input:focus { border-color: rgba(96, 165, 250, 0.50); background: rgba(255,255,255,0.08); }
#ca-pip-input::placeholder { color: #475569; }
.ca-pip-row button {
  background: rgba(96, 165, 250, 0.10);
  border: 1px solid rgba(96, 165, 250, 0.20);
  color: #e2e8f0;
  border-radius: 6px;
  padding: 5px 11px;
  font-size: 12px;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.13s;
}
.ca-pip-row button:hover {
  background: rgba(96, 165, 250, 0.22);
  border-color: rgba(96, 165, 250, 0.48);
}
#ca-pip-output {
  flex: 1;
  overflow-y: auto;
  padding: 8px 12px;
  font-family: 'Fira Code', monospace;
  font-size: 12px;
  scrollbar-width: thin;
  scrollbar-color: rgba(96, 165, 250, 0.15) transparent;
}
.ca-pip-loading { color: #60a5fa; }
.ca-pip-ok      { color: #4ade80; white-space: pre-wrap; }
.ca-pip-error   { color: #f87171; }

/* ── Context Menu ── */
.ca-ctx-menu {
  position: fixed;
  background: rgba(12, 12, 28, 0.98);
  border: 1px solid rgba(96, 165, 250, 0.22);
  border-radius: 8px;
  padding: 4px 0;
  min-width: 155px;
  z-index: 10500;
  box-shadow: 0 10px 36px rgba(0, 0, 0, 0.55);
  backdrop-filter: blur(14px);
  animation: caCtxIn 0.11s ease;
}
@keyframes caCtxIn {
  from { opacity: 0; transform: scale(0.93) translateY(-5px); }
  to   { opacity: 1; transform: scale(1)    translateY(0);    }
}
.ca-ctx-item {
  padding: 8px 16px;
  cursor: pointer;
  font-size: 13px;
  color: #e2e8f0;
  transition: background 0.10s;
}
.ca-ctx-item:hover { background: rgba(96, 165, 250, 0.10); color: #60a5fa; }
.ca-ctx-sep { height: 1px; background: rgba(96, 165, 250, 0.12); margin: 3px 8px; }
</style>

<div id="coding-agent-overlay">
  <div id="coding-agent-panel">

    <!-- ═══ Toolbar ═══ -->
    <div id="ca-toolbar">
      <span class="ca-title">🔬 Coding Agent</span>

      <select id="ca-lang-select" title="言語を選択">
        <option value="python">🐍 Python</option>
        <option value="javascript">🟨 JavaScript</option>
        <option value="typescript">🔷 TypeScript</option>
        <option value="bash">💲 Bash</option>
        <option value="java">☕ Java</option>
        <option value="cpp">⚙️ C++</option>
        <option value="go">🐹 Go</option>
        <option value="r">📊 R</option>
        <option value="html">🌐 HTML</option>
        <option value="css">🎨 CSS</option>
        <option value="json">📋 JSON</option>
        <option value="sql">🗄️ SQL</option>
        <option value="markdown">📝 Markdown</option>
        <option value="plaintext">📄 Plain Text</option>
      </select>

      <button id="ca-run-btn"   onclick="caRunCode()"         title="実行 (Ctrl+Enter)">▶ Run</button>
      <button id="ca-save-btn"  onclick="caSaveFile()"        title="保存 (Ctrl+S)">💾 Save</button>
      <button id="ca-close-btn" onclick="closeCodingAgent()"  title="チャットに戻る">↩ チャットに戻る</button>
    </div>

    <!-- ═══ Body ═══ -->
    <div id="ca-body">

      <!-- ─── Sidebar ─── -->
      <div id="ca-sidebar">
        <div id="ca-sidebar-header">
          <span class="ca-sidebar-title">📁 /workspace</span>
          <div class="ca-sidebar-btns">
            <button id="ca-new-btn"    onclick="caNewFile()"    title="新規ファイル">+</button>
            <button id="ca-upload-btn" onclick="caUploadFile()" title="ファイルをアップロード">⬆</button>
            <button id="ca-refresh-btn" onclick="caRefreshTree()" title="ツリーを更新">🔄</button>
          </div>
        </div>
        <div id="ca-file-tree"></div>
        <input type="file" id="ca-upload-input" style="display:none"
               onchange="caHandleUpload(event)" multiple />
      </div>

      <!-- ─── Editor + Output ─── -->
      <div id="ca-editor-section">

        <!-- Tab Bar -->
        <div id="ca-tabbar">
          <div class="ca-tab-empty">← ファイルを選択するか ▶ Run で実行</div>
        </div>

        <!-- Monaco Editor -->
        <div id="ca-editor-container">
          <div id="ca-editor-loading">
            <div class="ca-loading-icon">🔬</div>
            <div>Monaco Editor を読み込み中...</div>
          </div>
        </div>

        <!-- Resize Handle -->
        <div id="ca-resize-handle" title="ドラッグでパネルをリサイズ"></div>

        <!-- Output Panel -->
        <div id="ca-output-panel">
          <div id="ca-output-tabs">
            <div class="ca-out-tab ca-out-tab-active"
                 data-tab="output"    onclick="caSelectOutTab('output')">📤 Output</div>
            <div class="ca-out-tab"
                 data-tab="artifacts" onclick="caSelectOutTab('artifacts')">🖼️ Artifacts</div>
            <div class="ca-out-tab"
                 data-tab="pip"       onclick="caSelectOutTab('pip')">📦 pip</div>
            <button class="ca-clear-btn" onclick="caClearOutput()" title="出力をクリア">🗑️</button>
          </div>

          <!-- Output -->
          <div id="ca-out-content-output" class="ca-out-content ca-out-active"></div>

          <!-- Artifacts -->
          <div id="ca-out-content-artifacts" class="ca-out-content">
            <div class="ca-artifacts-empty">
              🖼️ アーティファクトがここに表示されます<br>
              <small>matplotlib などで画像を生成すると表示されます</small>
            </div>
          </div>

          <!-- pip install -->
          <div id="ca-out-content-pip" class="ca-out-content">
            <div class="ca-pip-row">
              <input id="ca-pip-input"
                     placeholder="numpy pandas matplotlib scikit-learn ..."
                     onkeydown="if(event.key==='Enter') caInstallPackages()" />
              <button onclick="caInstallPackages()">📦 Install</button>
              <button onclick="caSandboxReset()"   title="サンドボックスをリセット">🔄 Reset</button>
            </div>
            <div id="ca-pip-output"></div>
          </div>
        </div>

      </div><!-- /ca-editor-section -->
    </div><!-- /ca-body -->
  </div><!-- /ca-panel -->
</div><!-- /ca-overlay -->

<script>
/* ================================================================
   Coding Agent — Full IDE JavaScript (IIFE-isolated)
   ================================================================ */
(function () {
'use strict';

/* ── ESC character helper (avoids raw 0x1B in source) ── */
var ESC = String.fromCharCode(27);

/* ──────────────────────────────────────────────────────────────
   STATE
   ────────────────────────────────────────────────────────────── */
var _CA = {
  editor:       null,
  models:       {},       /* path -> monaco.editor.ITextModel  */
  tabs:         [],       /* [{path, lang, dirty, viewState}]  */
  activeTab:    null,
  fileTree:     [],
  treeState:    {},       /* path -> bool (expanded)           */
  outputH:      220,
  resizing:     false,
  monacoLoaded: false,
  monacoLoading: false,
};

/* ──────────────────────────────────────────────────────────────
   UTILITIES
   ────────────────────────────────────────────────────────────── */
function _esc(s) {
  if (typeof esc === 'function') return esc(String(s));
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function _toast(msg, type) {
  if (typeof toast === 'function') toast(msg, type || 'info');
  else console.log('[CodingAgent][' + (type || 'info') + ']', msg);
}

function caLangFromExt(filename) {
  var ext = (filename || '').split('.').pop().toLowerCase();
  var MAP = {
    py:'python', pyw:'python',
    js:'javascript', jsx:'javascript',
    ts:'typescript', tsx:'typescript',
    html:'html', htm:'html',
    css:'css', scss:'scss', less:'less',
    json:'json', jsonc:'json',
    go:'go',
    java:'java',
    cpp:'cpp', cc:'cpp', cxx:'cpp', c:'cpp', h:'cpp', hpp:'cpp',
    sh:'shell', bash:'shell', zsh:'shell',
    r:'r', R:'r',
    md:'markdown', markdown:'markdown',
    yml:'yaml', yaml:'yaml',
    xml:'xml',
    sql:'sql',
    rs:'rust',
    rb:'ruby',
    php:'php',
    swift:'swift',
    kt:'kotlin',
    cs:'csharp',
    lua:'lua',
    toml:'ini', ini:'ini',
  };
  return MAP[ext] || 'plaintext';
}

function caFileIcon(name, isDir) {
  if (isDir) return '📁';
  var ext = (name || '').split('.').pop().toLowerCase();
  var ICONS = {
    py:'🐍', pyw:'🐍',
    js:'🟨', jsx:'🟨',
    ts:'🔷', tsx:'🔷',
    html:'🌐', htm:'🌐',
    css:'🎨', scss:'🎨', less:'🎨',
    json:'📋', jsonc:'📋',
    go:'🐹',
    r:'📊', R:'📊',
    md:'📝', markdown:'📝',
    sh:'💲', bash:'💲', zsh:'💲',
    java:'☕',
    cpp:'⚙️', c:'⚙️', h:'⚙️', cc:'⚙️',
    sql:'🗄️',
    yml:'⚙️', yaml:'⚙️',
    toml:'⚙️', ini:'⚙️',
    txt:'📄',
    csv:'📊',
    png:'🖼️', jpg:'🖼️', jpeg:'🖼️', gif:'🖼️', svg:'🖼️', webp:'🖼️',
    pdf:'📕',
    zip:'📦', tar:'📦', gz:'📦', bz2:'📦',
    rs:'🦀',
    rb:'💎',
    php:'🐘',
    swift:'🍎',
    kt:'🅺',
    cs:'#️⃣',
    lua:'🌙',
  };
  return ICONS[ext] || '📄';
}

/* ──────────────────────────────────────────────────────────────
   API HELPER
   ────────────────────────────────────────────────────────────── */
async function caApi(path, opts) {
  opts = opts || {};
  var persona = (window.S && window.S.persona) ? window.S.persona : 'default';
  var url = '/api/chat/' + persona + path;
  var res = await fetch(url, opts);
  if (!res.ok) {
    var body = await res.text().catch(function () { return 'HTTP ' + res.status; });
    throw new Error(body || 'HTTP ' + res.status);
  }
  return res.json();
}

/* ──────────────────────────────────────────────────────────────
   MONACO LOADER
   ────────────────────────────────────────────────────────────── */
function caLoadMonaco(cb) {
  if (_CA.monacoLoaded)  { cb(); return; }
  if (_CA.monacoLoading) {
    var tid = setInterval(function () {
      if (_CA.monacoLoaded) { clearInterval(tid); cb(); }
    }, 120);
    return;
  }
  _CA.monacoLoading = true;
  var s = document.createElement('script');
  s.src = 'https://cdn.jsdelivr.net/npm/monaco-editor@0.52.0/min/vs/loader.js';
  s.onerror = function () {
    _CA.monacoLoading = false;
    _toast('Monaco Editor の読み込みに失敗しました', 'error');
  };
  s.onload = function () {
    require.config({
      paths: { vs: 'https://cdn.jsdelivr.net/npm/monaco-editor@0.52.0/min/vs' }
    });
    require(['vs/editor/editor.main'], function () {
      _CA.monacoLoaded  = true;
      _CA.monacoLoading = false;
      cb();
    });
  };
  document.head.appendChild(s);
}

function caInitEditor(cb) {
  caLoadMonaco(function () {
    if (_CA.editor) { if (cb) cb(); return; }

    var loading = document.getElementById('ca-editor-loading');
    if (loading) loading.style.display = 'none';

    var container = document.getElementById('ca-editor-container');
    _CA.editor = monaco.editor.create(container, {
      value:                   '',
      language:                'python',
      theme:                   'vs-dark',
      fontSize:                14,
      fontFamily:              "'Fira Code', 'Cascadia Code', 'JetBrains Mono', Consolas, monospace",
      fontLigatures:           true,
      minimap:                 { enabled: true, scale: 1 },
      scrollBeyondLastLine:    false,
      automaticLayout:         false,
      tabSize:                 4,
      insertSpaces:            true,
      wordWrap:                'off',
      lineNumbers:             'on',
      renderLineHighlight:     'all',
      renderWhitespace:        'selection',
      bracketPairColorization: { enabled: true },
      quickSuggestions:        { other: true, comments: false, strings: false },
      scrollbar: { vertical: 'auto', horizontal: 'auto', useShadows: false },
    });

    /* Ctrl+S → Save */
    _CA.editor.addCommand(
      monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS,
      function () { caSaveFile(); }
    );
    /* Ctrl+Enter → Run */
    _CA.editor.addCommand(
      monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter,
      function () { caRunCode(); }
    );

    /* Mark tab dirty on edit */
    _CA.editor.onDidChangeModelContent(function () {
      if (_CA.activeTab) {
        var tab = _CA.tabs.find(function (t) { return t.path === _CA.activeTab; });
        if (tab && !tab.dirty) { tab.dirty = true; caRenderTabs(); }
      }
    });

    if (cb) cb();
  });
}

/* ──────────────────────────────────────────────────────────────
   TAB SYSTEM
   ────────────────────────────────────────────────────────────── */
function caOpenTab(path, content, lang) {
  var existing = _CA.tabs.find(function (t) { return t.path === path; });
  if (existing) { caActivateTab(path); return; }

  /* Max 10 tabs — evict oldest clean tab */
  if (_CA.tabs.length >= 10) {
    var oldest = _CA.tabs.find(function (t) { return !t.dirty; });
    if (oldest) { caCloseTabForce(oldest.path); }
    else { _toast('タブが多すぎます。タブを閉じてください。', 'error'); return; }
  }

  lang = lang || caLangFromExt(path.split('/').pop());
  _CA.tabs.push({ path: path, lang: lang, dirty: false, viewState: null });

  caInitEditor(function () {
    if (!_CA.models[path]) {
      var uri;
      try { uri = monaco.Uri.parse('file://' + path); } catch (e) { uri = undefined; }
      _CA.models[path] = monaco.editor.createModel(content || '', lang, uri);
    }
    caActivateTab(path);
  });
}

function caActivateTab(path) {
  /* Save view state of outgoing tab */
  if (_CA.editor && _CA.activeTab && _CA.activeTab !== path) {
    var cur = _CA.tabs.find(function (t) { return t.path === _CA.activeTab; });
    if (cur) cur.viewState = _CA.editor.saveViewState();
  }

  _CA.activeTab = path;
  caRenderTabs();
  _caHighlightTreeItem(path);

  if (_CA.editor && _CA.models[path]) {
    _CA.editor.setModel(_CA.models[path]);
    var tab = _CA.tabs.find(function (t) { return t.path === path; });
    if (tab) {
      monaco.editor.setModelLanguage(_CA.models[path], tab.lang);
      var sel = document.getElementById('ca-lang-select');
      if (sel) sel.value = tab.lang;
      if (tab.viewState) _CA.editor.restoreViewState(tab.viewState);
    }
    setTimeout(function () { _CA.editor.layout(); }, 50);
    _CA.editor.focus();
  }
}

function caCloseTab(path) {
  var tab = _CA.tabs.find(function (t) { return t.path === path; });
  if (!tab) return;
  if (tab.dirty) {
    var name = path.split('/').pop();
    if (!confirm('"' + name + '" に未保存の変更があります。閉じますか?')) return;
  }
  caCloseTabForce(path);
}

function caCloseTabForce(path) {
  var idx = _CA.tabs.findIndex(function (t) { return t.path === path; });
  if (idx === -1) return;
  _CA.tabs.splice(idx, 1);
  if (_CA.models[path]) { _CA.models[path].dispose(); delete _CA.models[path]; }

  if (_CA.activeTab === path) {
    if (_CA.tabs.length > 0) {
      caActivateTab(_CA.tabs[Math.min(idx, _CA.tabs.length - 1)].path);
    } else {
      _CA.activeTab = null;
      if (_CA.editor) _CA.editor.setModel(null);
      caRenderTabs();
    }
  } else {
    caRenderTabs();
  }
}

function caRenderTabs() {
  var tabbar = document.getElementById('ca-tabbar');
  if (!tabbar) return;
  tabbar.innerHTML = '';

  if (_CA.tabs.length === 0) {
    var empty = document.createElement('div');
    empty.className = 'ca-tab-empty';
    empty.textContent = '← ファイルを選択するか \u25B6 Run で実行';
    tabbar.appendChild(empty);
    return;
  }

  _CA.tabs.forEach(function (tab) {
    var name  = tab.path.split('/').pop();
    var icon  = caFileIcon(name, false);
    var dirty = tab.dirty ? '\u25CF ' : '';

    var div = document.createElement('div');
    div.className = 'ca-tab' + (tab.path === _CA.activeTab ? ' ca-tab-active' : '');
    div.title = tab.path;
    div.setAttribute('data-path', tab.path);

    var iconSpan = document.createElement('span');
    iconSpan.className = 'ca-tab-icon';
    iconSpan.textContent = icon;

    var nameSpan = document.createElement('span');
    nameSpan.className = 'ca-tab-name';
    nameSpan.textContent = dirty + name;

    var closeBtn = document.createElement('button');
    closeBtn.className = 'ca-tab-close';
    closeBtn.title = '閉じる';
    closeBtn.textContent = '\u2715';
    closeBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      caCloseTab(div.getAttribute('data-path'));
    });

    div.appendChild(iconSpan);
    div.appendChild(nameSpan);
    div.appendChild(closeBtn);
    div.addEventListener('click', function () {
      caActivateTab(this.getAttribute('data-path'));
    });
    tabbar.appendChild(div);
  });
}

/* ──────────────────────────────────────────────────────────────
   FILE TREE
   ────────────────────────────────────────────────────────────── */
async function caRefreshTree() {
  try {
    var data = await caApi('/sandbox/tree');
    _CA.fileTree = data.tree || [];
    caRenderFileTree();
  } catch (e) {
    var ct = document.getElementById('ca-file-tree');
    if (ct) {
      ct.innerHTML =
        '<div style="padding:10px 12px;font-size:12px;color:#f87171;">' +
        '\u26A0\uFE0F ツリーの取得に失敗しました</div>';
    }
    console.warn('[CodingAgent] Tree error:', e);
  }
}

function caRenderFileTree() {
  var container = document.getElementById('ca-file-tree');
  if (!container) return;
  container.innerHTML = '';
  _renderNodes(_CA.fileTree, container, 0);
}

function _renderNodes(nodes, container, depth) {
  if (!nodes || !nodes.length) return;
  nodes.forEach(function (node) {
    var item = document.createElement('div');
    item.className = 'ca-tree-item';
    item.style.paddingLeft = (8 + depth * 14) + 'px';

    if (node.type === 'directory') {
      var isOpen = (_CA.treeState[node.path] !== false);
      item.classList.add('ca-tree-dir');

      var toggle = document.createElement('span');
      toggle.className = 'ca-tree-toggle';
      toggle.textContent = isOpen ? '\u25BE' : '\u25B8';

      var icon = document.createElement('span');
      icon.className = 'ca-tree-icon';
      icon.textContent = isOpen ? '📂' : '📁';

      var label = document.createElement('span');
      label.className = 'ca-tree-name';
      label.textContent = node.name;

      item.appendChild(toggle);
      item.appendChild(icon);
      item.appendChild(label);

      item.addEventListener('click', function (e) {
        e.stopPropagation();
        _CA.treeState[node.path] = !(_CA.treeState[node.path] !== false);
        caRenderFileTree();
      });
      item.addEventListener('contextmenu', function (e) {
        e.preventDefault();
        _caShowCtxMenu(e, node.path, true);
      });

      container.appendChild(item);

      if (isOpen && node.children && node.children.length) {
        var sub = document.createElement('div');
        _renderNodes(node.children, sub, depth + 1);
        container.appendChild(sub);
      }

    } else {
      var fileIcon = caFileIcon(node.name, false);
      item.setAttribute('data-path', node.path);
      if (node.path === _CA.activeTab) item.classList.add('ca-tree-active');

      var tog2 = document.createElement('span');
      tog2.className = 'ca-tree-toggle';
      tog2.textContent = ' ';

      var ic2 = document.createElement('span');
      ic2.className = 'ca-tree-icon';
      ic2.textContent = fileIcon;

      var lbl2 = document.createElement('span');
      lbl2.className = 'ca-tree-name';
      lbl2.textContent = node.name;

      item.appendChild(tog2);
      item.appendChild(ic2);
      item.appendChild(lbl2);

      item.addEventListener('click', function () {
        caOpenFile(node.path);
      });
      item.addEventListener('contextmenu', function (e) {
        e.preventDefault();
        _caShowCtxMenu(e, node.path, false);
      });
      container.appendChild(item);
    }
  });
}

function _caHighlightTreeItem(path) {
  var items = document.querySelectorAll('#ca-file-tree .ca-tree-item');
  items.forEach(function (el) {
    var p = el.getAttribute('data-path');
    el.classList.toggle('ca-tree-active', p === path);
  });
}

async function caOpenFile(path) {
  if (_CA.tabs.find(function (t) { return t.path === path; })) {
    caActivateTab(path);
    return;
  }
  try {
    var data = await caApi('/sandbox/file/read?path=' + encodeURIComponent(path));
    caOpenTab(path, data.content || '', caLangFromExt(path.split('/').pop()));
  } catch (e) {
    _toast('ファイルの読み込みに失敗しました: ' + e.message, 'error');
  }
}

/* ──────────────────────────────────────────────────────────────
   CONTEXT MENU
   ────────────────────────────────────────────────────────────── */
function _caShowCtxMenu(e, path, isDir) {
  _caRemoveCtxMenu();

  var menu = document.createElement('div');
  menu.className = 'ca-ctx-menu';
  menu.id = '_ca_ctx';
  menu.style.left = e.clientX + 'px';
  menu.style.top  = e.clientY + 'px';

  var actions = [];
  if (!isDir) {
    actions.push({ label: '📂 開く',          fn: function () { caOpenFile(path); } });
    actions.push({ type: 'sep' });
  }
  actions.push({ label: '\u270F\uFE0F 名前を変更',      fn: function () { caRenameFile(path); } });
  actions.push({ label: '🗑️ 削除',     fn: function () { caDeleteFile(path); } });

  actions.forEach(function (act) {
    if (act.type === 'sep') {
      var sep = document.createElement('div');
      sep.className = 'ca-ctx-sep';
      menu.appendChild(sep);
    } else {
      var item = document.createElement('div');
      item.className = 'ca-ctx-item';
      item.textContent = act.label;
      item.addEventListener('click', function () { _caRemoveCtxMenu(); act.fn(); });
      menu.appendChild(item);
    }
  });

  document.body.appendChild(menu);

  /* Clamp to viewport */
  var r = menu.getBoundingClientRect();
  if (r.right  > window.innerWidth)  menu.style.left = (e.clientX - r.width)  + 'px';
  if (r.bottom > window.innerHeight) menu.style.top  = (e.clientY - r.height) + 'px';

  /* Auto-close on outside click */
  setTimeout(function () {
    document.addEventListener('click', _caCtxOutside, { once: false });
  }, 0);
}
function _caCtxOutside(e) {
  var m = document.getElementById('_ca_ctx');
  if (m && !m.contains(e.target)) {
    _caRemoveCtxMenu();
    document.removeEventListener('click', _caCtxOutside);
  }
}
function _caRemoveCtxMenu() {
  var m = document.getElementById('_ca_ctx');
  if (m) m.remove();
}

/* ──────────────────────────────────────────────────────────────
   RUN CODE
   ────────────────────────────────────────────────────────────── */
async function caRunCode() {
  var runBtn = document.getElementById('ca-run-btn');
  if (!_CA.editor) {
    caInitEditor(function () { caRunCode(); });
    return;
  }
  var code = _CA.editor.getValue();
  if (!code.trim()) { _toast('コードが空です', 'warning'); return; }

  var sel  = document.getElementById('ca-lang-select');
  var lang = sel ? sel.value : 'python';

  runBtn.disabled   = true;
  runBtn.textContent = '\u23F3 Running...';
  caSelectOutTab('output');
  caAppendOutput(ESC + '[36m\u25BA Running [' + lang + ']...' + ESC + '[0m\n', 'stdout');

  try {
    var result = await caApi('/sandbox/execute', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ code: code, language: lang }),
    });

    if (result.stdout) caAppendOutput(result.stdout, 'stdout');
    if (result.stderr) caAppendOutput(result.stderr, 'stderr');

    if (result.artifacts && result.artifacts.length) {
      caAddArtifacts(result.artifacts);
      caSelectOutTab('artifacts');
    }

    var exitStr = (result.exit_code !== undefined)
      ? ' [exit: ' + result.exit_code + ']' : '';
    caAppendOutput(ESC + '[32m\u2714 Done' + exitStr + ESC + '[0m\n', 'stdout');

  } catch (e) {
    caAppendOutput(ESC + '[31mError: ' + e.message + ESC + '[0m\n', 'stderr');
  } finally {
    runBtn.disabled   = false;
    runBtn.textContent = '\u25B6 Run';
  }
}

/* ──────────────────────────────────────────────────────────────
   SAVE FILE
   ────────────────────────────────────────────────────────────── */
async function caSaveFile() {
  if (!_CA.editor || !_CA.activeTab) {
    _toast('保存するファイルがありません', 'warning');
    return;
  }
  var path    = _CA.activeTab;
  var content = _CA.editor.getValue();
  try {
    await caApi('/sandbox/file/write', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ path: path, content: content }),
    });
    var tab = _CA.tabs.find(function (t) { return t.path === path; });
    if (tab) { tab.dirty = false; caRenderTabs(); }
    _toast('💾 保存しました: ' + path.split('/').pop(), 'success');
  } catch (e) {
    _toast('保存に失敗しました: ' + e.message, 'error');
  }
}

/* ──────────────────────────────────────────────────────────────
   OUTPUT PANEL — ANSI RENDERER
   ────────────────────────────────────────────────────────────── */
function _ansiToHtml(raw) {
  var COLORS = {
    '30':'#1e1e2e','31':'#f87171','32':'#4ade80','33':'#facc15',
    '34':'#60a5fa','35':'#c084fc','36':'#22d3ee','37':'#e2e8f0',
    '90':'#64748b','91':'#fb7185','92':'#86efac','93':'#fde047',
    '94':'#93c5fd','95':'#d8b4fe','96':'#67e8f9','97':'#f8fafc',
  };
  var out   = '';
  var open  = 0;
  var i     = 0;
  var ESC_CODE = 27; /* 0x1B */

  while (i < raw.length) {
    var code = raw.charCodeAt(i);
    if (code === ESC_CODE && raw[i + 1] === '[') {
      /* Find closing 'm' */
      var j = i + 2;
      while (j < raw.length && raw[j] !== 'm') j++;
      if (raw[j] === 'm') {
        var segs = raw.slice(i + 2, j).split(';');
        segs.forEach(function (seg) {
          if (seg === '0' || seg === '') {
            if (open > 0) { out += '</span>'.repeat(open); open = 0; }
          } else if (seg === '1') {
            out += '<b>';
          } else if (seg === '3') {
            out += '<i>';
          } else if (COLORS[seg]) {
            out += '<span style="color:' + COLORS[seg] + '">';
            open++;
          }
        });
        i = j + 1;
        continue;
      }
    }
    var ch = raw[i];
    if      (ch === '&') out += '&amp;';
    else if (ch === '<') out += '&lt;';
    else if (ch === '>') out += '&gt;';
    else                 out += ch;
    i++;
  }
  if (open > 0) out += '</span>'.repeat(open);
  return out;
}

function caAppendOutput(text, type) {
  var out = document.getElementById('ca-out-content-output');
  if (!out) return;
  var div = document.createElement('div');
  div.className = (type === 'stderr') ? 'ca-out-stderr' : 'ca-out-stdout';
  div.innerHTML = _ansiToHtml(text);
  out.appendChild(div);
  out.scrollTop = out.scrollHeight;
}

function caClearOutput() {
  var o = document.getElementById('ca-out-content-output');
  if (o) o.innerHTML = '';
  var a = document.getElementById('ca-out-content-artifacts');
  if (a) {
    a.innerHTML =
      '<div class="ca-artifacts-empty">' +
      '🖼️ アーティファクトがここに表示されます<br>' +
      '<small>matplotlib など画像を生成すると表示されます</small>' +
      '</div>';
  }
}

function caAddArtifacts(artifacts) {
  var ct = document.getElementById('ca-out-content-artifacts');
  if (!ct) return;
  var ph = ct.querySelector('.ca-artifacts-empty');
  if (ph) ph.remove();

  artifacts.forEach(function (art) {
    var wrapper = document.createElement('div');
    wrapper.className = 'ca-artifact-item';
    var img = document.createElement('img');
    img.className = 'ca-artifact-img';
    img.title = '\u30AF\u30EA\u30C3\u30AF\u3067\u62E1\u5927';
    var src = (typeof art === 'string' && art.startsWith('data:'))
      ? art : 'data:image/png;base64,' + art;
    img.src = src;
    img.addEventListener('click', function () {
      var w = window.open('', '_blank');
      if (w) {
        w.document.write(
          '<html><body style="margin:0;background:#000;display:flex;' +
          'align-items:center;justify-content:center;min-height:100vh;">' +
          '<img src="' + src + '" style="max-width:100%;max-height:100vh;"></body></html>'
        );
      }
    });
    wrapper.appendChild(img);
    ct.appendChild(wrapper);
  });
  ct.scrollTop = ct.scrollHeight;
}

function caSelectOutTab(tab) {
  document.querySelectorAll('.ca-out-tab').forEach(function (el) {
    el.classList.toggle('ca-out-tab-active', el.dataset.tab === tab);
  });
  document.querySelectorAll('.ca-out-content').forEach(function (el) {
    el.classList.remove('ca-out-active');
  });
  var target = document.getElementById('ca-out-content-' + tab);
  if (target) target.classList.add('ca-out-active');
}

/* ──────────────────────────────────────────────────────────────
   PIP INSTALL
   ────────────────────────────────────────────────────────────── */
async function caInstallPackages() {
  var inp = document.getElementById('ca-pip-input');
  var out = document.getElementById('ca-pip-output');
  if (!inp || !out) return;

  var raw  = inp.value.trim();
  var pkgs = raw.split(/\\s+/).filter(Boolean);
  if (!pkgs.length) { _toast('\u30D1\u30C3\u30B1\u30FC\u30B8\u540D\u3092\u5165\u529B\u3057\u3066\u304F\u3060\u3055\u3044', 'warning'); return; }

  out.innerHTML = '<div class="ca-pip-loading">📦 Installing ' + _esc(pkgs.join(', ')) + '...</div>';
  try {
    var r = await caApi('/sandbox/install', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ packages: pkgs }),
    });
    out.innerHTML = '<div class="ca-pip-ok">\u2705 ' + _esc(r.message || '\u30A4\u30F3\u30B9\u30C8\u30FC\u30EB\u5B8C\u4E86') + '</div>';
    inp.value = '';
  } catch (e) {
    out.innerHTML = '<div class="ca-pip-error">\u274C ' + _esc(e.message) + '</div>';
  }
}

async function caSandboxReset() {
  var out = document.getElementById('ca-pip-output');
  if (out) out.innerHTML = '<div class="ca-pip-loading">🔄 \u30B5\u30F3\u30C9\u30DC\u30C3\u30AF\u30B9\u3092\u30EA\u30BB\u30C3\u30C8\u4E2D...</div>';
  try {
    var r = await caApi('/sandbox/reset', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({}),
    });
    if (out) out.innerHTML = '<div class="ca-pip-ok">\u2705 ' + _esc(r.message || '\u30EA\u30BB\u30C3\u30C8\u5B8C\u4E86') + '</div>';
    caClearOutput();
    await caRefreshTree();
    _toast('🔄 \u30B5\u30F3\u30C9\u30DC\u30C3\u30AF\u30B9\u3092\u30EA\u30BB\u30C3\u30C8\u3057\u307E\u3057\u305F', 'success');
  } catch (e) {
    if (out) out.innerHTML = '<div class="ca-pip-error">\u274C ' + _esc(e.message) + '</div>';
  }
}

/* ──────────────────────────────────────────────────────────────
   FILE OPERATIONS
   ────────────────────────────────────────────────────────────── */
async function caNewFile() {
  var name = prompt('\u65B0\u3057\u3044\u30D5\u30A1\u30A4\u30EB\u540D\u3092\u5165\u529B\u3057\u3066\u304F\u3060\u3055\u3044:', 'untitled.py');
  if (!name || !name.trim()) return;
  var clean = name.trim().replace(/^\\/+/, '');
  var path  = '/workspace/' + clean;
  try {
    await caApi('/sandbox/file/write', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ path: path, content: '' }),
    });
    await caRefreshTree();
    caOpenTab(path, '', caLangFromExt(clean));
    _toast('📄 \u30D5\u30A1\u30A4\u30EB\u3092\u4F5C\u6210\u3057\u307E\u3057\u305F: ' + clean, 'success');
  } catch (e) {
    _toast('\u30D5\u30A1\u30A4\u30EB\u306E\u4F5C\u6210\u306B\u5931\u6557\u3057\u307E\u3057\u305F: ' + e.message, 'error');
  }
}

function caUploadFile() {
  var inp = document.getElementById('ca-upload-input');
  if (inp) inp.click();
}

async function caHandleUpload(event) {
  var files = event.target.files;
  if (!files || !files.length) return;
  var persona = (window.S && window.S.persona) ? window.S.persona : 'default';

  for (var i = 0; i < files.length; i++) {
    var file = files[i];
    var fd   = new FormData();
    fd.append('file', file);
    try {
      var res = await fetch('/api/chat/' + persona + '/sandbox/files', {
        method: 'POST',
        body:   fd,
      });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      var data = await res.json();
      await caRefreshTree();
      if (data.remote_path) caOpenFile(data.remote_path);
      _toast('\u2B06 \u30A2\u30C3\u30D7\u30ED\u30FC\u30C9\u5B8C\u4E86: ' + file.name, 'success');
    } catch (e) {
      _toast('\u30A2\u30C3\u30D7\u30ED\u30FC\u30C9\u5931\u6557: ' + file.name + ' \u2014 ' + e.message, 'error');
    }
  }
  event.target.value = '';
}

async function caRenameFile(path) {
  var oldName = path.split('/').pop();
  var newName = prompt('\u65B0\u3057\u3044\u30D5\u30A1\u30A4\u30EB\u540D:', oldName);
  if (!newName || newName === oldName) return;

  var dir     = path.split('/').slice(0, -1).join('/');
  var newPath = dir + '/' + newName;
  try {
    var data = await caApi('/sandbox/file/read?path=' + encodeURIComponent(path));
    await caApi('/sandbox/file/write', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ path: newPath, content: data.content || '' }),
    });
    var persona = (window.S && window.S.persona) ? window.S.persona : 'default';
    await fetch('/api/chat/' + persona + '/sandbox/files/' + encodeURIComponent(path),
      { method: 'DELETE' });

    if (_CA.tabs.find(function (t) { return t.path === path; })) {
      var savedContent = _CA.models[path] ? _CA.models[path].getValue() : (data.content || '');
      caCloseTabForce(path);
      caOpenTab(newPath, savedContent, caLangFromExt(newName));
    }
    await caRefreshTree();
    _toast('\u270F\uFE0F \u540D\u524D\u3092\u5909\u66F4\u3057\u307E\u3057\u305F: ' + newName, 'success');
  } catch (e) {
    _toast('\u540D\u524D\u306E\u5909\u66F4\u306B\u5931\u6557\u3057\u307E\u3057\u305F: ' + e.message, 'error');
  }
}

async function caDeleteFile(path) {
  var name = path.split('/').pop();
  if (!confirm('"' + name + '" \u3092\u524A\u9664\u3057\u307E\u3059\u304B?\n\u3053\u306E\u64CD\u4F5C\u306F\u5143\u306B\u623B\u305B\u307E\u305B\u3093\u3002')) return;
  try {
    var persona = (window.S && window.S.persona) ? window.S.persona : 'default';
    var res = await fetch(
      '/api/chat/' + persona + '/sandbox/files/' + encodeURIComponent(path),
      { method: 'DELETE' }
    );
    if (!res.ok) throw new Error('HTTP ' + res.status);
    if (_CA.tabs.find(function (t) { return t.path === path; })) caCloseTabForce(path);
    await caRefreshTree();
    _toast('🗑️ \u524A\u9664\u3057\u307E\u3057\u305F: ' + name, 'success');
  } catch (e) {
    _toast('\u524A\u9664\u306B\u5931\u6557\u3057\u307E\u3057\u305F: ' + e.message, 'error');
  }
}

/* ──────────────────────────────────────────────────────────────
   RESIZE HANDLE (output panel)
   ────────────────────────────────────────────────────────────── */
function _initResizeHandle() {
  var handle  = document.getElementById('ca-resize-handle');
  var outPane = document.getElementById('ca-output-panel');
  if (!handle || !outPane) return;

  var startY = 0, startH = 0;

  handle.addEventListener('mousedown', function (e) {
    startY = e.clientY;
    startH = outPane.offsetHeight;
    _CA.resizing = true;
    handle.classList.add('ca-resizing');
    document.body.style.userSelect = 'none';
    document.body.style.cursor     = 'ns-resize';
    e.preventDefault();
  });

  document.addEventListener('mousemove', function (e) {
    if (!_CA.resizing) return;
    var delta = startY - e.clientY;
    var newH  = Math.max(120, Math.min(640, startH + delta));
    outPane.style.height = newH + 'px';
    _CA.outputH = newH;
    if (_CA.editor) _CA.editor.layout();
  });

  document.addEventListener('mouseup', function () {
    if (_CA.resizing) {
      _CA.resizing = false;
      handle.classList.remove('ca-resizing');
      document.body.style.userSelect = '';
      document.body.style.cursor     = '';
    }
  });
}

/* ──────────────────────────────────────────────────────────────
   LANGUAGE SELECT → sync Monaco model language
   ────────────────────────────────────────────────────────────── */
function _initLangSelect() {
  var sel = document.getElementById('ca-lang-select');
  if (!sel || sel._caInited) return;
  sel._caInited = true;
  sel.addEventListener('change', function (e) {
    var lang = e.target.value;
    if (_CA.editor && _CA.activeTab && _CA.models[_CA.activeTab] && window.monaco) {
      monaco.editor.setModelLanguage(_CA.models[_CA.activeTab], lang);
      var tab = _CA.tabs.find(function (t) { return t.path === _CA.activeTab; });
      if (tab) tab.lang = lang;
    }
  });
}

/* ──────────────────────────────────────────────────────────────
   WINDOW RESIZE → relayout Monaco
   ────────────────────────────────────────────────────────────── */
window.addEventListener('resize', function () {
  if (_CA.editor && window.isCodingAgentOpen && window.isCodingAgentOpen()) {
    _CA.editor.layout();
  }
});

/* ──────────────────────────────────────────────────────────────
   GLOBAL API  (called from chat.js)
   ────────────────────────────────────────────────────────────── */
window.openCodingAgent = function (options) {
  options = options || {};
  var overlay = document.getElementById('coding-agent-overlay');
  if (!overlay) return;

  overlay.style.display = 'flex';
  overlay.classList.add('ca-visible');

  caInitEditor(function () {
    _initLangSelect();

    if (options.code !== undefined) {
      var lang   = options.language || 'python';
      var extMap = {
        python:'py', javascript:'js', typescript:'ts', bash:'sh',
        java:'java', cpp:'cpp', go:'go', r:'r', html:'html',
        css:'css', json:'json', sql:'sql', markdown:'md',
      };
      var ext      = extMap[lang] || 'txt';
      var fakePath = '/workspace/scratch.' + ext;

      var existingTab = _CA.tabs.find(function (t) { return t.path === fakePath; });
      if (existingTab) {
        caActivateTab(fakePath);
        if (_CA.models[fakePath]) {
          _CA.models[fakePath].setValue(options.code);
          monaco.editor.setModelLanguage(_CA.models[fakePath], lang);
        }
        existingTab.lang  = lang;
        existingTab.dirty = true;
        caRenderTabs();
      } else {
        caOpenTab(fakePath, options.code, lang);
      }
      var sel = document.getElementById('ca-lang-select');
      if (sel) sel.value = lang;
    }

    setTimeout(function () {
      _CA.editor.layout();
      _CA.editor.focus();
    }, 60);
  });

  caRefreshTree();
};

window.closeCodingAgent = function () {
  var overlay = document.getElementById('coding-agent-overlay');
  if (overlay) {
    overlay.style.display = 'none';
    overlay.classList.remove('ca-visible');
  }
  _caRemoveCtxMenu();
};

window.isCodingAgentOpen = function () {
  var o = document.getElementById('coding-agent-overlay');
  return o ? (o.style.display !== 'none' && o.style.display !== '') : false;
};

/* Expose key functions for external use */
window.caRunCode          = caRunCode;
window.caSaveFile         = caSaveFile;
window.caRefreshTree      = caRefreshTree;
window.caSelectOutTab     = caSelectOutTab;
window.caClearOutput      = caClearOutput;
window.caInstallPackages  = caInstallPackages;
window.caSandboxReset     = caSandboxReset;
window.caNewFile          = caNewFile;
window.caUploadFile       = caUploadFile;
window.caHandleUpload     = caHandleUpload;
window.caActivateTab      = caActivateTab;
window.caCloseTab         = caCloseTab;
window.caOpenFile         = caOpenFile;
window.caRenameFile       = caRenameFile;
window.caDeleteFile       = caDeleteFile;

/* ──────────────────────────────────────────────────────────────
   DOM INIT
   ────────────────────────────────────────────────────────────── */
function _domInit() {
  _initResizeHandle();
  _initLangSelect();

  /* Escape key → close context menu */
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') _caRemoveCtxMenu();
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', _domInit);
} else {
  _domInit();
}

})(); /* end IIFE */
</script>
"""
