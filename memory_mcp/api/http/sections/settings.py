"""Settings tab section for the MemoryMCP Dashboard.

Renders the settings configuration panel with live hot-reload support,
source-priority display (env > override > default), settings profiles,
search/filter, field validation, and dependency rules.
"""


def render_settings_tab() -> str:
    """Return the HTML for the Settings tab panel with skeleton loader and inline CSS."""
    return """
        <style>
        .setting-category-card .cat-body { transition: max-height 0.3s ease; overflow: hidden; }
        .setting-diff-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--accent-blue); display: inline-block; }
        .setting-reset-btn { background: rgba(96,165,250,0.1); border: 1px solid rgba(96,165,250,0.2); border-radius: 8px; color: var(--accent-blue); cursor: pointer; font-size: 0.72rem; padding: 4px 10px; transition: all 0.2s; white-space: nowrap; }
        .setting-reset-btn:hover { background: rgba(96,165,250,0.2); }
        .cat-reset-btn { background: rgba(96,165,250,0.08); border: 1px solid rgba(96,165,250,0.15); border-radius: 8px; color: var(--accent-blue); cursor: pointer; font-size: 0.72rem; padding: 3px 10px; transition: all 0.2s; }
        .cat-reset-btn:hover { background: rgba(96,165,250,0.18); }
        .cat-toggle-btn { background: none; border: none; color: var(--text-muted); cursor: pointer; font-size: 0.9rem; padding: 2px 6px; transition: transform 0.2s; }
        .profile-chip { transition: all 0.2s; }
        .profile-chip:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(167,139,250,0.2); }
        </style>
        <!-- ========== SETTINGS TAB ========== -->
        <section id="tab-settings" class="tab-panel" role="tabpanel">
            <div id="settings-content">
                <div class="glass p-6"><div class="skeleton skeleton-title"></div><div class="skeleton skeleton-text"></div><div class="skeleton skeleton-text" style="width:70%"></div></div>
            </div>
        </section>"""


def render_settings_js() -> str:
    """Return the JavaScript for settings management.

    Contains: CONSTANTS, loadSettings(), sourceIcon(), renderSettings(),
    filterSettings(), toggleCategory(), resetField(), resetCategory(),
    applyDependsRules(), validateField(), saveProfile(), loadProfile(),
    deleteProfile(), renderProfiles(), startStatusPoll().
    Returns a plain string — no <script> tags.
    """
    return """
const DEPENDS_RULES = {
    'summarization.use_llm': { field: 'summarization.enabled', value: true },
    'summarization.llm_api_url': { field: 'summarization.use_llm', value: true },
    'summarization.llm_api_key': { field: 'summarization.use_llm', value: true },
    'summarization.llm_model': { field: 'summarization.use_llm', value: true },
    'summarization.llm_max_tokens': { field: 'summarization.use_llm', value: true },
    'summarization.check_interval_seconds': { field: 'summarization.enabled', value: true },
    'summarization.min_importance': { field: 'summarization.enabled', value: true }
};

const BUILTIN_PROFILES = {
    'Development': {
        server: { host: '0.0.0.0', port: 26262 },
        embedding: { model: 'cl-nagoya/ruri-v3-30m', device: 'cpu', batch_size: 32 },
        reranker: { model: 'hotchpotch/japanese-reranker-xsmall-v2', enabled: true },
        general: { log_level: 'DEBUG', contradiction_threshold: 0.85, duplicate_threshold: 0.90 },
        forgetting: { enabled: true, decay_interval_seconds: 3600, min_strength: 0.01 }
    },
    'Production': {
        embedding: { model: 'cl-nagoya/ruri-v3-30m', device: 'auto', batch_size: 64 },
        reranker: { model: 'hotchpotch/japanese-reranker-xsmall-v2', enabled: true },
        general: { log_level: 'WARNING', contradiction_threshold: 0.85, duplicate_threshold: 0.90 },
        forgetting: { enabled: true, decay_interval_seconds: 1800, min_strength: 0.01 }
    }
};

const CATEGORY_ICONS = {
    server: '🖥️', embedding: '🧠', reranker: '🔍', qdrant: '📦',
    worker: '⏰', general: '⚙️', search: '🔎', persona: '👤',
    summarization: '🤖', forgetting: '🧹'
};

async function loadSettings() {
    const el = document.getElementById('settings-content');
    try {
        const [resp, status] = await Promise.all([
            api('/api/settings'),
            api('/api/settings/status')
        ]);
        const settingsData = resp.settings || resp;
        S.settingsData = settingsData;
        S.settingsReloadStatus = status;
        renderSettings(el, settingsData, status);
        updateLastTime();
    } catch (e) {
        el.innerHTML = errorCard('Failed to load settings: ' + e.message);
    }
}

function sourceIcon(src) {
    if (src === 'env') return '<span class="setting-source source-env">🌐 env</span>';
    if (src === 'override') return '<span class="setting-source source-override">📝 override</span>';
    return '<span class="setting-source source-default">📋 default</span>';
}

function renderSettings(el, settings, status) {
    const reloadStatus = (status && status.reload_status) || {};
    let html = '';

    /* ── Profiles section ── */
    html += '<div class="glass p-4 mb-6">';
    html += '<div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px">';
    html += '<h3 style="font-size:1rem;font-weight:600;color:var(--text-primary)">📋 Settings Profiles</h3>';
    html += '<button id="save-profile-btn" class="glass-btn" style="padding:6px 14px;font-size:0.8rem">💾 Save Current as Profile</button>';
    html += '</div>';
    html += '<div id="profiles-list" style="display:flex;flex-wrap:wrap;gap:8px;margin-top:12px"></div>';
    html += '</div>';

    /* ── Search bar ── */
    html += '<div class="glass p-4 mb-6" style="position:sticky;top:120px;z-index:30">';
    html += '<div style="position:relative">';
    html += '<span style="position:absolute;left:14px;top:50%;transform:translateY(-50%);color:var(--text-muted);font-size:0.9rem">🔍</span>';
    html += '<input id="settings-search" type="text" class="glass-input" placeholder="Search settings..." style="width:100%;padding-left:38px;padding-right:36px;font-size:0.9rem" oninput="filterSettings(this.value)">';
    html += '<button id="settings-search-clear" style="position:absolute;right:10px;top:50%;transform:translateY(-50%);background:none;border:none;color:var(--text-muted);cursor:pointer;font-size:0.85rem;display:none">✕</button>';
    html += '</div>';
    html += '</div>';

    /* ── Category cards ── */
    for (const [cat, fields] of Object.entries(settings)) {
        if (cat === 'reload_status') continue;
        if (typeof fields !== 'object' || fields === null) continue;
        const hasFields = Object.values(fields).some(f => typeof f === 'object' && f !== null);
        if (!hasFields) continue;

        const icon = CATEGORY_ICONS[cat] || '⚙️';
        const catLabel = cat.charAt(0).toUpperCase() + cat.slice(1);

        /* Diff detection for category */
        let hasDiffs = false;
        const catSearchText = cat + ' ' + catLabel;
        for (const [key, meta] of Object.entries(fields)) {
            if (typeof meta !== 'object' || meta === null) continue;
            if (meta.value != null && meta.default_value != null && String(meta.value) !== '***') {
                if (String(meta.value) !== String(meta.default_value)) { hasDiffs = true; break; }
            }
        }

        /* Reload status */
        const catStatus = reloadStatus[cat];
        let statusHtml = '';
        if (catStatus && catStatus.status && catStatus.status !== 'idle') {
            const st = catStatus.status;
            if (st === 'loading' || st === 'reloading') {
                statusHtml = '<div style="margin-top:8px"><div style="font-size:0.78rem;color:var(--accent-yellow);margin-bottom:4px">⏳ ' + esc(catStatus.message || 'Loading...') + '</div><div class="progress-wrap"><div class="progress-bar progress-indeterminate"></div></div></div>';
            } else if (st === 'ready' || st === 'success') {
                statusHtml = '<div style="margin-top:8px;font-size:0.78rem;color:var(--accent-green)">✅ ' + esc(catStatus.message || 'Ready') + '</div>';
            } else if (st === 'error') {
                statusHtml = '<div style="margin-top:8px;font-size:0.78rem;color:var(--accent-red)">❌ ' + esc(catStatus.message || 'Error') + '</div>';
            }
        }

        /* Card wrapper */
        html += '<div class="glass p-6 mb-6 setting-category-card" data-category="' + esc(cat) + '" data-searchtext="' + esc(catSearchText) + '">';
        html += '<div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;margin-bottom:16px">';
        html += '<div style="display:flex;align-items:center;gap:10px">';
        html += '<button class="cat-toggle-btn" id="cat-toggle-' + cat + '" data-toggle-cat="' + cat + '">▼</button>';
        html += '<span class="card-title" style="margin:0">' + icon + ' ' + esc(catLabel) + ' Settings</span>';
        html += '</div>';
        if (hasDiffs) {
            html += '<button class="cat-reset-btn" data-reset-cat="' + cat + '">↩ Reset Category</button>';
        }
        html += '</div>';
        html += statusHtml;
        html += '<div id="cat-body-' + cat + '" class="cat-body">';

        /* ── Fields ── */
        for (const [key, meta] of Object.entries(fields)) {
            if (typeof meta !== 'object' || meta === null) continue;
            const val = meta.value != null ? meta.value : '';
            const defaultVal = meta.default_value;
            const src = meta.source || 'default';
            const hot = meta.hot_reload !== false;
            const inputId = 'setting-' + cat + '-' + key;
            const isPassword = key.toLowerCase().includes('key') || key.toLowerCase().includes('password') || key.toLowerCase().includes('secret');
            const isBool = val === true || val === false;
            const desc = meta.description || '';
            const isMasked = String(val) === '***';
            const isDiff = !isMasked && defaultVal != null && String(val) !== String(defaultVal);
            const reloadHint = hot ? '🔄 Hot-reload OK' : '🔒 Requires restart';
            const tooltipText = reloadHint + (meta.reload_time ? ' (⏱ ' + meta.reload_time + ')' : '');
            const searchText = key.replace(/_/g, ' ') + ' ' + desc + ' ' + cat;

            html += '<div class="setting-row" data-setting-key="' + cat + '.' + key + '" data-category="' + cat + '" data-searchtext="' + esc(searchText) + '">';

            /* Label column with blue dot */
            html += '<div style="display:flex;flex-direction:column;gap:2px;flex:0 0 auto;min-width:160px;position:relative">';
            html += '<span class="setting-diff-dot" style="' + (isDiff ? '' : 'display:none;') + 'position:absolute;left:-14px;top:8px;width:8px;height:8px;border-radius:50%;background:var(--accent-blue)"></span>';
            html += '<label class="setting-label" for="' + inputId + '" title="' + esc(tooltipText) + '" style="margin-bottom:0">' + esc(key.replace(/_/g, ' ')) + '</label>';
            if (desc) html += '<span style="font-size:0.7rem;color:var(--text-muted);line-height:1.3">' + esc(desc) + '</span>';
            html += '</div>';

            /* Source icon */
            html += sourceIcon(src);

            /* Lock icon */
            if (!hot) html += '<span title="Restart required" style="cursor:help">🔒</span>';

            /* Input element */
            if (key === 'log_level') {
                html += '<select id="' + inputId + '" class="glass-input" style="flex:1;min-width:120px" data-cat="' + esc(cat) + '" data-key="' + esc(key) + '">';
                ['DEBUG','INFO','WARNING','ERROR','CRITICAL'].forEach(lv => {
                    html += '<option value="' + lv + '"' + (String(val).toUpperCase() === lv ? ' selected' : '') + '>' + lv + '</option>';
                });
                html += '</select>';
            } else if (key === 'device') {
                html += '<select id="' + inputId + '" class="glass-input" style="flex:1;min-width:120px" data-cat="' + esc(cat) + '" data-key="' + esc(key) + '">';
                ['cpu','cuda','mps','auto'].forEach(d => {
                    html += '<option value="' + d + '"' + (String(val) === d ? ' selected' : '') + '>' + d + '</option>';
                });
                html += '</select>';
            } else if (isBool) {
                html += '<select id="' + inputId + '" class="glass-input" style="flex:1;min-width:120px" data-cat="' + esc(cat) + '" data-key="' + esc(key) + '">';
                html += '<option value="true"' + (val === true ? ' selected' : '') + '>true</option>';
                html += '<option value="false"' + (val === false ? ' selected' : '') + '>false</option>';
                html += '</select>';
            } else {
                const inputType = isPassword ? 'password' : (typeof val === 'number' ? 'number' : 'text');
                html += '<input id="' + inputId + '" type="' + inputType + '" class="glass-input" style="flex:1;min-width:160px" value="' + esc(String(val)) + '" data-cat="' + esc(cat) + '" data-key="' + esc(key) + '"' + (typeof val === 'number' ? ' step="any"' : '') + '>';
            }

            /* Apply button */
            html += '<button class="glass-btn setting-apply-btn" data-cat="' + esc(cat) + '" data-key="' + esc(key) + '" data-input="' + inputId + '" style="padding:6px 12px;font-size:0.78rem">' + (hot ? '✅ Apply' : '🔒 Apply*') + '</button>';

            /* Reset button (hidden when no diff) */
            html += '<button class="setting-reset-btn" data-cat="' + esc(cat) + '" data-key="' + esc(key) + '" style="' + (isDiff ? '' : 'display:none;') + 'padding:4px 10px;font-size:0.72rem">↩ Reset</button>';

            /* Restart hint */
            if (!hot) html += '<span style="font-size:0.7rem;color:var(--accent-yellow)">Restart required</span>';

            /* Validation error placeholder */
            html += '<div class="setting-validation-error" style="display:none;width:100%;font-size:0.72rem;color:var(--accent-red);margin-top:2px"></div>';

            html += '</div>'; /* end setting-row */
        }

        html += '</div>'; /* end cat-body */
        html += '</div>'; /* end category card */
    }

    /* ── Source legend & action buttons ── */
    html += '<div class="glass p-6">';
    html += '<div class="card-title">💾 Configuration Source Priority</div>';
    html += '<div style="font-size:0.85rem;color:var(--text-secondary);margin-bottom:16px">';
    html += '<span class="setting-source source-env">🌐 env</span>';
    html += '<span style="margin:0 8px">></span>';
    html += '<span class="setting-source source-override">📝 override</span>';
    html += '<span style="margin:0 8px">></span>';
    html += '<span class="setting-source source-default">📋 default</span>';
    html += '</div>';
    html += '<div style="display:flex;gap:10px;flex-wrap:wrap">';
    html += '<button id="export-config-btn" class="glass-btn-success glass-btn">📤 Export Config</button>';
    html += '<button id="reset-config-btn" class="glass-btn-danger glass-btn">🗑️ Reset All to Defaults</button>';
    html += '</div>';
    html += '</div>';

    el.innerHTML = html;

    /* ═══════════════════════ EVENT BINDING ═══════════════════════ */

    /* Save profile button */
    var saveProfileBtn = document.getElementById('save-profile-btn');
    if (saveProfileBtn) saveProfileBtn.onclick = saveProfile;

    /* Search clear button */
    var searchClearBtn = document.getElementById('settings-search-clear');
    if (searchClearBtn) searchClearBtn.onclick = function() {
        document.getElementById('settings-search').value = '';
        filterSettings('');
    };

    /* Category toggle buttons */
    document.querySelectorAll('.cat-toggle-btn').forEach(function(btn) {
        btn.onclick = function() { toggleCategory(this.dataset.toggleCat); };
    });

    /* Category reset buttons */
    document.querySelectorAll('.cat-reset-btn').forEach(function(btn) {
        btn.onclick = function() { resetCategory(this.dataset.resetCat); };
    });

    /* Per-field reset buttons */
    document.querySelectorAll('.setting-reset-btn').forEach(function(btn) {
        btn.onclick = function() {
            var cat = this.dataset.cat;
            var key = this.dataset.key;
            var meta = S.settingsData && S.settingsData[cat] && S.settingsData[cat][key];
            if (meta && meta.default_value != null) resetField(cat, key, meta.default_value);
        };
    });

    /* Apply buttons */
    document.querySelectorAll('.setting-apply-btn').forEach(function(btn) {
        btn.onclick = async function() {
            var cat = btn.dataset.cat;
            var key = btn.dataset.key;
            var input = document.getElementById(btn.dataset.input);
            var value = input.value;
            /* Type coercion */
            if (input.tagName === 'SELECT') {
                if (value === 'true') value = true;
                else if (value === 'false') value = false;
            } else if (input.type === 'number') {
                value = parseFloat(value);
            }
            /* Validation */
            var meta = S.settingsData && S.settingsData[cat] && S.settingsData[cat][key];
            if (meta) {
                var result = validateField(cat, key, value, meta);
                if (!result.valid) {
                    var errEl = btn.closest('.setting-row').querySelector('.setting-validation-error');
                    if (errEl) { errEl.textContent = result.error; errEl.style.display = 'block'; }
                    input.style.borderColor = 'var(--accent-red)';
                    toast('❌ Validation error: ' + result.error, 'error');
                    return;
                }
            }
            btn.textContent = '⏳';
            btn.disabled = true;
            try {
                await api('/api/settings', { method: 'PUT', body: JSON.stringify({ category: cat, key: key, value: value }) });
                toast('✅ Setting saved: ' + cat + '.' + key, 'success');
                btn.textContent = '✅ Done';
                if (cat === 'embedding' || cat === 'reranker') startStatusPoll();
                setTimeout(function() { loadSettings(); }, 1500);
            } catch (e) {
                toast('❌ Failed to save: ' + e.message, 'error');
                btn.textContent = '❌ Error';
            }
            setTimeout(function() { btn.disabled = false; }, 2000);
        };
    });

    /* Input validation listeners */
    document.querySelectorAll('.setting-row input, .setting-row select').forEach(function(input) {
        input.addEventListener('input', function() {
            var cat = this.dataset.cat;
            var key = this.dataset.key;
            var meta = S.settingsData && S.settingsData[cat] && S.settingsData[cat][key];
            if (!meta) return;
            var result = validateField(cat, key, this.value, meta);
            var errEl = this.closest('.setting-row').querySelector('.setting-validation-error');
            var applyBtn = this.closest('.setting-row').querySelector('.setting-apply-btn');
            if (!result.valid) {
                this.style.borderColor = 'var(--accent-red)';
                if (errEl) { errEl.textContent = result.error; errEl.style.display = 'block'; }
                if (applyBtn) applyBtn.disabled = true;
            } else {
                this.style.borderColor = '';
                if (errEl) { errEl.textContent = ''; errEl.style.display = 'none'; }
                if (applyBtn) applyBtn.disabled = false;
            }
        });
    });

    /* Export button */
    var expBtn = document.getElementById('export-config-btn');
    if (expBtn) expBtn.onclick = function() {
        var blob = new Blob([JSON.stringify(settings, null, 2)], {type: 'application/json'});
        var a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = 'memorymcp-config.json';
        a.click();
        toast('📤 Config exported', 'success');
    };

    /* Reset All button */
    var rstBtn = document.getElementById('reset-config-btn');
    if (rstBtn) rstBtn.onclick = async function() {
        if (!confirm('Reset ALL settings to defaults? This cannot be undone.')) return;
        try {
            for (const [rCat, rFields] of Object.entries(settings)) {
                if (typeof rFields !== 'object') continue;
                for (const [rKey, rMeta] of Object.entries(rFields)) {
                    if (rMeta && rMeta.source === 'override' && rMeta.default_value != null) {
                        await api('/api/settings', { method: 'PUT', body: JSON.stringify({ category: rCat, key: rKey, value: rMeta.default_value }) });
                    }
                }
            }
            toast('✅ All settings reset to defaults', 'success');
            setTimeout(function() { loadSettings(); }, 500);
        } catch (e) {
            toast('❌ Reset failed: ' + e.message, 'error');
        }
    };

    /* Profile event delegation */
    var profilesList = document.getElementById('profiles-list');
    if (profilesList) {
        profilesList.addEventListener('click', function(e) {
            var btn = e.target.closest('[data-profile-action]');
            if (!btn) return;
            var action = btn.dataset.profileAction;
            var name = btn.dataset.profileName;
            if (action === 'load-builtin') {
                loadProfile(name, BUILTIN_PROFILES[name]);
            } else if (action === 'load-user') {
                var data = localStorage.getItem('memorymcp_profile_' + name);
                if (data) loadProfile(name, JSON.parse(data));
            } else if (action === 'delete') {
                deleteProfile(name);
            }
        });
    }

    applyDependsRules();
    renderProfiles();
}

/* ═══════════════════════ SEARCH / FILTER ═══════════════════════ */

function filterSettings(query) {
    var q = query.toLowerCase().trim();
    var clearBtn = document.getElementById('settings-search-clear');
    if (clearBtn) clearBtn.style.display = q ? 'block' : 'none';

    document.querySelectorAll('.setting-category-card').forEach(function(card) {
        var cat = card.dataset.category || '';
        var catText = (card.dataset.searchtext || '').toLowerCase();
        var rows = card.querySelectorAll('.setting-row');

        if (!q) {
            card.style.display = '';
            rows.forEach(function(r) { r.style.display = ''; });
            return;
        }

        var catMatch = catText.includes(q);
        var anyRowMatch = false;

        rows.forEach(function(r) {
            var rowText = (r.dataset.searchtext || '').toLowerCase();
            if (catMatch) {
                r.style.display = '';
                anyRowMatch = true;
            } else if (rowText.includes(q)) {
                r.style.display = '';
                anyRowMatch = true;
            } else {
                r.style.display = 'none';
            }
        });

        card.style.display = (catMatch || anyRowMatch) ? '' : 'none';

        /* Auto-expand matching categories */
        if (catMatch || anyRowMatch) {
            var body = document.getElementById('cat-body-' + cat);
            var toggle = document.getElementById('cat-toggle-' + cat);
            if (body) body.style.display = 'block';
            if (toggle) toggle.textContent = '▼';
        }
    });
}

/* ═══════════════════════ CATEGORY TOGGLE ═══════════════════════ */

function toggleCategory(catId) {
    var body = document.getElementById('cat-body-' + catId);
    var toggle = document.getElementById('cat-toggle-' + catId);
    if (body.style.display === 'none') {
        body.style.display = 'block';
        toggle.textContent = '▼';
    } else {
        body.style.display = 'none';
        toggle.textContent = '▶';
    }
}

/* ═══════════════════════ RESET FUNCTIONS ═══════════════════════ */

async function resetField(cat, key, defaultVal) {
    try {
        await api('/api/settings', { method: 'PUT', body: JSON.stringify({ category: cat, key: key, value: defaultVal }) });
        toast('✅ Reset ' + cat + '.' + key + ' to default', 'success');
        setTimeout(function() { loadSettings(); }, 800);
    } catch (e) {
        toast('❌ Reset failed: ' + e.message, 'error');
    }
}

async function resetCategory(cat) {
    if (!confirm('Reset all ' + cat + ' settings to defaults?')) return;
    var settings = S.settingsData;
    if (!settings || !settings[cat]) return;
    try {
        for (const [key, meta] of Object.entries(settings[cat])) {
            if (meta && meta.source === 'override' && meta.default_value != null) {
                await api('/api/settings', { method: 'PUT', body: JSON.stringify({ category: cat, key: key, value: meta.default_value }) });
            }
        }
        toast('✅ Category ' + cat + ' reset to defaults', 'success');
        setTimeout(function() { loadSettings(); }, 800);
    } catch (e) {
        toast('❌ Reset failed: ' + e.message, 'error');
    }
}

/* ═══════════════════════ DEPENDENCY RULES ═══════════════════════ */

function applyDependsRules() {
    for (const [targetKey, rule] of Object.entries(DEPENDS_RULES)) {
        var parts = rule.field.split('.');
        var depCat = parts[0];
        var depKey = parts[1];
        var settings = S.settingsData;
        if (!settings || !settings[depCat] || !settings[depCat][depKey]) continue;
        var depValue = settings[depCat][depKey].value;
        var isEnabled = depValue === rule.value || depValue === String(rule.value);
        var row = document.querySelector('[data-setting-key="' + targetKey + '"]');
        if (row) {
            row.style.opacity = isEnabled ? '1' : '0.4';
            row.style.pointerEvents = isEnabled ? 'auto' : 'none';
            var input = row.querySelector('input, select');
            var btn = row.querySelector('.setting-apply-btn');
            if (!isEnabled) {
                if (input) input.disabled = true;
                if (btn) btn.disabled = true;
            } else {
                if (input) input.disabled = false;
                if (btn) btn.disabled = false;
            }
        }
    }
}

/* ═══════════════════════ FIELD VALIDATION ═══════════════════════ */

function validateField(cat, key, value, meta) {
    /* Number validation */
    if (typeof meta.default_value === 'number' || meta.default_value === 0) {
        var num = parseFloat(value);
        if (isNaN(num)) return { valid: false, error: 'Must be a number' };
        if (key === 'port' && (num < 1 || num > 65535)) return { valid: false, error: 'Port must be 1-65535' };
        if (key === 'batch_size' && num < 1) return { valid: false, error: 'Must be >= 1' };
        if (key === 'min_strength' && (num < 0 || num > 1)) return { valid: false, error: 'Must be 0-1' };
        if (key === 'min_importance' && (num < 0 || num > 1)) return { valid: false, error: 'Must be 0-1' };
        if (key === 'contradiction_threshold' && (num < 0 || num > 1)) return { valid: false, error: 'Must be 0-1' };
        if (key === 'duplicate_threshold' && (num < 0 || num > 1)) return { valid: false, error: 'Must be 0-1' };
        if (key.includes('interval') && num < 0) return { valid: false, error: 'Must be >= 0' };
        if (key === 'llm_max_tokens' && num < 1) return { valid: false, error: 'Must be >= 1' };
    }
    /* URL validation */
    if (key.includes('url') && value && !(String(value).startsWith('http://') || String(value).startsWith('https://'))) {
        return { valid: false, error: 'Must start with http:// or https://' };
    }
    return { valid: true, error: '' };
}

/* ═══════════════════════ PROFILES ═══════════════════════ */

function saveProfile() {
    var name = prompt('Enter profile name:');
    if (!name || !name.trim()) return;
    var settings = S.settingsData;
    if (!settings) { toast('No settings loaded', 'error'); return; }
    var profile = {};
    for (const [cat, fields] of Object.entries(settings)) {
        if (typeof fields !== 'object' || fields === null) continue;
        profile[cat] = {};
        for (const [key, meta] of Object.entries(fields)) {
            if (meta && meta.value != null) profile[cat][key] = meta.value;
        }
    }
    localStorage.setItem('memorymcp_profile_' + name.trim(), JSON.stringify(profile));
    toast('💾 Profile "' + esc(name.trim()) + '" saved', 'success');
    renderProfiles();
}

async function loadProfile(name, profile) {
    if (!confirm('Load profile "' + esc(name) + '"? This will apply all settings from the profile.')) return;
    try {
        var count = 0;
        for (const [cat, fields] of Object.entries(profile)) {
            for (const [key, value] of Object.entries(fields)) {
                await api('/api/settings', { method: 'PUT', body: JSON.stringify({ category: cat, key: key, value: value }) });
                count++;
            }
        }
        toast('✅ Loaded profile "' + esc(name) + '" (' + count + ' settings)', 'success');
        setTimeout(function() { loadSettings(); }, 1000);
    } catch (e) {
        toast('❌ Failed to load profile: ' + e.message, 'error');
    }
}

function deleteProfile(name) {
    if (!confirm('Delete profile "' + esc(name) + '"?')) return;
    localStorage.removeItem('memorymcp_profile_' + name);
    toast('Profile "' + esc(name) + '" deleted', 'info');
    renderProfiles();
}

function renderProfiles() {
    var container = document.getElementById('profiles-list');
    if (!container) return;
    var html = '';
    /* Built-in profiles */
    for (const [name] of Object.entries(BUILTIN_PROFILES)) {
        html += '<button data-profile-action="load-builtin" data-profile-name="' + esc(name) + '" class="glass-btn profile-chip" style="padding:5px 14px;font-size:0.78rem;background:linear-gradient(135deg,rgba(167,139,250,0.15),rgba(244,114,182,0.15));border-color:rgba(167,139,250,0.3)">';
        html += '📦 ' + esc(name);
        html += '</button>';
    }
    /* User profiles from localStorage */
    for (var i = 0; i < localStorage.length; i++) {
        var k = localStorage.key(i);
        if (k && k.startsWith('memorymcp_profile_')) {
            var pName = k.replace('memorymcp_profile_', '');
            html += '<div style="display:inline-flex;align-items:center;gap:0">';
            html += '<button data-profile-action="load-user" data-profile-name="' + esc(pName) + '" class="glass-btn profile-chip" style="padding:5px 14px;font-size:0.78rem;border-top-right-radius:0;border-bottom-right-radius:0">';
            html += '👤 ' + esc(pName);
            html += '</button>';
            html += '<button data-profile-action="delete" data-profile-name="' + esc(pName) + '" class="glass-btn glass-btn-danger" style="padding:5px 8px;font-size:0.72rem;border-top-left-radius:0;border-bottom-left-radius:0;border-left:none" title="Delete profile">✕</button>';
            html += '</div>';
        }
    }
    if (!html) html = '<span style="font-size:0.8rem;color:var(--text-muted)">No profiles yet</span>';
    container.innerHTML = html;
}

/* ═══════════════════════ STATUS POLLING ═══════════════════════ */

function startStatusPoll() {
    if (S.statusPoll) clearInterval(S.statusPoll);
    S.statusPoll = setInterval(async function() {
        try {
            var status = await api('/api/settings/status');
            var rs = status.reload_status || {};
            var allDone = Object.values(rs).every(function(s) {
                return !s.status || s.status === 'idle' || s.status === 'ready' || s.status === 'success' || s.status === 'error';
            });
            if (allDone) {
                clearInterval(S.statusPoll);
                S.statusPoll = null;
                loadSettings();
            } else {
                var el = document.getElementById('settings-content');
                var settings = S.settingsData;
                if (settings) renderSettings(el, settings, status);
            }
        } catch(e) { /* ignore poll errors */ }
    }, 2000);
}"""
