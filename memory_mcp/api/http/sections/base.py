"""Base layout components for the MemoryMCP Dashboard.

Provides the shared HTML head, navigation bar, utility JavaScript,
and the overall page shell that section-specific renderers plug into.
"""


# ---------------------------------------------------------------------------
# 1. render_head
# ---------------------------------------------------------------------------


def render_head() -> str:
    """Return the full <head>…</head> block (meta, CDN scripts, all CSS)."""
    return r"""<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MemoryMCP Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
    <script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <style>
        /* ============================================================
           ROOT VARIABLES & THEMING
           ============================================================ */
        :root {
            --bg-primary: #1a0533;
            --bg-secondary: #2d1b69;
            --bg-tertiary: #0f0c29;
            --glass-bg: rgba(255, 255, 255, 0.08);
            --glass-border: rgba(255, 255, 255, 0.15);
            --glass-hover: rgba(255, 255, 255, 0.12);
            --text-primary: #f1f5f9;
            --text-secondary: #cbd5e1;
            --text-muted: #94a3b8;
            --accent-purple: #a78bfa;
            --accent-green: #34d399;
            --accent-pink: #f472b6;
            --accent-blue: #60a5fa;
            --accent-yellow: #fbbf24;
            --accent-orange: #fb923c;
            --accent-red: #f87171;
            --shadow-glow: rgba(167, 139, 250, 0.15);
            --card-radius: 16px;
        }
        html.light {
            --bg-primary: #f0eef5;
            --bg-secondary: #e8e4f0;
            --bg-tertiary: #f8f7fc;
            --glass-bg: rgba(139, 92, 246, 0.06);
            --glass-border: rgba(139, 92, 246, 0.18);
            --glass-hover: rgba(139, 92, 246, 0.10);
            --text-primary: #1e1b4b;
            --text-secondary: #4c4576;
            --text-muted: #7c7399;
            --shadow-glow: rgba(139, 92, 246, 0.1);
        }

        /* ============================================================
           BASE STYLES
           ============================================================ */
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            background: linear-gradient(135deg, var(--bg-primary) 0%, var(--bg-secondary) 50%, var(--bg-tertiary) 100%);
            color: var(--text-primary);
            min-height: 100vh;
            overflow-x: hidden;
        }
        html.light body {
            background: linear-gradient(135deg, #f0eef5 0%, #e8e4f0 50%, #f8f7fc 100%);
        }

        /* ============================================================
           FLOATING ORBS (Background decoration)
           ============================================================ */
        .orb {
            position: fixed;
            border-radius: 50%;
            filter: blur(100px);
            opacity: 0.12;
            pointer-events: none;
            z-index: 0;
        }
        .orb-1 { width: 600px; height: 600px; background: #7c3aed; top: -200px; left: -100px; animation: orb-float 25s ease-in-out infinite; }
        .orb-2 { width: 400px; height: 400px; background: #ec4899; bottom: -100px; right: -100px; animation: orb-float 30s ease-in-out infinite reverse; }
        .orb-3 { width: 350px; height: 350px; background: #3b82f6; top: 40%; left: 60%; animation: orb-float 20s ease-in-out infinite 5s; }
        html.light .orb { opacity: 0.06; }
        @keyframes orb-float {
            0%, 100% { transform: translate(0, 0) scale(1); }
            33% { transform: translate(50px, -30px) scale(1.05); }
            66% { transform: translate(-30px, 40px) scale(0.95); }
        }

        /* ============================================================
           GLASSMORPHISM
           ============================================================ */
        .glass {
            background: var(--glass-bg);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid var(--glass-border);
            border-radius: var(--card-radius);
            transition: all 0.3s ease;
        }
        .glass:hover {
            background: var(--glass-hover);
            box-shadow: 0 8px 32px var(--shadow-glow);
        }
        .glass-static {
            background: var(--glass-bg);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid var(--glass-border);
            border-radius: var(--card-radius);
        }
        .glass-input {
            background: rgba(255,255,255,0.06);
            border: 1px solid var(--glass-border);
            border-radius: 10px;
            color: var(--text-primary);
            padding: 8px 14px;
            font-size: 0.85rem;
            outline: none;
            transition: all 0.3s ease;
        }
        html.light .glass-input { background: rgba(139,92,246,0.06); }
        .glass-input:focus {
            border-color: var(--accent-purple);
            box-shadow: 0 0 0 3px rgba(167,139,250,0.2);
        }
        .glass-input option { background: #1e1145; color: #f1f5f9; }
        html.light .glass-input option { background: #fff; color: #1e1b4b; }
        .glass-btn {
            background: rgba(167,139,250,0.15);
            border: 1px solid rgba(167,139,250,0.3);
            border-radius: 10px;
            color: var(--text-primary);
            padding: 8px 16px;
            cursor: pointer;
            font-size: 0.85rem;
            transition: all 0.3s ease;
            white-space: nowrap;
        }
        .glass-btn:hover {
            background: rgba(167,139,250,0.25);
            box-shadow: 0 0 20px rgba(167,139,250,0.2);
            transform: translateY(-1px);
        }
        .glass-btn:active { transform: translateY(0); }
        .glass-btn-danger {
            background: rgba(244,114,182,0.15);
            border-color: rgba(244,114,182,0.3);
        }
        .glass-btn-danger:hover {
            background: rgba(244,114,182,0.25);
            box-shadow: 0 0 20px rgba(244,114,182,0.2);
        }
        .glass-btn-success {
            background: rgba(52,211,153,0.15);
            border-color: rgba(52,211,153,0.3);
        }
        .glass-btn-success:hover {
            background: rgba(52,211,153,0.25);
            box-shadow: 0 0 20px rgba(52,211,153,0.2);
        }

        /* ============================================================
           HEADER
           ============================================================ */
        .app-header {
            position: sticky; top: 0; z-index: 50;
            background: rgba(26,5,51,0.85);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border-bottom: 1px solid var(--glass-border);
            padding: 14px 24px;
            display: flex; align-items: center; justify-content: space-between;
            flex-wrap: wrap; gap: 12px;
        }
        html.light .app-header {
            background: rgba(240,238,245,0.88);
        }
        .app-header h1 {
            font-size: 1.25rem; font-weight: 700;
            background: linear-gradient(135deg, var(--accent-purple), var(--accent-pink));
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .header-controls { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }

        /* ============================================================
           TAB BAR
           ============================================================ */
        .tab-bar {
            position: sticky; top: 60px; z-index: 40;
            display: flex; gap: 4px;
            padding: 8px 24px;
            background: rgba(26,5,51,0.6);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border-bottom: 1px solid var(--glass-border);
            overflow-x: auto;
        }
        html.light .tab-bar { background: rgba(240,238,245,0.7); }
        .tab-btn {
            padding: 10px 22px;
            border-radius: 12px;
            border: 1px solid transparent;
            background: transparent;
            color: var(--text-muted);
            cursor: pointer;
            font-size: 0.9rem;
            font-weight: 500;
            transition: all 0.3s ease;
            white-space: nowrap;
        }
        .tab-btn:hover {
            color: var(--text-primary);
            background: rgba(167,139,250,0.08);
        }
        .tab-btn.active {
            color: var(--accent-purple);
            background: rgba(167,139,250,0.15);
            border-color: rgba(167,139,250,0.3);
            box-shadow: 0 0 20px rgba(167,139,250,0.1);
        }

        /* ============================================================
           MAIN CONTENT
           ============================================================ */
        .main-content {
            position: relative; z-index: 1;
            max-width: 1400px;
            margin: 0 auto;
            padding: 24px;
        }
        .tab-panel { display: none; }
        .tab-panel.active { display: block; }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(8px); }
            to { opacity: 1; transform: translateY(0); }
        }

        /* ============================================================
           CARD COMPONENTS
           ============================================================ */
        .card-title {
            font-size: 0.85rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-muted);
            margin-bottom: 16px;
            display: flex; align-items: center; gap: 8px;
        }
        .stat-value {
            font-size: 2rem; font-weight: 700;
            background: linear-gradient(135deg, var(--accent-purple), var(--accent-blue));
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .stat-label { font-size: 0.8rem; color: var(--text-muted); margin-top: 2px; }

        /* ============================================================
           BADGES
           ============================================================ */
        .badge {
            display: inline-flex; align-items: center; gap: 4px;
            padding: 3px 10px;
            border-radius: 20px;
            font-size: 0.72rem;
            font-weight: 600;
            border: 1px solid transparent;
        }
        .badge-purple { background: rgba(167,139,250,0.15); color: #c4b5fd; border-color: rgba(167,139,250,0.3); }
        .badge-green { background: rgba(52,211,153,0.15); color: #6ee7b7; border-color: rgba(52,211,153,0.3); }
        .badge-pink { background: rgba(244,114,182,0.15); color: #f9a8d4; border-color: rgba(244,114,182,0.3); }
        .badge-blue { background: rgba(96,165,250,0.15); color: #93c5fd; border-color: rgba(96,165,250,0.3); }
        .badge-yellow { background: rgba(251,191,36,0.15); color: #fde68a; border-color: rgba(251,191,36,0.3); }
        .badge-red { background: rgba(248,113,113,0.15); color: #fca5a5; border-color: rgba(248,113,113,0.3); }
        .badge-gray { background: rgba(148,163,184,0.15); color: #cbd5e1; border-color: rgba(148,163,184,0.3); }
        html.light .badge-purple { color: #7c3aed; } html.light .badge-green { color: #059669; }
        html.light .badge-pink { color: #db2777; } html.light .badge-blue { color: #2563eb; }
        html.light .badge-yellow { color: #d97706; } html.light .badge-red { color: #dc2626; }

        /* ============================================================
           MEMORY CARDS
           ============================================================ */
        .memory-card {
            padding: 16px 20px;
            border-bottom: 1px solid var(--glass-border);
            transition: background 0.2s;
        }
        .memory-card:hover { background: rgba(167,139,250,0.05); }
        .memory-card:last-child { border-bottom: none; }
        .memory-key {
            font-size: 0.82rem; font-weight: 600; color: var(--accent-purple);
            margin-bottom: 6px; font-family: 'Cascadia Code', 'Fira Code', monospace;
        }
        .memory-content {
            font-size: 0.88rem; color: var(--text-secondary);
            line-height: 1.5; margin-bottom: 8px;
        }
        .memory-meta {
            display: flex; flex-wrap: wrap; align-items: center; gap: 8px;
            font-size: 0.78rem; color: var(--text-muted);
        }

        /* ============================================================
           SKELETON LOADING
           ============================================================ */
        @keyframes shimmer {
            0% { background-position: -200% 0; }
            100% { background-position: 200% 0; }
        }
        .skeleton {
            background: linear-gradient(90deg,
                rgba(167,139,250,0.06) 25%,
                rgba(167,139,250,0.12) 50%,
                rgba(167,139,250,0.06) 75%);
            background-size: 200% 100%;
            animation: shimmer 1.5s ease-in-out infinite;
            border-radius: 8px;
        }
        .skeleton-text { height: 16px; margin-bottom: 10px; border-radius: 4px; }
        .skeleton-title { height: 24px; width: 60%; margin-bottom: 14px; border-radius: 4px; }
        .skeleton-chart { height: 200px; border-radius: 12px; }

        /* ============================================================
           PROGRESS BAR
           ============================================================ */
        .progress-wrap {
            width: 100%; height: 6px; border-radius: 3px;
            background: rgba(255,255,255,0.08); overflow: hidden;
        }
        .progress-bar {
            height: 100%; border-radius: 3px;
            background: linear-gradient(90deg, var(--accent-purple), var(--accent-pink));
            transition: width 0.5s ease;
        }
        .progress-indeterminate {
            width: 40%;
            animation: indeterminate 1.4s ease-in-out infinite;
        }
        @keyframes indeterminate {
            0% { transform: translateX(-100%); }
            100% { transform: translateX(350%); }
        }

        /* ============================================================
           SETTINGS FORM
           ============================================================ */
        .setting-row {
            display: flex; align-items: center; gap: 12px;
            padding: 12px 0;
            border-bottom: 1px solid rgba(255,255,255,0.05);
            flex-wrap: wrap;
        }
        .setting-row:last-child { border-bottom: none; }
        .setting-label {
            font-size: 0.85rem; font-weight: 500; color: var(--text-secondary);
            min-width: 140px;
        }
        .setting-source {
            font-size: 0.7rem; padding: 2px 8px; border-radius: 10px;
        }
        .source-env { background: rgba(52,211,153,0.15); color: var(--accent-green); }
        .source-override { background: rgba(96,165,250,0.15); color: var(--accent-blue); }
        .source-default { background: rgba(148,163,184,0.15); color: var(--text-muted); }
        .setting-label { position: relative; }
        .tooltip-icon { cursor: help; opacity: 0.6; font-size: 0.75rem; margin-left: 2px; }
        .tooltip-icon:hover { opacity: 1; }
        .setting-badge { font-size: 0.65rem; padding: 1px 5px; border-radius: 6px; margin-left: 4px; vertical-align: middle; }
        .badge-hot { background: rgba(52,211,153,0.15); color: var(--accent-green); }
        .badge-restart { background: rgba(251,146,60,0.15); color: #fb923c; }

        /* ============================================================
           SCROLLBAR
           ============================================================ */
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: rgba(167,139,250,0.3); border-radius: 3px; }
        ::-webkit-scrollbar-thumb:hover { background: rgba(167,139,250,0.5); }

        /* ============================================================
           TOAST NOTIFICATION
           ============================================================ */
        .toast-container {
            position: fixed; bottom: 24px; right: 24px; z-index: 9999;
            display: flex; flex-direction: column; gap: 8px;
        }
        .toast {
            padding: 12px 20px; border-radius: 12px;
            font-size: 0.85rem; font-weight: 500;
            backdrop-filter: blur(12px);
            border: 1px solid var(--glass-border);
            animation: toastIn 0.3s ease, toastOut 0.3s ease 2.7s forwards;
            max-width: 360px;
        }
        .toast-success { background: rgba(52,211,153,0.2); color: var(--accent-green); }
        .toast-error { background: rgba(248,113,113,0.2); color: var(--accent-red); }
        .toast-info { background: rgba(96,165,250,0.2); color: var(--accent-blue); }
        @keyframes toastIn { from { opacity:0; transform: translateX(40px); } to { opacity:1; transform: translateX(0); } }
        @keyframes toastOut { from { opacity:1; } to { opacity:0; transform: translateY(10px); } }

        /* ============================================================
           RESPONSIVE
           ============================================================ */
        @media (max-width: 768px) {
            .app-header { padding: 10px 16px; }
            .app-header h1 { font-size: 1rem; }
            .tab-bar { padding: 6px 12px; }
            .tab-btn { padding: 8px 14px; font-size: 0.82rem; }
            .main-content { padding: 16px; }
            .stat-value { font-size: 1.5rem; }
        }
        /* Memory Detail Modal */
        .mem-modal-overlay {
            position: fixed; inset: 0; background: rgba(0,0,0,0.6); z-index: 1000;
            display: flex; align-items: center; justify-content: center;
            padding: 20px; backdrop-filter: blur(4px);
        }
        .mem-modal {
            background: var(--bg-secondary); border: 1px solid var(--glass-border);
            border-radius: var(--card-radius); max-width: 700px; width: 100%;
            max-height: 85vh; overflow-y: auto; padding: 24px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.4);
        }
        .mem-modal-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; }
        .mem-modal-close { background: none; border: none; color: var(--text-muted); font-size: 1.5rem; cursor: pointer; padding: 0 4px; line-height: 1; }
        .mem-modal-close:hover { color: var(--text-primary); }
        .mem-modal-content { white-space: pre-wrap; word-break: break-word; font-size: 0.9rem; color: var(--text-secondary); line-height: 1.7; margin-bottom: 16px; padding: 12px; background: var(--glass-bg); border-radius: 8px; max-height: none; overflow: visible; }
        .mem-modal-row { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; padding: 6px 0; border-bottom: 1px solid rgba(255,255,255,0.05); font-size: 0.82rem; }
        .mem-modal-row:last-child { border-bottom: none; }
        .mem-modal-key { color: var(--text-muted); min-width: 100px; flex-shrink: 0; }

        /* ── Phase 5: Skeleton loading (extended) ── */
        .skeleton-card { height: 120px; margin-bottom: 12px; }
        .skeleton-line { height: 16px; margin-bottom: 8px; }
        .skeleton-line.short { width: 60%; }
        .skeleton-circle { width: 48px; height: 48px; border-radius: 50%; }

        /* ── Phase 5: Transitions & Animations ── */
        .tab-panel.active { animation: fadeInUp 0.4s ease; }
        @keyframes fadeInUp {
            from { opacity: 0; transform: translateY(16px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .animate-in { animation: fadeInUp 0.4s ease; }
        .glass:hover { transform: translateY(-2px); }
        .mem-modal-overlay { opacity: 0; transition: opacity 0.2s ease; }
        .mem-modal-overlay.show { opacity: 1; }
        .mem-modal { transform: scale(0.95); transition: transform 0.2s ease; }
        .mem-modal-overlay.show .mem-modal { transform: scale(1); }
        .count-up { display: inline-block; }
        .collapsible { max-height: 0; overflow: hidden; transition: max-height 0.3s ease; }
        .collapsible.open { max-height: 2000px; }

        /* ── Phase 5: Mobile optimization ── */
        @media (max-width: 640px) {
            .tab-bar { flex-wrap: wrap; }
            .tab-bar .tab-btn { flex: 1 1 auto; min-width: 0; font-size: 0.75rem; padding: 8px 6px; gap: 2px; }
            .mobile-toggle { display: flex !important; }
            .grid { grid-template-columns: 1fr !important; }
            .stat-value { font-size: 1.5rem !important; }
            .mem-modal-overlay { padding: 8px; }
            .mem-modal { width: 100% !important; max-width: none !important; max-height: 90vh !important; }
            #graph-container { height: 400px !important; }
        }
        @media (max-width: 1024px) {
            .lg\:grid-cols-4 { grid-template-columns: repeat(2, 1fr) !important; }
            .lg\:grid-cols-3 { grid-template-columns: repeat(2, 1fr) !important; }
        }
    </style>
</head>"""


# ---------------------------------------------------------------------------
# 2. render_nav
# ---------------------------------------------------------------------------


def render_nav(tabs: list[dict]) -> str:
    """Build ``<nav class="tab-bar">`` dynamically from *tabs*.

    Each element in *tabs* is ``{"id": "...", "icon": "...", "label": "..."}``.
    The first tab is marked active.
    """
    buttons: list[str] = []
    for i, tab in enumerate(tabs):
        if i == 0:
            cls = "tab-btn active"
            sel = "true"
        else:
            cls = "tab-btn"
            sel = "false"
        buttons.append(
            '<button class="'
            + cls
            + '" data-tab="'
            + tab["id"]
            + '" role="tab" aria-selected="'
            + sel
            + '">'
            + tab["icon"]
            + " "
            + tab["label"]
            + "</button>"
        )
    return (
        '    <nav class="tab-bar" role="tablist">\n'
        '        <button class="mobile-toggle" onclick="toggleMobileNav()" '
        'aria-label="Toggle navigation" '
        'style="display:none;align-items:center;gap:4px;padding:8px 12px;'
        "background:none;border:1px solid rgba(255,255,255,0.2);border-radius:8px;"
        'color:rgba(255,255,255,0.7);cursor:pointer;font-size:0.9rem;">'
        "☰ Menu</button>\n        " + "\n        ".join(buttons) + "\n    </nav>"
    )


# ---------------------------------------------------------------------------
# 3. render_utilities_js
# ---------------------------------------------------------------------------


def render_utilities_js() -> str:
    """Return ALL shared JavaScript (no ``<script>`` wrapper)."""
    return """/* =================================================================
   STATE
   ================================================================= */
const S = {
    persona: null,
    tab: 'overview',
    refreshTimer: null,
    charts: {},
    mem: { page: 1, tag: '', q: '', perPage: 20 },
    statusPoll: null,
    dashCache: null,
    initTime: Date.now()
};

const CHART_COLORS = ['#a78bfa','#f472b6','#60a5fa','#34d399','#fbbf24','#fb923c','#f87171','#2dd4bf','#a3e635','#e879f9'];
const EMOTION_COLORS = {
    joy:'#fbbf24', sadness:'#60a5fa', anger:'#f87171', fear:'#a78bfa',
    surprise:'#fb923c', disgust:'#6ee7b7', love:'#ec4899', neutral:'#94a3b8',
    anticipation:'#F59E0B', trust:'#10B981', anxiety:'#8B5CF6', excitement:'#EC4899',
    frustration:'#DC2626', nostalgia:'#92400E', pride:'#F97316', shame:'#BE185D',
    guilt:'#78350F', loneliness:'#1E3A5F', contentment:'#065F46', curiosity:'#0891B2',
    awe:'#5B21B6', relief:'#34D399',
    happiness:'#fbbf24', calm:'#2dd4bf'
};

/* =================================================================
   UTILITIES
   ================================================================= */
function esc(s) {
    if (!s) return '';
    const d = document.createElement('div');
    d.textContent = String(s);
    return d.innerHTML.replace(/"/g, '&quot;');
}
function truncate(s, n) { return s && s.length > n ? s.slice(0, n) + '...' : (s || ''); }
function relativeTime(iso) {
    if (!iso) return '--';
    const diff = Date.now() - new Date(iso).getTime();
    if (diff < 0) return 'just now';
    if (diff < 60000) return Math.floor(diff/1000) + 's ago';
    if (diff < 3600000) return Math.floor(diff/60000) + 'm ago';
    if (diff < 86400000) return Math.floor(diff/3600000) + 'h ago';
    return Math.floor(diff/86400000) + 'd ago';
}
function fmtDate(iso) {
    if (!iso) return '--';
    return new Date(iso).toLocaleDateString('ja-JP', {month:'short', day:'numeric'});
}

/* =================================================================
   TOAST NOTIFICATIONS
   ================================================================= */
function toast(msg, type='info') {
    const c = document.getElementById('toast-container');
    const t = document.createElement('div');
    t.className = 'toast toast-' + type;
    t.textContent = msg;
    c.appendChild(t);
    setTimeout(() => t.remove(), 3200);
}

/* =================================================================
   API HELPER
   ================================================================= */
async function api(path, opts={}) {
    try {
        const resp = await fetch(path, {
            headers: { 'Content-Type': 'application/json', ...opts.headers },
            ...opts
        });
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({error: resp.statusText}));
            throw new Error(err.error || resp.statusText);
        }
        return await resp.json();
    } catch (e) {
        console.error('API error:', path, e);
        throw e;
    }
}

/* =================================================================
   CHART HELPERS
   ================================================================= */
function destroyChart(id) {
    if (S.charts[id]) { S.charts[id].destroy(); delete S.charts[id]; }
}
function chartOpts(extra={}) {
    const color = getComputedStyle(document.documentElement).getPropertyValue('--text-muted').trim() || '#94a3b8';
    return {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { labels: { color, font: { size: 11 } } },
            ...extra.plugins
        },
        scales: extra.scales ? Object.fromEntries(
            Object.entries(extra.scales).map(([k,v]) => [k, { ...v, ticks: { color, ...(v.ticks||{}) }, grid: { color: 'rgba(167,139,250,0.08)', ...(v.grid||{}) } }])
        ) : undefined
    };
}

/* =================================================================
   SKELETON HELPERS
   ================================================================= */
function skeletonCard() {
    return '<div class="glass p-6"><div class="skeleton skeleton-title"></div><div class="skeleton skeleton-text" style="width:80%"></div><div class="skeleton skeleton-text" style="width:60%"></div></div>';
}
function errorCard(msg) {
    return '<div class="glass p-6 text-center" style="color:var(--accent-red)"><p style="font-size:1.2rem;margin-bottom:8px">⚠️</p><p>' + esc(msg) + '</p></div>';
}

/* =================================================================
   THEME TOGGLE
   ================================================================= */
function applyTheme() {
    const dark = localStorage.getItem('mmcp-dark') !== 'false';
    document.documentElement.className = dark ? 'dark' : 'light';
    document.getElementById('dark-toggle').textContent = dark ? '🌙' : '☀️';
    // Re-render charts for color update
    Object.values(S.charts).forEach(c => c.update());
}
function toggleTheme() {
    const isDark = document.documentElement.classList.contains('dark');
    localStorage.setItem('mmcp-dark', isDark ? 'false' : 'true');
    applyTheme();
}

/* =================================================================
   SKELETON LOADING
   ================================================================= */
function showSkeleton(tabId) {
    const container = document.getElementById('tab-' + tabId);
    if (!container) return;
    const skeletons = {
        overview: '<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">'
            + '<div class="skeleton skeleton-card glass"></div>'.repeat(4)
            + '</div><div class="grid grid-cols-1 lg:grid-cols-2 gap-6">'
            + '<div class="skeleton glass" style="height:200px"></div>'.repeat(2) + '</div>',
        analytics: '<div class="skeleton skeleton-chart glass mb-6"></div>'
            + '<div class="grid grid-cols-1 md:grid-cols-2 gap-4">'
            + '<div class="skeleton glass" style="height:200px"></div>'.repeat(2) + '</div>',
        memories: '<div class="skeleton skeleton-line mb-4" style="height:48px"></div>'
            + '<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">'
            + '<div class="skeleton skeleton-card glass"></div>'.repeat(6) + '</div>',
        settings: '<div class="skeleton glass mb-4" style="height:160px"></div>'.repeat(3),
        graph: '<div class="skeleton glass" style="height:600px"></div>',
        'import-export': '<div class="skeleton glass mb-4" style="height:200px"></div>'
            + '<div class="skeleton glass" style="height:200px"></div>',
        personas: '<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">'
            + '<div class="skeleton skeleton-card glass"></div>'.repeat(3) + '</div>',
        admin: '<div class="skeleton glass" style="height:300px"></div>'
    };
    /* graph / import-export / personas / chat manage their own loading state via
       inner elements (#graph-loading, #persona-grid, #export-preview, #chat-messages).
       Replacing their innerHTML would destroy those elements and cause
       silent failures in the corresponding load functions. */
    if (tabId === 'graph' || tabId === 'import-export' || tabId === 'personas' || tabId === 'chat') return;
    const content = container.querySelector('[id$="-content"]') || container;
    content.innerHTML = skeletons[tabId] || '<div class="skeleton skeleton-card glass"></div>';
}

/* =================================================================
   TAB SWITCHING
   ================================================================= */
function switchTab(tab) {
    S.tab = tab;
    document.querySelectorAll('.tab-btn').forEach(b => {
        const isActive = b.dataset.tab === tab;
        b.classList.toggle('active', isActive);
        b.setAttribute('aria-selected', isActive);
    });
    document.querySelectorAll('.tab-panel').forEach(p => {
        p.classList.toggle('active', p.id === 'tab-' + tab);
    });
    showSkeleton(tab);
    loadTab(tab);
}
function loadTab(tab) {
    if (!S.persona && tab !== 'settings' && tab !== 'personas' && tab !== 'skills') return;
    switch(tab) {
        case 'overview': loadOverview(); break;
        case 'analytics': loadAnalytics(); break;
        case 'memories': loadMemories(); break;
        case 'graph': loadGraph(); break;
        case 'import-export': loadImportExport(); break;
        case 'personas': loadPersonas(); break;
        case 'settings': loadSettings(); break;
        case 'chat': loadChat(); break;
        case 'skills': loadSkills(); break;
        case 'admin': loadAdmin(); break;
    }
}

/* =================================================================
   MEMORY DETAIL MODAL
   ================================================================= */
function openMemModal(mem) {
    const overlay = document.getElementById('mem-modal-overlay');
    const content = document.getElementById('mem-modal-content');
    const tags = (mem.tags || []).map(t => '<span class="badge badge-purple">' + esc(t) + '</span>').join(' ');
    const emoHtml = mem.emotion_type ? '<span class="badge badge-pink">😊 ' + esc(mem.emotion_type) + (mem.emotion_intensity != null ? ' (' + (mem.emotion_intensity * 100).toFixed(0) + '%)' : '') + '</span>' : '';
    content.innerHTML = `
        <div class="mem-modal-header">
            <div>
                <div style="font-size:0.7rem;color:var(--text-muted);margin-bottom:4px">Memory Key</div>
                <div style="font-family:monospace;font-size:0.85rem;color:var(--accent-purple)">${esc(mem.memory_key)}</div>
            </div>
            <button class="mem-modal-close" onclick="closeMemModal()">✕</button>
        </div>
        <div class="mem-modal-content">${esc(mem.content)}</div>
        <div>
            ${tags || emoHtml ? `<div class="mem-modal-row"><span class="mem-modal-key">Tags/Emotion</span><span>${tags} ${emoHtml}</span></div>` : ''}
            ${mem.importance != null ? `<div class="mem-modal-row"><span class="mem-modal-key">Importance</span><span style="color:var(--accent-yellow)">${(mem.importance).toFixed(2)}</span></div>` : ''}
            ${mem.strength != null ? `<div class="mem-modal-row"><span class="mem-modal-key">Strength</span><span style="color:var(--accent-green)">⚡${(mem.strength).toFixed(3)}</span></div>` : ''}
            ${mem.privacy_level ? `<div class="mem-modal-row"><span class="mem-modal-key">Privacy</span><span>${esc(mem.privacy_level)}</span></div>` : ''}
            ${mem.source_context ? `<div class="mem-modal-row"><span class="mem-modal-key">Source</span><span style="color:var(--text-muted)">${esc(mem.source_context)}</span></div>` : ''}
            ${mem.created_at ? `<div class="mem-modal-row"><span class="mem-modal-key">Created</span><span>📅 ${relativeTime(mem.created_at)} <span style="color:var(--text-muted);font-size:0.75rem">(${new Date(mem.created_at).toLocaleString('ja-JP')})</span></span></div>` : ''}
            ${mem.updated_at ? `<div class="mem-modal-row"><span class="mem-modal-key">Updated</span><span>📅 ${relativeTime(mem.updated_at)}</span></div>` : ''}
        </div>`;
    overlay.style.display = 'flex';
    overlay.classList.add('show');
    document.addEventListener('keydown', _memModalKeyHandler);
}
function closeMemModal() {
    const overlay = document.getElementById('mem-modal-overlay');
    overlay.classList.remove('show');
    setTimeout(() => { overlay.style.display = 'none'; }, 220);
    document.removeEventListener('keydown', _memModalKeyHandler);
}
function _memModalKeyHandler(e) { if (e.key === 'Escape') closeMemModal(); }

/* =================================================================
   LAST UPDATE TIMESTAMP
   ================================================================= */
function updateLastTime() {
    const el = document.getElementById('last-update');
    if (el) el.textContent = 'Last: ' + new Date().toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

/* =================================================================
   AUTO REFRESH
   ================================================================= */
function setAutoRefresh(sec) {
    if (S.refreshTimer) { clearInterval(S.refreshTimer); S.refreshTimer = null; }
    if (sec > 0) {
        S.refreshTimer = setInterval(() => loadTab(S.tab), sec * 1000);
    }
}

/* =================================================================
   INITIALIZATION
   ================================================================= */
async function init() {
    // Theme
    applyTheme();

    // Load personas
    try {
        const data = await api('/api/personas');
        const personas = data.personas || [];
        const sel = document.getElementById('persona-select');
        sel.innerHTML = '';
        if (personas.length === 0) {
            sel.innerHTML = '<option value="">No personas found</option>';
            document.getElementById('overview-content').innerHTML =
                '<div class="glass p-8 text-center"><div style="font-size:2rem;margin-bottom:12px">🤷</div><p style="color:var(--text-secondary)">No personas found. Create a persona to get started.</p></div>';
            return;
        }
        personas.forEach(p => {
            const opt = document.createElement('option');
            opt.value = p; opt.textContent = p;
            sel.appendChild(opt);
        });
        // 優先度: __INITIAL_PERSONA__ > localStorage > personas[0]
        const savedPersona = localStorage.getItem('mmcp-persona');
        let _target = null;
        if (window.__INITIAL_PERSONA__) {
            _target = window.__INITIAL_PERSONA__;
        } else if (savedPersona && personas.some(p => (p.id || p) === savedPersona)) {
            _target = savedPersona;
        } else {
            _target = personas[0]?.id || personas[0];
        }
        S.persona = _target;
        sel.value = _target;
        loadTab(S.tab);
    } catch (e) {
        toast('Failed to load personas: ' + e.message, 'error');
    }

    // Event: Persona change
    document.getElementById('persona-select').onchange = (e) => {
        S.persona = e.target.value;
        S.dashCache = null;
        // Reset pagination/search without losing extended properties from memories.js
        Object.assign(S.mem, { page: 1, tag: '', q: '', perPage: 20,
            selectMode: false, advOpen: false, dateFrom: '', dateTo: '',
            searchTags: [], emotion: '' });
        if (S.mem.selected instanceof Set) S.mem.selected.clear();
        loadTab(S.tab);
    };

    // Event: Tab switch
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => switchTab(btn.dataset.tab));
    });

    // Event: Refresh button
    document.getElementById('refresh-btn').onclick = () => {
        S.dashCache = null;
        loadTab(S.tab);
    };

    // Event: Auto-refresh
    document.getElementById('auto-refresh').onchange = (e) => {
        setAutoRefresh(parseInt(e.target.value));
    };

    // Event: Theme toggle
    document.getElementById('dark-toggle').onclick = toggleTheme;

    // Keyboard: tab navigation
    document.addEventListener('keydown', (e) => {
        if (e.altKey && e.key >= '1' && e.key <= '8') {
            e.preventDefault();
            const tabs = ['overview','analytics','memories','graph','import-export','personas','settings','admin'];
            switchTab(tabs[parseInt(e.key) - 1]);
        }
    });
}

/* =================================================================
   COUNT-UP ANIMATION
   ================================================================= */
function animateCount(el, target, duration) {
    duration = duration || 800;
    const startTime = performance.now();
    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3);
        el.textContent = Math.round(target * eased).toLocaleString();
        if (progress < 1) requestAnimationFrame(update);
    }
    requestAnimationFrame(update);
}

/* =================================================================
   STAGGERED CARD ANIMATION
   ================================================================= */
function animateCards(container) {
    if (!container) return;
    const cards = container.querySelectorAll('.glass');
    cards.forEach(function(card, i) {
        card.style.opacity = '0';
        card.style.transform = 'translateY(16px)';
        setTimeout(function() {
            card.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
            card.style.opacity = '1';
            card.style.transform = 'translateY(0)';
        }, i * 60);
    });
}

/* =================================================================
   MOBILE NAV TOGGLE
   ================================================================= */
function toggleMobileNav() {
    const nav = document.querySelector('.tab-bar');
    if (nav) nav.classList.toggle('mobile-open');
}

/* =================================================================
   KEYBOARD SHORTCUTS (Ctrl+F / Escape)
   ================================================================= */
document.addEventListener('keydown', function(e) {
    if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
        var searchInput = document.querySelector('.tab-panel.active input[type="text"][placeholder*="earch"]');
        if (searchInput) { e.preventDefault(); searchInput.focus(); }
    }
    if (e.key === 'Escape') {
        document.querySelectorAll('.mem-modal-overlay').forEach(function(m) {
            m.style.display = 'none';
            m.classList.remove('show');
        });
    }
});

/* =================================================================
   ARIA LABELS ON LOAD
   ================================================================= */
document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.tab-btn').forEach(function(btn, i) {
        btn.setAttribute('role', 'tab');
        btn.setAttribute('aria-label', btn.textContent.trim());
        btn.setAttribute('tabindex', '0');
    });
    document.querySelectorAll('.tab-panel').forEach(function(tab) {
        tab.setAttribute('role', 'tabpanel');
    });
    var tablist = document.querySelector('.tab-bar');
    if (tablist) tablist.setAttribute('role', 'tablist');
});

// Boot
init();"""


# ---------------------------------------------------------------------------
# 4. render_layout_shell
# ---------------------------------------------------------------------------


def render_layout_shell(nav_html: str, tab_contents: str, tab_js: str, initial_persona: str | None = None) -> str:
    """Compose the full HTML page.

    Uses string concatenation (NOT f-strings) because the embedded
    JavaScript relies on ``${}`` template literals.
    """
    # Inject initial persona as a JS variable so the SPA can pre-select it
    if initial_persona:
        safe_persona = (
            initial_persona.replace("\\", "\\\\").replace('"', '\\"').replace("<", "").replace(">", "").replace("&", "")
        )
        persona_init_script = '<script>window.__INITIAL_PERSONA__="' + safe_persona + '";</script>\n'
    else:
        persona_init_script = ""

    return (
        "<!DOCTYPE html>\n"
        '<html lang="ja" class="dark">\n' + render_head() + "\n<body>\n"
        "    <!-- Background Orbs -->\n"
        '    <div class="orb orb-1"></div>\n'
        '    <div class="orb orb-2"></div>\n'
        '    <div class="orb orb-3"></div>\n'
        "\n"
        "    <!-- ============================================================\n"
        "         HEADER\n"
        "         ============================================================ -->\n"
        '    <header class="app-header">\n'
        '        <div style="display:flex;align-items:center;gap:10px;">\n'
        '            <span style="font-size:1.6rem;">🧠</span>\n'
        "            <h1>MemoryMCP v2.0.0 Dashboard</h1>\n"
        "        </div>\n"
        '        <div class="header-controls">\n'
        '            <select id="persona-select" class="glass-input" title="Select persona">\n'
        '                <option value="">Loading...</option>\n'
        "            </select>\n"
        '            <select id="auto-refresh" class="glass-input" title="Auto refresh interval">\n'
        '                <option value="0">Auto: Off</option>\n'
        '                <option value="30">30s</option>\n'
        '                <option value="60">1min</option>\n'
        '                <option value="300">5min</option>\n'
        "            </select>\n"
        '            <button id="refresh-btn" class="glass-btn" title="Refresh now">🔄</button>\n'
        '            <span id="last-update" style="font-size:0.75rem;color:var(--text-muted);white-space:nowrap;">Last: --</span>\n'
        '            <button id="dark-toggle" class="glass-btn" title="Toggle theme">🌙</button>\n'
        "        </div>\n"
        "    </header>\n"
        "\n" + nav_html + "\n"
        "\n"
        '    <main class="main-content">\n' + tab_contents + "\n"
        "    </main>\n"
        "\n"
        "    <!-- Memory Detail Modal -->\n"
        '    <div id="mem-modal-overlay" class="mem-modal-overlay" style="display:none" onclick="if(event.target===this)closeMemModal()">\n'
        '        <div class="mem-modal" id="mem-modal-content"></div>\n'
        "    </div>\n"
        "\n"
        "    <!-- Toast container -->\n"
        '    <div id="toast-container" class="toast-container"></div>\n'
        "\n" + persona_init_script + "<script>\n" + render_utilities_js() + "\n"
        "\n" + tab_js + "\n"
        "</script>\n"
        "</body>\n"
        "</html>"
    )
