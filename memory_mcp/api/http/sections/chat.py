"""Chat tab section for the MemoryMCP Dashboard.

Renders a fully-functional chat interface with SSE streaming,
tool call visualization, and an inline settings panel.
"""


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
        /* Settings sidebar */
        #chat-sidebar {
            width: 280px; flex-shrink: 0; display: flex; flex-direction: column; gap: 12px;
            overflow-y: auto;
        }
        #chat-sidebar.collapsed { width: 0; overflow: hidden; }
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
            word-break: break-word;
        }
        .memory-item-card .mem-score {
            font-size: 0.68rem; color: var(--accent-purple); margin-bottom: 3px;
            font-weight: 600;
        }
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
            #chat-sidebar { width: 100% !important; }
            #memory-panel { display: none; }
        }
        /* Debug panel */
        .chat-debug-panel {
            margin-top: 4px; max-width: 85%;
            background: rgba(0,0,0,0.25); border: 1px solid rgba(139,92,246,0.2);
            border-radius: 8px; font-size: 0.72rem; overflow: hidden;
        }
        .chat-debug-panel details {
            padding: 5px 10px; border-bottom: 1px solid rgba(255,255,255,0.04);
        }
        .chat-debug-panel details:last-child { border-bottom: none; }
        .chat-debug-panel summary {
            cursor: pointer; color: var(--text-muted); user-select: none; outline: none;
            padding: 2px 0;
        }
        .chat-debug-panel summary:hover { color: var(--text-secondary); }
        .chat-debug-panel pre {
            margin: 6px 0 2px; white-space: pre-wrap; word-break: break-all;
            color: rgba(200,200,255,0.7); max-height: 180px; overflow-y: auto;
            font-size: 0.7rem; line-height: 1.4;
        }
        .chat-debug-btn {
            background: none; border: 1px solid var(--glass-border);
            border-radius: 8px; color: var(--text-muted); padding: 4px 8px;
            cursor: pointer; font-size: 0.78rem; transition: all 0.2s;
            opacity: 0.4;
        }
        .chat-debug-btn.active { opacity: 1; border-color: rgba(139,92,246,0.5); color: var(--accent-purple); }
        .chat-debug-btn:hover { opacity: 0.8; }
        #chat-cancel-btn {
            background: rgba(248,113,113,0.12); border: 1px solid rgba(248,113,113,0.3);
            border-radius: 8px; color: var(--accent-red); padding: 8px 14px;
            cursor: pointer; font-size: 0.85rem; font-weight: 600; transition: all 0.2s;
        }
        #chat-cancel-btn:hover { background: rgba(248,113,113,0.22); }
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
        </style>
        <!-- ========== CHAT TAB ========== -->
        <section id="tab-chat" class="tab-panel" role="tabpanel">
            <div style="position:relative; margin-bottom:12px; display:flex; align-items:center; justify-content:space-between;">
                <h2 style="font-size:1.1rem; font-weight:600; color:var(--text-primary);">💬 Chat</h2>
                <div style="display:flex;gap:8px;align-items:center;">
                    <button class="mem-panel-toggle" id="memory-panel-toggle-btn" onclick="toggleMemoryPanel()" title="記憶パネルを開閉">🧠</button>
                    <button class="chat-debug-btn" id="chat-debug-btn" onclick="toggleDebugMode()" title="デバッグ情報の表示切替">🐛 Debug</button>
                    <button class="chat-sidebar-toggle" onclick="toggleChatSidebar()" id="chat-sidebar-toggle-btn" title="設定パネルを開閉">⚙️ 設定</button>
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
                    <div id="chat-input-area">
                        <textarea id="chat-input" placeholder="メッセージを入力... (Shift+Enter で改行、Enter で送信)" rows="1"></textarea>
                        <button id="chat-cancel-btn" onclick="chatCancel()" style="display:none;">⏹ 中止</button>
                        <button id="chat-send-btn" onclick="chatSend()">送信 ↑</button>
                    </div>
                </div>
                <!-- Settings sidebar -->
                <div id="chat-sidebar" class="glass" style="margin:0; border-radius:0; border-left:1px solid var(--glass-border); padding:16px; gap:12px; display:flex; flex-direction:column;">
                    <div style="font-size:0.85rem; font-weight:600; color:var(--text-primary); margin-bottom:4px;">⚙️ チャット設定</div>
                    <!-- Provider -->
                    <div>
                        <div class="chat-field-label">プロバイダー</div>
                        <select id="chat-provider" class="chat-field-input" onchange="onChatProviderChange()">
                            <option value="anthropic">Anthropic (Claude)</option>
                            <option value="openai">OpenAI</option>
                            <option value="openrouter">OpenRouter</option>
                        </select>
                    </div>
                    <!-- Model -->
                    <div>
                        <div class="chat-field-label">モデル <span style="color:var(--accent-blue);font-size:0.7rem;">（空白でデフォルト）</span></div>
                        <input type="text" id="chat-model" class="chat-field-input" placeholder="例: claude-opus-4-5" />
                    </div>
                    <!-- API Key -->
                    <div>
                        <div class="chat-field-label">APIキー</div>
                        <input type="password" id="chat-api-key" class="chat-field-input" placeholder="sk-..." autocomplete="off" />
                    </div>
                    <!-- Base URL (OpenRouter / Custom) -->
                    <div id="chat-base-url-row">
                        <div class="chat-field-label">Base URL <span style="color:var(--text-muted);font-size:0.7rem;">（任意）</span></div>
                        <input type="text" id="chat-base-url" class="chat-field-input" placeholder="https://openrouter.ai/api/v1" />
                    </div>
                    <!-- Temperature -->
                    <div>
                        <div class="chat-field-label" style="display:flex;justify-content:space-between;">
                            <span>Temperature</span>
                            <span id="chat-temp-val" style="color:var(--accent-purple);">0.7</span>
                        </div>
                        <input type="range" id="chat-temperature" min="0" max="2" step="0.05" value="0.7"
                            oninput="document.getElementById('chat-temp-val').textContent=parseFloat(this.value).toFixed(2)"
                            style="width:100%;accent-color:var(--accent-purple);" />
                    </div>
                    <!-- Max tokens -->
                    <div>
                        <div class="chat-field-label">Max Tokens</div>
                        <input type="number" id="chat-max-tokens" class="chat-field-input" min="1" max="32768" value="2048" />
                    </div>
                    <!-- Context window turns -->
                    <div>
                        <div class="chat-field-label">コンテキスト履歴 (turns)</div>
                        <input type="number" id="chat-window-turns" class="chat-field-input" min="1" max="50" value="3" />
                    </div>
                    <!-- Max tool calls -->
                    <div>
                        <div class="chat-field-label">最大ツール呼び出し回数</div>
                        <input type="number" id="chat-max-tool-calls" class="chat-field-input" min="0" max="20" value="5" />
                    </div>
                    <!-- System prompt -->
                    <div style="flex:1; display:flex; flex-direction:column; min-height:80px;">
                        <div class="chat-field-label">システムプロンプト</div>
                        <textarea id="chat-system-prompt" class="chat-field-input" rows="4"
                            placeholder="（空白でデフォルト: ペルソナ名のアシスタント）"
                            style="flex:1;resize:vertical;min-height:70px;"></textarea>
                    </div>
                    <!-- Auto extract -->
                    <div style="border-top:1px solid var(--glass-border);padding-top:10px;">
                        <div style="font-size:0.8rem; font-weight:600; color:var(--text-secondary); margin-bottom:8px;">🧠 自動ファクト抽出 (Mem0方式)</div>
                        <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
                            <input type="checkbox" id="chat-auto-extract" checked
                                style="width:15px;height:15px;accent-color:var(--accent-purple);cursor:pointer;" />
                            <label for="chat-auto-extract" class="chat-field-label" style="margin:0;cursor:pointer;">ターン毎に記憶を自動抽出</label>
                        </div>
                        <div>
                            <div class="chat-field-label">抽出モデル <span style="color:var(--text-muted);font-size:0.7rem;">（空白でチャットと同モデル）</span></div>
                            <input type="text" id="chat-extract-model" class="chat-field-input"
                                placeholder="例: claude-haiku-4-5, gpt-4o-mini" />
                        </div>
                    </div>
                    <!-- MCP Servers -->
                    <div style="border-top:1px solid var(--glass-border);padding-top:10px;" id="chat-mcp-section">
                        <div style="margin-bottom:6px;">
                            <div style="font-size:0.8rem; font-weight:600; color:var(--text-secondary); margin-bottom:4px;">🔌 MCPサーバー</div>
                            <div style="font-size:0.72rem;color:var(--text-muted);margin-bottom:6px;">Claude の mcp.json 形式で貼り付け・編集できます</div>
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
                    <!-- Skills -->
                    <div style="border-top:1px solid var(--glass-border);padding-top:10px;" id="chat-skills-section">
                        <div style="font-size:0.8rem; font-weight:600; color:var(--text-secondary); margin-bottom:8px;">🎯 Skills</div>
                        <div id="chat-skills-list" style="display:flex;flex-direction:column;gap:4px;"></div>
                    </div>
                    <!-- Reflection & Retrieval settings -->
                    <div style="border-top:1px solid var(--glass-border);padding-top:10px;">
                        <div style="font-size:0.8rem; font-weight:600; color:var(--text-secondary); margin-bottom:8px;">🔮 リフレクション設定</div>
                        <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
                            <input type="checkbox" id="chat-reflection-enabled" checked
                                style="width:15px;height:15px;accent-color:var(--accent-purple);cursor:pointer;" />
                            <label for="chat-reflection-enabled" class="chat-field-label" style="margin:0;cursor:pointer;">リフレクション有効</label>
                        </div>
                        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px;">
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
                    <!-- Retrieval weights -->
                    <div style="border-top:1px solid var(--glass-border);padding-top:10px;">
                        <div style="font-size:0.8rem; font-weight:600; color:var(--text-secondary); margin-bottom:8px;">⚖️ 検索重み</div>
                        <div style="margin-bottom:8px;">
                            <div class="chat-field-label" style="display:flex;justify-content:space-between;">
                                <span>鮮度</span>
                                <span id="chat-recency-weight-val" style="color:var(--accent-purple);">0.30</span>
                            </div>
                            <input type="range" id="chat-recency-weight" min="0" max="1" step="0.05" value="0.3"
                                oninput="document.getElementById('chat-recency-weight-val').textContent=parseFloat(this.value).toFixed(2)"
                                style="width:100%;accent-color:var(--accent-purple);" />
                        </div>
                        <div style="margin-bottom:8px;">
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
                    <!-- Buttons -->
                    <button class="chat-save-btn" onclick="saveChatConfig()">💾 設定を保存</button>
                    <button class="chat-clear-btn" onclick="clearChatHistory()">🗑️ 会話をリセット</button>
                    <!-- Config status -->
                    <div id="chat-config-status" style="font-size:0.75rem; text-align:center; min-height:16px;"></div>
                </div>
            </div>
        </section>"""


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
    debugMode: localStorage.getItem('chat_debug_mode') === 'true',
    messages: [],  // { role, content, time }
    mcpServers: [],
    enabledSkills: [],
    abortController: null,  // F4: AbortController for streaming cancel
};

function loadChat() {
    if (!S.persona) return;
    loadChatConfig();
    loadSkillsForChat();
    restoreChatHistory();
    loadChatCommitments();
    // Restore debug button state
    const btn = document.getElementById('chat-debug-btn');
    if (btn && CHAT.debugMode) btn.classList.add('active');
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
    set('chat-provider', cfg.provider);
    set('chat-model', cfg.model || '');
    set('chat-api-key', cfg.api_key || '');
    set('chat-base-url', cfg.base_url || '');
    set('chat-temperature', cfg.temperature != null ? cfg.temperature : 0.7);
    set('chat-max-tokens', cfg.max_tokens || 2048);
    set('chat-window-turns', cfg.max_window_turns || 3);
    set('chat-max-tool-calls', cfg.max_tool_calls || 5);
    set('chat-system-prompt', cfg.system_prompt || '');
    const autoExtract = document.getElementById('chat-auto-extract');
    if (autoExtract) autoExtract.checked = cfg.auto_extract !== false;
    set('chat-extract-model', cfg.extract_model || '');
    const tempEl = document.getElementById('chat-temp-val');
    if (tempEl) tempEl.textContent = parseFloat(cfg.temperature || 0.7).toFixed(2);
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
    const reflEnabled = document.getElementById('chat-reflection-enabled');
    if (reflEnabled) reflEnabled.checked = cfg.reflection_enabled !== false;
    set('chat-reflection-threshold', cfg.reflection_threshold != null ? cfg.reflection_threshold : 1.0);
    set('chat-reflection-interval', cfg.reflection_min_interval_hours != null ? cfg.reflection_min_interval_hours : 1.0);
    const sessSum = document.getElementById('chat-session-summarize');
    if (sessSum) sessSum.checked = cfg.session_summarize !== false;
    // Retrieval weights
    const setSlider = (id, valId, v) => {
        const el = document.getElementById(id);
        const vel = document.getElementById(valId);
        if (el && v != null) { el.value = v; if (vel) vel.textContent = parseFloat(v).toFixed(2); }
    };
    setSlider('chat-recency-weight', 'chat-recency-weight-val', cfg.retrieval_recency_weight != null ? cfg.retrieval_recency_weight : 0.3);
    setSlider('chat-importance-weight', 'chat-importance-weight-val', cfg.retrieval_importance_weight != null ? cfg.retrieval_importance_weight : 0.3);
    setSlider('chat-relevance-weight', 'chat-relevance-weight-val', cfg.retrieval_relevance_weight != null ? cfg.retrieval_relevance_weight : 0.4);
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
        auto_extract: document.getElementById('chat-auto-extract')?.checked ?? true,
        extract_model: document.getElementById('chat-extract-model')?.value.trim() || '',
        mcp_servers: parseMcpJson(),
        tool_result_max_chars: parseInt(document.getElementById('chat-tool-result-max')?.value || '4000'),
        enabled_skills: CHAT.enabledSkills,
        reflection_enabled: document.getElementById('chat-reflection-enabled')?.checked ?? true,
        reflection_threshold: parseFloat(document.getElementById('chat-reflection-threshold')?.value || '1.0'),
        reflection_min_interval_hours: parseFloat(document.getElementById('chat-reflection-interval')?.value || '1.0'),
        session_summarize: document.getElementById('chat-session-summarize')?.checked ?? true,
        retrieval_recency_weight: parseFloat(document.getElementById('chat-recency-weight')?.value || '0.3'),
        retrieval_importance_weight: parseFloat(document.getElementById('chat-importance-weight')?.value || '0.3'),
        retrieval_relevance_weight: parseFloat(document.getElementById('chat-relevance-weight')?.value || '0.4'),
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

function toggleChatSidebar() {
    const sidebar = document.getElementById('chat-sidebar');
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
    const btn = document.getElementById('memory-panel-toggle-btn');
    CHAT.memoryPanelOpen = !CHAT.memoryPanelOpen;
    if (!panel) return;
    if (CHAT.memoryPanelOpen) {
        panel.style.display = 'flex';
        if (btn) btn.style.opacity = '1';
    } else {
        panel.style.display = 'none';
        if (btn) btn.style.opacity = '0.4';
    }
}

function toggleDebugMode() {
    CHAT.debugMode = !CHAT.debugMode;
    localStorage.setItem('chat_debug_mode', CHAT.debugMode);
    const btn = document.getElementById('chat-debug-btn');
    if (btn) btn.classList.toggle('active', CHAT.debugMode);
    document.querySelectorAll('.chat-debug-panel').forEach(el => {
        el.style.display = CHAT.debugMode ? 'block' : 'none';
    });
}

function renderDebugPanel(anchorEl, data) {
    try {
        const panel = document.createElement('div');
        panel.className = 'chat-debug-panel';
        panel.style.display = CHAT.debugMode ? 'block' : 'none';

        const SECTIONS = [
            { key: 'system_prompt',    label: '📝 System Prompt' },
            { key: 'context_summary',  label: '🧠 Context' },
            { key: 'memories_raw',     label: '💡 Memories',     isArray: true },
            { key: 'tool_calls',       label: '🔧 Tool Calls',   isArray: true },
            { key: 'messages_sent',    label: '💬 Messages Sent', isArray: true },
            { key: 'context_state',    label: '📊 Context State' },
            { key: 'skills_raw',       label: '🎯 Skills',       isArray: true },
        ];
        const knownKeys = new Set(['type', ...SECTIONS.map(s => s.key)]);

        let html = '';
        for (const sec of SECTIONS) {
            const val = data[sec.key];
            if (val === undefined || val === null) continue;
            let displayVal;
            try { displayVal = typeof val === 'string' ? val : JSON.stringify(val, null, 2); }
            catch (e) { displayVal = String(val); }
            const count = sec.isArray && Array.isArray(val) ? ' (' + val.length + ')' : '';
            html += '<details class="chat-debug-section"><summary>' + sec.label + count + '</summary>' +
                    '<pre class="chat-tool-detail">' + esc(displayVal) + '</pre></details>';
        }
        // Extra keys not in known sections
        const extra = {};
        for (const [k, v] of Object.entries(data)) {
            if (!knownKeys.has(k)) extra[k] = v;
        }
        if (Object.keys(extra).length) {
            let extraStr;
            try { extraStr = JSON.stringify(extra, null, 2); } catch (e) { extraStr = String(extra); }
            html += '<details class="chat-debug-section"><summary>📎 その他</summary>' +
                    '<pre class="chat-tool-detail">' + esc(extraStr) + '</pre></details>';
        }
        panel.innerHTML = html;

        const container = document.getElementById('chat-messages');
        // T5: anchorEl が null や container 外の場合、最後の非デバッグ要素にフォールバック
        let anchor = (anchorEl && anchorEl.parentNode === container) ? anchorEl : null;
        if (!anchor) {
            const children = [...container.children].filter(el => !el.classList.contains('chat-debug-panel'));
            anchor = children.length ? children[children.length - 1] : null;
        }
        if (anchor) {
            anchor.insertAdjacentElement('afterend', panel);
        } else {
            container.appendChild(panel);
        }
        container.scrollTop = container.scrollHeight;
    } catch (e) {
        console.error('[debug panel render error]', e);
    }
}

/* ── Memory Panel helpers ── */
function updateMemoryPanel(retrieved, saved, goals, promises) {
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
                    return '<div class="memory-item-card">' +
                        (meta ? '<div class="mem-score">' + esc(meta) + '</div>' : '') +
                        content + '</div>';
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
                    return '<div class="memory-item-card">' + content +
                        (tags ? '<div class="mem-score">' + esc(tags) + '</div>' : '') + '</div>';
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
                goalsList.innerHTML = goals.map(g =>
                    '<div class="memory-item-card">🎯 ' + esc((g.content || '').substring(0, 80)) + '</div>'
                ).join('');
            }
        }
    }
    if (promises !== undefined) {
        const promisesList = document.getElementById('memory-promises-list');
        if (promisesList) {
            if (!promises || promises.length === 0) {
                promisesList.innerHTML = '<div class="memory-empty">なし</div>';
            } else {
                promisesList.innerHTML = promises.map(p =>
                    '<div class="memory-item-card">🤝 ' + esc((p.content || '').substring(0, 80)) + '</div>'
                ).join('');
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
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
    return div;
}

// F1: Safe Markdown renderer using marked.js + DOMPurify
function safeMarkdown(text) {
    if (!text) return '';
    try {
        if (typeof marked !== 'undefined' && typeof DOMPurify !== 'undefined') {
            const html = marked.parse(text, { breaks: true, gfm: true });
            return DOMPurify.sanitize(html, {
                ALLOWED_TAGS: ['p','strong','em','b','i','u','s','code','pre','ul','ol','li',
                               'h1','h2','h3','h4','blockquote','a','br','hr','table','thead',
                               'tbody','tr','th','td','span'],
                ALLOWED_ATTR: ['href','title','class'],
            });
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
        container.innerHTML = '';
        for (const msg of data.messages) {
            appendChatMessage(msg.role, msg.content, msg.time, msg.role === 'assistant');
        }
    } catch (_e) {
        // Session not found or API unavailable — start fresh
    }
}

// F4: Cancel streaming
function chatCancel() {
    if (CHAT.abortController) {
        CHAT.abortController.abort();
        CHAT.abortController = null;
    }
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

async function chatSend() {
    if (!S.persona) { toast('ペルソナを選択してください', 'error'); return; }
    if (CHAT.streaming) return;

    const inputEl = document.getElementById('chat-input');
    const message = inputEl.value.trim();
    if (!message) return;

    inputEl.value = '';
    inputEl.style.height = 'auto';

    const sendBtn = document.getElementById('chat-send-btn');
    const cancelBtn = document.getElementById('chat-cancel-btn');
    const statusEl = document.getElementById('chat-status');

    // Show user message
    const timeStr = new Date().toLocaleTimeString('ja-JP', {hour:'2-digit',minute:'2-digit'});
    appendChatMessage('user', message, timeStr);
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
            body: JSON.stringify({ message, session_id: sessionId, debug: CHAT.debugMode }),
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
                    appendToolEvent('tool_call', evt);
                    statusEl.textContent = '🔧 ' + evt.name + ' を実行中...';

                } else if (evt.type === 'tool_result') {
                    appendToolEvent('tool_result', evt);
                    statusEl.textContent = '応答中...';

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
                    console.log('[debug_info received]', Object.keys(evt));
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
            chatSend();
        }
    });
    input.addEventListener('input', () => {
        input.style.height = 'auto';
        input.style.height = Math.min(input.scrollHeight, 160) + 'px';
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
"""
