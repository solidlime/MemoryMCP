"""MemoryMCP v2 Dashboard - Single Page Application.

A 5-tab glassmorphism dashboard for managing persona memories,
analytics, settings, and administration.
"""


def render_dashboard() -> str:
    """Return the complete HTML string for the 5-tab SPA dashboard."""
    return """<!DOCTYPE html>
<html lang="ja" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MemoryMCP Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
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
        .tab-panel { display: none; animation: fadeIn 0.35s ease; }
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
        .mem-modal-content { white-space: pre-wrap; word-break: break-word; font-size: 0.9rem; color: var(--text-secondary); line-height: 1.7; margin-bottom: 16px; padding: 12px; background: var(--glass-bg); border-radius: 8px; }
        .mem-modal-row { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; padding: 6px 0; border-bottom: 1px solid rgba(255,255,255,0.05); font-size: 0.82rem; }
        .mem-modal-row:last-child { border-bottom: none; }
        .mem-modal-key { color: var(--text-muted); min-width: 100px; flex-shrink: 0; }
    </style>
</head>
<body>
    <!-- Background Orbs -->
    <div class="orb orb-1"></div>
    <div class="orb orb-2"></div>
    <div class="orb orb-3"></div>

    <!-- ============================================================
         HEADER
         ============================================================ -->
    <header class="app-header">
        <div style="display:flex;align-items:center;gap:10px;">
            <span style="font-size:1.6rem;">🧠</span>
            <h1>MemoryMCP v2.0.0 Dashboard</h1>
        </div>
        <div class="header-controls">
            <select id="persona-select" class="glass-input" title="Select persona">
                <option value="">Loading...</option>
            </select>
            <select id="auto-refresh" class="glass-input" title="Auto refresh interval">
                <option value="0">Auto: Off</option>
                <option value="30">30s</option>
                <option value="60">1min</option>
                <option value="300">5min</option>
            </select>
            <button id="refresh-btn" class="glass-btn" title="Refresh now">🔄</button>
            <span id="last-update" style="font-size:0.75rem;color:var(--text-muted);white-space:nowrap;">Last: --</span>
            <button id="dark-toggle" class="glass-btn" title="Toggle theme">🌙</button>
        </div>
    </header>

    <!-- ============================================================
         TAB BAR
         ============================================================ -->
    <nav class="tab-bar" role="tablist">
        <button class="tab-btn active" data-tab="overview" role="tab" aria-selected="true">📊 Overview</button>
        <button class="tab-btn" data-tab="analytics" role="tab" aria-selected="false">📈 Analytics</button>
        <button class="tab-btn" data-tab="memories" role="tab" aria-selected="false">🧠 Memories</button>
        <button class="tab-btn" data-tab="settings" role="tab" aria-selected="false">⚙️ Settings</button>
        <button class="tab-btn" data-tab="admin" role="tab" aria-selected="false">🔧 Admin</button>
    </nav>

    <!-- ============================================================
         MAIN CONTENT
         ============================================================ -->
    <main class="main-content">
        <!-- ========== OVERVIEW TAB ========== -->
        <section id="tab-overview" class="tab-panel active" role="tabpanel">
            <div id="overview-content">
                <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
                    <div class="glass p-6"><div class="skeleton skeleton-title"></div><div class="skeleton skeleton-text" style="width:80%"></div><div class="skeleton skeleton-text" style="width:60%"></div><div class="skeleton skeleton-text" style="width:70%"></div></div>
                    <div class="glass p-6"><div class="skeleton skeleton-title"></div><div class="skeleton skeleton-text" style="width:90%"></div><div class="skeleton skeleton-text" style="width:75%"></div></div>
                </div>
                <div class="glass p-6 mb-6"><div class="skeleton skeleton-title"></div><div class="skeleton skeleton-text"></div><div class="skeleton skeleton-text" style="width:85%"></div></div>
                <div class="glass p-6 mb-6"><div class="skeleton skeleton-title"></div><div class="skeleton skeleton-text" style="width:70%"></div></div>
                <div class="grid grid-cols-1 lg:grid-cols-2 gap-6"><div class="glass p-6"><div class="skeleton skeleton-chart"></div></div><div class="glass p-6"><div class="skeleton skeleton-chart"></div></div></div>
            </div>
        </section>

        <!-- ========== ANALYTICS TAB ========== -->
        <section id="tab-analytics" class="tab-panel" role="tabpanel">
            <div id="analytics-content">
                <div class="glass p-6 mb-6"><div class="skeleton skeleton-title"></div><div class="skeleton skeleton-chart"></div></div>
                <div class="glass p-6"><div class="skeleton skeleton-title"></div><div class="skeleton skeleton-chart"></div></div>
            </div>
        </section>

        <!-- ========== MEMORIES TAB ========== -->
        <section id="tab-memories" class="tab-panel" role="tabpanel">
            <div id="memories-content">
                <div class="glass p-6"><div class="skeleton skeleton-title"></div><div class="skeleton skeleton-text"></div><div class="skeleton skeleton-text" style="width:80%"></div></div>
            </div>
        </section>

        <!-- ========== SETTINGS TAB ========== -->
        <section id="tab-settings" class="tab-panel" role="tabpanel">
            <div id="settings-content">
                <div class="glass p-6"><div class="skeleton skeleton-title"></div><div class="skeleton skeleton-text"></div><div class="skeleton skeleton-text" style="width:70%"></div></div>
            </div>
        </section>

        <!-- ========== ADMIN TAB ========== -->
        <section id="tab-admin" class="tab-panel" role="tabpanel">
            <div id="admin-content">
                <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <div class="glass p-6"><div class="skeleton skeleton-title"></div><div class="skeleton skeleton-text"></div></div>
                    <div class="glass p-6"><div class="skeleton skeleton-title"></div><div class="skeleton skeleton-text"></div></div>
                    <div class="glass p-6"><div class="skeleton skeleton-title"></div><div class="skeleton skeleton-text"></div></div>
                </div>
            </div>
        </section>
    </main>

    <!-- Memory Detail Modal -->
    <div id="mem-modal-overlay" class="mem-modal-overlay" style="display:none" onclick="if(event.target===this)closeMemModal()">
        <div class="mem-modal" id="mem-modal-content"></div>
    </div>

    <!-- Toast container -->
    <div id="toast-container" class="toast-container"></div>

<script>
/* =================================================================
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
    joy:'#fbbf24', happiness:'#fbbf24', sadness:'#60a5fa', anger:'#f87171',
    fear:'#a78bfa', surprise:'#fb923c', disgust:'#34d399', calm:'#2dd4bf',
    excitement:'#f472b6', love:'#ec4899', anxiety:'#e879f9', trust:'#34d399',
    anticipation:'#fbbf24', neutral:'#94a3b8'
};

/* =================================================================
   UTILITIES
   ================================================================= */
function esc(s) {
    if (!s) return '';
    const d = document.createElement('div');
    d.textContent = String(s);
    return d.innerHTML;
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
    const dark = localStorage.getItem('mmcp-dark') === 'true';
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
    loadTab(tab);
}
function loadTab(tab) {
    if (!S.persona && tab !== 'settings') return;
    switch(tab) {
        case 'overview': loadOverview(); break;
        case 'analytics': loadAnalytics(); break;
        case 'memories': loadMemories(); break;
        case 'settings': loadSettings(); break;
        case 'admin': loadAdmin(); break;
    }
}

/* =================================================================
   TAB 1: OVERVIEW
   ================================================================= */
async function loadOverview() {
    const el = document.getElementById('overview-content');
    try {
        const data = await api('/api/dashboard/' + encodeURIComponent(S.persona));
        S.dashCache = data;
        const stats = data.stats || {};
        const ctx = data.context || {};
        const equip = data.equipment || {};
        const items = data.items || [];
        const str = data.strengths || {};

        // --- Build tag/emotion distributions from stats ---
        const tagDist = stats.tag_distribution || {};
        const emoDist = stats.emotion_distribution || {};
        const topTags = Object.entries(tagDist).sort((a,b) => b[1]-a[1]).slice(0,5);
        const topEmo = Object.entries(emoDist).sort((a,b) => b[1]-a[1]).slice(0,5);

        // --- Equipment list ---
        let equipHtml = '';
        if (equip && typeof equip === 'object') {
            const slots = Object.entries(equip).filter(([_,v]) => v);
            if (slots.length === 0) equipHtml = '<span style="color:var(--text-muted)">None equipped</span>';
            else slots.forEach(([slot, item]) => {
                equipHtml += '<div style="display:flex;gap:6px;margin-top:4px"><span class="badge badge-blue">' + esc(slot) + '</span><span style="color:var(--text-secondary)">' + esc(typeof item === 'string' ? item : item.name || JSON.stringify(item)) + '</span></div>';
            });
        }

        // --- Core blocks ---
        let blocksHtml = '';
        if (data.blocks && data.blocks.length > 0) {
            data.blocks.forEach(b => {
                const name = typeof b === 'string' ? b : (b.name || b.block_name || 'block');
                const content = typeof b === 'object' ? (b.content || b.value || '') : '';
                const priority = typeof b === 'object' ? b.priority : null;
                blocksHtml += '<div style="padding:10px 0;border-bottom:1px solid rgba(255,255,255,0.05)">';
                blocksHtml += '<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">';
                blocksHtml += '<span style="font-weight:600;color:var(--accent-purple);font-size:0.85rem">' + esc(name) + '</span>';
                if (priority != null) blocksHtml += '<span class="badge badge-yellow">P' + esc(String(priority)) + '</span>';
                blocksHtml += '</div>';
                if (content) blocksHtml += '<div style="font-size:0.82rem;color:var(--text-muted)">' + esc(truncate(String(content), 80)) + '</div>';
                blocksHtml += '</div>';
            });
        } else {
            blocksHtml = '<span style="color:var(--text-muted)">No core memory blocks</span>';
        }

        // --- Goals & Promises ---
        function renderItems(items, label) {
            if (!items || items.length === 0) return '<span style="color:var(--text-muted)">No ' + label + '</span>';
            let html = '';
            items.forEach(item => {
                const status = (item.status || '').toLowerCase();
                const icon = status === 'done' || status === 'completed' ? '✅' : status === 'active' || status === 'in_progress' ? '🔄' : '⏳';
                html += '<div style="display:flex;align-items:center;gap:8px;padding:6px 0">';
                html += '<span>' + icon + '</span>';
                html += '<span style="flex:1;font-size:0.85rem;color:var(--text-secondary)">' + esc(item.description || item.content || item.title || JSON.stringify(item)) + '</span>';
                if (item.created_at || item.date) html += '<span style="font-size:0.72rem;color:var(--text-muted)">' + relativeTime(item.created_at || item.date) + '</span>';
                html += '</div>';
            });
            return html;
        }

        // --- Profile: user_info / persona_info / relationship ---
        const userInfo = ctx.user_info || {};
        const personaInfo = ctx.persona_info || {};
        const relStatus = ctx.relationship_status || ctx.relationship_type || '--';

        // --- Recent memories grouped by date (for 7-day chart) ---
        const recent = data.recent || [];
        const dayMap = {};
        const now = new Date();
        for (let i = 6; i >= 0; i--) {
            const d = new Date(now); d.setDate(d.getDate() - i);
            dayMap[d.toISOString().slice(0,10)] = 0;
        }
        recent.forEach(m => {
            const d = (m.created_at || '').slice(0,10);
            if (d in dayMap) dayMap[d]++;
        });
        // Augment with stats if available
        if (stats.daily_counts) {
            Object.entries(stats.daily_counts).forEach(([d, c]) => { if (d in dayMap) dayMap[d] = c; });
        }
        const dayLabels = Object.keys(dayMap).map(d => fmtDate(d));
        const dayCounts = Object.values(dayMap);

        // --- Render ---
        el.innerHTML = `
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
            <!-- Memory Info -->
            <div class="glass p-6">
                <div class="card-title">📊 Memory Info</div>
                <div class="grid grid-cols-2 gap-4 mb-4">
                    <div><div class="stat-value">${stats.total_count ?? '--'}</div><div class="stat-label">Total Memories</div></div>
                    <div><div class="stat-value" style="font-size:1.3rem">${esc(ctx.emotion_type || '--')}</div><div class="stat-label">Current Emotion${ctx.emotion_intensity != null ? ' (' + (ctx.emotion_intensity * 100).toFixed(0) + '%)' : ''}</div></div>
                </div>
                <div style="display:flex;gap:16px;margin-bottom:12px;flex-wrap:wrap">
                    <div><span style="font-size:0.78rem;color:var(--text-muted)">Physical:</span> <span style="font-size:0.85rem">${esc(ctx.physical_state || '--')}</span></div>
                    <div><span style="font-size:0.78rem;color:var(--text-muted)">Mental:</span> <span style="font-size:0.85rem">${esc(ctx.mental_state || '--')}</span></div>
                </div>
                <div style="font-size:0.78rem;color:var(--text-muted);margin-bottom:6px">Equipment:</div>
                ${equipHtml}
            </div>
            <!-- Metrics -->
            <div class="glass p-6">
                <div class="card-title">📈 Metrics</div>
                <div style="margin-bottom:14px">
                    <div style="font-size:0.78rem;color:var(--text-muted);margin-bottom:6px">Top Tags</div>
                    <div style="display:flex;flex-wrap:wrap;gap:6px">${topTags.length ? topTags.map(([t,c]) => '<span class="badge badge-purple">' + esc(t) + ' <span style="opacity:0.7">(' + c + ')</span></span>').join('') : '<span style="color:var(--text-muted)">--</span>'}</div>
                </div>
                <div style="margin-bottom:14px">
                    <div style="font-size:0.78rem;color:var(--text-muted);margin-bottom:6px">Top Emotions</div>
                    <div style="display:flex;flex-wrap:wrap;gap:6px">${topEmo.length ? topEmo.map(([e,c]) => '<span class="badge badge-pink">' + esc(e) + ' <span style="opacity:0.7">(' + c + ')</span></span>').join('') : '<span style="color:var(--text-muted)">--</span>'}</div>
                </div>
                <div style="display:flex;gap:20px;flex-wrap:wrap;font-size:0.85rem">
                    <div><span style="color:var(--text-muted)">Avg Strength:</span> <span style="color:var(--accent-green);font-weight:600">${str.avg ?? '--'}</span></div>
                    <div><span style="color:var(--text-muted)">Tagged:</span> <span style="color:var(--accent-blue);font-weight:600">${stats.tagged_ratio != null ? (stats.tagged_ratio * 100).toFixed(1) + '%' : '--'}</span></div>
                    <div><span style="color:var(--text-muted)">Linked:</span> <span style="color:var(--accent-yellow);font-weight:600">${stats.linked_ratio != null ? (stats.linked_ratio * 100).toFixed(1) + '%' : '--'}</span></div>
                </div>
            </div>
        </div>
        <!-- Core Memory Blocks -->
        <div class="glass p-6 mb-6">
            <div class="card-title">🧠 Core Memory Blocks</div>
            ${blocksHtml}
        </div>
        <!-- Goals & Promises -->
        <div class="glass p-6 mb-6">
            <div class="card-title">🎯 Goals & Promises</div>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                    <div style="font-size:0.8rem;font-weight:600;color:var(--accent-green);margin-bottom:8px">Goals</div>
                    ${renderItems(data.goals, 'goals')}
                </div>
                <div>
                    <div style="font-size:0.8rem;font-weight:600;color:var(--accent-pink);margin-bottom:8px">Promises</div>
                    ${renderItems(data.promises, 'promises')}
                </div>
            </div>
        </div>
        <!-- Profile & Relationship -->
        <div class="glass p-6 mb-6">
            <div class="card-title">👤 Profile & Relationship</div>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                    <div style="font-size:0.78rem;color:var(--text-muted);margin-bottom:8px;font-weight:600">Relationship</div>
                    <div style="font-size:0.9rem;color:var(--accent-pink);font-weight:600;margin-bottom:12px">${esc(relStatus)}</div>
                    <div style="font-size:0.78rem;color:var(--text-muted);margin-bottom:6px;font-weight:600">User Info</div>
                    ${Object.entries(userInfo).length ? Object.entries(userInfo).map(([k,v]) => `<div style="display:flex;gap:8px;padding:4px 0;font-size:0.85rem"><span style="color:var(--text-muted);min-width:120px">${esc(k.replace(/_/g,' '))}</span><span style="color:var(--text-secondary)">${esc(String(v))}</span></div>`).join('') : '<span style="color:var(--text-muted)">No user info</span>'}
                </div>
                <div>
                    <div style="font-size:0.78rem;color:var(--text-muted);margin-bottom:6px;font-weight:600">Persona Info</div>
                    ${Object.entries(personaInfo).length ? Object.entries(personaInfo).map(([k,v]) => `<div style="display:flex;gap:8px;padding:4px 0;font-size:0.85rem"><span style="color:var(--text-muted);min-width:120px">${esc(k.replace(/_/g,' '))}</span><span style="color:var(--accent-purple)">${esc(String(v))}</span></div>`).join('') : '<span style="color:var(--text-muted)">No persona info</span>'}
                </div>
            </div>
        </div>
        <!-- Inventory -->
        <div class="glass p-6 mb-6">
            <div class="card-title">🎒 Inventory</div>
            ${items.length === 0
                ? '<span style="color:var(--text-muted)">No items in inventory</span>'
                : `<div style="display:grid;gap:4px">${items.map(it => `<div style="display:flex;align-items:center;gap:8px;padding:6px 0;border-bottom:1px solid rgba(255,255,255,0.04)"><span class="badge badge-blue">${esc(it.category || 'item')}</span><span style="flex:1;font-size:0.85rem;color:var(--text-secondary)">${esc(it.name)}</span>${it.quantity > 1 ? `<span style="font-size:0.78rem;color:var(--text-muted)">x${it.quantity}</span>` : ''}<span class="badge badge-purple">${esc(it.description ? it.description.slice(0,30) + (it.description.length > 30 ? '...' : '') : '')}</span></div>`).join('')}</div>`
            }
        </div>
        <!-- Charts -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div class="glass p-6">
                <div class="card-title">📅 7-Day Timeline</div>
                <div style="height:220px;position:relative"><canvas id="chart-timeline"></canvas></div>
            </div>
            <div class="glass p-6">
                <div class="card-title">🏷️ Tag Distribution</div>
                <div style="height:220px;position:relative"><canvas id="chart-tags"></canvas></div>
            </div>
        </div>`;

        // --- Charts ---
        destroyChart('chart-timeline');
        destroyChart('chart-tags');
        const tlCtx = document.getElementById('chart-timeline');
        if (tlCtx) {
            S.charts['chart-timeline'] = new Chart(tlCtx, {
                type: 'bar',
                data: { labels: dayLabels, datasets: [{ label: 'Memories', data: dayCounts, backgroundColor: 'rgba(167,139,250,0.5)', borderColor: '#a78bfa', borderWidth: 1, borderRadius: 6 }] },
                options: chartOpts({ plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } }, x: {} } })
            });
        }
        const allTags = Object.entries(tagDist).sort((a,b) => b[1]-a[1]).slice(0, 8);
        const tgCtx = document.getElementById('chart-tags');
        if (tgCtx && allTags.length) {
            S.charts['chart-tags'] = new Chart(tgCtx, {
                type: 'doughnut',
                data: { labels: allTags.map(t=>t[0]), datasets: [{ data: allTags.map(t=>t[1]), backgroundColor: CHART_COLORS.slice(0, allTags.length), borderWidth: 0 }] },
                options: { ...chartOpts(), cutout: '60%' }
            });
        }
        updateLastTime();
    } catch (e) {
        el.innerHTML = errorCard('Failed to load overview: ' + e.message);
    }
}

/* =================================================================
   TAB 2: ANALYTICS
   ================================================================= */
async function loadAnalytics(days=7) {
    const el = document.getElementById('analytics-content');
    try {
        const [emoData, strData] = await Promise.all([
            api('/api/emotions/' + encodeURIComponent(S.persona) + '?days=' + days),
            api('/api/strengths/' + encodeURIComponent(S.persona))
        ]);

        // --- Build emotion timeline datasets ---
        const history = emoData.history || {};
        const dates = Object.keys(history).sort();
        const emotionTypes = new Set();
        dates.forEach(d => (history[d] || []).forEach(r => emotionTypes.add(r.emotion_type)));
        const datasets = [];
        [...emotionTypes].forEach((etype, i) => {
            const data = dates.map(d => {
                const records = (history[d] || []).filter(r => r.emotion_type === etype);
                return records.length ? records.reduce((s,r) => s + (r.intensity || 0.5), 0) / records.length : null;
            });
            datasets.push({
                label: etype,
                data: data,
                borderColor: EMOTION_COLORS[etype] || CHART_COLORS[i % CHART_COLORS.length],
                backgroundColor: (EMOTION_COLORS[etype] || CHART_COLORS[i % CHART_COLORS.length]) + '22',
                fill: true,
                tension: 0.4,
                pointRadius: 3,
                spanGaps: true
            });
        });

        // --- Strength histogram ---
        const histogram = strData.histogram || [];
        const total = strData.total || 0;
        const values = (strData.strengths || []).map(s => s.strength);
        const avgStr = values.length ? (values.reduce((a,b)=>a+b,0)/values.length).toFixed(3) : '0';
        const weak = values.filter(v => v < 0.3).length;
        const strong = values.filter(v => v > 0.7).length;

        el.innerHTML = `
        <div class="glass p-6 mb-6">
            <div class="card-title" style="justify-content:space-between;flex-wrap:wrap">
                <span>💭 Emotion Timeline</span>
                <div style="display:flex;gap:6px">
                    <button class="glass-btn emo-days-btn ${days===7?'active':''}" data-days="7" style="padding:4px 12px;font-size:0.78rem">7d</button>
                    <button class="glass-btn emo-days-btn ${days===30?'active':''}" data-days="30" style="padding:4px 12px;font-size:0.78rem">30d</button>
                    <button class="glass-btn emo-days-btn ${days===90?'active':''}" data-days="90" style="padding:4px 12px;font-size:0.78rem">3M</button>
                    <button class="glass-btn emo-days-btn ${days===365?'active':''}" data-days="365" style="padding:4px 12px;font-size:0.78rem">1Y</button>
                </div>
            </div>
            <div style="height:280px;position:relative"><canvas id="chart-emotions"></canvas></div>
        </div>
        <div class="glass p-6">
            <div class="card-title">🧪 Memory Strength Distribution</div>
            <div style="display:flex;gap:20px;margin-bottom:16px;flex-wrap:wrap;font-size:0.85rem">
                <div><span style="color:var(--text-muted)">Total:</span> <span style="font-weight:600">${total}</span></div>
                <div><span style="color:var(--text-muted)">Avg:</span> <span style="color:var(--accent-green);font-weight:600">${avgStr}</span></div>
                <div><span style="color:var(--text-muted)">Weak (&lt;0.3):</span> <span style="color:var(--accent-red);font-weight:600">${weak}</span></div>
                <div><span style="color:var(--text-muted)">Strong (&gt;0.7):</span> <span style="color:var(--accent-green);font-weight:600">${strong}</span></div>
            </div>
            <div style="height:250px;position:relative"><canvas id="chart-strength"></canvas></div>
        </div>`;

        // Emotion days buttons
        document.querySelectorAll('.emo-days-btn').forEach(btn => {
            btn.addEventListener('click', () => loadAnalytics(parseInt(btn.dataset.days)));
        });

        // --- Render Charts ---
        destroyChart('chart-emotions');
        destroyChart('chart-strength');

        const emoCtx = document.getElementById('chart-emotions');
        if (emoCtx && datasets.length) {
            S.charts['chart-emotions'] = new Chart(emoCtx, {
                type: 'line',
                data: { labels: dates.map(d => fmtDate(d)), datasets },
                options: chartOpts({ scales: { y: { min: 0, max: 1 }, x: {} } })
            });
        } else if (emoCtx) {
            emoCtx.parentElement.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--text-muted)">No emotion data for this period</div>';
        }

        const strCtx = document.getElementById('chart-strength');
        if (strCtx && histogram.length) {
            S.charts['chart-strength'] = new Chart(strCtx, {
                type: 'bar',
                data: {
                    labels: histogram.map(h => h.range),
                    datasets: [{
                        label: 'Count',
                        data: histogram.map(h => h.count),
                        backgroundColor: histogram.map((_, i) => {
                            const ratio = i / 9;
                            if (ratio < 0.3) return 'rgba(248,113,113,0.5)';
                            if (ratio < 0.7) return 'rgba(251,191,36,0.5)';
                            return 'rgba(52,211,153,0.5)';
                        }),
                        borderWidth: 0,
                        borderRadius: 4
                    }]
                },
                options: chartOpts({ plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true }, x: {} } })
            });
        }
        updateLastTime();
    } catch (e) {
        el.innerHTML = errorCard('Failed to load analytics: ' + e.message);
    }
}

/* =================================================================
   TAB 3: MEMORIES
   ================================================================= */
async function loadMemories(page) {
    if (page != null) S.mem.page = page;
    const el = document.getElementById('memories-content');

    // Build tag options from cache
    let tagOptions = '<option value="">All Tags</option>';
    if (S.dashCache && S.dashCache.stats && S.dashCache.stats.tag_distribution) {
        Object.keys(S.dashCache.stats.tag_distribution).sort().forEach(t => {
            tagOptions += '<option value="' + esc(t) + '"' + (S.mem.tag === t ? ' selected' : '') + '>' + esc(t) + '</option>';
        });
    }

    try {
        let data;
        if (S.mem.q) {
            // Search mode
            data = await api('/api/search/' + encodeURIComponent(S.persona) + '?q=' + encodeURIComponent(S.mem.q) + '&limit=50');
            const results = (data.results || []);
            const memories = results.map(r => ({ ...(r.memory || {}), _score: r.score, _source: r.source }));
            renderMemoryList(el, memories, tagOptions, 0, 0, true);
        } else {
            // Browse mode
            let url = '/api/observations/' + encodeURIComponent(S.persona) + '?page=' + S.mem.page + '&per_page=' + S.mem.perPage + '&sort=desc';
            if (S.mem.tag) url += '&tag=' + encodeURIComponent(S.mem.tag);
            data = await api(url);
            renderMemoryList(el, data.memories || [], tagOptions, data.total_pages || 1, data.total_count || 0, false);
        }
        bindMemoryEvents();
        updateLastTime();
    } catch (e) {
        el.innerHTML = errorCard('Failed to load memories: ' + e.message);
    }
}

function renderMemoryList(el, memories, tagOptions, totalPages, totalCount, isSearch) {
    let html = `
    <div class="glass p-4 mb-6">
        <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">
            <input id="mem-search" type="text" class="glass-input" style="flex:1;min-width:200px" placeholder="Search memories..." value="${esc(S.mem.q)}">
            <select id="mem-tag" class="glass-input">${tagOptions}</select>
            <button id="mem-search-btn" class="glass-btn">🔍 Search</button>
        </div>
    </div>
    <div class="glass" style="overflow:hidden">`;

    if (memories.length === 0) {
        html += '<div style="padding:40px;text-align:center;color:var(--text-muted)">No memories found</div>';
    } else {
        memories.forEach(m => {
            const tags = (m.context_tags || m.tags || []);
            const tagsHtml = tags.map(t => '<span class="badge badge-purple">' + esc(t) + '</span>').join(' ');
            const emoHtml = m.emotion_type ? '<span class="badge badge-pink">😊 ' + esc(m.emotion_type) + (m.emotion_intensity != null ? '(' + (m.emotion_intensity).toFixed(1) + ')' : '') + '</span>' : '';
            const strHtml = m.strength != null ? '<span style="color:var(--accent-yellow)">⚡' + (m.strength).toFixed(2) + '</span>' : '';
            const timeHtml = m.created_at ? '<span>📅 ' + relativeTime(m.created_at) + '</span>' : '';
            const scoreHtml = m._score != null ? '<span class="badge badge-green">Score: ' + m._score.toFixed(3) + '</span>' : '';

            html += `<div class="memory-card" style="cursor:pointer" data-memkey="${esc(m.memory_key || m.key || '')}" data-memjson='${JSON.stringify({
                memory_key: m.memory_key || m.key || '',
                content: m.content || '',
                tags: m.context_tags || m.tags || [],
                emotion_type: m.emotion_type || '',
                emotion_intensity: m.emotion_intensity,
                importance: m.importance,
                strength: m._score != null ? m._score : (m.strength != null ? m.strength : null),
                privacy_level: m.privacy_level || '',
                source_context: m.source_context || '',
                created_at: m.created_at || '',
                updated_at: m.updated_at || '',
            }).replace(/'/g, "&#39;")}'>
                <div class="memory-key">${esc(m.memory_key || m.key || '--')}</div>
                <div class="memory-content">${esc(truncate(m.content || '', 200))}</div>
                <div class="memory-meta">${tagsHtml} ${emoHtml} ${strHtml} ${scoreHtml} ${timeHtml}</div>
            </div>`;
        });
    }
    html += '</div>';

    if (!isSearch && totalPages > 0) {
        html += `<div style="display:flex;justify-content:center;align-items:center;gap:12px;margin-top:16px">
            <button class="glass-btn mem-page-btn" data-page="${S.mem.page - 1}" ${S.mem.page <= 1 ? 'disabled style="opacity:0.4;pointer-events:none"' : ''}>◀ Prev</button>
            <span style="font-size:0.85rem;color:var(--text-muted)">Page ${S.mem.page} of ${totalPages} (${totalCount} total)</span>
            <button class="glass-btn mem-page-btn" data-page="${S.mem.page + 1}" ${S.mem.page >= totalPages ? 'disabled style="opacity:0.4;pointer-events:none"' : ''}>Next ▶</button>
        </div>`;
    }
    el.innerHTML = html;
}

function bindMemoryEvents() {
    const searchBtn = document.getElementById('mem-search-btn');
    const searchInput = document.getElementById('mem-search');
    const tagSelect = document.getElementById('mem-tag');
    if (searchBtn) searchBtn.onclick = () => {
        S.mem.q = searchInput.value.trim();
        S.mem.tag = tagSelect.value;
        S.mem.page = 1;
        loadMemories();
    };
    if (searchInput) searchInput.onkeydown = (e) => { if (e.key === 'Enter') searchBtn.click(); };
    if (tagSelect) tagSelect.onchange = () => {
        S.mem.tag = tagSelect.value;
        S.mem.q = '';
        if (searchInput) searchInput.value = '';
        S.mem.page = 1;
        loadMemories();
    };
    document.querySelectorAll('.mem-page-btn').forEach(btn => {
        btn.onclick = () => loadMemories(parseInt(btn.dataset.page));
    });
    document.querySelectorAll('.memory-card[data-memjson]').forEach(card => {
        card.onclick = () => {
            try {
                const mem = JSON.parse(card.getAttribute('data-memjson').replace(/&#39;/g, "'"));
                openMemModal(mem);
            } catch(e) { console.error('Modal parse error', e); }
        };
    });
}

/* =================================================================
   TAB 4: SETTINGS
   ================================================================= */
async function loadSettings() {
    const el = document.getElementById('settings-content');
    try {
        const [settings, status] = await Promise.all([
            api('/api/settings'),
            api('/api/settings/status')
        ]);
        S.settingsData = settings;
        renderSettings(el, settings, status);
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
    const categoryIcons = {
        server: '🖥️', embedding: '🧠', reranker: '🔍', qdrant: '📦',
        worker: '⏰', general: '⚙️', search: '🔎', persona: '👤'
    };

    let html = '';
    for (const [cat, fields] of Object.entries(settings)) {
        if (typeof fields !== 'object' || fields === null) continue;
        // Skip categories with no renderable fields
        const hasFields = Object.values(fields).some(f => typeof f === 'object' && f !== null);
        if (!hasFields) continue;
        const icon = categoryIcons[cat] || '⚙️';
        const catLabel = cat.charAt(0).toUpperCase() + cat.slice(1);

        // Check reload status
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

        html += '<div class="glass p-6 mb-6">';
        html += '<div class="card-title">' + icon + ' ' + esc(catLabel) + ' Settings</div>';
        html += statusHtml;

        for (const [key, meta] of Object.entries(fields)) {
            if (typeof meta !== 'object' || meta === null) continue;
            const val = meta.value != null ? meta.value : '';
            const src = meta.source || 'default';
            const hot = meta.hot_reload !== false;
            const inputId = 'setting-' + cat + '-' + key;
            const isPassword = key.toLowerCase().includes('key') || key.toLowerCase().includes('password') || key.toLowerCase().includes('secret');
            const inputType = isPassword ? 'password' : (typeof val === 'number' ? 'number' : 'text');

            html += '<div class="setting-row">';
            var desc = meta.description || '';
            var reloadHint = hot ? '🔄 Hot-reload OK' : '🔒 Requires restart';
            if (meta.reload_time) reloadHint += ' (⏱ ' + meta.reload_time + ')';
            var tooltipText = reloadHint;
            html += '<div style="display:flex;flex-direction:column;gap:2px;flex:0 0 auto;min-width:160px">';
            html += '<label class="setting-label" for="' + inputId + '" title="' + esc(tooltipText) + '" style="margin-bottom:0">' + esc(key.replace(/_/g, ' ')) + '</label>';
            if (desc) html += '<span style="font-size:0.7rem;color:var(--text-muted);line-height:1.3">' + esc(desc) + '</span>';
            html += '</div>';
            html += sourceIcon(src);
            if (!hot) html += '<span title="Restart required" style="cursor:help">🔒</span>';

            // Select for known enum-like fields
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
            } else {
                html += '<input id="' + inputId + '" type="' + inputType + '" class="glass-input" style="flex:1;min-width:160px" value="' + esc(String(val)) + '" data-cat="' + esc(cat) + '" data-key="' + esc(key) + '"' + (typeof val === 'number' ? ' step="any"' : '') + '>';
            }

            html += '<button class="glass-btn setting-apply-btn" data-cat="' + esc(cat) + '" data-key="' + esc(key) + '" data-input="' + inputId + '" style="padding:6px 12px;font-size:0.78rem">' + (hot ? '✅ Apply' : '🔒 Apply*') + '</button>';
            if (!hot) html += '<span style="font-size:0.7rem;color:var(--accent-yellow)">Restart required</span>';
            html += '</div>';
        }
        html += '</div>';
    }

    // Source legend & action buttons
    html += `
    <div class="glass p-6">
        <div class="card-title">💾 Configuration Source Priority</div>
        <div style="font-size:0.85rem;color:var(--text-secondary);margin-bottom:16px">
            <span class="setting-source source-env">🌐 env</span>
            <span style="margin:0 8px">></span>
            <span class="setting-source source-override">📝 override</span>
            <span style="margin:0 8px">></span>
            <span class="setting-source source-default">📋 default</span>
        </div>
        <div style="display:flex;gap:10px;flex-wrap:wrap">
            <button id="export-config-btn" class="glass-btn-success glass-btn">📤 Export Config</button>
            <button id="reset-config-btn" class="glass-btn-danger glass-btn">🗑️ Reset All to Defaults</button>
        </div>
    </div>`;

    el.innerHTML = html;

    // Bind apply buttons
    document.querySelectorAll('.setting-apply-btn').forEach(btn => {
        btn.onclick = async () => {
            const cat = btn.dataset.cat;
            const key = btn.dataset.key;
            const input = document.getElementById(btn.dataset.input);
            let value = input.value;
            // Type coercion
            if (input.type === 'number') value = parseFloat(value);
            btn.textContent = '⏳';
            btn.disabled = true;
            try {
                await api('/api/settings', { method: 'PUT', body: JSON.stringify({ category: cat, key, value }) });
                toast('Updated ' + cat + '.' + key, 'success');
                btn.textContent = '✅ Done';
                // Poll status for model reloads
                if (cat === 'embedding' || cat === 'reranker') startStatusPoll();
                setTimeout(() => loadSettings(), 1500);
            } catch (e) {
                toast('Error: ' + e.message, 'error');
                btn.textContent = '❌ Error';
            }
            setTimeout(() => { btn.disabled = false; }, 2000);
        };
    });

    // Export
    const expBtn = document.getElementById('export-config-btn');
    if (expBtn) expBtn.onclick = () => {
        const blob = new Blob([JSON.stringify(settings, null, 2)], {type: 'application/json'});
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = 'memorymcp-config.json';
        a.click();
        toast('Config exported', 'success');
    };

    // Reset
    const rstBtn = document.getElementById('reset-config-btn');
    if (rstBtn) rstBtn.onclick = async () => {
        if (!confirm('Reset ALL settings to defaults? This cannot be undone.')) return;
        try {
            // Reset each override setting
            for (const [cat, fields] of Object.entries(settings)) {
                if (typeof fields !== 'object') continue;
                for (const [key, meta] of Object.entries(fields)) {
                    if (meta && meta.source === 'override') {
                        await api('/api/settings', { method: 'PUT', body: JSON.stringify({ category: cat, key, value: meta.default_value != null ? meta.default_value : meta.value }) });
                    }
                }
            }
            toast('Settings reset to defaults', 'success');
            setTimeout(() => loadSettings(), 500);
        } catch (e) {
            toast('Reset failed: ' + e.message, 'error');
        }
    };
}

function startStatusPoll() {
    if (S.statusPoll) clearInterval(S.statusPoll);
    S.statusPoll = setInterval(async () => {
        try {
            const status = await api('/api/settings/status');
            const rs = status.reload_status || {};
            const allDone = Object.values(rs).every(s => !s.status || s.status === 'idle' || s.status === 'ready' || s.status === 'success' || s.status === 'error');
            if (allDone) {
                clearInterval(S.statusPoll);
                S.statusPoll = null;
                loadSettings();
            } else {
                // Re-render to show progress
                const el = document.getElementById('settings-content');
                const settings = S.settingsData;
                if (settings) renderSettings(el, settings, status);
            }
        } catch(e) { /* ignore poll errors */ }
    }, 2000);
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
    document.addEventListener('keydown', _memModalKeyHandler);
}
function closeMemModal() {
    document.getElementById('mem-modal-overlay').style.display = 'none';
    document.removeEventListener('keydown', _memModalKeyHandler);
}
function _memModalKeyHandler(e) { if (e.key === 'Escape') closeMemModal(); }

/* =================================================================
   TAB 5: ADMIN
   ================================================================= */
async function loadAdmin() {
    const el = document.getElementById('admin-content');
    try {
        const [health, dashData] = await Promise.all([
            api('/health'),
            S.dashCache ? Promise.resolve(S.dashCache) : api('/api/dashboard/' + encodeURIComponent(S.persona))
        ]);
        if (!S.dashCache) S.dashCache = dashData;
        const stats = dashData.stats || {};
        const uptimeMs = Date.now() - S.initTime;
        const uptimeStr = uptimeMs < 3600000 ? Math.floor(uptimeMs/60000) + 'm' : Math.floor(uptimeMs/3600000) + 'h ' + Math.floor((uptimeMs%3600000)/60000) + 'm';

        el.innerHTML = `
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
            <div class="glass p-6">
                <div class="card-title">🔄 Rebuild Vector Store</div>
                <p style="font-size:0.85rem;color:var(--text-secondary);margin-bottom:16px">Rebuild the Qdrant vector collection for the current persona. This may take a few minutes.</p>
                <button id="rebuild-btn" class="glass-btn" style="width:100%">🔄 Rebuild Vectors</button>
                <div id="rebuild-status" style="margin-top:12px;font-size:0.82rem;color:var(--text-muted);text-align:center"></div>
            </div>
            <div class="glass p-6">
                <div class="card-title">📊 Database Stats</div>
                <div style="display:grid;gap:10px">
                    <div style="display:flex;justify-content:space-between"><span style="color:var(--text-muted)">Total Memories</span><span style="font-weight:600">${stats.total_count ?? '--'}</span></div>
                    <div style="display:flex;justify-content:space-between"><span style="color:var(--text-muted)">Blocks</span><span style="font-weight:600">${(dashData.blocks || []).length}</span></div>
                    <div style="display:flex;justify-content:space-between"><span style="color:var(--text-muted)">Unique Tags</span><span style="font-weight:600">${Object.keys(stats.tag_distribution || {}).length}</span></div>
                    <div style="display:flex;justify-content:space-between"><span style="color:var(--text-muted)">Emotions Tracked</span><span style="font-weight:600">${Object.keys(stats.emotion_distribution || {}).length}</span></div>
                    <div style="display:flex;justify-content:space-between"><span style="color:var(--text-muted)">Goals</span><span style="font-weight:600">${(dashData.goals || []).length}</span></div>
                    <div style="display:flex;justify-content:space-between"><span style="color:var(--text-muted)">Promises</span><span style="font-weight:600">${(dashData.promises || []).length}</span></div>
                </div>
            </div>
            <div class="glass p-6">
                <div class="card-title">📋 System Info</div>
                <div style="display:grid;gap:10px">
                    <div style="display:flex;justify-content:space-between"><span style="color:var(--text-muted)">Version</span><span style="font-weight:600">${esc(health.version || '--')}</span></div>
                    <div style="display:flex;justify-content:space-between"><span style="color:var(--text-muted)">Status</span><span class="badge ${health.status === 'ok' ? 'badge-green' : 'badge-red'}">${esc(health.status || '--')}</span></div>
                    <div style="display:flex;justify-content:space-between"><span style="color:var(--text-muted)">Qdrant</span><span class="badge ${health.qdrant === 'connected' ? 'badge-green' : 'badge-yellow'}">${esc(health.qdrant || '--')}</span></div>
                    <div style="display:flex;justify-content:space-between"><span style="color:var(--text-muted)">Session</span><span style="font-weight:600">${uptimeStr}</span></div>
                    <div style="display:flex;justify-content:space-between"><span style="color:var(--text-muted)">Persona</span><span style="font-weight:600">${esc(S.persona)}</span></div>
                </div>
            </div>
        </div>`;

        // Rebuild button
        document.getElementById('rebuild-btn').onclick = async () => {
            const btn = document.getElementById('rebuild-btn');
            const statusEl = document.getElementById('rebuild-status');
            btn.disabled = true;
            btn.textContent = '⏳ Rebuilding...';
            statusEl.innerHTML = '<div class="progress-wrap"><div class="progress-bar progress-indeterminate"></div></div>';
            try {
                await api('/api/admin/rebuild/' + encodeURIComponent(S.persona), { method: 'POST' });
                statusEl.innerHTML = '<span style="color:var(--accent-green)">✅ Rebuild started successfully</span>';
                toast('Vector rebuild initiated', 'success');
            } catch (e) {
                statusEl.innerHTML = '<span style="color:var(--accent-red)">❌ ' + esc(e.message) + '</span>';
                toast('Rebuild failed: ' + e.message, 'error');
            }
            btn.disabled = false;
            btn.textContent = '🔄 Rebuild Vectors';
        };
        updateLastTime();
    } catch (e) {
        el.innerHTML = errorCard('Failed to load admin: ' + e.message);
    }
}

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
        S.persona = personas[0];
        loadTab(S.tab);
    } catch (e) {
        toast('Failed to load personas: ' + e.message, 'error');
    }

    // Event: Persona change
    document.getElementById('persona-select').onchange = (e) => {
        S.persona = e.target.value;
        S.dashCache = null;
        S.mem = { page: 1, tag: '', q: '', perPage: 20 };
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
        if (e.altKey && e.key >= '1' && e.key <= '5') {
            e.preventDefault();
            const tabs = ['overview','analytics','memories','settings','admin'];
            switchTab(tabs[parseInt(e.key) - 1]);
        }
    });
}

// Boot
init();
</script>
</body>
</html>"""
