"""Memories tab section: HTML skeleton and JavaScript for full CRUD, advanced search, sorting, and batch operations."""


def render_memories_tab() -> str:
    """Return the memories tab HTML section with all UI elements."""
    return """        <!-- ========== MEMORIES TAB ========== -->
        <section id="tab-memories" class="tab-panel" role="tabpanel">
            <style>
            /* ── Tag chips with per-tag hue ── */
            .mem-tag-chip {
                display: inline-flex; align-items: center; gap: 3px;
                padding: 2px 10px; border-radius: 20px; font-size: 0.72rem; font-weight: 600;
                background: hsla(var(--chip-hue), 70%, 60%, 0.15);
                color: hsla(var(--chip-hue), 70%, 70%, 1);
                border: 1px solid hsla(var(--chip-hue), 70%, 60%, 0.3);
            }
            html.light .mem-tag-chip { color: hsla(var(--chip-hue), 70%, 35%, 1); }

            /* ── Advanced search panel ── */
            .adv-search-panel {
                max-height: 0; overflow: hidden;
                transition: max-height 0.35s ease, padding 0.35s ease, opacity 0.35s ease;
                opacity: 0; padding: 0 16px;
            }
            .adv-search-panel.open { max-height: 600px; opacity: 1; padding: 16px; }
            .adv-search-row { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; margin-bottom: 10px; }
            .adv-search-label { font-size: 0.78rem; color: var(--text-muted); min-width: 80px; }

            /* ── Search mode button group ── */
            .mode-btn-group {
                display: flex; gap: 2px; border-radius: 10px; overflow: hidden;
                border: 1px solid var(--glass-border);
            }
            .mode-btn {
                padding: 5px 12px; font-size: 0.75rem; border: none; background: transparent;
                color: var(--text-muted); cursor: pointer; transition: all 0.2s;
            }
            .mode-btn.active {
                background: rgba(167,139,250,0.25); color: var(--accent-purple); font-weight: 600;
            }

            /* ── Toolbar ── */
            .mem-toolbar {
                display: flex; gap: 8px; flex-wrap: wrap; align-items: center; padding: 10px 0;
            }
            .mem-toolbar-spacer { flex: 1; }

            /* ── Batch bar ── */
            .mem-batch-bar {
                display: none; gap: 8px; align-items: center; padding: 10px 16px;
                background: rgba(248,113,113,0.08); border-radius: 10px; margin-bottom: 8px;
                border: 1px solid rgba(248,113,113,0.2);
            }
            .mem-batch-bar.active { display: flex; }

            /* ── View toggle ── */
            .view-toggle {
                display: flex; gap: 2px; border-radius: 8px; overflow: hidden;
                border: 1px solid var(--glass-border);
            }
            .view-btn {
                padding: 5px 10px; font-size: 0.8rem; border: none; background: transparent;
                color: var(--text-muted); cursor: pointer; transition: all 0.2s;
            }
            .view-btn.active { background: rgba(167,139,250,0.2); color: var(--accent-purple); }

            /* ── Compact list view ── */
            .memory-compact {
                display: flex; align-items: center; gap: 12px; padding: 8px 16px;
                border-bottom: 1px solid var(--glass-border); font-size: 0.82rem; cursor: pointer;
                transition: background 0.2s;
            }
            .memory-compact:hover { background: rgba(167,139,250,0.05); }
            .memory-compact:last-child { border-bottom: none; }
            .mem-compact-key {
                font-family: monospace; color: var(--accent-purple); font-size: 0.75rem;
                min-width: 120px; flex-shrink: 0; overflow: hidden;
                text-overflow: ellipsis; white-space: nowrap;
            }
            .mem-compact-content {
                flex: 1; color: var(--text-secondary); overflow: hidden;
                text-overflow: ellipsis; white-space: nowrap;
            }
            .mem-compact-meta { display: flex; gap: 6px; align-items: center; flex-shrink: 0; }
            .mem-compact-imp {
                width: 50px; height: 4px; border-radius: 2px;
                background: rgba(255,255,255,0.08); overflow: hidden;
            }
            .mem-compact-imp-fill {
                height: 100%; border-radius: 2px;
                background: linear-gradient(90deg, var(--accent-purple), var(--accent-pink));
            }

            /* ── Edit/Create modal overlay ── */
            .mem-edit-overlay {
                position: fixed; inset: 0; background: rgba(0,0,0,0.6); z-index: 1100;
                display: none; align-items: center; justify-content: center;
                padding: 20px; backdrop-filter: blur(4px);
            }
            .mem-edit-overlay.active { display: flex; }
            .mem-edit-modal {
                background: var(--bg-secondary); border: 1px solid var(--glass-border);
                border-radius: var(--card-radius); max-width: 640px; width: 100%;
                max-height: 85vh; overflow-y: auto; padding: 24px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.4);
                animation: fadeIn 0.2s ease;
            }
            @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
            .form-group { margin-bottom: 14px; }
            .form-label { display: block; font-size: 0.78rem; color: var(--text-muted); margin-bottom: 4px; font-weight: 600; }
            .form-textarea {
                width: 100%; min-height: 120px; background: rgba(255,255,255,0.06);
                border: 1px solid var(--glass-border); border-radius: 10px;
                color: var(--text-primary); padding: 10px; font-size: 0.88rem;
                font-family: inherit; resize: vertical; outline: none;
            }
            .form-textarea:focus { border-color: var(--accent-purple); box-shadow: 0 0 0 3px rgba(167,139,250,0.2); }
            html.light .form-textarea { background: rgba(139,92,246,0.06); }

            /* ── Tags input ── */
            .tags-input-wrap {
                display: flex; flex-wrap: wrap; gap: 4px; padding: 6px 10px; min-height: 38px; align-items: center;
                background: rgba(255,255,255,0.06); border: 1px solid var(--glass-border); border-radius: 10px;
            }
            .tags-input-wrap:focus-within { border-color: var(--accent-purple); box-shadow: 0 0 0 3px rgba(167,139,250,0.2); }
            html.light .tags-input-wrap { background: rgba(139,92,246,0.06); }
            .tag-chip-edit {
                display: inline-flex; align-items: center; gap: 3px; padding: 2px 8px;
                border-radius: 14px; font-size: 0.75rem; font-weight: 600;
                background: hsla(var(--chip-hue), 70%, 60%, 0.2); color: hsla(var(--chip-hue), 70%, 70%, 1);
                border: 1px solid hsla(var(--chip-hue), 70%, 60%, 0.3);
            }
            .tag-chip-remove { cursor: pointer; opacity: 0.6; font-size: 0.85rem; line-height: 1; }
            .tag-chip-remove:hover { opacity: 1; }
            .tag-text-input {
                border: none; background: transparent; color: var(--text-primary); font-size: 0.82rem;
                outline: none; min-width: 60px; flex: 1;
            }

            /* ── Range slider ── */
            .range-row { display: flex; align-items: center; gap: 8px; }
            .range-value { font-size: 0.78rem; color: var(--accent-purple); min-width: 32px; text-align: center; font-weight: 600; }
            input[type="range"].glass-range {
                -webkit-appearance: none; appearance: none; width: 100%; height: 6px; border-radius: 3px;
                background: rgba(255,255,255,0.1); outline: none;
            }
            input[type="range"].glass-range::-webkit-slider-thumb {
                -webkit-appearance: none; width: 16px; height: 16px; border-radius: 50%;
                background: var(--accent-purple); cursor: pointer; border: 2px solid var(--bg-secondary);
                box-shadow: 0 0 8px rgba(167,139,250,0.4);
            }
            input[type="range"].glass-range::-moz-range-thumb {
                width: 16px; height: 16px; border-radius: 50%; background: var(--accent-purple);
                cursor: pointer; border: 2px solid var(--bg-secondary);
            }

            /* ── Checkbox in select mode ── */
            .mem-cb { display: none; }
            .mem-cb.show { display: inline-block; }
            .mem-cb input[type="checkbox"] {
                width: 16px; height: 16px; accent-color: var(--accent-purple); cursor: pointer; vertical-align: middle;
            }

            /* ── Copy button ── */
            .copy-btn { background: none; border: none; cursor: pointer; padding: 2px 6px; font-size: 0.8rem; opacity: 0.5; transition: opacity 0.2s; color: var(--text-primary); }
            .copy-btn:hover { opacity: 1; }

            /* ── Progress bar in modal ── */
            .modal-progress { display: flex; align-items: center; gap: 8px; }
            .modal-progress-bar { flex: 1; height: 8px; border-radius: 4px; background: rgba(255,255,255,0.08); overflow: hidden; }
            .modal-progress-fill { height: 100%; border-radius: 4px; transition: width 0.3s ease; }

            /* ── Filter tag pills in advanced search ── */
            .filter-tags-wrap {
                display: flex; flex-wrap: wrap; gap: 4px; padding: 4px; min-height: 30px;
                background: rgba(255,255,255,0.04); border-radius: 8px;
            }
            .filter-tag {
                padding: 3px 10px; border-radius: 14px; font-size: 0.72rem; cursor: pointer;
                border: 1px solid var(--glass-border); color: var(--text-muted); transition: all 0.2s;
                user-select: none;
            }
            .filter-tag.active {
                background: rgba(167,139,250,0.2); color: var(--accent-purple);
                border-color: rgba(167,139,250,0.4);
            }

            /* ── Sort dropdown ── */
            .mem-sort-select { font-size: 0.8rem; padding: 5px 10px; }
            </style>

            <div id="memories-content">
                <div class="glass p-6"><div class="skeleton skeleton-title"></div><div class="skeleton skeleton-text"></div><div class="skeleton skeleton-text" style="width:80%"></div></div>
            </div>

            <!-- Edit/Create Modal -->
            <div id="mem-edit-overlay" class="mem-edit-overlay" onclick="if(event.target===this)closeEditModal()">
                <div class="mem-edit-modal">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
                        <h3 id="edit-modal-title" style="font-size:1.1rem;font-weight:700;color:var(--text-primary)">Edit Memory</h3>
                        <button class="mem-modal-close" onclick="closeEditModal()">&#10005;</button>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Content *</label>
                        <textarea id="edit-content" class="form-textarea" placeholder="Memory content..."></textarea>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Tags</label>
                        <div class="tags-input-wrap" id="edit-tags-wrap">
                            <input type="text" class="tag-text-input" id="edit-tag-input" placeholder="Type tag + Enter">
                        </div>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Importance</label>
                        <div class="range-row">
                            <span class="range-value" id="edit-imp-val">0.50</span>
                            <input type="range" class="glass-range" id="edit-importance" min="0" max="1" step="0.01" value="0.5">
                        </div>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Emotion Type</label>
                        <select id="edit-emotion" class="glass-input" style="width:100%">
                            <option value="">None</option>
                            <option value="joy">&#128522; Joy</option>
                            <option value="sadness">&#128546; Sadness</option>
                            <option value="anger">&#128544; Anger</option>
                            <option value="fear">&#128552; Fear</option>
                            <option value="surprise">&#128562; Surprise</option>
                            <option value="disgust">&#129326; Disgust</option>
                            <option value="trust">&#129309; Trust</option>
                            <option value="anticipation">&#129300; Anticipation</option>
                            <option value="neutral">&#128528; Neutral</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Emotion Intensity</label>
                        <div class="range-row">
                            <span class="range-value" id="edit-emo-val">0.00</span>
                            <input type="range" class="glass-range" id="edit-emo-intensity" min="0" max="1" step="0.01" value="0">
                        </div>
                    </div>
                    <input type="hidden" id="edit-memory-key" value="">
                    <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:16px">
                        <button class="glass-btn" onclick="closeEditModal()">Cancel</button>
                        <button class="glass-btn glass-btn-success" onclick="saveMemory()">&#128190; Save</button>
                    </div>
                </div>
            </div>
        </section>"""


def render_memories_js() -> str:
    """Return all JavaScript for the Memories tab."""
    return (
        "/* =================================================================\n"
        "   MEMORIES TAB \u2014 Extended State + Full CRUD\n"
        "   ================================================================= */\n"
        "Object.assign(S.mem, {\n"
        "    sort: 'date_desc', viewMode: 'card', selectMode: false, selected: new Set(),\n"
        "    searchMode: 'hybrid', dateFrom: '', dateTo: '', impMin: 0, impMax: 1,\n"
        "    searchTags: [], emotion: '', advOpen: false\n"
        "});\n"
        "\n"
        "/* ── Hash to hue ── */\n"
        "function hashToHue(str) {\n"
        "    var h = 0;\n"
        "    for (var i = 0; i < str.length; i++) { h = str.charCodeAt(i) + ((h << 5) - h); }\n"
        "    return Math.abs(h) % 360;\n"
        "}\n"
        "\n"
        "/* ── Tag chip HTML ── */\n"
        "function tagChipHtml(tag) {\n"
        "    var hue = hashToHue(tag);\n"
        "    return '<span class=\"mem-tag-chip\" style=\"--chip-hue:' + hue + '\">' + esc(tag) + '</span>';\n"
        "}\n"
        "\n"
        "/* ── Client-side sort helper ── */\n"
        "function _sortMemories(arr) {\n"
        "    var s = S.mem.sort;\n"
        "    var sorted = arr.slice();\n"
        "    if (s === 'date_desc') sorted.sort(function(a,b){ return (b.created_at||'').localeCompare(a.created_at||''); });\n"
        "    else if (s === 'date_asc') sorted.sort(function(a,b){ return (a.created_at||'').localeCompare(b.created_at||''); });\n"
        "    else if (s === 'imp_desc') sorted.sort(function(a,b){ return (b.importance||0) - (a.importance||0); });\n"
        "    else if (s === 'str_desc') sorted.sort(function(a,b){ return (b.strength||0) - (a.strength||0); });\n"
        "    else if (s === 'updated_desc') sorted.sort(function(a,b){ return (b.updated_at||'').localeCompare(a.updated_at||''); });\n"
        "    return sorted;\n"
        "}\n"
        "\n"
        "/* ── Client-side filter helper ── */\n"
        "function _filterMemories(arr) {\n"
        "    return arr.filter(function(m) {\n"
        "        if (S.mem.dateFrom) {\n"
        "            var d = m.created_at ? m.created_at.slice(0,10) : '';\n"
        "            if (d < S.mem.dateFrom) return false;\n"
        "        }\n"
        "        if (S.mem.dateTo) {\n"
        "            var d2 = m.created_at ? m.created_at.slice(0,10) : '';\n"
        "            if (d2 > S.mem.dateTo) return false;\n"
        "        }\n"
        "        var imp = m.importance != null ? m.importance : 0;\n"
        "        if (imp < S.mem.impMin || imp > S.mem.impMax) return false;\n"
        "        if (S.mem.searchTags.length > 0) {\n"
        "            var mtags = m.context_tags || m.tags || [];\n"
        "            var hasTag = false;\n"
        "            for (var i = 0; i < S.mem.searchTags.length; i++) {\n"
        "                if (mtags.indexOf(S.mem.searchTags[i]) !== -1) { hasTag = true; break; }\n"
        "            }\n"
        "            if (!hasTag) return false;\n"
        "        }\n"
        "        if (S.mem.emotion && m.emotion_type !== S.mem.emotion) return false;\n"
        "        return true;\n"
        "    });\n"
        "}\n"
        "\n"
        "/* ================================================================\n"
        "   loadMemories\n"
        "   ================================================================ */\n"
        "async function loadMemories(page) {\n"
        "    if (page != null) S.mem.page = page;\n"
        "    var el = document.getElementById('memories-content');\n"
        "\n"
        "    /* Build tag dropdown options from cache */\n"
        "    var tagOptions = '<option value=\"\">All Tags</option>';\n"
        "    var allKnownTags = [];\n"
        "    if (S.dashCache && S.dashCache.stats && S.dashCache.stats.tag_distribution) {\n"
        "        Object.keys(S.dashCache.stats.tag_distribution).sort().forEach(function(t) {\n"
        "            tagOptions += '<option value=\"' + esc(t) + '\"' + (S.mem.tag === t ? ' selected' : '') + '>' + esc(t) + '</option>';\n"
        "            allKnownTags.push(t);\n"
        "        });\n"
        "    }\n"
        "\n"
        "    try {\n"
        "        var data, memories, totalPages = 0, totalCount = 0, isSearch = false;\n"
        "        if (S.mem.q) {\n"
        "            isSearch = true;\n"
        "            var searchUrl = '/api/search/' + encodeURIComponent(S.persona)\n"
        "                + '?q=' + encodeURIComponent(S.mem.q)\n"
        "                + '&limit=50'\n"
        "                + '&mode=' + encodeURIComponent(S.mem.searchMode);\n"
        "            data = await api(searchUrl);\n"
        "            var results = data.results || [];\n"
        "            memories = results.map(function(r) {\n"
        "                var m = Object.assign({}, r.memory || {});\n"
        "                m._score = r.score; m._source = r.source;\n"
        "                return m;\n"
        "            });\n"
        "            memories = _filterMemories(memories);\n"
        "            memories = _sortMemories(memories);\n"
        "        } else {\n"
        "            var url = '/api/observations/' + encodeURIComponent(S.persona)\n"
        "                + '?page=' + S.mem.page\n"
        "                + '&per_page=' + S.mem.perPage\n"
        "                + '&sort=desc';\n"
        "            if (S.mem.tag) url += '&tag=' + encodeURIComponent(S.mem.tag);\n"
        "            data = await api(url);\n"
        "            memories = data.memories || [];\n"
        "            memories = _filterMemories(memories);\n"
        "            memories = _sortMemories(memories);\n"
        "            totalPages = data.total_pages || 1;\n"
        "            totalCount = data.total_count || 0;\n"
        "        }\n"
        "        renderMemoryList(el, memories, tagOptions, totalPages, totalCount, isSearch, allKnownTags);\n"
        "        bindMemoryEvents();\n"
        "        updateLastTime();\n"
        "    } catch (e) {\n"
        "        el.innerHTML = errorCard('Failed to load memories: ' + e.message);\n"
        "    }\n"
        "}\n"
        "\n"
        "/* ================================================================\n"
        "   renderMemoryList\n"
        "   ================================================================ */\n"
        "function renderMemoryList(el, memories, tagOptions, totalPages, totalCount, isSearch, allKnownTags) {\n"
        "    var selMode = S.mem.selectMode;\n"
        "    var cbClass = selMode ? 'mem-cb show' : 'mem-cb';\n"
        "    allKnownTags = allKnownTags || [];\n"
        "\n"
        "    /* ── Search bar ── */\n"
        "    var html = '<div class=\"glass p-4 mb-6\">';\n"
        "    html += '<div style=\"display:flex;gap:8px;flex-wrap:wrap;align-items:center\">';\n"
        "    html += '<input id=\"mem-search\" type=\"text\" class=\"glass-input\" style=\"flex:1;min-width:200px\" placeholder=\"Search memories...\" value=\"' + esc(S.mem.q) + '\">';\n"
        "    html += '<select id=\"mem-tag\" class=\"glass-input\">' + tagOptions + '</select>';\n"
        "    html += '<button id=\"mem-search-btn\" class=\"glass-btn\">&#128269; Search</button>';\n"
        "    html += '<button id=\"adv-search-toggle\" class=\"glass-btn\" style=\"font-size:0.8rem\">&#128269; Advanced</button>';\n"
        "    html += '</div>';\n"
        "\n"
        "    /* ── Advanced search panel ── */\n"
        "    html += '<div id=\"adv-search-panel\" class=\"adv-search-panel' + (S.mem.advOpen ? ' open' : '') + '\">';\n"
        "\n"
        "    /* Search mode */\n"
        "    html += '<div class=\"adv-search-row\" style=\"margin-top:8px\">';\n"
        "    html += '<span class=\"adv-search-label\">Mode</span>';\n"
        "    html += '<div class=\"mode-btn-group\">';\n"
        "    var modes = ['semantic','keyword','hybrid','smart'];\n"
        "    for (var mi = 0; mi < modes.length; mi++) {\n"
        "        var m = modes[mi];\n"
        "        html += '<button class=\"mode-btn adv-mode-btn' + (S.mem.searchMode === m ? ' active' : '') + '\" data-mode=\"' + m + '\">' + m + '</button>';\n"
        "    }\n"
        "    html += '</div></div>';\n"
        "\n"
        "    /* Date range */\n"
        "    html += '<div class=\"adv-search-row\">';\n"
        "    html += '<span class=\"adv-search-label\">Date From</span>';\n"
        "    html += '<input type=\"date\" id=\"adv-date-from\" class=\"glass-input\" style=\"font-size:0.8rem\" value=\"' + esc(S.mem.dateFrom) + '\">';\n"
        "    html += '<span class=\"adv-search-label\" style=\"min-width:auto\">To</span>';\n"
        "    html += '<input type=\"date\" id=\"adv-date-to\" class=\"glass-input\" style=\"font-size:0.8rem\" value=\"' + esc(S.mem.dateTo) + '\">';\n"
        "    html += '</div>';\n"
        "\n"
        "    /* Importance range */\n"
        "    html += '<div class=\"adv-search-row\">';\n"
        "    html += '<span class=\"adv-search-label\">Importance</span>';\n"
        "    html += '<span class=\"range-value\" id=\"adv-imp-min-val\">' + S.mem.impMin.toFixed(2) + '</span>';\n"
        "    html += '<input type=\"range\" class=\"glass-range\" id=\"adv-imp-min\" min=\"0\" max=\"1\" step=\"0.01\" value=\"' + S.mem.impMin + '\" style=\"max-width:140px\">';\n"
        "    html += '<span style=\"color:var(--text-muted);font-size:0.75rem\">~</span>';\n"
        "    html += '<input type=\"range\" class=\"glass-range\" id=\"adv-imp-max\" min=\"0\" max=\"1\" step=\"0.01\" value=\"' + S.mem.impMax + '\" style=\"max-width:140px\">';\n"
        "    html += '<span class=\"range-value\" id=\"adv-imp-max-val\">' + S.mem.impMax.toFixed(2) + '</span>';\n"
        "    html += '</div>';\n"
        "\n"
        "    /* Tags filter pills */\n"
        "    html += '<div class=\"adv-search-row\">';\n"
        "    html += '<span class=\"adv-search-label\">Tags</span>';\n"
        "    html += '<div class=\"filter-tags-wrap\" id=\"adv-tags-wrap\">';\n"
        "    for (var ti = 0; ti < allKnownTags.length; ti++) {\n"
        "        var t = allKnownTags[ti];\n"
        "        var isActive = S.mem.searchTags.indexOf(t) !== -1;\n"
        "        html += '<span class=\"filter-tag adv-filter-tag' + (isActive ? ' active' : '') + '\" data-tag=\"' + esc(t) + '\">' + esc(t) + '</span>';\n"
        "    }\n"
        "    if (allKnownTags.length === 0) html += '<span style=\"font-size:0.75rem;color:var(--text-muted)\">No tags available</span>';\n"
        "    html += '</div></div>';\n"
        "\n"
        "    /* Emotion filter */\n"
        "    html += '<div class=\"adv-search-row\">';\n"
        "    html += '<span class=\"adv-search-label\">Emotion</span>';\n"
        "    html += '<select id=\"adv-emotion\" class=\"glass-input\" style=\"font-size:0.8rem\">';\n"
        "    html += '<option value=\"\">Any</option>';\n"
        "    var emos = ['joy','sadness','anger','fear','surprise','disgust','trust','anticipation','calm','excitement','love','anxiety','neutral'];\n"
        "    for (var ei = 0; ei < emos.length; ei++) {\n"
        "        html += '<option value=\"' + emos[ei] + '\"' + (S.mem.emotion === emos[ei] ? ' selected' : '') + '>' + emos[ei] + '</option>';\n"
        "    }\n"
        "    html += '</select></div>';\n"
        "\n"
        "    /* Apply / Clear buttons */\n"
        "    html += '<div class=\"adv-search-row\" style=\"justify-content:flex-end;margin-top:4px\">';\n"
        "    html += '<button id=\"adv-clear-btn\" class=\"glass-btn\" style=\"font-size:0.78rem\">Clear</button>';\n"
        "    html += '<button id=\"adv-apply-btn\" class=\"glass-btn glass-btn-success\" style=\"font-size:0.78rem\">Apply Filters</button>';\n"
        "    html += '</div>';\n"
        "\n"
        "    html += '</div>'; /* close adv-search-panel */\n"
        "    html += '</div>'; /* close glass */\n"
        "\n"
        "    /* ── Toolbar row ── */\n"
        "    html += '<div class=\"mem-toolbar\">';\n"
        "    html += '<button id=\"mem-new-btn\" class=\"glass-btn glass-btn-success\" style=\"font-size:0.82rem\">&#10133; New Memory</button>';\n"
        "    html += '<button id=\"mem-select-toggle\" class=\"glass-btn\" style=\"font-size:0.82rem\">' + (selMode ? '&#9745; Select ON' : '&#9744; Select') + '</button>';\n"
        "    html += '<div class=\"mem-toolbar-spacer\"></div>';\n"
        "    html += '<select id=\"mem-sort\" class=\"glass-input mem-sort-select\">';\n"
        "    var sortOpts = [['date_desc','Newest First'],['date_asc','Oldest First'],['imp_desc','Importance \\u2193'],['str_desc','Strength \\u2193'],['updated_desc','Recently Updated']];\n"
        "    for (var si = 0; si < sortOpts.length; si++) {\n"
        "        html += '<option value=\"' + sortOpts[si][0] + '\"' + (S.mem.sort === sortOpts[si][0] ? ' selected' : '') + '>' + sortOpts[si][1] + '</option>';\n"
        "    }\n"
        "    html += '</select>';\n"
        "    html += '<div class=\"view-toggle\">';\n"
        "    html += '<button class=\"view-btn' + (S.mem.viewMode === 'card' ? ' active' : '') + '\" data-view=\"card\">&#9638; Cards</button>';\n"
        "    html += '<button class=\"view-btn' + (S.mem.viewMode === 'compact' ? ' active' : '') + '\" data-view=\"compact\">&#9776; Compact</button>';\n"
        "    html += '</div>';\n"
        "    html += '</div>';\n"
        "\n"
        "    /* ── Batch bar ── */\n"
        "    html += '<div id=\"mem-batch-bar\" class=\"mem-batch-bar' + (selMode ? ' active' : '') + '\">';\n"
        "    html += '<button id=\"batch-select-all\" class=\"glass-btn\" style=\"font-size:0.78rem\">Select All</button>';\n"
        "    html += '<button id=\"batch-deselect\" class=\"glass-btn\" style=\"font-size:0.78rem\">Deselect All</button>';\n"
        "    html += '<div class=\"mem-toolbar-spacer\"></div>';\n"
        "    html += '<button id=\"batch-delete\" class=\"glass-btn glass-btn-danger\" style=\"font-size:0.78rem\">&#128465; Delete Selected (<span id=\"batch-count\">' + S.mem.selected.size + '</span>)</button>';\n"
        "    html += '</div>';\n"
        "\n"
        "    /* ── Memory items ── */\n"
        "    html += '<div id=\"mem-list\" class=\"glass\" style=\"overflow:hidden\">';\n"
        "    if (memories.length === 0) {\n"
        "        html += '<div style=\"padding:40px;text-align:center;color:var(--text-muted)\">No memories found</div>';\n"
        "    } else if (S.mem.viewMode === 'compact') {\n"
        "        /* ── Compact view ── */\n"
        "        memories.forEach(function(m) {\n"
        "            var key = m.memory_key || m.key || '';\n"
        "            var checked = S.mem.selected.has(key) ? ' checked' : '';\n"
        "            var tags = (m.context_tags || m.tags || []);\n"
        "            var tagsHtml = tags.slice(0, 3).map(function(t){ return tagChipHtml(t); }).join(' ');\n"
        "            var impPct = m.importance != null ? (m.importance * 100) : 0;\n"
        "            var timeStr = m.created_at ? relativeTime(m.created_at) : '';\n"
        "            var memJson = JSON.stringify({\n"
        "                memory_key: key, content: m.content || '',\n"
        "                tags: tags, emotion_type: m.emotion_type || '',\n"
        "                emotion_intensity: m.emotion_intensity, importance: m.importance,\n"
        "                strength: m.strength, privacy_level: m.privacy_level || '',\n"
        "                source_context: m.source_context || '',\n"
        "                created_at: m.created_at || '', updated_at: m.updated_at || '',\n"
        "                _score: m._score != null ? m._score : null,\n"
        "                _source: m._source || ''\n"
        "            }).replace(/'/g, '&#39;');\n"
        "\n"
        "            html += '<div class=\"memory-compact\" data-memkey=\"' + esc(key) + '\" data-memjson=\\'' + memJson + '\\'>';\n"
        "            html += '<span class=\"' + cbClass + '\"><input type=\"checkbox\" class=\"mem-checkbox\" data-key=\"' + esc(key) + '\"' + checked + '></span>';\n"
        "            html += '<span class=\"mem-compact-key\">' + esc(truncate(key, 20)) + '</span>';\n"
        "            html += '<span class=\"mem-compact-content\">' + esc(truncate(m.content || '', 80)) + '</span>';\n"
        "            html += '<span class=\"mem-compact-meta\">' + tagsHtml + '</span>';\n"
        "            html += '<span class=\"mem-compact-meta\"><span class=\"mem-compact-imp\"><span class=\"mem-compact-imp-fill\" style=\"width:' + impPct + '%\"></span></span></span>';\n"
        "            html += '<span class=\"mem-compact-meta\" style=\"font-size:0.72rem;color:var(--text-muted);min-width:50px\">' + timeStr + '</span>';\n"
        "            html += '</div>';\n"
        "        });\n"
        "    } else {\n"
        "        /* ── Card view ── */\n"
        "        memories.forEach(function(m) {\n"
        "            var key = m.memory_key || m.key || '';\n"
        "            var checked = S.mem.selected.has(key) ? ' checked' : '';\n"
        "            var tags = (m.context_tags || m.tags || []);\n"
        "            var tagsHtml = tags.map(function(t){ return tagChipHtml(t); }).join(' ');\n"
        "            var emoColor = EMOTION_COLORS[m.emotion_type] || '#94a3b8';\n"
        "            var emoHtml = m.emotion_type ? '<span class=\"badge\" style=\"background:' + emoColor + '22;color:' + emoColor + ';border:1px solid ' + emoColor + '44\">' + esc(m.emotion_type) + (m.emotion_intensity != null ? '(' + m.emotion_intensity.toFixed(1) + ')' : '') + '</span>' : '';\n"
        "            var strHtml = m.strength != null ? '<span style=\"color:var(--accent-yellow)\">\\u26A1' + m.strength.toFixed(2) + '</span>' : '';\n"
        "            var timeHtml = m.created_at ? '<span>\\uD83D\\uDCC5 ' + relativeTime(m.created_at) + '</span>' : '';\n"
        "            var scoreHtml = m._score != null ? '<span class=\"badge badge-green\">Score: ' + m._score.toFixed(3) + '</span>' : '';\n"
        "            var memJson = JSON.stringify({\n"
        "                memory_key: key, content: m.content || '',\n"
        "                tags: tags, emotion_type: m.emotion_type || '',\n"
        "                emotion_intensity: m.emotion_intensity, importance: m.importance,\n"
        "                strength: m.strength, privacy_level: m.privacy_level || '',\n"
        "                source_context: m.source_context || '',\n"
        "                created_at: m.created_at || '', updated_at: m.updated_at || '',\n"
        "                _score: m._score != null ? m._score : null,\n"
        "                _source: m._source || ''\n"
        "            }).replace(/'/g, '&#39;');\n"
        "\n"
        "            html += '<div class=\"memory-card\" style=\"cursor:pointer\" data-memkey=\"' + esc(key) + '\" data-memjson=\\'' + memJson + '\\'>';\n"
        "            html += '<div style=\"display:flex;align-items:center;gap:8px\">';\n"
        "            html += '<span class=\"' + cbClass + '\"><input type=\"checkbox\" class=\"mem-checkbox\" data-key=\"' + esc(key) + '\"' + checked + '></span>';\n"
        "            html += '<div class=\"memory-key\">' + esc(key) + '</div>';\n"
        "            html += '</div>';\n"
        "            html += '<div class=\"memory-content\">' + esc(truncate(m.content || '', 200)) + '</div>';\n"
        "            html += '<div class=\"memory-meta\">' + tagsHtml + ' ' + emoHtml + ' ' + strHtml + ' ' + scoreHtml + ' ' + timeHtml + '</div>';\n"
        "            html += '</div>';\n"
        "        });\n"
        "    }\n"
        "    html += '</div>'; /* close mem-list */\n"
        "\n"
        "    /* ── Pagination ── */\n"
        "    if (!isSearch && totalPages > 0) {\n"
        "        html += '<div style=\"display:flex;justify-content:center;align-items:center;gap:12px;margin-top:16px\">';\n"
        "        html += '<button class=\"glass-btn mem-page-btn\" data-page=\"' + (S.mem.page - 1) + '\"' + (S.mem.page <= 1 ? ' disabled style=\"opacity:0.4;pointer-events:none\"' : '') + '>\\u25C0 Prev</button>';\n"
        "        html += '<span style=\"font-size:0.85rem;color:var(--text-muted)\">Page ' + S.mem.page + ' of ' + totalPages + ' (' + totalCount + ' total)</span>';\n"
        "        html += '<button class=\"glass-btn mem-page-btn\" data-page=\"' + (S.mem.page + 1) + '\"' + (S.mem.page >= totalPages ? ' disabled style=\"opacity:0.4;pointer-events:none\"' : '') + '>Next \\u25B6</button>';\n"
        "        html += '</div>';\n"
        "    }\n"
        "    el.innerHTML = html;\n"
        "}\n"
        "\n"
        "/* ================================================================\n"
        "   bindMemoryEvents\n"
        "   ================================================================ */\n"
        "function bindMemoryEvents() {\n"
        "    var searchBtn = document.getElementById('mem-search-btn');\n"
        "    var searchInput = document.getElementById('mem-search');\n"
        "    var tagSelect = document.getElementById('mem-tag');\n"
        "\n"
        "    /* Search button */\n"
        "    if (searchBtn) searchBtn.onclick = function() {\n"
        "        S.mem.q = searchInput ? searchInput.value.trim() : '';\n"
        "        S.mem.tag = tagSelect ? tagSelect.value : '';\n"
        "        S.mem.page = 1;\n"
        "        loadMemories();\n"
        "    };\n"
        "    /* Enter in search */\n"
        "    if (searchInput) searchInput.onkeydown = function(e) {\n"
        "        if (e.key === 'Enter' && searchBtn) searchBtn.click();\n"
        "    };\n"
        "    /* Tag dropdown */\n"
        "    if (tagSelect) tagSelect.onchange = function() {\n"
        "        S.mem.tag = tagSelect.value;\n"
        "        S.mem.q = '';\n"
        "        if (searchInput) searchInput.value = '';\n"
        "        S.mem.page = 1;\n"
        "        loadMemories();\n"
        "    };\n"
        "\n"
        "    /* Page buttons */\n"
        "    document.querySelectorAll('.mem-page-btn').forEach(function(btn) {\n"
        "        btn.onclick = function() { loadMemories(parseInt(btn.dataset.page)); };\n"
        "    });\n"
        "\n"
        "    /* Memory card / compact row clicks */\n"
        "    document.querySelectorAll('[data-memjson]').forEach(function(card) {\n"
        "        card.onclick = function(e) {\n"
        "            /* Don't open modal when clicking checkbox */\n"
        "            if (e.target.type === 'checkbox') return;\n"
        "            try {\n"
        "                var mem = JSON.parse(card.getAttribute('data-memjson').replace(/&#39;/g, \"'\"));\n"
        "                openMemModal(mem);\n"
        "            } catch(err) { console.error('Modal parse error', err); }\n"
        "        };\n"
        "    });\n"
        "\n"
        "    /* New Memory button */\n"
        "    var newBtn = document.getElementById('mem-new-btn');\n"
        "    if (newBtn) newBtn.onclick = function() { openCreateModal(); };\n"
        "\n"
        "    /* Select toggle */\n"
        "    var selToggle = document.getElementById('mem-select-toggle');\n"
        "    if (selToggle) selToggle.onclick = function() { toggleSelectMode(); };\n"
        "\n"
        "    /* Sort dropdown */\n"
        "    var sortSel = document.getElementById('mem-sort');\n"
        "    if (sortSel) sortSel.onchange = function() {\n"
        "        S.mem.sort = sortSel.value;\n"
        "        loadMemories();\n"
        "    };\n"
        "\n"
        "    /* View toggle */\n"
        "    document.querySelectorAll('.view-btn').forEach(function(btn) {\n"
        "        btn.onclick = function() {\n"
        "            S.mem.viewMode = btn.dataset.view;\n"
        "            loadMemories();\n"
        "        };\n"
        "    });\n"
        "\n"
        "    /* Advanced search toggle */\n"
        "    var advToggle = document.getElementById('adv-search-toggle');\n"
        "    if (advToggle) advToggle.onclick = function() { toggleAdvancedSearch(); };\n"
        "\n"
        "    /* Checkboxes */\n"
        "    document.querySelectorAll('.mem-checkbox').forEach(function(cb) {\n"
        "        cb.onchange = function() {\n"
        "            var k = cb.dataset.key;\n"
        "            if (cb.checked) S.mem.selected.add(k);\n"
        "            else S.mem.selected.delete(k);\n"
        "            var countEl = document.getElementById('batch-count');\n"
        "            if (countEl) countEl.textContent = S.mem.selected.size;\n"
        "        };\n"
        "    });\n"
        "\n"
        "    /* Batch bar buttons */\n"
        "    var batchAll = document.getElementById('batch-select-all');\n"
        "    if (batchAll) batchAll.onclick = function() {\n"
        "        document.querySelectorAll('.mem-checkbox').forEach(function(cb) {\n"
        "            cb.checked = true;\n"
        "            S.mem.selected.add(cb.dataset.key);\n"
        "        });\n"
        "        var countEl = document.getElementById('batch-count');\n"
        "        if (countEl) countEl.textContent = S.mem.selected.size;\n"
        "    };\n"
        "    var batchDesel = document.getElementById('batch-deselect');\n"
        "    if (batchDesel) batchDesel.onclick = function() {\n"
        "        document.querySelectorAll('.mem-checkbox').forEach(function(cb) { cb.checked = false; });\n"
        "        S.mem.selected.clear();\n"
        "        var countEl = document.getElementById('batch-count');\n"
        "        if (countEl) countEl.textContent = '0';\n"
        "    };\n"
        "    var batchDel = document.getElementById('batch-delete');\n"
        "    if (batchDel) batchDel.onclick = function() { batchDeleteMemories(); };\n"
        "\n"
        "    /* Advanced search: mode buttons */\n"
        "    document.querySelectorAll('.adv-mode-btn').forEach(function(btn) {\n"
        "        btn.onclick = function() {\n"
        "            document.querySelectorAll('.adv-mode-btn').forEach(function(b){ b.classList.remove('active'); });\n"
        "            btn.classList.add('active');\n"
        "            S.mem.searchMode = btn.dataset.mode;\n"
        "        };\n"
        "    });\n"
        "\n"
        "    /* Advanced search: importance sliders live update */\n"
        "    var impMinSlider = document.getElementById('adv-imp-min');\n"
        "    var impMaxSlider = document.getElementById('adv-imp-max');\n"
        "    if (impMinSlider) impMinSlider.oninput = function() {\n"
        "        var v = document.getElementById('adv-imp-min-val');\n"
        "        if (v) v.textContent = parseFloat(impMinSlider.value).toFixed(2);\n"
        "    };\n"
        "    if (impMaxSlider) impMaxSlider.oninput = function() {\n"
        "        var v = document.getElementById('adv-imp-max-val');\n"
        "        if (v) v.textContent = parseFloat(impMaxSlider.value).toFixed(2);\n"
        "    };\n"
        "\n"
        "    /* Advanced search: filter tag pills toggle */\n"
        "    document.querySelectorAll('.adv-filter-tag').forEach(function(pill) {\n"
        "        pill.onclick = function() { pill.classList.toggle('active'); };\n"
        "    });\n"
        "\n"
        "    /* Advanced search: Apply */\n"
        "    var advApply = document.getElementById('adv-apply-btn');\n"
        "    if (advApply) advApply.onclick = function() { applyAdvancedSearch(); };\n"
        "\n"
        "    /* Advanced search: Clear */\n"
        "    var advClear = document.getElementById('adv-clear-btn');\n"
        "    if (advClear) advClear.onclick = function() { clearAdvancedSearch(); };\n"
        "\n"
        "    /* Edit modal: importance slider live update */\n"
        "    var editImp = document.getElementById('edit-importance');\n"
        "    if (editImp) editImp.oninput = function() {\n"
        "        var v = document.getElementById('edit-imp-val');\n"
        "        if (v) v.textContent = parseFloat(editImp.value).toFixed(2);\n"
        "    };\n"
        "    /* Edit modal: emotion intensity slider live update */\n"
        "    var editEmo = document.getElementById('edit-emo-intensity');\n"
        "    if (editEmo) editEmo.oninput = function() {\n"
        "        var v = document.getElementById('edit-emo-val');\n"
        "        if (v) v.textContent = parseFloat(editEmo.value).toFixed(2);\n"
        "    };\n"
        "    /* Edit modal: tag input Enter to add */\n"
        "    var tagInput = document.getElementById('edit-tag-input');\n"
        "    if (tagInput) tagInput.onkeydown = function(e) {\n"
        "        if (e.key === 'Enter') {\n"
        "            e.preventDefault();\n"
        "            var val = tagInput.value.trim();\n"
        "            if (!val) return;\n"
        "            _addEditTag(val);\n"
        "            tagInput.value = '';\n"
        "        }\n"
        "    };\n"
        "}\n"
        "\n"
        "/* ================================================================\n"
        "   openMemModal \u2014 OVERRIDE base.py version\n"
        "   ================================================================ */\n"
        "function openMemModal(mem) {\n"
        "    var overlay = document.getElementById('mem-modal-overlay');\n"
        "    var content = document.getElementById('mem-modal-content');\n"
        "    if (!overlay || !content) return;\n"
        "\n"
        "    var tags = (mem.tags || []);\n"
        "    var tagsHtml = tags.map(function(t){ return tagChipHtml(t); }).join(' ');\n"
        "    var emoColor = EMOTION_COLORS[mem.emotion_type] || '#94a3b8';\n"
        "\n"
        "    var h = '';\n"
        "    h += '<div class=\"mem-modal-header\">';\n"
        "    h += '<div>';\n"
        "    h += '<div style=\"font-size:0.7rem;color:var(--text-muted);margin-bottom:4px\">Memory Key</div>';\n"
        "    h += '<div style=\"display:flex;align-items:center;gap:6px\">';\n"
        "    h += '<span style=\"font-family:monospace;font-size:0.85rem;color:var(--accent-purple)\">' + esc(mem.memory_key) + '</span>';\n"
        "    h += '<button class=\"copy-btn\" onclick=\"navigator.clipboard.writeText(\\'' + esc(mem.memory_key).replace(/'/g,'\\\\\\'')"
        " + '\\');toast(\\'Key copied!\\',\\'info\\')\" title=\"Copy key\">\\uD83D\\uDCCB</button>';\n"
        "    h += '</div></div>';\n"
        "    h += '<button class=\"mem-modal-close\" onclick=\"closeMemModal()\">\\u2715</button>';\n"
        "    h += '</div>';\n"
        "\n"
        "    /* Full content */\n"
        "    h += '<div class=\"mem-modal-content\">' + esc(mem.content) + '</div>';\n"
        "\n"
        "    /* Tags */\n"
        "    if (tagsHtml) {\n"
        "        h += '<div class=\"mem-modal-row\"><span class=\"mem-modal-key\">Tags</span><span>' + tagsHtml + '</span></div>';\n"
        "    }\n"
        "\n"
        "    /* Emotion */\n"
        "    if (mem.emotion_type) {\n"
        "        h += '<div class=\"mem-modal-row\"><span class=\"mem-modal-key\">Emotion</span><span>';\n"
        "        h += '<span class=\"badge\" style=\"background:' + emoColor + '22;color:' + emoColor + ';border:1px solid ' + emoColor + '44\">' + esc(mem.emotion_type) + '</span>';\n"
        "        if (mem.emotion_intensity != null) {\n"
        "            h += ' <div class=\"modal-progress\" style=\"display:inline-flex;width:120px;vertical-align:middle\">';\n"
        "            h += '<div class=\"modal-progress-bar\"><div class=\"modal-progress-fill\" style=\"width:' + (mem.emotion_intensity * 100) + '%;background:' + emoColor + '\"></div></div>';\n"
        "            h += '<span style=\"font-size:0.75rem;color:' + emoColor + '\">' + mem.emotion_intensity.toFixed(2) + '</span></div>';\n"
        "        }\n"
        "        h += '</span></div>';\n"
        "    }\n"
        "\n"
        "    /* Importance */\n"
        "    if (mem.importance != null) {\n"
        "        h += '<div class=\"mem-modal-row\"><span class=\"mem-modal-key\">Importance</span><span>';\n"
        "        h += '<div class=\"modal-progress\" style=\"display:inline-flex;width:160px\">';\n"
        "        h += '<div class=\"modal-progress-bar\"><div class=\"modal-progress-fill\" style=\"width:' + (mem.importance * 100) + '%;background:linear-gradient(90deg,var(--accent-purple),var(--accent-yellow))\"></div></div>';\n"
        "        h += '<span style=\"font-size:0.78rem;color:var(--accent-yellow);font-weight:600\">' + mem.importance.toFixed(2) + '</span></div>';\n"
        "        h += '</span></div>';\n"
        "    }\n"
        "\n"
        "    /* Strength */\n"
        "    if (mem.strength != null) {\n"
        "        h += '<div class=\"mem-modal-row\"><span class=\"mem-modal-key\">Strength</span><span>';\n"
        "        h += '<div class=\"modal-progress\" style=\"display:inline-flex;width:160px\">';\n"
        "        h += '<div class=\"modal-progress-bar\"><div class=\"modal-progress-fill\" style=\"width:' + Math.min(mem.strength * 100, 100) + '%;background:linear-gradient(90deg,var(--accent-green),var(--accent-blue))\"></div></div>';\n"
        "        h += '<span style=\"font-size:0.78rem;color:var(--accent-green);font-weight:600\">' + mem.strength.toFixed(3) + '</span></div>';\n"
        "        h += '</span></div>';\n"
        "    }\n"
        "\n"
        "    /* Score (search) */\n"
        "    if (mem._score != null) {\n"
        "        h += '<div class=\"mem-modal-row\"><span class=\"mem-modal-key\">Search Score</span><span class=\"badge badge-green\">' + mem._score.toFixed(3) + '</span></div>';\n"
        "    }\n"
        "\n"
        "    /* Privacy */\n"
        "    if (mem.privacy_level) {\n"
        "        h += '<div class=\"mem-modal-row\"><span class=\"mem-modal-key\">Privacy</span><span>' + esc(mem.privacy_level) + '</span></div>';\n"
        "    }\n"
        "\n"
        "    /* Source context */\n"
        "    if (mem.source_context) {\n"
        "        h += '<div class=\"mem-modal-row\"><span class=\"mem-modal-key\">Source</span><span style=\"color:var(--text-muted)\">' + esc(mem.source_context) + '</span></div>';\n"
        "    }\n"
        "\n"
        "    /* Created at */\n"
        "    if (mem.created_at) {\n"
        "        h += '<div class=\"mem-modal-row\"><span class=\"mem-modal-key\">Created</span><span>\\uD83D\\uDCC5 ' + relativeTime(mem.created_at)"
        " + ' <span style=\"color:var(--text-muted);font-size:0.75rem\">(' + new Date(mem.created_at).toLocaleString() + ')</span></span></div>';\n"
        "    }\n"
        "\n"
        "    /* Updated at */\n"
        "    if (mem.updated_at) {\n"
        "        h += '<div class=\"mem-modal-row\"><span class=\"mem-modal-key\">Updated</span><span>\\uD83D\\uDCC5 ' + relativeTime(mem.updated_at)"
        " + ' <span style=\"color:var(--text-muted);font-size:0.75rem\">(' + new Date(mem.updated_at).toLocaleString() + ')</span></span></div>';\n"
        "    }\n"
        "\n"
        "    /* Action buttons */\n"
        "    h += '<div style=\"display:flex;gap:8px;margin-top:16px;justify-content:flex-end\">';\n"
        "    h += '<button class=\"glass-btn glass-btn-danger\" onclick=\"deleteMemory(\\'' + esc(mem.memory_key).replace(/'/g,'\\\\\\'') + '\\')\">\\uD83D\\uDDD1 Delete</button>';\n"
        "    h += '<button class=\"glass-btn glass-btn-success\" id=\"mem-modal-edit-btn\">\\u270F\\uFE0F Edit</button>';\n"
        "    h += '</div>';\n"
        "\n"
        "    content.innerHTML = h;\n"
        "    overlay.style.display = 'flex';\n"
        "    document.addEventListener('keydown', _memModalKeyHandler);\n"
        "\n"
        "    /* Bind the edit button - we store the mem object in closure */\n"
        "    var editBtn = document.getElementById('mem-modal-edit-btn');\n"
        "    if (editBtn) editBtn.onclick = function() { openEditModal(mem); };\n"
        "}\n"
        "\n"
        "/* ================================================================\n"
        "   openEditModal / openCreateModal\n"
        "   ================================================================ */\n"
        "var _editTags = [];\n"
        "\n"
        "function _renderEditTags() {\n"
        "    var wrap = document.getElementById('edit-tags-wrap');\n"
        "    if (!wrap) return;\n"
        "    /* Remove existing chips, keep the input */\n"
        "    var chips = wrap.querySelectorAll('.tag-chip-edit');\n"
        "    chips.forEach(function(c){ c.remove(); });\n"
        "    var inp = document.getElementById('edit-tag-input');\n"
        "    _editTags.forEach(function(tag, idx) {\n"
        "        var hue = hashToHue(tag);\n"
        "        var chip = document.createElement('span');\n"
        "        chip.className = 'tag-chip-edit';\n"
        "        chip.style.cssText = '--chip-hue:' + hue;\n"
        "        chip.innerHTML = esc(tag) + ' <span class=\"tag-chip-remove\" data-tidx=\"' + idx + '\">\\u00D7</span>';\n"
        "        wrap.insertBefore(chip, inp);\n"
        "    });\n"
        "    /* Bind remove buttons */\n"
        "    wrap.querySelectorAll('.tag-chip-remove').forEach(function(btn) {\n"
        "        btn.onclick = function(e) {\n"
        "            e.stopPropagation();\n"
        "            var i = parseInt(btn.dataset.tidx);\n"
        "            _editTags.splice(i, 1);\n"
        "            _renderEditTags();\n"
        "        };\n"
        "    });\n"
        "}\n"
        "\n"
        "function _addEditTag(val) {\n"
        "    val = val.trim().toLowerCase();\n"
        "    if (!val || _editTags.indexOf(val) !== -1) return;\n"
        "    _editTags.push(val);\n"
        "    _renderEditTags();\n"
        "}\n"
        "\n"
        "function openEditModal(mem) {\n"
        "    document.getElementById('edit-modal-title').textContent = 'Edit Memory';\n"
        "    document.getElementById('edit-content').value = mem.content || '';\n"
        "    document.getElementById('edit-memory-key').value = mem.memory_key || '';\n"
        "\n"
        "    var imp = mem.importance != null ? mem.importance : 0.5;\n"
        "    document.getElementById('edit-importance').value = imp;\n"
        "    document.getElementById('edit-imp-val').textContent = imp.toFixed(2);\n"
        "\n"
        "    document.getElementById('edit-emotion').value = mem.emotion_type || '';\n"
        "\n"
        "    var emoInt = mem.emotion_intensity != null ? mem.emotion_intensity : 0;\n"
        "    document.getElementById('edit-emo-intensity').value = emoInt;\n"
        "    document.getElementById('edit-emo-val').textContent = emoInt.toFixed(2);\n"
        "\n"
        "    _editTags = (mem.tags || []).slice();\n"
        "    _renderEditTags();\n"
        "\n"
        "    document.getElementById('mem-edit-overlay').classList.add('active');\n"
        "}\n"
        "\n"
        "function openCreateModal() {\n"
        "    document.getElementById('edit-modal-title').textContent = 'New Memory';\n"
        "    document.getElementById('edit-content').value = '';\n"
        "    document.getElementById('edit-memory-key').value = '';\n"
        "\n"
        "    document.getElementById('edit-importance').value = 0.5;\n"
        "    document.getElementById('edit-imp-val').textContent = '0.50';\n"
        "\n"
        "    document.getElementById('edit-emotion').value = '';\n"
        "\n"
        "    document.getElementById('edit-emo-intensity').value = 0;\n"
        "    document.getElementById('edit-emo-val').textContent = '0.00';\n"
        "\n"
        "    _editTags = [];\n"
        "    _renderEditTags();\n"
        "\n"
        "    document.getElementById('mem-edit-overlay').classList.add('active');\n"
        "}\n"
        "\n"
        "function closeEditModal() {\n"
        "    document.getElementById('mem-edit-overlay').classList.remove('active');\n"
        "}\n"
        "\n"
        "/* ================================================================\n"
        "   saveMemory\n"
        "   ================================================================ */\n"
        "async function saveMemory() {\n"
        "    var contentVal = document.getElementById('edit-content').value.trim();\n"
        "    if (!contentVal) { toast('Content is required', 'error'); return; }\n"
        "\n"
        "    var key = document.getElementById('edit-memory-key').value;\n"
        "    var imp = parseFloat(document.getElementById('edit-importance').value);\n"
        "    var emoType = document.getElementById('edit-emotion').value;\n"
        "    var emoInt = parseFloat(document.getElementById('edit-emo-intensity').value);\n"
        "\n"
        "    var body = { content: contentVal, importance: imp, tags: _editTags.slice() };\n"
        "    if (emoType) { body.emotion_type = emoType; body.emotion_intensity = emoInt; }\n"
        "\n"
        "    try {\n"
        "        if (key) {\n"
        "            /* Update existing */\n"
        "            await api('/api/memories/' + encodeURIComponent(S.persona) + '/' + encodeURIComponent(key), {\n"
        "                method: 'PUT', body: JSON.stringify(body)\n"
        "            });\n"
        "            toast('Memory updated', 'success');\n"
        "        } else {\n"
        "            /* Create new */\n"
        "            await api('/api/memories/' + encodeURIComponent(S.persona), {\n"
        "                method: 'POST', body: JSON.stringify(body)\n"
        "            });\n"
        "            toast('Memory created', 'success');\n"
        "        }\n"
        "        closeEditModal();\n"
        "        closeMemModal();\n"
        "        loadMemories();\n"
        "    } catch (e) {\n"
        "        toast('Save failed: ' + e.message, 'error');\n"
        "    }\n"
        "}\n"
        "\n"
        "/* ================================================================\n"
        "   deleteMemory\n"
        "   ================================================================ */\n"
        "async function deleteMemory(key) {\n"
        "    if (!confirm('Are you sure? This cannot be undone.')) return;\n"
        "    try {\n"
        "        await api('/api/memories/' + encodeURIComponent(S.persona) + '/' + encodeURIComponent(key), {\n"
        "            method: 'DELETE'\n"
        "        });\n"
        "        toast('Memory deleted', 'success');\n"
        "        closeMemModal();\n"
        "        loadMemories();\n"
        "    } catch (e) {\n"
        "        toast('Delete failed: ' + e.message, 'error');\n"
        "    }\n"
        "}\n"
        "\n"
        "/* ================================================================\n"
        "   batchDeleteMemories\n"
        "   ================================================================ */\n"
        "async function batchDeleteMemories() {\n"
        "    var keys = Array.from(S.mem.selected);\n"
        "    if (keys.length === 0) { toast('No memories selected', 'error'); return; }\n"
        "    if (!confirm('Delete ' + keys.length + ' memories? This cannot be undone.')) return;\n"
        "\n"
        "    var ok = 0, fail = 0;\n"
        "    for (var i = 0; i < keys.length; i++) {\n"
        "        try {\n"
        "            await api('/api/memories/' + encodeURIComponent(S.persona) + '/' + encodeURIComponent(keys[i]), {\n"
        "                method: 'DELETE'\n"
        "            });\n"
        "            ok++;\n"
        "        } catch (e) { fail++; }\n"
        "    }\n"
        "    S.mem.selected.clear();\n"
        "    toast('Deleted ' + ok + ' memories' + (fail ? ', ' + fail + ' failed' : ''), fail ? 'error' : 'success');\n"
        "    loadMemories();\n"
        "}\n"
        "\n"
        "/* ================================================================\n"
        "   toggleSelectMode\n"
        "   ================================================================ */\n"
        "function toggleSelectMode() {\n"
        "    S.mem.selectMode = !S.mem.selectMode;\n"
        "    if (!S.mem.selectMode) S.mem.selected.clear();\n"
        "    loadMemories();\n"
        "}\n"
        "\n"
        "/* ================================================================\n"
        "   toggleAdvancedSearch\n"
        "   ================================================================ */\n"
        "function toggleAdvancedSearch() {\n"
        "    S.mem.advOpen = !S.mem.advOpen;\n"
        "    var panel = document.getElementById('adv-search-panel');\n"
        "    if (panel) {\n"
        "        if (S.mem.advOpen) panel.classList.add('open');\n"
        "        else panel.classList.remove('open');\n"
        "    }\n"
        "}\n"
        "\n"
        "/* ================================================================\n"
        "   applyAdvancedSearch\n"
        "   ================================================================ */\n"
        "function applyAdvancedSearch() {\n"
        "    var df = document.getElementById('adv-date-from');\n"
        "    var dt = document.getElementById('adv-date-to');\n"
        "    var impMin = document.getElementById('adv-imp-min');\n"
        "    var impMax = document.getElementById('adv-imp-max');\n"
        "    var emo = document.getElementById('adv-emotion');\n"
        "\n"
        "    S.mem.dateFrom = df ? df.value : '';\n"
        "    S.mem.dateTo = dt ? dt.value : '';\n"
        "    S.mem.impMin = impMin ? parseFloat(impMin.value) : 0;\n"
        "    S.mem.impMax = impMax ? parseFloat(impMax.value) : 1;\n"
        "    S.mem.emotion = emo ? emo.value : '';\n"
        "\n"
        "    /* Gather active tag pills */\n"
        "    S.mem.searchTags = [];\n"
        "    document.querySelectorAll('.adv-filter-tag.active').forEach(function(pill) {\n"
        "        S.mem.searchTags.push(pill.dataset.tag);\n"
        "    });\n"
        "\n"
        "    loadMemories(1);\n"
        "}\n"
        "\n"
        "/* ================================================================\n"
        "   clearAdvancedSearch\n"
        "   ================================================================ */\n"
        "function clearAdvancedSearch() {\n"
        "    S.mem.dateFrom = '';\n"
        "    S.mem.dateTo = '';\n"
        "    S.mem.impMin = 0;\n"
        "    S.mem.impMax = 1;\n"
        "    S.mem.searchTags = [];\n"
        "    S.mem.emotion = '';\n"
        "    S.mem.searchMode = 'hybrid';\n"
        "    loadMemories(1);\n"
        "}\n"
    )
