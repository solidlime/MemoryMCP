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
            font-size: 0.78rem; padding: 6px 10px; border-radius: 8px;
            background: rgba(96,165,250,0.1); border: 1px solid rgba(96,165,250,0.2);
            color: var(--accent-blue); margin: 4px 0;
        }
        .chat-tool-result {
            font-size: 0.78rem; padding: 6px 10px; border-radius: 8px;
            background: rgba(52,211,153,0.08); border: 1px solid rgba(52,211,153,0.2);
            color: var(--accent-green); margin: 4px 0;
        }
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
        @media (max-width: 768px) {
            #chat-layout { flex-direction: column; height: auto; }
            #chat-messages { min-height: 350px; max-height: 50vh; }
            #chat-sidebar { width: 100% !important; }
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
        </style>
        <!-- ========== CHAT TAB ========== -->
        <section id="tab-chat" class="tab-panel" role="tabpanel">
            <div style="position:relative; margin-bottom:12px; display:flex; align-items:center; justify-content:space-between;">
                <h2 style="font-size:1.1rem; font-weight:600; color:var(--text-primary);">💬 Chat</h2>
                <div style="display:flex;gap:8px;align-items:center;">
                    <button class="chat-debug-btn" id="chat-debug-btn" onclick="toggleDebugMode()" title="デバッグ情報の表示切替">🐛 Debug</button>
                    <button class="chat-sidebar-toggle" onclick="toggleChatSidebar()" id="chat-sidebar-toggle-btn" title="設定パネルを開閉">⚙️ 設定</button>
                </div>
            </div>
            <div id="chat-layout" class="glass" style="padding:0; overflow:hidden;">
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
    debugMode: localStorage.getItem('chat_debug_mode') === 'true',
    messages: [],  // { role, content, time }
    mcpServers: [],
    enabledSkills: [],
};

function loadChat() {
    if (!S.persona) return;
    loadChatConfig();
    loadSkillsForChat();
    // Restore debug button state
    const btn = document.getElementById('chat-debug-btn');
    if (btn && CHAT.debugMode) btn.classList.add('active');
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
        system_prompt: document.getElementById('chat-system-prompt').value.trim(),
        auto_extract: document.getElementById('chat-auto-extract')?.checked ?? true,
        extract_model: document.getElementById('chat-extract-model')?.value.trim() || '',
        mcp_servers: parseMcpJson(),
        tool_result_max_chars: parseInt(document.getElementById('chat-tool-result-max')?.value || '4000'),
        enabled_skills: CHAT.enabledSkills,
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
        sidebar.style.display = 'flex';
        if (btn) btn.textContent = '⚙️ 設定';
    } else {
        sidebar.style.width = '0';
        sidebar.style.overflow = 'hidden';
        sidebar.style.padding = '0';
        if (btn) btn.textContent = '⚙️';
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
    const panel = document.createElement('div');
    panel.className = 'chat-debug-panel';
    panel.style.display = CHAT.debugMode ? 'block' : 'none';
    let html = '';
    if (data.system_prompt) {
        html += `<details><summary>📋 System Prompt</summary><pre>${esc(data.system_prompt)}</pre></details>`;
    }
    const queries = data.memory_queries || [];
    const results = data.memory_results || [];
    if (queries.length > 0 || results.length > 0) {
        const qStr = queries.join(' / ') || '(none)';
        const rStr = results.length > 0
            ? results.map(r => `[${(r.importance||0).toFixed(1)}] (${(r.score||0).toFixed(3)}) ${r.content}`).join('\n')
            : '(no results)';
        html += `<details><summary>🔍 Memory Search — ${queries.length} quer${queries.length===1?'y':'ies'}, ${results.length} result${results.length!==1?'s':''}</summary><pre>Queries: ${esc(qStr)}\n\nResults:\n${esc(rStr)}</pre></details>`;
    }
    if (data.context_summary) {
        html += `<details><summary>🧠 Context Summary</summary><pre>${esc(data.context_summary)}</pre></details>`;
    }
    const toolCalls = data.tool_calls || [];
    if (toolCalls.length > 0) {
        const tStr = toolCalls.map(t =>
            `▶ ${t.name}(${JSON.stringify(t.input)})\n← ${JSON.stringify(t.result)}`
        ).join('\n\n');
        html += `<details><summary>🔧 Tool Calls (${toolCalls.length})</summary><pre>${esc(tStr)}</pre></details>`;
    }
    panel.innerHTML = html || '<div style="padding:6px 10px;color:var(--text-muted);">No debug data</div>';
    if (anchorEl) {
        anchorEl.insertAdjacentElement('afterend', panel);
    } else {
        document.getElementById('chat-messages').appendChild(panel);
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
    // Generate a new session ID
    const newSession = 'sess_' + Date.now();
    localStorage.setItem('chat_session_id', newSession);
    document.getElementById('chat-status').textContent = '会話をリセットしました';
    setTimeout(() => { document.getElementById('chat-status').textContent = ''; }, 2000);
}

function getChatSessionId() {
    let sid = localStorage.getItem('chat_session_id');
    if (!sid) {
        sid = 'sess_' + Date.now();
        localStorage.setItem('chat_session_id', sid);
    }
    return sid;
}

function appendChatMessage(role, content, timeStr) {
    const container = document.getElementById('chat-messages');
    // Remove welcome message if present
    const welcome = container.querySelector('.chat-welcome');
    if (welcome) welcome.remove();

    const div = document.createElement('div');
    div.className = 'chat-msg ' + role;
    div.innerHTML =
        '<div class="chat-bubble">' + esc(content) + '</div>' +
        '<div class="chat-time">' + (timeStr || new Date().toLocaleTimeString('ja-JP', {hour:'2-digit',minute:'2-digit'})) + '</div>';
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
    return div;
}

function appendToolEvent(eventType, data) {
    const container = document.getElementById('chat-messages');
    const div = document.createElement('div');
    if (eventType === 'tool_call') {
        div.className = 'chat-tool-call';
        div.innerHTML = '🔧 <strong>' + esc(data.name) + '</strong>: ' + esc(JSON.stringify(data.input).slice(0, 120));
    } else if (eventType === 'tool_result') {
        div.className = 'chat-tool-result';
        const resultStr = typeof data.result === 'object' ? JSON.stringify(data.result) : String(data.result);
        div.innerHTML = '✓ <strong>' + esc(data.name) + '</strong>: ' + esc(resultStr.slice(0, 120));
    }
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
    return div;
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
    const statusEl = document.getElementById('chat-status');

    // Show user message
    const timeStr = new Date().toLocaleTimeString('ja-JP', {hour:'2-digit',minute:'2-digit'});
    appendChatMessage('user', message, timeStr);
    showTypingIndicator();

    CHAT.streaming = true;
    sendBtn.disabled = true;
    statusEl.textContent = '応答中...';

    const sessionId = getChatSessionId();

    try {
        const response = await fetch('/api/chat/' + encodeURIComponent(S.persona), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message, session_id: sessionId }),
        });

        if (!response.ok) {
            throw new Error('HTTP ' + response.status);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let assistantText = '';
        let assistantBubble = null;
        let assistantDiv = null;

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
                    assistantBubble.textContent = assistantText;
                    document.getElementById('chat-messages').scrollTop = document.getElementById('chat-messages').scrollHeight;

                } else if (evt.type === 'tool_call') {
                    appendToolEvent('tool_call', evt);
                    statusEl.textContent = '🔧 ' + evt.name + ' を実行中...';

                } else if (evt.type === 'tool_result') {
                    appendToolEvent('tool_result', evt);
                    statusEl.textContent = '応答中...';

                } else if (evt.type === 'error') {
                    removeTypingIndicator();
                    toast('エラー: ' + evt.message, 'error');
                    statusEl.textContent = '';

                } else if (evt.type === 'debug_info') {
                    renderDebugPanel(assistantDiv, evt);

                } else if (evt.type === 'done') {
                    statusEl.textContent = '';
                }
            }
        }

    } catch (e) {
        removeTypingIndicator();
        toast('送信失敗: ' + e.message, 'error');
        statusEl.textContent = '';
    } finally {
        CHAT.streaming = false;
        sendBtn.disabled = false;
        inputEl.focus();
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
const _origPersonaChange = document.getElementById('persona-select') ? document.getElementById('persona-select').onchange : null;
window.__chatPersonaWatcher = setInterval(() => {
    const sel = document.getElementById('persona-select');
    if (!sel) return;
    if (!sel._chatBound) {
        sel._chatBound = true;
        sel.addEventListener('change', () => {
            if (S.tab === 'chat') loadChatConfig();
        });
    }
}, 500);
"""
