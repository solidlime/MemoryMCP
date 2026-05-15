"""Chat tab section for the MemoryMCP Dashboard.

Renders a fully-functional chat interface with SSE streaming,
tool call visualization, and an inline settings panel.
"""

from .coding_agent import render_coding_agent_panel


def render_chat_tab() -> str:
    """Return the HTML for the Chat tab."""
    return """
        <style>
        /* ── Chat tab styles ── */
        #chat-layout { display: flex; gap: 16px; height: calc(100vh - 200px); min-height: 500px; }
        #chat-main { flex: 1; display: flex; flex-direction: column; min-width: 0; }
        #chat-messages {
            flex: 1; overflow-y: auto; padding: 16px; display: flex;
            flex-direction: column; gap: 12px;
        }
        #chat-input-area {
            padding: 12px 16px; border-top: 1px solid var(--glass-border);
            display: flex; gap: 10px; align-items: flex-end;
        }
        #chat-input {
            flex: 1; background: rgba(255,255,255,0.06); border: 1px solid var(--glass-border);
            border-radius: 12px; padding: 12px 14px; color: var(--text-primary);
            font-size: 0.9rem; resize: none; min-height: 44px; max-height: 160px;
            font-family: inherit; outline: none; line-height: 1.5;
            transition: border-color 0.2s;
        }
        #chat-input:focus { border-color: var(--accent-purple); }
        #chat-input::placeholder { color: var(--text-muted); }
        #chat-send-btn {
            padding: 10px 20px; border-radius: 12px;
            background: linear-gradient(135deg, var(--accent-purple), #7c3aed);
            border: none; color: white; font-size: 0.9rem; cursor: pointer;
            font-weight: 600; transition: all 0.2s; white-space: nowrap;
            align-self: flex-end;
        }
        #chat-send-btn:hover:not(:disabled) { transform: translateY(-1px); box-shadow: 0 4px 16px rgba(167,139,250,0.4); }
        #chat-send-btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
        .chat-msg { display: flex; flex-direction: column; gap: 4px; max-width: 85%; animation: fadeInUp 0.25s ease; }
        .chat-msg.user { align-self: flex-end; align-items: flex-end; }
        .chat-msg.assistant { align-self: flex-start; align-items: flex-start; }
        .chat-bubble {
            padding: 10px 14px; border-radius: 14px; font-size: 0.9rem; line-height: 1.6;
            white-space: pre-wrap; word-break: break-word;
        }
        .chat-msg.user .chat-bubble {
            background: linear-gradient(135deg, rgba(167,139,250,0.25), rgba(124,58,237,0.2));
            border: 1px solid rgba(167,139,250,0.3); color: var(--text-primary);
            border-bottom-right-radius: 4px;
        }
        .chat-msg.assistant .chat-bubble {
            background: var(--glass-bg); border: 1px solid var(--glass-border);
            color: var(--text-secondary); border-bottom-left-radius: 4px;
        }
        .chat-time { font-size: 0.72rem; color: var(--text-muted); padding: 0 4px; }
        .chat-tool-call {
            font-size: 0.78rem; padding: 2px 8px; border-radius: 8px;
            background: rgba(96,165,250,0.1); border: 1px solid rgba(96,165,250,0.2);
            color: var(--accent-blue); margin: 4px 0;
        }
        .chat-tool-call.done {
            border-color: rgba(52,211,153,0.3); background: rgba(52,211,153,0.06);
        }
        .chat-tool-result {
            font-size: 0.78rem; padding: 2px 8px; border-radius: 8px;
            background: rgba(52,211,153,0.08); border: 1px solid rgba(52,211,153,0.2);
            color: var(--accent-green); margin: 4px 0;
        }
        .chat-tool-call details, .chat-tool-result details { padding: 0; }
        .chat-tool-call summary, .chat-tool-result summary {
            cursor: pointer; user-select: none; padding: 4px 6px;
            outline: none; list-style: none;
        }
        .chat-tool-call summary::-webkit-details-marker,
        .chat-tool-result summary::-webkit-details-marker { display: none; }
        .chat-tool-status { opacity: 0.7; font-size: 0.72rem; margin-left: 6px; }
        .chat-tool-detail {
            margin: 4px 0 4px 10px; white-space: pre-wrap; word-break: break-all;
            color: rgba(220,235,255,0.92); max-height: 200px; overflow-y: auto;
            font-size: 0.7rem; line-height: 1.4;
            border-left: 2px solid rgba(96,165,250,0.3); padding-left: 8px;
        }
        .chat-tool-result-content {
            border-left-color: rgba(52,211,153,0.4); color: rgba(160,255,200,0.92);
        }
        html.light .chat-tool-call { color: rgba(30,80,200,0.9); }
        html.light .chat-tool-result { color: rgba(0,120,60,0.9); }
        html.light .chat-tool-detail { color: rgba(30,50,120,0.9); }
        html.light .chat-tool-result-content { color: rgba(0,100,40,0.9); }
        .chat-typing { display: flex; gap: 4px; align-items: center; padding: 10px 14px; }
        .chat-typing span {
            width: 6px; height: 6px; border-radius: 50%;
            background: var(--accent-purple); animation: typingDot 1.2s ease-in-out infinite;
        }
        .chat-typing span:nth-child(2) { animation-delay: 0.2s; }
        .chat-typing span:nth-child(3) { animation-delay: 0.4s; }
        @keyframes typingDot { 0%,80%,100%{transform:scale(0.7);opacity:0.4} 40%{transform:scale(1);opacity:1} }
        /* Message action buttons */
        .chat-msg-actions {
            display: flex; gap: 4px; margin-top: 4px; opacity: 0; transition: opacity 0.2s;
        }
        .chat-msg:hover .chat-msg-actions { opacity: 1; }
        .chat-msg-action-btn {
            background: none; border: 1px solid var(--glass-border); border-radius: 4px;
            color: var(--text-muted); padding: 1px 6px; font-size: 0.68rem;
            cursor: pointer; transition: all 0.15s;
        }
        .chat-msg-action-btn:hover { color: var(--text-primary); background: var(--glass-bg); }
        .chat-msg-action-btn.retry:hover { color: var(--accent-purple); border-color: rgba(167,139,250,0.4); }
        .chat-msg-action-btn.edit:hover { color: var(--accent-blue); border-color: rgba(96,165,250,0.4); }
        /* Settings sidebar */
        #settings-panel {
            width: 280px; flex-shrink: 0; display: flex; flex-direction: column; gap: 12px;
            overflow-y: auto;
        }
        #settings-panel.collapsed { width: 0; overflow: hidden; }
        /* Settings accordion */
        #settings-panel details {
            border: 1px solid var(--glass-border); border-radius: 8px;
            margin-bottom: 8px;
        }
        #settings-panel details:not([open]) { overflow: hidden; }
        #settings-panel details[open] { border-color: rgba(167,139,250,0.25); overflow: visible; }
        #settings-panel details[open] .details-body { max-height: 280px; overflow-y: auto; }
        #settings-panel summary {
            padding: 9px 12px; font-size: 0.8rem; font-weight: 600;
            color: var(--text-secondary); cursor: pointer;
            background: rgba(255,255,255,0.03);
            user-select: none; transition: background 0.15s;
        }
        #settings-panel summary:hover { background: rgba(255,255,255,0.06); }
        #settings-panel details .details-body {
            padding: 10px 12px; display: flex; flex-direction: column; gap: 10px;
        }
        /* Settings sticky footer */
        .settings-footer {
            position: sticky; bottom: 0;
            background: linear-gradient(transparent, var(--bg-primary) 40%);
            padding: 12px 0 4px; margin-top: 4px;
            display: flex; flex-direction: column; gap: 8px;
            z-index: 5;
        }
        .chat-sidebar-toggle {
            position: absolute; right: 16px; top: 8px;
            background: none; border: 1px solid var(--glass-border);
            border-radius: 8px; color: var(--text-muted); padding: 4px 10px;
            cursor: pointer; font-size: 0.78rem; transition: all 0.2s;
        }
        .chat-sidebar-toggle:hover { color: var(--text-primary); background: var(--glass-bg); }
        .chat-field-label { font-size: 0.78rem; color: var(--text-muted); margin-bottom: 4px; }
        .chat-field-input {
            width: 100%; background: rgba(255,255,255,0.05); border: 1px solid var(--glass-border);
            border-radius: 8px; padding: 8px 10px; color: var(--text-primary);
            font-size: 0.85rem; font-family: inherit; outline: none; transition: border-color 0.2s;
            box-sizing: border-box;
        }
        .chat-field-input:focus { border-color: var(--accent-purple); }
        .chat-field-input option { background: #1a0533; }
        .chat-save-btn {
            width: 100%; padding: 8px; border-radius: 8px;
            background: rgba(167,139,250,0.15); border: 1px solid rgba(167,139,250,0.3);
            color: var(--accent-purple); cursor: pointer; font-size: 0.85rem; font-weight: 600;
            transition: all 0.2s;
        }
        .chat-save-btn:hover { background: rgba(167,139,250,0.25); }
        .chat-clear-btn {
            width: 100%; padding: 7px; border-radius: 8px;
            background: rgba(248,113,113,0.08); border: 1px solid rgba(248,113,113,0.2);
            color: var(--accent-red); cursor: pointer; font-size: 0.82rem;
            transition: all 0.2s;
        }
        .chat-clear-btn:hover { background: rgba(248,113,113,0.15); }
        #chat-status { font-size: 0.75rem; color: var(--text-muted); padding: 4px 16px; min-height: 20px; }
        .chat-welcome {
            flex: 1; display: flex; flex-direction: column; align-items: center;
            justify-content: center; gap: 12px; color: var(--text-muted); text-align: center;
            padding: 40px;
        }
        .chat-welcome-icon { font-size: 3rem; opacity: 0.5; }
        .chat-welcome p { font-size: 0.9rem; max-width: 300px; }
        /* Memory activity panel */
        #memory-panel {
            width: 260px; flex-shrink: 0; display: flex; flex-direction: column; gap: 10px;
            overflow-y: auto; padding: 14px;
            background: rgba(255,255,255,0.03); border-right: 1px solid var(--glass-border);
        }
        .memory-panel-title {
            font-size: 0.82rem; font-weight: 600; color: var(--text-secondary); margin-bottom: 4px;
        }
        .memory-section-header {
            font-size: 0.75rem; font-weight: 600; color: var(--text-muted);
            text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 6px;
            padding-bottom: 4px; border-bottom: 1px solid rgba(255,255,255,0.06);
        }
        .memory-item-card {
            background: rgba(255,255,255,0.04); border: 1px solid var(--glass-border);
            border-radius: 8px; padding: 7px 9px; font-size: 0.74rem;
            color: var(--text-secondary); line-height: 1.4; margin-bottom: 5px;
            word-break: break-word; cursor: pointer; transition: all 0.2s;
        }
        .memory-item-card:hover { background: rgba(255,255,255,0.07); border-color: rgba(167,139,250,0.25); }
        .memory-item-card .mem-score {
            font-size: 0.68rem; color: var(--accent-purple); margin-bottom: 3px;
            font-weight: 600;
        }
        .memory-item-card .mem-actions {
            display: flex; gap: 4px; margin-top: 4px; opacity: 0; transition: opacity 0.2s;
        }
        .memory-item-card:hover .mem-actions { opacity: 1; }
        .mem-action-btn {
            background: none; border: 1px solid var(--glass-border); border-radius: 4px;
            color: var(--text-muted); padding: 1px 5px; font-size: 0.64rem;
            cursor: pointer; transition: all 0.15s;
        }
        .mem-action-btn:hover { color: var(--text-primary); background: var(--glass-bg); }
        .mem-action-btn.done:hover { color: var(--accent-green); border-color: rgba(52,211,153,0.4); }
        .mem-action-btn.del:hover { color: var(--accent-red); border-color: rgba(248,113,113,0.4); }
        /* Memory edit modal */
        #mem-edit-overlay {
            position: fixed; inset: 0; background: rgba(0,0,0,0.6); z-index: 2000;
            display: none; align-items: center; justify-content: center;
        }
        #mem-edit-overlay.show { display: flex; }
        #mem-edit-modal {
            background: var(--bg-primary); border: 1px solid var(--glass-border);
            border-radius: 12px; padding: 20px; width: 400px; max-width: 90vw;
            display: flex; flex-direction: column; gap: 10px;
        }
        #mem-edit-modal .mem-edit-label { font-size: 0.78rem; color: var(--text-muted); }
        #mem-edit-modal textarea, #mem-edit-modal input {
            width: 100%; background: rgba(255,255,255,0.05); border: 1px solid var(--glass-border);
            border-radius: 8px; padding: 8px 10px; color: var(--text-primary);
            font-size: 0.85rem; font-family: inherit; outline: none; box-sizing: border-box;
        }
        #mem-edit-modal textarea { min-height: 80px; resize: vertical; }
        .memory-empty { font-size: 0.74rem; color: var(--text-muted); font-style: italic; padding: 4px 0; }
        .reflection-insight {
            background: rgba(167,139,250,0.08); border: 1px solid rgba(167,139,250,0.2);
            border-radius: 8px; padding: 7px 9px; font-size: 0.74rem;
            color: var(--text-secondary); line-height: 1.4; margin-bottom: 5px;
        }
        .memory-panel-section { margin-bottom: 12px; }
        .mem-panel-toggle {
            background: none; border: 1px solid var(--glass-border); border-radius: 6px;
            color: var(--text-muted); padding: 2px 7px; font-size: 0.7rem;
            cursor: pointer; transition: all 0.2s; margin-left: 6px;
        }
        .mem-panel-toggle:hover { color: var(--text-primary); background: var(--glass-bg); }
        @media (max-width: 900px) {
            #memory-panel { display: none; }
        }
        @media (max-width: 768px) {
            #chat-layout { flex-direction: column; height: auto; }
            #chat-messages { min-height: 350px; max-height: 50vh; }
            #settings-panel { width: 100% !important; }
            #memory-panel { display: none; }
        }
        #chat-cancel-btn {
            background: rgba(248,113,113,0.12); border: 1px solid rgba(248,113,113,0.3);
            border-radius: 8px; color: var(--accent-red); padding: 8px 14px;
            cursor: pointer; font-size: 0.85rem; font-weight: 600; transition: all 0.2s;
        }
        #chat-cancel-btn:hover { background: rgba(248,113,113,0.22); }
        /* Attachment area */
        #chat-attachments {
            display: flex; flex-wrap: wrap; gap: 6px; padding: 6px 16px 0;
            min-height: 0; border-top: 0;
        }
        #chat-attachments:empty { display: none; }
        .chat-attachment-badge {
            display: flex; align-items: center; gap: 5px;
            background: rgba(255,255,255,0.07); border: 1px solid var(--glass-border);
            border-radius: 8px; padding: 4px 8px; font-size: 0.78rem; color: var(--text-secondary);
            max-width: 180px; cursor: default;
        }
        .chat-attachment-badge img.thumb {
            width: 36px; height: 36px; object-fit: cover; border-radius: 4px; cursor: pointer;
            flex-shrink: 0;
        }
        .chat-attachment-badge video.thumb {
            width: 36px; height: 36px; object-fit: cover; border-radius: 4px; cursor: pointer;
            flex-shrink: 0;
        }
        .chat-attachment-badge .attach-name {
            overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1;
        }
        .chat-attachment-badge .attach-remove {
            background: none; border: none; color: var(--text-muted); cursor: pointer;
            font-size: 0.85rem; padding: 0 2px; line-height: 1; flex-shrink: 0;
        }
        .chat-attachment-badge .attach-remove:hover { color: var(--accent-red); }
        #chat-input.dragover {
            border-color: var(--accent-purple); background: rgba(167,139,250,0.08);
        }
        /* Media viewer overlay */
        #media-viewer-overlay {
            display: none; position: fixed; inset: 0; z-index: 9500;
            background: rgba(0,0,0,0.85); backdrop-filter: blur(6px);
            align-items: center; justify-content: center; cursor: pointer;
        }
        #media-viewer-overlay.visible { display: flex; }
        #media-viewer-inner { max-width: 90vw; max-height: 90vh; }
        #media-viewer-inner img { max-width: 90vw; max-height: 90vh; border-radius: 8px; object-fit: contain; }
        #media-viewer-inner video { max-width: 90vw; max-height: 90vh; border-radius: 8px; }
        /* Chat bubble markdown styles */
        .chat-bubble h1,.chat-bubble h2,.chat-bubble h3,.chat-bubble h4 {
            font-weight:700; margin:0.5em 0 0.25em; line-height:1.3;
        }
        .chat-bubble h1 { font-size:1.1em; }
        .chat-bubble h2 { font-size:1.0em; }
        .chat-bubble h3,.chat-bubble h4 { font-size:0.95em; }
        .chat-bubble p { margin:0.3em 0; }
        .chat-bubble ul,.chat-bubble ol { margin:0.3em 0; padding-left:1.4em; }
        .chat-bubble li { margin:0.1em 0; }
        .chat-bubble code { background:rgba(0,0,0,0.3); border-radius:3px; padding:0.1em 0.3em; font-size:0.85em; font-family:monospace; }
        .chat-bubble pre { background:rgba(0,0,0,0.3); border-radius:6px; padding:8px 10px; overflow-x:auto; margin:0.4em 0; }
        .chat-bubble pre code { background:none; padding:0; }
        .chat-bubble blockquote { border-left:3px solid var(--accent-purple); padding-left:8px; margin:0.3em 0; opacity:0.8; }
        .chat-bubble a { color:var(--accent-blue); text-decoration:underline; }
        /* Code block Run button styles */
        .hljs-block-wrapper {
            position: relative; margin: 0.5em 0; border-radius: 8px; overflow: hidden;
            border: 1px solid rgba(255,255,255,0.1);
        }
        .hljs-block-header {
            display: flex; align-items: center; justify-content: space-between;
            padding: 4px 8px; background: rgba(0,0,0,0.3); font-size: 0.72rem;
            border-bottom: 1px solid rgba(255,255,255,0.08);
        }
        .hljs-lang-badge {
            color: rgba(96,165,250,0.8); font-family: monospace; font-weight: 600;
        }
        .hljs-block-actions { display: flex; gap: 4px; }
        .hljs-copy-btn, .hljs-run-btn {
            background: none; border: 1px solid rgba(255,255,255,0.15);
            border-radius: 4px; color: var(--text-muted); padding: 2px 7px;
            font-size: 0.68rem; cursor: pointer; transition: all 0.15s;
        }
        .hljs-copy-btn:hover { border-color: rgba(255,255,255,0.35); color: var(--text-primary); }
        .hljs-run-btn { border-color: rgba(52,211,153,0.3); color: rgba(52,211,153,0.8); }
        .hljs-run-btn:hover { border-color: rgba(52,211,153,0.7); background: rgba(52,211,153,0.08); color: rgba(52,211,153,1); }
        .hljs-run-btn:disabled { opacity: 0.4; cursor: not-allowed; }
        .hljs-run-result {
            padding: 6px 10px; background: rgba(0,0,0,0.4); font-size: 0.76rem;
            font-family: monospace; white-space: pre-wrap; word-break: break-all;
            border-top: 1px solid rgba(255,255,255,0.06); max-height: 200px; overflow-y: auto;
        }
        .hljs-run-result.stdout { color: #85e89d; }
        .hljs-run-result.stderr { color: #f97583; }
        .hljs-run-result.running { color: rgba(96,165,250,0.7); font-style: italic; }
        .hljs-artifact-img {
            display: block; max-width: 100%; border-top: 1px solid rgba(255,255,255,0.06);
            cursor: pointer;
        }
        /* Sandbox toggle button */
        #sandbox-toggle-btn {
            background: rgba(96,165,250,0.1); border: 1px solid rgba(96,165,250,0.3);
            border-radius: 8px; color: rgba(96,165,250,0.8);
            padding: 4px 10px; font-size: 0.75rem; cursor: pointer; transition: all 0.2s;
        }
        #sandbox-toggle-btn:hover { background: rgba(96,165,250,0.2); }
        #sandbox-toggle-btn.active { background: rgba(96,165,250,0.2); color: rgba(96,165,250,1); }
        </style>
        <!-- ========== CHAT TAB ========== -->
        <section id="tab-chat" class="tab-panel" role="tabpanel">
            <div style="position:relative; margin-bottom:12px; display:flex; align-items:center; justify-content:space-between;">
                <h2 style="font-size:1.1rem; font-weight:600; color:var(--text-primary);">💬 Chat</h2>
                <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
                    <button class="mem-panel-toggle" id="memory-panel-toggle-btn" onclick="toggleMemoryPanel()" title="記憶パネルを開閉">🧠</button>
                    <button id="sandbox-toggle-btn" onclick="openCodingAgent()" title="Coding Agent を開く">🔬 Code</button>
                    <button class="chat-sidebar-toggle" onclick="toggleSettingsPanel()" id="chat-sidebar-toggle-btn" title="設定パネルを開閉">⚙️ 設定</button>
                </div>
            </div>
            <div id="chat-layout" class="glass" style="padding:0; overflow:hidden;">
                <!-- Memory activity panel (left) -->
                <div id="memory-panel">
                    <div class="memory-panel-title">🧠 記憶活動</div>

                    <!-- Retrieved memories -->
                    <div class="memory-panel-section">
                        <div class="memory-section-header">📥 取得された記憶</div>
                        <div id="memory-retrieved-list">
                            <div class="memory-empty">チャット中に自動更新されます</div>
                        </div>
                    </div>

                    <!-- Saved memories -->
                    <div class="memory-panel-section">
                        <div class="memory-section-header">💾 保存された記憶</div>
                        <div id="memory-saved-list">
                            <div class="memory-empty">チャット中に自動更新されます</div>
                        </div>
                    </div>

                    <!-- Reflection -->
                    <div class="memory-panel-section">
                        <div class="memory-section-header" id="reflection-header">✨ リフレクション</div>
                        <div id="memory-reflection-list">
                            <div class="memory-empty">リフレクション洞察がここに表示されます</div>
                        </div>
                    </div>

                    <!-- Active goals -->
                    <div class="memory-panel-section">
                        <div class="memory-section-header">🎯 アクティブな目標</div>
                        <div id="memory-goals-list">
                            <div class="memory-empty">チャット中に自動更新されます</div>
                        </div>
                    </div>

                    <!-- Active promises -->
                    <div class="memory-panel-section">
                        <div class="memory-section-header">🤝 アクティブな約束</div>
                        <div id="memory-promises-list">
                            <div class="memory-empty">チャット中に自動更新されます</div>
                        </div>
                    </div>

                    <!-- Memory operation log -->
                    <div class="memory-panel-section">
                        <div class="memory-section-header">🔧 操作ログ</div>
                        <div id="memory-tool-ops-list">
                            <div class="memory-empty">LLMの記憶操作がここに表示されます</div>
                        </div>
                    </div>

                    <!-- Equipment -->
                    <div class="memory-panel-section">
                        <div class="memory-section-header">🎒 装備</div>
                        <div id="memory-equipment-list">
                            <div class="memory-empty">装備情報がここに表示されます</div>
                        </div>
                    </div>
                </div>

                <!-- Chat area -->
                <div id="chat-main">
                    <div id="chat-messages">
                        <div class="chat-welcome" id="chat-welcome">
                            <div class="chat-welcome-icon">💬</div>
                            <p>チャットを開始するには下のテキストボックスにメッセージを入力してください。</p>
                            <p style="font-size:0.78rem; opacity:0.7;">右の設定パネルでAPIキーとプロバイダーを設定してください。</p>
                        </div>
                    </div>
                    <div id="chat-status"></div>
                    <div id="chat-attachments"></div>
                    <div id="chat-input-area">
                        <textarea id="chat-input" placeholder="メッセージを入力... (Shift+Enter で改行、Enter で送信、ファイルドロップ可)" rows="1"></textarea>
                        <div style="display:flex;align-items:center;gap:6px;flex-shrink:0;">
                            <button id="chat-voice-btn" onclick="toggleVoiceInput()" title="音声入力" style="background:none;border:1px solid var(--glass-border);border-radius:6px;color:var(--text-muted);padding:3px 8px;font-size:0.85rem;cursor:pointer;white-space:nowrap;">🎤</button>
                            <label id="chat-web-search-label" style="display:flex;align-items:center;gap:4px;font-size:0.72rem;color:var(--text-muted);cursor:pointer;white-space:nowrap;">
                                <input type="checkbox" id="chat-web-search" style="width:14px;height:14px;accent-color:var(--accent-blue);cursor:pointer;" />🌐 Web検索
                            </label>
                            <button id="chat-export-btn" onclick="exportChatHistory()" title="会話をエクスポート" style="background:none;border:1px solid var(--glass-border);border-radius:6px;color:var(--text-muted);padding:3px 8px;font-size:0.72rem;cursor:pointer;white-space:nowrap;">📥 Export</button>
                        </div>
                        <button id="chat-cancel-btn" onclick="chatCancel()" style="display:none;">⏹ 中止</button>
                        <button id="chat-send-btn" onclick="chatSend()">送信 ↑</button>
                    </div>
                </div>
                <!-- Settings sidebar -->
                <div id="settings-panel" class="glass" style="margin:0; border-radius:0; border-left:1px solid var(--glass-border); padding:16px; gap:8px; display:flex; flex-direction:column;">
                    <div style="font-size:0.85rem; font-weight:600; color:var(--text-primary); margin-bottom:4px;">⚙️ チャット設定</div>
                    <!-- Provider / Model / API -->
                    <details open>
                        <summary>🔧 基本設定</summary>
                        <div class="details-body">
                            <div>
                                <div class="chat-field-label">プロバイダー</div>
                                <select id="chat-provider" class="chat-field-input" onchange="onChatProviderChange()">
                                    <option value="anthropic">Anthropic (Claude)</option>
                                    <option value="openai">OpenAI</option>
                                    <option value="openrouter">OpenRouter</option>
                                </select>
                            </div>
                            <div>
                                <div class="chat-field-label">モデル <span style="color:var(--accent-blue);font-size:0.7rem;">（空白でデフォルト）</span></div>
                                <input type="text" id="chat-model" class="chat-field-input" placeholder="例: claude-opus-4-5" />
                            </div>
                            <div>
                                <div class="chat-field-label">APIキー</div>
                                <input type="password" id="chat-api-key" class="chat-field-input" placeholder="sk-..." autocomplete="off" />
                            </div>
                            <div id="chat-base-url-row">
                                <div class="chat-field-label">Base URL <span style="color:var(--text-muted);font-size:0.7rem;">（任意）</span></div>
                                <input type="text" id="chat-base-url" class="chat-field-input" placeholder="https://openrouter.ai/api/v1" />
                            </div>
                            <div>
                                <div class="chat-field-label" style="display:flex;justify-content:space-between;">
                                    <span>Temperature</span>
                                    <span id="chat-temp-val" style="color:var(--accent-purple);">0.7</span>
                                </div>
                                <input type="range" id="chat-temperature" min="0" max="2" step="0.05" value="0.7"
                                    oninput="document.getElementById('chat-temp-val').textContent=parseFloat(this.value).toFixed(2)"
                                    style="width:100%;accent-color:var(--accent-purple);" />
                            </div>
                            <div>
                                <div class="chat-field-label">Max Tokens</div>
                                <input type="number" id="chat-max-tokens" class="chat-field-input" min="1" max="32768" value="2048" />
                            </div>
                        </div>
                    </details>
                    <!-- Context & System Prompt -->
                    <details>
                        <summary>💬 コンテキスト</summary>
                        <div class="details-body">
                            <div>
                                <div class="chat-field-label">コンテキスト履歴 (turns)</div>
                                <input type="number" id="chat-window-turns" class="chat-field-input" min="1" max="50" value="3" />
                            </div>
                            <div>
                                <div class="chat-field-label">表示履歴 (turns) <span style="color:var(--text-muted);font-size:0.7rem;">（ページロード時に遡る件数）</span></div>
                                <input type="number" id="chat-display-history-turns" class="chat-field-input" min="1" max="200" value="20" />
                            </div>
                            <div>
                                <div class="chat-field-label">最大ツール呼び出し回数</div>
                                <input type="number" id="chat-max-tool-calls" class="chat-field-input" min="0" max="20" value="5" />
                            </div>
                            <div style="flex:1; display:flex; flex-direction:column; min-height:80px;">
                                <div class="chat-field-label">システムプロンプト</div>
                                <textarea id="chat-system-prompt" class="chat-field-input" rows="4"
                                    placeholder="（空白でデフォルト: ペルソナ名のアシスタント）"
                                    style="flex:1;resize:vertical;min-height:70px;max-height:300px;overflow-y:auto;"></textarea>
                            </div>
                        </div>
                    </details>
                    <!-- Memory extraction -->
                    <details>
                        <summary>🧠 記憶・抽出</summary>
                        <div class="details-body">
                            <div style="display:flex;align-items:center;gap:8px;">
                                <input type="checkbox" id="chat-auto-extract" checked
                                    style="width:15px;height:15px;accent-color:var(--accent-purple);cursor:pointer;" />
                                <label for="chat-auto-extract" class="chat-field-label" style="margin:0;cursor:pointer;">ターン毎に記憶を自動抽出 (Mem0方式)</label>
                            </div>
                            <div>
                                <div class="chat-field-label">抽出モデル <span style="color:var(--text-muted);font-size:0.7rem;">（空白でチャットと同モデル）</span></div>
                                <input type="text" id="chat-extract-model" class="chat-field-input"
                                    placeholder="例: claude-haiku-4-5, gpt-4o-mini" />
                            </div>
                            <div>
                                <div class="chat-field-label">抽出 Max Tokens</div>
                                <input type="number" id="chat-extract-max-tokens" class="chat-field-input" min="64" max="2048" value="512" />
                            </div>
                            <div style="display:flex;align-items:center;gap:8px;">
                                <input type="checkbox" id="chat-enable-memory-tools" checked
                                    style="width:15px;height:15px;accent-color:var(--accent-purple);cursor:pointer;" />
                                <label for="chat-enable-memory-tools" class="chat-field-label" style="margin:0;cursor:pointer;">LLMに組み込みメモリツールを渡す</label>
                            </div>
                        </div>
                    </details>
                    <!-- MCP Servers -->
                    <details>
                        <summary>🔌 MCPサーバー</summary>
                        <div class="details-body" id="chat-mcp-section">
                            <div>
                                <div style="font-size:0.72rem;color:var(--text-muted);margin-bottom:4px;">Claude の mcp.json 形式で貼り付け・編集できます</div>
                                <textarea id="chat-mcp-json" class="chat-field-input" rows="6"
                                    style="resize:vertical;min-height:100px;font-family:monospace;font-size:0.73rem;line-height:1.45;"
                                    placeholder='{&#10;  "mcpServers": {&#10;    "my-server": {&#10;      "command": "npx",&#10;      "args": ["-y", "@modelcontextprotocol/server-filesystem"]&#10;    }&#10;  }&#10;}'></textarea>
                                <div id="chat-mcp-json-error" style="font-size:0.72rem;color:var(--accent-red);margin-top:3px;display:none;"></div>
                            </div>
                            <div>
                                <div class="chat-field-label" style="display:flex;justify-content:space-between;">
                                    <span>ツール結果最大文字数</span>
                                    <span id="chat-tool-max-val" style="color:var(--accent-purple);">4000</span>
                                </div>
                                <input type="range" id="chat-tool-result-max" min="500" max="20000" step="500" value="4000"
                                    oninput="document.getElementById('chat-tool-max-val').textContent=this.value"
                                    style="width:100%;accent-color:var(--accent-purple);" />
                            </div>
                        </div>
                    </details>
                    <!-- Skills -->
                    <details>
                        <summary>🎯 Skills</summary>
                        <div class="details-body" id="chat-skills-section">
                            <div id="chat-skills-list" style="display:flex;flex-direction:column;gap:4px;"></div>
                        </div>
                    </details>
                    <!-- Reflection -->
                    <details>
                        <summary>🔮 リフレクション</summary>
                        <div class="details-body">
                            <div style="display:flex;align-items:center;gap:8px;">
                                <input type="checkbox" id="chat-reflection-enabled" checked
                                    style="width:15px;height:15px;accent-color:var(--accent-purple);cursor:pointer;" />
                                <label for="chat-reflection-enabled" class="chat-field-label" style="margin:0;cursor:pointer;">リフレクション有効</label>
                            </div>
                            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
                                <div>
                                    <div class="chat-field-label">閾値</div>
                                    <input type="number" id="chat-reflection-threshold" class="chat-field-input"
                                        min="0.1" max="100" step="0.1" value="1.0" />
                                </div>
                                <div>
                                    <div class="chat-field-label">最小間隔 (時間)</div>
                                    <input type="number" id="chat-reflection-interval" class="chat-field-input"
                                        min="0" max="168" step="0.5" value="1.0" />
                                </div>
                            </div>
                            <div style="display:flex;align-items:center;gap:8px;">
                                <input type="checkbox" id="chat-session-summarize" checked
                                    style="width:15px;height:15px;accent-color:var(--accent-purple);cursor:pointer;" />
                                <label for="chat-session-summarize" class="chat-field-label" style="margin:0;cursor:pointer;">セッション要約</label>
                            </div>
                        </div>
                    </details>
                    <!-- Mental Model -->
                    <details>
                        <summary>🧩 メンタルモデル</summary>
                        <div class="details-body">
                            <div style="display:flex;align-items:center;gap:8px;">
                                <input type="checkbox" id="chat-mental-model-enabled" checked
                                    style="width:15px;height:15px;accent-color:var(--accent-purple);cursor:pointer;" />
                                <label for="chat-mental-model-enabled" class="chat-field-label" style="margin:0;cursor:pointer;">メンタルモデル抽出を有効</label>
                            </div>
                            <div>
                                <div class="chat-field-label">最小サンプル数</div>
                                <input type="number" id="chat-mental-model-min-samples" class="chat-field-input"
                                    min="1" max="20" value="3" />
                            </div>
                        </div>
                    </details>
                    <!-- Retrieval weights -->
                    <details>
                        <summary>⚖️ 検索重み</summary>
                        <div class="details-body">
                            <div>
                                <div class="chat-field-label" style="display:flex;justify-content:space-between;">
                                    <span>鮮度</span>
                                    <span id="chat-recency-weight-val" style="color:var(--accent-purple);">0.30</span>
                                </div>
                                <input type="range" id="chat-recency-weight" min="0" max="1" step="0.05" value="0.3"
                                    oninput="document.getElementById('chat-recency-weight-val').textContent=parseFloat(this.value).toFixed(2)"
                                    style="width:100%;accent-color:var(--accent-purple);" />
                            </div>
                            <div>
                                <div class="chat-field-label" style="display:flex;justify-content:space-between;">
                                    <span>重要度</span>
                                    <span id="chat-importance-weight-val" style="color:var(--accent-purple);">0.30</span>
                                </div>
                                <input type="range" id="chat-importance-weight" min="0" max="1" step="0.05" value="0.3"
                                    oninput="document.getElementById('chat-importance-weight-val').textContent=parseFloat(this.value).toFixed(2)"
                                    style="width:100%;accent-color:var(--accent-purple);" />
                            </div>
                            <div>
                                <div class="chat-field-label" style="display:flex;justify-content:space-between;">
                                    <span>関連性</span>
                                    <span id="chat-relevance-weight-val" style="color:var(--accent-purple);">0.40</span>
                                </div>
                                <input type="range" id="chat-relevance-weight" min="0" max="1" step="0.05" value="0.4"
                                    oninput="document.getElementById('chat-relevance-weight-val').textContent=parseFloat(this.value).toFixed(2)"
                                    style="width:100%;accent-color:var(--accent-purple);" />
                            </div>
                        </div>
                    </details>
                    <!-- Housekeeping & Other -->
                    <details>
                        <summary>🧹 整理・その他</summary>
                        <div class="details-body">
                            <div>
                                <div class="chat-field-label">自動整理 閾値 (goals+promises 合計がこの数を超えたら実行)</div>
                                <input type="number" id="chat-housekeeping-threshold" class="chat-field-input" min="1" max="100" value="10" />
                            </div>
                            <button class="chat-clear-btn" style="margin-top:4px;" onclick="runHousekeeping()">🧹 今すぐ整理</button>
                            <div id="chat-housekeeping-status" style="font-size:0.75rem; text-align:center; min-height:16px;"></div>
                            <div style="border-top:1px solid var(--glass-border);padding-top:8px;display:flex;align-items:center;gap:8px;">
                                <input type="checkbox" id="chat-sandbox-enabled"
                                    style="width:15px;height:15px;accent-color:var(--accent-blue);cursor:pointer;"
                                    onchange="onSandboxEnabledChange()" />
                                <label for="chat-sandbox-enabled" class="chat-field-label" style="margin:0;cursor:pointer;">コード実行 (Dockerサンドボックス)</label>
                            </div>
                            <div style="display:flex;align-items:center;gap:8px;">
                                <input type="checkbox" id="chat-debug-mode"
                                    style="width:15px;height:15px;accent-color:var(--accent-purple);cursor:pointer;" />
                                <label for="chat-debug-mode" class="chat-field-label" style="margin:0;cursor:pointer;">🐛 デバッグモード</label>
                            </div>
                        </div>
                    </details>
                    <!-- Sticky footer buttons -->
                    <div class="settings-footer">
                        <button class="chat-save-btn" onclick="saveChatConfig()">💾 設定を保存</button>
                        <button class="chat-clear-btn" onclick="clearChatHistory()">🗑️ 会話をリセット</button>
                        <div id="chat-config-status" style="font-size:0.75rem; text-align:center; min-height:16px;"></div>
                    </div>
                </div>
            </div>
            <!-- highlight.js for syntax highlighting in chat bubbles -->
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github-dark.min.css">
            <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js" crossorigin="anonymous"></script>
            <!-- Media viewer overlay -->
            <div id="media-viewer-overlay" onclick="closeMediaViewer()">
                <div id="media-viewer-inner" onclick="event.stopPropagation()"></div>
            </div>
            <!-- Memory edit modal -->
            <div id="mem-edit-overlay" onclick="closeMemEdit()">
                <div id="mem-edit-modal" onclick="event.stopPropagation()">
                    <div style="font-size:0.85rem;font-weight:600;color:var(--text-primary);">メモリ編集</div>
                    <div>
                        <div class="mem-edit-label">内容</div>
                        <textarea id="mem-edit-content"></textarea>
                    </div>
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
                        <div>
                            <div class="mem-edit-label">重要度 (0.0-1.0)</div>
                            <input type="number" id="mem-edit-importance" min="0" max="1" step="0.05" value="0.5" />
                        </div>
                        <div>
                            <div class="mem-edit-label">タグ (カンマ区切り)</div>
                            <input type="text" id="mem-edit-tags" placeholder="goal, active" />
                        </div>
                    </div>
                    <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:4px;">
                        <button class="chat-clear-btn" style="width:auto;padding:6px 14px;" onclick="deleteMemCard()">削除</button>
                        <button class="chat-save-btn" style="width:auto;padding:6px 14px;" onclick="saveMemEdit()">保存</button>
                    </div>
                </div>
            </div>
        </section>""" + render_coding_agent_panel()


def render_chat_js() -> str:
    """Return the JavaScript for the chat tab."""
    return r"""
/* =================================================================
   CHAT TAB
   ================================================================= */
const CHAT = {
    streaming: false,
    sidebarOpen: true,
    memoryPanelOpen: true,
    messages: [],  // { role, content, time }
    mcpServers: [],
    enabledSkills: [],
    abortController: null,  // F4: AbortController for streaming cancel
    attachments: [],  // { filename, url, workspace_path, mime_type, size }
};

function loadChat() {
    if (!S.persona) return;
    loadChatConfig();
    loadSkillsForChat();
    restoreChatHistory();
    loadChatCommitments();
}

async function loadChatCommitments() {
    if (!S.persona) return;
    try {
        const data = await api('/api/chat/' + encodeURIComponent(S.persona) + '/commitments');
        if (Array.isArray(data.goals) || Array.isArray(data.promises)) {
            updateMemoryPanel(undefined, undefined, data.goals || [], data.promises || []);
        }
        if (data.insights && data.insights.length > 0) {
            updateReflectionPanel(data.insights);
        }
    } catch (_e) {
        // commitments API unavailable — ignore silently
    }
}

async function loadSkillsForChat() {
    try {
        const skills = await api('/api/skills');
        renderSkillsList(skills, CHAT.enabledSkills);
    } catch (_e) {
        // skills API not available yet, ignore
    }
}

async function loadChatConfig() {
    try {
        const cfg = await api('/api/chat/' + encodeURIComponent(S.persona) + '/config');
        applyChatConfig(cfg);
    } catch (e) {
        document.getElementById('chat-config-status').textContent = '設定読込失敗: ' + e.message;
    }
}

function applyChatConfig(cfg) {
    if (!cfg) return;
    const set = (id, v) => { const el = document.getElementById(id); if (el && v !== undefined && v !== null) el.value = v; };
    const setChecked = (id, v) => { const el = document.getElementById(id); if (el) el.checked = v === true; };
    set('chat-provider', cfg.provider);
    set('chat-model', cfg.model || '');
    set('chat-api-key', cfg.api_key || '');
    set('chat-base-url', cfg.base_url || '');
    set('chat-temperature', cfg.temperature != null ? cfg.temperature : 0.7);
    set('chat-max-tokens', cfg.max_tokens || 2048);
    set('chat-window-turns', cfg.max_window_turns || 3);
    set('chat-max-tool-calls', cfg.max_tool_calls || 5);
    set('chat-system-prompt', cfg.system_prompt || '');
    setChecked('chat-auto-extract', cfg.auto_extract !== false);
    set('chat-extract-model', cfg.extract_model || '');
    set('chat-extract-max-tokens', cfg.extract_max_tokens || 512);
    setChecked('chat-enable-memory-tools', cfg.enable_memory_tools !== false);
    // Temperature display sync
    const tempEl = document.getElementById('chat-temp-val');
    const tempSlider = document.getElementById('chat-temperature');
    if (tempEl && tempSlider) {
        tempEl.textContent = parseFloat(tempSlider.value).toFixed(2);
    }
    onChatProviderChange();
    CHAT.mcpServers = cfg.mcp_servers || [];
    renderMcpJson(CHAT.mcpServers);
    const toolMax = document.getElementById('chat-tool-result-max');
    const toolMaxVal = document.getElementById('chat-tool-max-val');
    if (toolMax && cfg.tool_result_max_chars) {
        toolMax.value = cfg.tool_result_max_chars;
        if (toolMaxVal) toolMaxVal.textContent = cfg.tool_result_max_chars;
    }
    CHAT.enabledSkills = cfg.enabled_skills || [];
    // Reflection settings
    setChecked('chat-reflection-enabled', cfg.reflection_enabled !== false);
    set('chat-reflection-threshold', cfg.reflection_threshold != null ? cfg.reflection_threshold : 1.0);
    set('chat-reflection-interval', cfg.reflection_min_interval_hours != null ? cfg.reflection_min_interval_hours : 1.0);
    setChecked('chat-session-summarize', cfg.session_summarize !== false);
    // Mental model settings
    setChecked('chat-mental-model-enabled', cfg.mental_model_enabled !== false);
    set('chat-mental-model-min-samples', cfg.mental_model_min_samples != null ? cfg.mental_model_min_samples : 3);
    // Retrieval weights
    const setSlider = (id, valId, v) => {
        const el = document.getElementById(id);
        const vel = document.getElementById(valId);
        if (el && v != null) { el.value = v; if (vel) vel.textContent = parseFloat(v).toFixed(2); }
    };
    setSlider('chat-recency-weight', 'chat-recency-weight-val', cfg.retrieval_recency_weight != null ? cfg.retrieval_recency_weight : 0.3);
    setSlider('chat-importance-weight', 'chat-importance-weight-val', cfg.retrieval_importance_weight != null ? cfg.retrieval_importance_weight : 0.3);
    setSlider('chat-relevance-weight', 'chat-relevance-weight-val', cfg.retrieval_relevance_weight != null ? cfg.retrieval_relevance_weight : 0.4);
    // Housekeeping settings
    set('chat-display-history-turns', cfg.display_history_turns != null ? cfg.display_history_turns : 20);
    set('chat-housekeeping-threshold', cfg.housekeeping_threshold != null ? cfg.housekeeping_threshold : 10);
    // Sandbox settings
    setChecked('chat-sandbox-enabled', cfg.sandbox_enabled === true);
    onSandboxEnabledChange();
    // Debug mode
    setChecked('chat-debug-mode', cfg.debug_mode === true);
    const statusEl = document.getElementById('chat-config-status');
    if (statusEl) {
        if (cfg.is_configured) {
            statusEl.innerHTML = '<span style="color:var(--accent-green)">✓ APIキー設定済み</span>';
        } else {
            statusEl.innerHTML = '<span style="color:var(--accent-yellow)">⚠ APIキー未設定</span>';
        }
    }
}

function onChatProviderChange() {
    const provider = document.getElementById('chat-provider').value;
    const baseUrlRow = document.getElementById('chat-base-url-row');
    if (baseUrlRow) {
        baseUrlRow.style.display = (provider === 'openrouter' || provider === 'openai') ? '' : 'none';
    }
}

async function saveChatConfig() {
    if (!S.persona) { toast('ペルソナを選択してください', 'error'); return; }
    const apiKeyEl = document.getElementById('chat-api-key');
    const apiKeyVal = apiKeyEl ? apiKeyEl.value.trim() : '';
    const getChecked = (id) => document.getElementById(id)?.checked ?? false;
    const payload = {
        provider: document.getElementById('chat-provider').value,
        model: document.getElementById('chat-model').value.trim(),
        api_key: apiKeyVal,
        base_url: document.getElementById('chat-base-url').value.trim(),
        temperature: parseFloat(document.getElementById('chat-temperature').value),
        max_tokens: parseInt(document.getElementById('chat-max-tokens').value),
        max_window_turns: parseInt(document.getElementById('chat-window-turns').value),
        max_tool_calls: parseInt(document.getElementById('chat-max-tool-calls')?.value || '5'),
        system_prompt: document.getElementById('chat-system-prompt').value.trim(),
        auto_extract: getChecked('chat-auto-extract'),
        extract_model: document.getElementById('chat-extract-model')?.value.trim() || '',
        extract_max_tokens: parseInt(document.getElementById('chat-extract-max-tokens')?.value || '512'),
        enable_memory_tools: getChecked('chat-enable-memory-tools'),
        mcp_servers: parseMcpJson(),
        tool_result_max_chars: parseInt(document.getElementById('chat-tool-result-max')?.value || '4000'),
        enabled_skills: CHAT.enabledSkills,
        reflection_enabled: getChecked('chat-reflection-enabled'),
        reflection_threshold: parseFloat(document.getElementById('chat-reflection-threshold')?.value || '1.0'),
        reflection_min_interval_hours: parseFloat(document.getElementById('chat-reflection-interval')?.value || '1.0'),
        session_summarize: getChecked('chat-session-summarize'),
        retrieval_recency_weight: parseFloat(document.getElementById('chat-recency-weight')?.value || '0.3'),
        retrieval_importance_weight: parseFloat(document.getElementById('chat-importance-weight')?.value || '0.3'),
        retrieval_relevance_weight: parseFloat(document.getElementById('chat-relevance-weight')?.value || '0.4'),
        display_history_turns: parseInt(document.getElementById('chat-display-history-turns')?.value || '20'),
        housekeeping_threshold: parseInt(document.getElementById('chat-housekeeping-threshold')?.value || '10'),
        sandbox_enabled: getChecked('chat-sandbox-enabled'),
        mental_model_enabled: getChecked('chat-mental-model-enabled'),
        mental_model_min_samples: parseInt(document.getElementById('chat-mental-model-min-samples')?.value || '3'),
        debug_mode: getChecked('chat-debug-mode'),
    };
    try {
        const cfg = await api('/api/chat/' + encodeURIComponent(S.persona) + '/config', {
            method: 'POST',
            body: JSON.stringify(payload),
        });
        applyChatConfig(cfg);
        toast('チャット設定を保存しました', 'success');
    } catch (e) {
        toast('保存失敗: ' + e.message, 'error');
    }
}

function renderMcpJson(servers) {
    const ta = document.getElementById('chat-mcp-json');
    if (!ta) return;
    if (!servers || servers.length === 0) {
        ta.value = '{\n  "mcpServers": {}\n}';
        return;
    }
    const mcpServers = {};
    (servers || []).forEach(srv => {
        const entry = {};
        if (srv.transport === 'http') {
            entry.url = srv.url || '';
            if (srv.headers && Object.keys(srv.headers).length) entry.headers = srv.headers;
        } else {
            entry.command = srv.command || '';
            if (srv.args && srv.args.length) entry.args = srv.args;
            if (srv.headers && Object.keys(srv.headers).length) entry.env = srv.headers;
        }
        mcpServers[srv.name] = entry;
    });
    ta.value = JSON.stringify({ mcpServers }, null, 2);
}

function parseMcpJson() {
    const ta = document.getElementById('chat-mcp-json');
    const errEl = document.getElementById('chat-mcp-json-error');
    if (!ta) return CHAT.mcpServers;
    if (errEl) errEl.style.display = 'none';
    const raw = ta.value.trim();
    if (!raw || raw === '{\n  "mcpServers": {}\n}') return [];
    try {
        const parsed = JSON.parse(raw);
        const dict = parsed.mcpServers || {};
        return Object.entries(dict).map(([name, cfg]) => ({
            name,
            transport: cfg.url ? 'http' : 'stdio',
            url: cfg.url || '',
            command: cfg.command || '',
            args: cfg.args || [],
            headers: cfg.headers || cfg.env || {},
            enabled: true,
        }));
    } catch (e) {
        if (errEl) { errEl.textContent = 'JSON形式エラー: ' + e.message; errEl.style.display = ''; }
        return CHAT.mcpServers;
    }
}

function renderSkillsList(allSkills, enabledSkills) {
    const list = document.getElementById('chat-skills-list');
    if (!list) return;
    list.innerHTML = '';
    if (!allSkills || allSkills.length === 0) {
        list.innerHTML = '<div style="font-size:0.75rem;color:var(--text-muted);">スキルがありません</div>';
        return;
    }
    allSkills.forEach(skill => {
        const enabled = (enabledSkills || []).includes(skill.name);
        const item = document.createElement('div');
        item.style.cssText = 'display:flex;align-items:center;gap:8px;';
        const cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.checked = enabled;
        cb.id = 'skill-cb-' + skill.name;
        cb.style.cssText = 'width:14px;height:14px;accent-color:var(--accent-purple);cursor:pointer;';
        cb.addEventListener('change', () => {
            if (cb.checked) {
                if (!CHAT.enabledSkills.includes(skill.name)) CHAT.enabledSkills.push(skill.name);
            } else {
                CHAT.enabledSkills = CHAT.enabledSkills.filter(n => n !== skill.name);
            }
        });
        const label = document.createElement('label');
        label.htmlFor = cb.id;
        label.style.cssText = 'font-size:0.78rem;color:var(--text-secondary);cursor:pointer;';
        label.title = skill.description || '';
        label.textContent = skill.name;
        item.appendChild(cb);
        item.appendChild(label);
        list.appendChild(item);
    });
}

function toggleSettingsPanel() {
    const sidebar = document.getElementById('settings-panel');
    const btn = document.getElementById('chat-sidebar-toggle-btn');
    CHAT.sidebarOpen = !CHAT.sidebarOpen;
    if (CHAT.sidebarOpen) {
        sidebar.style.width = '280px';
        sidebar.style.overflow = 'auto';
        sidebar.style.padding = '16px';
        sidebar.style.display = 'flex';
        if (btn) btn.textContent = '⚙️ 設定';
    } else {
        sidebar.style.width = '0';
        sidebar.style.overflow = 'hidden';
        sidebar.style.padding = '0';
        if (btn) btn.textContent = '⚙️';
    }
}

function toggleMemoryPanel() {
    const panel = document.getElementById('memory-panel');
    CHAT.memoryPanelOpen = !CHAT.memoryPanelOpen;
    if (!panel) return;
    if (CHAT.memoryPanelOpen) {
        panel.style.display = 'flex';
    } else {
        panel.style.display = 'none';
    }
    document.querySelectorAll('.mem-panel-toggle').forEach(b => b.classList.toggle('active', CHAT.memoryPanelOpen));
}

function renderDebugPanel(anchorEl, data) {
    try {
        console.group('[debug_info]');
        const SECTIONS = ['system_prompt','context_summary','memories_raw','tool_calls','messages_sent','context_state','skills_raw'];
        for (const key of SECTIONS) {
            if (data[key] !== undefined && data[key] !== null) {
                console.debug(key + ':', data[key]);
            }
        }
        const extra = Object.fromEntries(Object.entries(data).filter(([k]) => !['type',...SECTIONS].includes(k)));
        if (Object.keys(extra).length) console.debug('extra:', extra);
        console.groupEnd();
    } catch (e) {
        console.error('[debug panel render error]', e);
    }
}

/* ── Memory Panel helpers ── */
function updateMemoryPanel(retrieved, saved, goals, promises) {
    const escAttr = (s) => String(s).replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    if (retrieved !== undefined) {
        const retrievedList = document.getElementById('memory-retrieved-list');
        if (retrievedList) {
            if (!retrieved || retrieved.length === 0) {
                retrievedList.innerHTML = '<div class="memory-empty">なし</div>';
            } else {
                retrievedList.innerHTML = retrieved.map(m => {
                    const score = m.score != null ? parseFloat(m.score).toFixed(3) : '';
                    const imp = m.importance != null ? parseFloat(m.importance).toFixed(2) : '';
                    const content = esc((m.content || '').substring(0, 80));
                    const meta = [score ? 'score:' + score : '', imp ? 'imp:' + imp : ''].filter(Boolean).join(' ');
                    const key = m.key || '';
                    return '<div class="memory-item-card" data-key="' + escAttr(key) + '" data-content="' + escAttr(m.content || '') + '" data-importance="' + (m.importance || 0.5) + '" data-tags="' + escAttr((m.tags || []).join(',')) + '" onclick="openMemEdit(this)">' +
                        (meta ? '<div class="mem-score">' + esc(meta) + '</div>' : '') +
                        content +
                        '<div class="mem-actions"><button class="mem-action-btn del" onclick="event.stopPropagation();deleteMemCard(\'' + escAttr(key) + '\')">削除</button></div>' +
                        '</div>';
                }).join('');
            }
        }
    }
    if (saved !== undefined) {
        const savedList = document.getElementById('memory-saved-list');
        if (savedList) {
            if (!saved || saved.length === 0) {
                savedList.innerHTML = '<div class="memory-empty">なし</div>';
            } else {
                savedList.innerHTML = saved.map(m => {
                    const content = esc((m.content || '').substring(0, 80));
                    const tags = m.tags ? m.tags.join(', ') : '';
                    const key = m.key || '';
                    return '<div class="memory-item-card" data-key="' + escAttr(key) + '" data-content="' + escAttr(m.content || '') + '" data-importance="' + (m.importance || 0.5) + '" data-tags="' + escAttr((m.tags || []).join(',')) + '" onclick="openMemEdit(this)">' + content +
                        (tags ? '<div class="mem-score">' + esc(tags) + '</div>' : '') +
                        '<div class="mem-actions"><button class="mem-action-btn del" onclick="event.stopPropagation();deleteMemCard(\'' + escAttr(key) + '\')">削除</button></div>' +
                        '</div>';
                }).join('');
            }
        }
    }
    if (goals !== undefined) {
        const goalsList = document.getElementById('memory-goals-list');
        if (goalsList) {
            if (!goals || goals.length === 0) {
                goalsList.innerHTML = '<div class="memory-empty">なし</div>';
            } else {
                goalsList.innerHTML = goals.map(g => {
                    const key = g.key || '';
                    return '<div class="memory-item-card" data-key="' + escAttr(key) + '" data-content="' + escAttr(g.content || '') + '" data-importance="' + (g.importance || 0.75) + '" data-tags="' + escAttr((g.tags || []).join(',')) + '" onclick="openMemEdit(this)">' +
                        '🎯 ' + esc((g.content || '').substring(0, 80)) +
                        '<div class="mem-actions"><button class="mem-action-btn done" onclick="event.stopPropagation();completeGoal(\'' + escAttr(key) + '\',\'' + escAttr((g.content || '').substring(0, 50)) + '\')">完了</button><button class="mem-action-btn del" onclick="event.stopPropagation();deleteMemCard(\'' + escAttr(key) + '\')">削除</button></div>' +
                        '</div>';
                }).join('');
            }
        }
    }
    if (promises !== undefined) {
        const promisesList = document.getElementById('memory-promises-list');
        if (promisesList) {
            if (!promises || promises.length === 0) {
                promisesList.innerHTML = '<div class="memory-empty">なし</div>';
            } else {
                promisesList.innerHTML = promises.map(p => {
                    const key = p.key || '';
                    return '<div class="memory-item-card" data-key="' + escAttr(key) + '" data-content="' + escAttr(p.content || '') + '" data-importance="' + (p.importance || 0.8) + '" data-tags="' + escAttr((p.tags || []).join(',')) + '" onclick="openMemEdit(this)">' +
                        '🤝 ' + esc((p.content || '').substring(0, 80)) +
                        '<div class="mem-actions"><button class="mem-action-btn done" onclick="event.stopPropagation();fulfillPromise(\'' + escAttr(key) + '\',\'' + escAttr((p.content || '').substring(0, 50)) + '\')">遂行</button><button class="mem-action-btn del" onclick="event.stopPropagation();deleteMemCard(\'' + escAttr(key) + '\')">削除</button></div>' +
                        '</div>';
                }).join('');
            }
        }
    }
}

function showReflectionStart() {
    const header = document.getElementById('reflection-header');
    if (header) header.textContent = '✨ リフレクション (実行中...)';
    const list = document.getElementById('memory-reflection-list');
    if (list) list.innerHTML = '<div class="memory-empty" style="color:var(--accent-purple);">分析中...</div>';
}

function updateReflectionPanel(insights) {
    const header = document.getElementById('reflection-header');
    if (header) header.textContent = '✨ リフレクション';
    const list = document.getElementById('memory-reflection-list');
    if (!list) return;
    if (!insights || insights.length === 0) {
        list.innerHTML = '<div class="memory-empty">洞察なし</div>';
        return;
    }
    list.innerHTML = insights.map(s =>
        '<div class="reflection-insight">' + esc(s) + '</div>'
    ).join('');
}

function showSessionSummarized(summary) {
    const statusEl = document.getElementById('chat-status');
    if (statusEl) {
        statusEl.textContent = '📝 セッションを要約しました';
        setTimeout(() => { if (statusEl) statusEl.textContent = ''; }, 3000);
    }
}

function clearChatHistory() {
    CHAT.messages = [];
    const container = document.getElementById('chat-messages');
    container.innerHTML = `
        <div class="chat-welcome" id="chat-welcome">
            <div class="chat-welcome-icon">💬</div>
            <p>チャットを開始するには下のテキストボックスにメッセージを入力してください。</p>
        </div>`;
    // Delete server-side session (F3)
    const oldSid = getChatSessionId();
    if (S.persona && oldSid) {
        fetch('/api/chat/' + encodeURIComponent(S.persona) + '/sessions/' + encodeURIComponent(oldSid), { method: 'DELETE' })
            .catch(() => {/* ignore */});
    }
    // Generate a new session ID (persona-scoped key)
    const newSession = 'sess_' + Date.now();
    const storageKey = 'chat_session_id_' + (S.persona || 'default');
    localStorage.setItem(storageKey, newSession);
    document.getElementById('chat-status').textContent = '会話をリセットしました';
    setTimeout(() => { document.getElementById('chat-status').textContent = ''; }, 2000);
}

function getChatSessionId() {
    const storageKey = 'chat_session_id_' + (S.persona || 'default');
    let sid = localStorage.getItem(storageKey);
    if (!sid) {
        sid = 'sess_' + Date.now();
        localStorage.setItem(storageKey, sid);
    }
    return sid;
}

function appendChatMessage(role, content, timeStr, isMarkdown) {
    const container = document.getElementById('chat-messages');
    // Remove welcome message if present
    const welcome = container.querySelector('.chat-welcome');
    if (welcome) welcome.remove();

    const div = document.createElement('div');
    div.className = 'chat-msg ' + role;
    const bubble = document.createElement('div');
    bubble.className = 'chat-bubble';
    if (isMarkdown && role === 'assistant') {
        bubble.innerHTML = safeMarkdown(content);
    } else {
        bubble.textContent = content;
    }
    const timeDiv = document.createElement('div');
    timeDiv.className = 'chat-time';
    timeDiv.textContent = timeStr || new Date().toLocaleTimeString('ja-JP', {hour:'2-digit',minute:'2-digit'});
    div.appendChild(bubble);
    div.appendChild(timeDiv);

    // Action buttons
    const actions = document.createElement('div');
    actions.className = 'chat-msg-actions';
    if (role === 'user') {
        const editBtn = document.createElement('button');
        editBtn.className = 'chat-msg-action-btn edit';
        editBtn.textContent = '✏️ 編集';
        editBtn.onclick = () => {
            const inputEl = document.getElementById('chat-input');
            if (inputEl) {
                inputEl.value = content;
                inputEl.focus();
                inputEl.dispatchEvent(new Event('input'));
            }
        };
        actions.appendChild(editBtn);
    } else if (role === 'assistant') {
        const retryBtn = document.createElement('button');
        retryBtn.className = 'chat-msg-action-btn retry';
        retryBtn.textContent = '🔄 再生成';
        retryBtn.onclick = () => { chatSend(true); };
        actions.appendChild(retryBtn);
        const copyBtn = document.createElement('button');
        copyBtn.className = 'chat-msg-action-btn';
        copyBtn.textContent = '📋';
        copyBtn.title = 'コピー';
        copyBtn.onclick = () => {
            navigator.clipboard.writeText(content).then(() => toast('コピーしました', 'success'));
        };
        actions.appendChild(copyBtn);
    }
    div.appendChild(actions);

    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
    return div;
}

// F1: Safe Markdown renderer using marked.js + DOMPurify
function safeMarkdown(text) {
    if (!text) return '';
    try {
        if (typeof marked !== 'undefined' && typeof DOMPurify !== 'undefined') {
            // Pre-process fenced code blocks to preserve onclick handlers through DOMPurify
            const codeBlocks = [];
            const textWithPlaceholders = text.replace(/```(\w*)\n([\s\S]*?)```/g, function(_, lang, code) {
                const idx = codeBlocks.length;
                codeBlocks.push(renderCodeBlock(lang || '', code.trimEnd()));
                return 'CODEBLOCK_PLACEHOLDER_' + idx + '_END';
            });
            const html = marked.parse(textWithPlaceholders, { breaks: true, gfm: true });
            let sanitized = DOMPurify.sanitize(html, {
                ALLOWED_TAGS: ['p','strong','em','b','i','u','s','code','pre','ul','ol','li',
                               'h1','h2','h3','h4','blockquote','a','br','hr','table','thead',
                               'tbody','tr','th','td','span'],
                ALLOWED_ATTR: ['href','title','class'],
            });
            // Restore code blocks (renderCodeBlock output is already escaped/safe)
            codeBlocks.forEach(function(block, idx) {
                sanitized = sanitized.replace('CODEBLOCK_PLACEHOLDER_' + idx + '_END', block);
            });
            return sanitized;
        }
    } catch (e) { /* fallback to escaped text */ }
    return esc(text).replace(/\n/g, '<br>');
}

// F2: Restore chat history from server on page load / persona switch
async function restoreChatHistory() {
    if (!S.persona) return;
    const sid = getChatSessionId();
    const container = document.getElementById('chat-messages');
    // Always reset DOM first to prevent previous persona's messages from lingering
    CHAT.messages = [];
    container.innerHTML = `
        <div class="chat-welcome" id="chat-welcome">
            <div class="chat-welcome-icon">💬</div>
            <p>チャットを開始するには下のテキストボックスにメッセージを入力してください。</p>
        </div>`;
    try {
        const data = await api('/api/chat/' + encodeURIComponent(S.persona) + '/sessions/' + encodeURIComponent(sid));
        if (!data || !data.messages || data.messages.length === 0) return;
        // display_history_turns 件数分（最新N turns = N*2 messages）に制限
        const displayTurns = parseInt(document.getElementById('chat-display-history-turns')?.value || '20');
        const maxMsgs = displayTurns * 2;
        const msgs = data.messages.slice(-maxMsgs);
        container.innerHTML = '';
        for (const msg of msgs) {
            appendChatMessage(msg.role, msg.content, msg.time, msg.role === 'assistant');
        }
    } catch (_e) {
        // Session not found or API unavailable — start fresh
    }
}

// Housekeeping: manual trigger
async function runHousekeeping() {
    if (!S.persona) { toast('ペルソナを選択してください', 'error'); return; }
    const statusEl = document.getElementById('chat-housekeeping-status');
    if (statusEl) statusEl.innerHTML = '<span style="color:var(--text-muted)">整理中...</span>';
    try {
        const result = await api('/api/chat/' + encodeURIComponent(S.persona) + '/housekeeping', {
            method: 'POST',
        });
        const g = (result.cancelled_goals || []).length;
        const p = (result.cancelled_promises || []).length;
        const i = (result.removed_items || []).length;
        const msg = `完了: goals ${g}件 / promises ${p}件 / items ${i}件 を整理`;
        if (statusEl) statusEl.innerHTML = `<span style="color:var(--accent-green)">${msg}</span>`;
        toast(msg, 'success');
    } catch (e) {
        if (statusEl) statusEl.innerHTML = `<span style="color:var(--accent-red)">失敗: ${e.message}</span>`;
        toast('整理失敗: ' + e.message, 'error');
    }
}

// F4: Cancel streaming
function chatCancel() {
    CHAT.streaming = false;
    if (CHAT.abortController) {
        CHAT.abortController.abort();
        CHAT.abortController = null;
    }
    const cancelBtn = document.getElementById('chat-cancel-btn');
    const sendBtn = document.getElementById('chat-send-btn');
    const statusEl = document.getElementById('chat-status');
    if (cancelBtn) cancelBtn.style.display = 'none';
    if (sendBtn) sendBtn.style.display = '';
    if (statusEl) statusEl.textContent = '中断しました';
    removeTypingIndicator();
}

/* ── Export chat history ── */
function exportChatHistory() {
    const container = document.getElementById('chat-messages');
    if (!container) return;
    const bubbles = container.querySelectorAll('.chat-msg');
    if (bubbles.length === 0) { toast('エクスポートする会話がありません', 'error'); return; }
    const lines = [];
    const persona = S.persona || 'default';
    lines.push('# 会話ログ - ' + persona);
    lines.push('> エクスポート日時: ' + new Date().toISOString());
    lines.push('');
    bubbles.forEach(msg => {
        const role = msg.classList.contains('user') ? '**👤 ユーザー**' : '**🤖 アシスタント**';
        const bubble = msg.querySelector('.chat-bubble');
        const time = msg.querySelector('.chat-time')?.textContent || '';
        const content = bubble ? bubble.textContent : '';
        lines.push('### ' + role + ' _' + time + '_');
        lines.push('');
        lines.push(content);
        lines.push('');
    });
    const blob = new Blob([lines.join('\n')], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'chat-' + persona + '-' + new Date().toISOString().slice(0, 10) + '.md';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    toast('会話をエクスポートしました', 'success');
}

/* ── Voice input (Web Speech API) ── */
let _voiceRecognition = null;
function toggleVoiceInput() {
    const btn = document.getElementById('chat-voice-btn');
    if (!('webkitSpeechRecognition' in window || 'SpeechRecognition' in window)) {
        toast('お使いのブラウザは音声入力に対応していません', 'error');
        return;
    }
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (_voiceRecognition) {
        _voiceRecognition.stop();
        _voiceRecognition = null;
        if (btn) { btn.textContent = '🎤'; btn.style.color = ''; }
        return;
    }
    _voiceRecognition = new SpeechRecognition();
    _voiceRecognition.lang = 'ja-JP';
    _voiceRecognition.interimResults = false;
    _voiceRecognition.continuous = false;
    if (btn) { btn.textContent = '🔴'; btn.style.color = 'var(--accent-red)'; }
    _voiceRecognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        const inputEl = document.getElementById('chat-input');
        if (inputEl) {
            inputEl.value = (inputEl.value ? inputEl.value + ' ' : '') + transcript;
            inputEl.dispatchEvent(new Event('input'));
        }
        _voiceRecognition = null;
        if (btn) { btn.textContent = '🎤'; btn.style.color = ''; }
    };
    _voiceRecognition.onerror = () => {
        toast('音声認識エラー', 'error');
        _voiceRecognition = null;
        if (btn) { btn.textContent = '🎤'; btn.style.color = ''; }
    };
    _voiceRecognition.onend = () => {
        if (btn) { btn.textContent = '🎤'; btn.style.color = ''; }
    };
    _voiceRecognition.start();
}

function appendToolEvent(eventType, data) {
    const container = document.getElementById('chat-messages');

    if (eventType === 'tool_call') {
        const div = document.createElement('div');
        div.className = 'chat-tool-call';
        div.dataset.toolId = data.id || '';
        let inputStr;
        try { inputStr = JSON.stringify(data.input, null, 2); } catch (e) { inputStr = String(data.input); }
        div.innerHTML =
            '<details><summary>🔧 <strong>' + esc(data.name) + '</strong>' +
            '<span class="chat-tool-status">実行中...</span></summary>' +
            '<pre class="chat-tool-detail">' + esc(inputStr) + '</pre></details>';
        container.appendChild(div);
        container.scrollTop = container.scrollHeight;
        return div;

    } else if (eventType === 'tool_result') {
        let resultStr;
        try {
            resultStr = typeof data.result === 'object' ? JSON.stringify(data.result, null, 2) : String(data.result);
        } catch (e) { resultStr = String(data.result); }

        // Find matching tool_call div by id and update it
        const callDiv = data.id ? container.querySelector('[data-tool-id="' + CSS.escape(data.id) + '"]') : null;
        if (callDiv) {
            const statusEl = callDiv.querySelector('.chat-tool-status');
            if (statusEl) statusEl.textContent = ' ✓ 完了';
            const details = callDiv.querySelector('details');
            if (details) {
                const resultPre = document.createElement('pre');
                resultPre.className = 'chat-tool-detail chat-tool-result-content';
                resultPre.textContent = resultStr;
                details.appendChild(resultPre);
            }
            callDiv.classList.add('done');
        } else {
            const div = document.createElement('div');
            div.className = 'chat-tool-result';
            div.innerHTML =
                '<details><summary>✓ <strong>' + esc(data.name) + '</strong></summary>' +
                '<pre class="chat-tool-detail chat-tool-result-content">' + esc(resultStr) + '</pre></details>';
            container.appendChild(div);
            container.scrollTop = container.scrollHeight;
            return div;
        }
    }
}

function showTypingIndicator() {
    const container = document.getElementById('chat-messages');
    const typing = document.createElement('div');
    typing.id = 'chat-typing';
    typing.className = 'chat-msg assistant';
    typing.innerHTML = '<div class="chat-bubble chat-typing"><span></span><span></span><span></span></div>';
    container.appendChild(typing);
    container.scrollTop = container.scrollHeight;
}

function removeTypingIndicator() {
    const el = document.getElementById('chat-typing');
    if (el) el.remove();
}

async function uploadAttachment(file) {
    if (!S.persona) { toast('ペルソナを選択してください', 'error'); return; }
    const formData = new FormData();
    formData.append('file', file);
    try {
        const res = await fetch('/api/chat/' + encodeURIComponent(S.persona) + '/attachment/upload', {
            method: 'POST',
            body: formData,
        });
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const data = await res.json();
        CHAT.attachments.push(data);
        renderAttachmentBadge(data);
    } catch (e) {
        toast('ファイルのアップロードに失敗しました: ' + e.message, 'error');
    }
}

function renderAttachmentBadge(att) {
    const area = document.getElementById('chat-attachments');
    if (!area) return;
    const badge = document.createElement('div');
    badge.className = 'chat-attachment-badge';
    badge.dataset.filename = att.filename;

    const isImage = att.mime_type && att.mime_type.startsWith('image/');
    const isVideo = att.mime_type && att.mime_type.startsWith('video/');

    if (isImage) {
        const img = document.createElement('img');
        img.className = 'thumb';
        img.src = att.url;
        img.alt = att.filename;
        img.onclick = () => openMediaViewer(att.url, 'image');
        badge.appendChild(img);
    } else if (isVideo) {
        const vid = document.createElement('video');
        vid.className = 'thumb';
        vid.src = att.url;
        vid.muted = true;
        vid.onclick = () => openMediaViewer(att.url, 'video');
        badge.appendChild(vid);
    } else {
        const icon = document.createElement('span');
        const ext = att.filename.split('.').pop().toLowerCase();
        icon.textContent = ext === 'pdf' ? '📕' : (ext === 'zip' || ext === 'tar' || ext === 'gz' ? '📦' : '📄');
        badge.appendChild(icon);
    }

    const nameSpan = document.createElement('span');
    nameSpan.className = 'attach-name';
    nameSpan.textContent = att.filename;
    badge.appendChild(nameSpan);

    const removeBtn = document.createElement('button');
    removeBtn.className = 'attach-remove';
    removeBtn.textContent = '✕';
    removeBtn.onclick = () => {
        CHAT.attachments = CHAT.attachments.filter(a => a.filename !== att.filename);
        badge.remove();
    };
    badge.appendChild(removeBtn);
    area.appendChild(badge);
}

function openMediaViewer(url, type) {
    const overlay = document.getElementById('media-viewer-overlay');
    const inner = document.getElementById('media-viewer-inner');
    if (!overlay || !inner) return;
    inner.innerHTML = '';
    if (type === 'image') {
        const img = document.createElement('img');
        img.src = url;
        inner.appendChild(img);
    } else {
        const vid = document.createElement('video');
        vid.src = url;
        vid.controls = true;
        vid.autoplay = true;
        inner.appendChild(vid);
    }
    overlay.classList.add('visible');
    // ESC to close
    const escHandler = (e) => {
        if (e.key === 'Escape') { closeMediaViewer(); document.removeEventListener('keydown', escHandler); }
    };
    document.addEventListener('keydown', escHandler);
}

function closeMediaViewer() {
    const overlay = document.getElementById('media-viewer-overlay');
    const inner = document.getElementById('media-viewer-inner');
    if (overlay) overlay.classList.remove('visible');
    if (inner) {
        const vid = inner.querySelector('video');
        if (vid) vid.pause();
        inner.innerHTML = '';
    }
}

/* ── Memory CRUD operations ── */
let _memEditKey = null;

function openMemEdit(card) {
    _memEditKey = card.dataset.key;
    document.getElementById('mem-edit-content').value = card.dataset.content || '';
    document.getElementById('mem-edit-importance').value = card.dataset.importance || '0.5';
    document.getElementById('mem-edit-tags').value = card.dataset.tags || '';
    document.getElementById('mem-edit-overlay').classList.add('show');
}

function closeMemEdit() {
    document.getElementById('mem-edit-overlay').classList.remove('show');
    _memEditKey = null;
}

async function saveMemEdit() {
    if (!_memEditKey || !S.persona) return;
    const content = document.getElementById('mem-edit-content').value.trim();
    const importance = parseFloat(document.getElementById('mem-edit-importance').value) || 0.5;
    const tagsStr = document.getElementById('mem-edit-tags').value.trim();
    const tags = tagsStr ? tagsStr.split(',').map(t => t.trim()).filter(Boolean) : [];
    if (!content) { toast('内容を入力してください', 'error'); return; }
    try {
        await api('/api/memories/' + encodeURIComponent(S.persona) + '/' + encodeURIComponent(_memEditKey), {
            method: 'PUT',
            body: JSON.stringify({ content, importance, tags }),
        });
        closeMemEdit();
        toast('メモリを更新しました', 'success');
        loadChatCommitments(); // refresh panels
    } catch (e) {
        toast('更新失敗: ' + e.message, 'error');
    }
}

async function deleteMemCard(key) {
    const k = key || _memEditKey;
    if (!k || !S.persona) return;
    if (!confirm('このメモリを削除しますか？')) return;
    try {
        await api('/api/memories/' + encodeURIComponent(S.persona) + '/' + encodeURIComponent(k), {
            method: 'DELETE',
        });
        closeMemEdit();
        toast('メモリを削除しました', 'success');
        loadChatCommitments(); // refresh panels
    } catch (e) {
        toast('削除失敗: ' + e.message, 'error');
    }
}

async function completeGoal(key, content) {
    if (!S.persona) return;
    try {
        const resp = await api('/api/chat/' + encodeURIComponent(S.persona) + '/tool', {
            method: 'POST',
            body: JSON.stringify({ tool: 'goal_achieve', input: { content } }),
        });
        if (resp.status === 'ok') {
            toast('目標を達成しました: ' + (resp.updated || content), 'success');
            loadChatCommitments();
        } else {
            toast('完了失敗: ' + (resp.message || ''), 'error');
        }
    } catch (e) {
        toast('エラー: ' + e.message, 'error');
    }
}

async function fulfillPromise(key, content) {
    if (!S.persona) return;
    try {
        const resp = await api('/api/chat/' + encodeURIComponent(S.persona) + '/tool', {
            method: 'POST',
            body: JSON.stringify({ tool: 'promise_fulfill', input: { content } }),
        });
        if (resp.status === 'ok') {
            toast('約束を遂行しました: ' + (resp.updated || content), 'success');
            loadChatCommitments();
        } else {
            toast('遂行失敗: ' + (resp.message || ''), 'error');
        }
    } catch (e) {
        toast('エラー: ' + e.message, 'error');
    }
}

/* ── Slash command handler ── */
async function handleSlashCommand(toolName, toolInput) {
    const inputEl = document.getElementById('chat-input');
    const rawInput = inputEl.value.trim();
    inputEl.value = '';
    inputEl.style.height = 'auto';
    const timeStr = new Date().toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit' });
    appendChatMessage('user', rawInput, timeStr);
    showTypingIndicator();
    try {
        const resp = await api('/api/chat/' + encodeURIComponent(S.persona) + '/tool', {
            method: 'POST',
            body: JSON.stringify({ tool: toolName, input: toolInput }),
        });
        removeTypingIndicator();
        const resultMsg = resp.status === 'ok'
            ? '✓ ' + (resp.key ? '作成: ' + resp.key : resp.updated ? '更新: ' + resp.updated : '実行完了')
            : '✗ ' + (resp.message || resp.error || 'エラー');
        appendChatMessage('assistant', resultMsg, new Date().toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit' }));
        if (resp.status === 'ok') toast(resultMsg, 'success');
    } catch (ex) {
        removeTypingIndicator();
        appendChatMessage('assistant', '✗ コマンド実行失敗: ' + ex.message,
            new Date().toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit' }));
        toast('コマンド失敗: ' + ex.message, 'error');
    }
}

async function chatSend(retry) {
    if (!S.persona) { toast('ペルソナを選択してください', 'error'); return; }
    if (CHAT.streaming) return;

    const inputEl = document.getElementById('chat-input');
    let rawInput;
    if (retry) {
        // Find last user message
        const msgs = document.querySelectorAll('.chat-msg.user .chat-bubble');
        rawInput = msgs.length > 0 ? msgs[msgs.length - 1].textContent : '';
        if (!rawInput) { toast('再送するメッセージがありません', 'error'); return; }
    } else {
        rawInput = inputEl.value.trim();
    }
    let message = rawInput;
    if (!message && CHAT.attachments.length === 0) return;
    if (!message) message = '';

    // Web search toggle
    const webSearchEl = document.getElementById('chat-web-search');
    if (webSearchEl && webSearchEl.checked && message) {
        message = '[Web検索モード]\n以下の質問について、まずWeb検索を行い最新の情報を取得してから回答してください。\n\n' + message;
        webSearchEl.checked = false; // one-shot
    }

    const sendBtn = document.getElementById('chat-send-btn');
    const cancelBtn = document.getElementById('chat-cancel-btn');
    const statusEl = document.getElementById('chat-status');

    // Append attachment references to message
    if (CHAT.attachments.length > 0) {
        const TEXT_EXTS = new Set(['txt','csv','json','py','js','ts','md','yaml','yml','toml','ini','cfg','sh','bash','html','css','xml','log','sql','rs','go','java','cpp','c','h']);
        const attachParts = [];
        for (const att of CHAT.attachments) {
            const ext = att.filename.split('.').pop().toLowerCase();
            const isText = TEXT_EXTS.has(ext);
            if (isText) {
                try {
                    const res = await fetch(att.url);
                    const content = await res.text();
                    attachParts.push('\n\n--- 添付: ' + att.filename + ' ---\n' + content + '\n---');
                } catch (_e) {
                    attachParts.push('\n[添付ファイル: ' + att.workspace_path + ']');
                }
            } else if (att.mime_type && att.mime_type.startsWith('image/')) {
                attachParts.push('\n[添付画像: ' + att.workspace_path + ']');
            } else {
                attachParts.push('\n[添付ファイル: ' + att.workspace_path + ']');
            }
        }
        if (attachParts.length > 0) {
            message = message + attachParts.join('');
        }
    }

    inputEl.value = '';
    inputEl.style.height = 'auto';
    // Save attachment info before clearing
    const attNames = CHAT.attachments.map(a => a.filename);
    CHAT.attachments = [];
    const attArea = document.getElementById('chat-attachments');
    if (attArea) attArea.innerHTML = '';

    // Show user message with filename display
    const displayMsg = rawInput || (attNames.length > 0 ? '📎 ' + attNames.join(', ') : '');
    const timeStr = new Date().toLocaleTimeString('ja-JP', {hour:'2-digit',minute:'2-digit'});
    appendChatMessage('user', displayMsg, timeStr);
    showTypingIndicator();

    CHAT.streaming = true;
    CHAT.abortController = new AbortController();
    sendBtn.style.display = 'none';
    if (cancelBtn) cancelBtn.style.display = '';
    statusEl.textContent = '応答中...';

    const sessionId = getChatSessionId();
    let assistantText = '';
    let assistantBubble = null;
    let assistantDiv = null;

    try {
        const response = await fetch('/api/chat/' + encodeURIComponent(S.persona), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message, session_id: sessionId, debug: false }),
            signal: CHAT.abortController.signal,
        });

        if (!response.ok) {
            throw new Error('HTTP ' + response.status);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let streamDone = false;

        removeTypingIndicator();

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });

            const lines = buffer.split('\n');
            buffer = lines.pop();  // keep incomplete line

            for (const line of lines) {
                if (!line.startsWith('data: ')) continue;
                let evt;
                try { evt = JSON.parse(line.slice(6)); } catch { continue; }

                if (evt.type === 'text_delta') {
                    if (!assistantDiv) {
                        const container = document.getElementById('chat-messages');
                        assistantDiv = document.createElement('div');
                        assistantDiv.className = 'chat-msg assistant';
                        assistantBubble = document.createElement('div');
                        assistantBubble.className = 'chat-bubble';
                        const timeDiv = document.createElement('div');
                        timeDiv.className = 'chat-time';
                        timeDiv.textContent = new Date().toLocaleTimeString('ja-JP', {hour:'2-digit',minute:'2-digit'});
                        assistantDiv.appendChild(assistantBubble);
                        assistantDiv.appendChild(timeDiv);
                        container.appendChild(assistantDiv);
                    }
                    assistantText += evt.content;
                    // F1: stream as plain text for performance; render markdown on done
                    assistantBubble.textContent = assistantText;
                    document.getElementById('chat-messages').scrollTop = document.getElementById('chat-messages').scrollHeight;

                } else if (evt.type === 'tool_call') {
                    if (MEMORY_TOOL_NAMES.has(evt.name)) {
                        handleMemoryToolCall(evt);
                    } else {
                        const sbEnabled = document.getElementById('chat-sandbox-enabled')?.checked;
                        if (FILE_OP_TOOLS.has(evt.name) && sbEnabled) {
                            handleFileToolCall(evt);
                        } else {
                            appendToolEvent('tool_call', evt);
                        }
                    }
                    statusEl.textContent = '🔧 ' + evt.name + ' を実行中...';
                    sandboxHandleToolEvent(evt);

                } else if (evt.type === 'tool_result') {
                    if (MEMORY_TOOL_NAMES.has(evt.name)) {
                        handleMemoryToolResult(evt);
                    } else {
                        const sbEnabled = document.getElementById('chat-sandbox-enabled')?.checked;
                        if (!FILE_OP_TOOLS.has(evt.name) || !sbEnabled) {
                            appendToolEvent('tool_result', evt);
                        }
                    }
                    statusEl.textContent = '応答中...';
                    sandboxHandleToolEvent(evt);

                } else if (evt.type === 'memory_activity') {
                    updateMemoryPanel(evt.retrieved, evt.saved, undefined, undefined);
                    setTimeout(() => loadChatCommitments(), 300);

                } else if (evt.type === 'reflection_start') {
                    showReflectionStart();

                } else if (evt.type === 'reflection_done') {
                    updateReflectionPanel(evt.insights);

                } else if (evt.type === 'session_summarized') {
                    showSessionSummarized(evt.summary);

                } else if (evt.type === 'error') {
                    removeTypingIndicator();
                    toast('エラー: ' + evt.message, 'error');
                    statusEl.textContent = '';
                    streamDone = true;
                    break;

                } else if (evt.type === 'debug_info') {
                    console.debug('[debug_info received]', Object.keys(evt));
                    renderDebugPanel(assistantDiv, evt);

                } else if (evt.type === 'done') {
                    // F1: final Markdown render
                    if (assistantBubble && assistantText) {
                        assistantBubble.innerHTML = safeMarkdown(assistantText);
                    }
                    statusEl.textContent = '';
                }
            }
            if (streamDone) break;
        }

    } catch (e) {
        removeTypingIndicator();
        if (e.name !== 'AbortError') {
            toast('送信失敗: ' + e.message, 'error');
        }
        statusEl.textContent = '';
    } finally {
        CHAT.streaming = false;
        CHAT.abortController = null;
        sendBtn.style.display = '';
        if (cancelBtn) cancelBtn.style.display = 'none';
        inputEl.focus();
        // Fallback: render markdown if stream ended without 'done' event
        if (assistantBubble && assistantText && assistantBubble.textContent === assistantText) {
            assistantBubble.innerHTML = safeMarkdown(assistantText);
        }
    }
}

// Chat input auto-resize and keyboard handler
document.addEventListener('DOMContentLoaded', () => {
    const input = document.getElementById('chat-input');
    if (!input) return;
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            const val = input.value.trim();
            // Slash commands
            if (val.startsWith('/memory ')) {
                handleSlashCommand('memory_create', { content: val.slice(8).trim(), importance: 0.7, tags: [] });
            } else if (val.startsWith('/goal ')) {
                handleSlashCommand('goal_create', { content: val.slice(6).trim(), importance: 0.8 });
            } else if (val.startsWith('/promise ')) {
                handleSlashCommand('promise_create', { content: val.slice(9).trim(), importance: 0.8 });
            } else if (val.startsWith('/code ') && S.persona) {
                handleSlashCommand('execute_code', { code: val.slice(6).trim(), language: 'python' });
            } else {
                chatSend();
            }
        }
    });
    input.addEventListener('input', () => {
        input.style.height = 'auto';
        input.style.height = Math.min(input.scrollHeight, 160) + 'px';
    });
    // File drag-and-drop on chat input
    input.addEventListener('dragover', (e) => {
        e.preventDefault();
        input.classList.add('dragover');
    });
    input.addEventListener('dragleave', () => {
        input.classList.remove('dragover');
    });
    input.addEventListener('drop', async (e) => {
        e.preventDefault();
        input.classList.remove('dragover');
        const files = Array.from(e.dataTransfer.files);
        for (const file of files) {
            await uploadAttachment(file);
        }
    });
});

// Reload chat config when persona changes
window.__chatPersonaWatcher = setInterval(() => {
    const sel = document.getElementById('persona-select');
    if (!sel) return;
    if (!sel._chatBound) {
        sel._chatBound = true;
        sel.addEventListener('change', () => {
            // DOM reset + history restore is handled by base.py's loadTab() → loadChat() → restoreChatHistory()
            // Do NOT call clearChatHistory() here — it would destroy the session ID and break history
            if (S.tab === 'chat') {
                loadChatConfig();
                loadChatCommitments();
            }
        });
        clearInterval(window.__chatPersonaWatcher);
    }
}, 500);

/* ── Memory tool filtering ── */
const MEMORY_TOOL_NAMES = new Set([
    // MCP tools
    'memory', 'search_memory', 'update_context', 'item', 'get_context',
    // Builtin tools
    'memory_create', 'memory_search', 'memory_update',
    'context_update', 'context_recall',
    'goal_create', 'goal_achieve', 'goal_cancel',
    'promise_create', 'promise_fulfill', 'promise_cancel',
    'invoke_skill',
]);
const FILE_OP_TOOLS = new Set(['edit', 'create', 'view', 'bash', 'powershell', 'str_replace_editor',
    'write_file', 'read_file', 'delete_file', 'list_files', 'glob', 'grep']);

// Track in-flight memory ops for result pairing
const _memOps = {};

function handleMemoryToolCall(evt) {
    const el = document.getElementById('memory-tool-ops-list');
    if (!el) return;
    const empty = el.querySelector('.memory-empty');
    if (empty) empty.remove();
    const op = evt.input?.operation || '';
    const icons = { memory:'💾', search_memory:'🔍', update_context:'🔄', item:'🎒', get_context:'📊' };
    const icon = icons[evt.name] || '🔧';
    const label = evt.name + (op ? '.' + op : '');
    const id = 'mop-' + (evt.id || (evt.name + Date.now()));
    const card = document.createElement('div');
    card.className = 'memory-item-card';
    card.id = id;
    card.innerHTML = '<div class="mem-score">' + esc(icon + ' ' + label) + '</div>' +
        '<span style="opacity:0.5;font-size:0.7rem">実行中...</span>';
    el.prepend(card);
    const cards = el.querySelectorAll('.memory-item-card');
    if (cards.length > 8) cards[cards.length - 1].remove();
    _memOps[evt.id || label] = id;
}

function handleMemoryToolResult(evt) {
    const key = evt.id || (evt.name + (evt.input?.operation || ''));
    const cardId = _memOps[key];
    if (cardId) {
        const card = document.getElementById(cardId);
        if (card) {
            const span = card.querySelector('span');
            if (span) span.remove();
            const resultStr = typeof evt.result === 'string' ? evt.result : JSON.stringify(evt.result);
            const detail = document.createElement('div');
            detail.style.cssText = 'font-size:0.7rem;opacity:0.75;margin-top:2px;';
            detail.textContent = resultStr.substring(0, 100) + (resultStr.length > 100 ? '...' : '');
            card.appendChild(detail);
        }
        delete _memOps[key];
    }
}

function handleFileToolCall(evt) {
    const icons = { edit:'✏️', create:'📝', view:'👁️', bash:'⚙️', powershell:'⚙️',
        str_replace_editor:'✏️', delete_file:'🗑️', list_files:'📂',
        write_file:'📝', read_file:'👁️', glob:'🔍', grep:'🔍' };
    const icon = icons[evt.name] || '🔧';
    const detail = evt.input?.path || evt.input?.file_path || evt.input?.command ||
        evt.input?.pattern || evt.input?.glob || '';
    sandboxLog(icon + ' ' + evt.name + (detail ? ': ' + String(detail).substring(0, 60) : ''), 'system');
}

function sandboxLog(text, type = '') {
    if (typeof isCodingAgentOpen === 'function' && isCodingAgentOpen() &&
        typeof caAppendOutput === 'function') {
        caAppendOutput(text + '\n', type === 'stderr' ? 'stderr' : 'stdout');
    }
}

function onSandboxEnabledChange() {
    const enabled = document.getElementById('chat-sandbox-enabled')?.checked;
    if (!enabled && typeof isCodingAgentOpen === 'function' && isCodingAgentOpen()) {
        closeCodingAgent();
    }
}

/* ── Sandbox: Add artifact to tab ── */
function sandboxAddArtifact(base64png, label) {
    const list = document.getElementById('sandbox-artifacts-list');
    if (!list) return;
    // Clear placeholder
    const placeholder = list.querySelector('div[style*="text-muted"]');
    if (placeholder) placeholder.remove();

    const thumb = document.createElement('div');
    thumb.className = 'artifact-thumb';
    const img = document.createElement('img');
    img.src = 'data:image/png;base64,' + base64png;
    img.alt = label || 'artifact';
    img.onclick = () => window.open(img.src, '_blank');
    const lbl = document.createElement('div');
    lbl.className = 'artifact-thumb-label';
    lbl.textContent = label || new Date().toLocaleTimeString();
    thumb.appendChild(img);
    thumb.appendChild(lbl);
    list.appendChild(thumb);
}

/* ── Code block Run button ── */
async function sandboxRunBlock(code, language, resultEl, runBtn) {
    if (!S.persona) return;
    if (typeof openCodingAgent === 'function') {
        openCodingAgent({ code, language });
        if (resultEl) {
            resultEl.className = 'hljs-run-result stdout';
            resultEl.textContent = '▶ Coding Agent で開きました';
            resultEl.style.display = 'block';
        }
        if (runBtn) runBtn.textContent = '▶ Run';
        return;
    }
    runBtn.disabled = true;
    runBtn.textContent = '⏳';
    resultEl.className = 'hljs-run-result running';
    resultEl.textContent = '実行中...';
    resultEl.style.display = 'block';
    try {
        const resp = await api('/api/chat/' + encodeURIComponent(S.persona) + '/sandbox/execute', {
            method: 'POST',
            body: JSON.stringify({ code, language }),
        });
        const out = (resp.stdout || '').trim();
        const err = (resp.stderr || '').trim();
        if (err) {
            resultEl.className = 'hljs-run-result stderr';
            resultEl.textContent = err;
        } else {
            resultEl.className = 'hljs-run-result stdout';
            resultEl.textContent = out || '(出力なし)';
        }
        if (resp.artifacts && resp.artifacts.length > 0) {
            resp.artifacts.forEach((a, i) => {
                const img = document.createElement('img');
                img.src = 'data:image/png;base64,' + a;
                img.className = 'hljs-artifact-img';
                img.title = 'クリックで拡大';
                img.onclick = () => window.open(img.src, '_blank');
                resultEl.parentNode.insertBefore(img, resultEl.nextSibling);
                sandboxAddArtifact(a, 'chart-' + new Date().toLocaleTimeString());
            });
        }
        sandboxLog('▶ [' + language + '] ' + code.split('\n')[0].substring(0, 60) + (code.includes('\n') ? '...' : ''), 'system');
        if (out) out.split('\n').forEach(l => l && sandboxLog(l, 'success'));
        if (err) err.split('\n').forEach(l => l && sandboxLog(l, 'stderr'));
    } catch (ex) {
        resultEl.className = 'hljs-run-result stderr';
        resultEl.textContent = 'Error: ' + ex.message;
    } finally {
        runBtn.disabled = false;
        runBtn.textContent = '▶ Run';
    }
}

/* ── Markdown code block rendering with syntax highlighting ── */
function renderCodeBlock(lang, code) {
    const sandboxEnabled = document.getElementById('chat-sandbox-enabled')?.checked;
    const runnable = sandboxEnabled && lang && lang !== 'text' && lang !== 'output';
    const escaped = esc(code);
    // Try highlight.js
    let highlighted = escaped;
    try {
        if (typeof hljs !== 'undefined' && lang && hljs.getLanguage(lang)) {
            highlighted = hljs.highlight(code, { language: lang }).value;
        } else if (typeof hljs !== 'undefined') {
            highlighted = hljs.highlightAuto(code).value;
        }
    } catch (_) { /* fallback to plain */ }

    const uid = 'codeblock-' + Math.random().toString(36).slice(2);
    const runBtnHtml = runnable
        ? '<button class="hljs-run-btn" id="runbtn-' + uid + '" onclick="sandboxRunBlock(' +
          JSON.stringify(code) + ', ' + JSON.stringify(lang || 'python') + ', document.getElementById(\'result-' + uid + '\'), this)">▶ Run</button>'
        : '';

    return '<div class="hljs-block-wrapper">' +
        '<div class="hljs-block-header">' +
            '<span class="hljs-lang-badge">' + esc(lang || '') + '</span>' +
            '<div class="hljs-block-actions">' +
                '<button class="hljs-copy-btn" onclick="navigator.clipboard.writeText(' + JSON.stringify(code) + ').then(()=>toast(\'コピーしました\',\'success\'))">📋 Copy</button>' +
                runBtnHtml +
            '</div>' +
        '</div>' +
        '<pre style="margin:0;padding:8px 10px;background:#0d1117;overflow-x:auto;"><code class="hljs language-' + esc(lang || '') + '">' + highlighted + '</code></pre>' +
        '<div id="result-' + uid + '" class="hljs-run-result" style="display:none;"></div>' +
    '</div>';
}
"""
