"""Memory Timeline tab section for the MemoryMCP Dashboard.

Interactive chronological visualization of memories using vis-timeline.
Memories are displayed as colored items along a horizontal time axis,
color-coded by emotion type with importance-based sizing. Supports
filtering by emotion type, tag, importance threshold, and time range.

API consumed:
    GET /api/observations/{persona}?page={page}&per_page={per_page}

Response shape (per entry):
    {
        "key", "content", "created_at", "importance",
        "emotion_type", "emotion_intensity", "tags", ...
    }
"""


def render_timeline_tab() -> str:
    """Return the HTML for the Memory Timeline tab panel.

    Includes:
    - Filter toolbar (emotion type, tag, importance min, date range, page size)
    - vis-timeline container (500px height)
    - Click-to-inspect detail panel (slide-out, right side)
    - Scoped styles for timeline items and panel
    """
    return r"""
        <section id="tab-timeline" class="tab-panel" role="tabpanel">
            <div style="margin-bottom:16px; padding-bottom:12px; border-bottom:1px solid var(--glass-border);">
                <h2 style="font-size:1.25rem; font-weight:700; color:var(--text-primary); display:flex; align-items:center; gap:10px;"><span style="font-size:1.4rem;">📅</span> Timeline</h2>
            </div>
            <style>
                #tab-timeline .tl-toolbar {
                    display: flex; flex-wrap: wrap; gap: 8px; align-items: flex-end;
                    margin-bottom: 12px; padding: 10px 12px;
                    background: rgba(255,255,255,0.03); border: 1px solid var(--glass-border);
                    border-radius: 10px;
                }
                #tab-timeline .tl-toolbar label {
                    font-size: 0.72rem; color: var(--text-muted); display: flex;
                    flex-direction: column; gap: 3px;
                }
                #tab-timeline .tl-toolbar select, #tab-timeline .tl-toolbar input {
                    background: rgba(255,255,255,0.05); border: 1px solid var(--glass-border);
                    border-radius: 6px; padding: 4px 8px; color: var(--text-primary);
                    font-size: 0.75rem; font-family: inherit; outline: none; min-width: 100px;
                }
                #tab-timeline .tl-toolbar select:focus, #tab-timeline .tl-toolbar input:focus {
                    border-color: var(--accent-purple);
                }
                #tl-container {
                    height: 500px; border: 1px solid var(--glass-border);
                    border-radius: 10px; overflow: hidden;
                    background: rgba(0,0,0,0.15);
                }
                #tl-container .vis-item {
                    border-radius: 6px; border-width: 2px; font-size: 0.72rem;
                    transition: transform 0.15s, box-shadow 0.15s;
                }
                #tl-container .vis-item:hover {
                    transform: scale(1.02); z-index: 10;
                    box-shadow: 0 4px 16px rgba(0,0,0,0.4);
                }
                #tl-container .vis-item.vis-selected {
                    border-color: var(--accent-purple) !important;
                    box-shadow: 0 0 12px rgba(167,139,250,0.4);
                }
                #tl-container .vis-item .vis-item-content {
                    padding: 4px 8px; white-space: nowrap; overflow: hidden;
                    text-overflow: ellipsis; max-width: 200px;
                }
                /* Timeline detail panel */
                #tl-detail-panel {
                    position: fixed; top: 0; right: -420px; width: 400px; height: 100vh;
                    background: var(--bg-primary); border-left: 1px solid var(--glass-border);
                    box-shadow: -4px 0 24px rgba(0,0,0,0.4); z-index: 500;
                    transition: right 0.3s ease; display: flex; flex-direction: column;
                    padding: 20px; gap: 10px; overflow-y: auto;
                }
                #tl-detail-panel.open { right: 0; }
                #tl-detail-panel .tl-detail-close {
                    position: absolute; top: 12px; right: 12px;
                    background: none; border: 1px solid var(--glass-border); border-radius: 6px;
                    color: var(--text-muted); padding: 4px 10px; cursor: pointer; font-size: 0.82rem;
                }
                #tl-detail-panel .tl-detail-close:hover { color: var(--text-primary); background: var(--glass-bg); }
                #tl-detail-panel .tl-detail-label {
                    font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase;
                    letter-spacing: 0.04em;
                }
                #tl-detail-panel .tl-detail-value {
                    font-size: 0.82rem; color: var(--text-secondary); line-height: 1.5;
                    word-break: break-word;
                }
                #tl-detail-panel .tl-detail-content {
                    background: rgba(255,255,255,0.04); border: 1px solid var(--glass-border);
                    border-radius: 8px; padding: 10px; font-size: 0.85rem;
                    color: var(--text-primary); line-height: 1.6; word-break: break-word;
                    max-height: 300px; overflow-y: auto;
                }
                #tl-loading {
                    display: flex; align-items: center; justify-content: center;
                    height: 500px; color: var(--text-muted); font-size: 0.9rem;
                }
                /* Emotion legend */
                #tl-legend {
                    display: flex; flex-wrap: wrap; gap: 4px 12px; margin-top: 8px;
                }
                #tl-legend .tl-legend-dot {
                    display: inline-block; width: 10px; height: 10px; border-radius: 50%;
                    margin-right: 3px; vertical-align: middle;
                }
                #tl-legend span { font-size: 0.68rem; color: var(--text-muted); }
            </style>

            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;">
                <h2 style="font-size:1.1rem;font-weight:600;color:var(--text-primary);">⏳ Memory Timeline</h2>
                <button onclick="loadTimeline()" style="background:none;border:1px solid var(--glass-border);border-radius:6px;color:var(--text-muted);padding:4px 10px;cursor:pointer;font-size:0.75rem;">🔄 更新</button>
            </div>

            <div class="tl-toolbar">
                <label>感情 <select id="tl-emotion"><option value="">すべて</option></select></label>
                <label>タグ <input type="text" id="tl-tag" placeholder="例: goal" /></label>
                <label>重要度≧ <input type="number" id="tl-min-importance" value="0" min="0" max="1" step="0.1" style="min-width:60px;" /></label>
                <label>件数 <select id="tl-per-page"><option value="50">50</option><option value="100" selected>100</option><option value="200">200</option><option value="500">500</option></select></label>
            </div>

            <div id="tl-container"><div id="tl-loading">読み込み中...</div></div>

            <div id="tl-legend"></div>

            <div id="tl-detail-panel">
                <button class="tl-detail-close" onclick="closeTimelineDetail()">✕</button>
                <div class="tl-detail-label">内容</div>
                <div class="tl-detail-content" id="tl-detail-content"></div>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
                    <div><div class="tl-detail-label">感情</div><div class="tl-detail-value" id="tl-detail-emotion"></div></div>
                    <div><div class="tl-detail-label">重要度</div><div class="tl-detail-value" id="tl-detail-importance"></div></div>
                    <div><div class="tl-detail-label">日時</div><div class="tl-detail-value" id="tl-detail-time"></div></div>
                    <div><div class="tl-detail-label">タグ</div><div class="tl-detail-value" id="tl-detail-tags"></div></div>
                </div>
                <div id="tl-detail-body" style="margin-top:10px;"></div>
            </div>
        </section>
    """


def render_timeline_js() -> str:
    """Return the JavaScript for the Memory Timeline tab."""
    return r"""
/* =================================================================
   MEMORY TIMELINE
   ================================================================= */
const TL_EMOTION_COLORS = {
    joy:         { bg: 'rgba(251,191,36,0.15)',  border: '#FBBF24', emoji: '😊' },
    sadness:     { bg: 'rgba(96,165,250,0.15)',  border: '#60A5FA', emoji: '😢' },
    anger:       { bg: 'rgba(248,113,113,0.15)', border: '#F87171', emoji: '😠' },
    love:        { bg: 'rgba(244,114,182,0.15)', border: '#F472B6', emoji: '❤️' },
    fear:        { bg: 'rgba(167,139,250,0.15)', border: '#A78BFA', emoji: '😨' },
    surprise:    { bg: 'rgba(52,211,153,0.15)',  border: '#34D399', emoji: '😲' },
    neutral:     { bg: 'rgba(156,163,175,0.15)', border: '#9CA3AF', emoji: '😐' },
    excitement:  { bg: 'rgba(245,158,11,0.15)',  border: '#F59E0B', emoji: '🤩' },
    pride:       { bg: 'rgba(129,140,248,0.15)', border: '#818CF8', emoji: '🦚' },
    shame:       { bg: 'rgba(251,113,133,0.15)', border: '#FB7185', emoji: '😳' },
    curiosity:   { bg: 'rgba(45,212,191,0.15)',  border: '#2DD4BF', emoji: '🤔' },
    anxiety:     { bg: 'rgba(248,113,113,0.12)', border: '#F87171', emoji: '😰' },
    frustration: { bg: 'rgba(251,146,60,0.15)',  border: '#FB923C', emoji: '😤' },
    nostalgia:   { bg: 'rgba(167,139,250,0.12)', border: '#A78BFA', emoji: '🌅' },
    trust:       { bg: 'rgba(52,211,153,0.12)',  border: '#34D399', emoji: '🤝' },
    loneliness:  { bg: 'rgba(148,163,184,0.15)', border: '#94A3B8', emoji: '😔' },
    contentment: { bg: 'rgba(134,239,172,0.15)', border: '#86EFAC', emoji: '😌' },
    awe:         { bg: 'rgba(192,132,252,0.15)', border: '#C084FC', emoji: '🌌' },
    relief:      { bg: 'rgba(110,231,183,0.15)', border: '#6EE7B7', emoji: '😮‍💨' },
    disgust:     { bg: 'rgba(163,230,53,0.15)',  border: '#A3E635', emoji: '🤢' },
    guilt:       { bg: 'rgba(252,165,165,0.15)', border: '#FCA5A5', emoji: '😞' },
};

function getEmotionStyle(emotion) {
    return TL_EMOTION_COLORS[emotion] || TL_EMOTION_COLORS['neutral'];
}

function buildEmotionLegend() {
    const legend = document.getElementById('tl-legend');
    if (!legend) return;
    let html = '';
    for (const [emo, style] of Object.entries(TL_EMOTION_COLORS)) {
        html += '<span><span class="tl-legend-dot" style="background:' + style.border + '"></span>' + style.emoji + ' ' + emo + '</span>';
    }
    legend.innerHTML = html;
    // Populate emotion filter dropdown
    const sel = document.getElementById('tl-emotion');
    if (sel) {
        sel.innerHTML = '<option value="">すべて</option>';
        for (const emo of Object.keys(TL_EMOTION_COLORS).sort()) {
            sel.innerHTML += '<option value="' + emo + '">' + TL_EMOTION_COLORS[emo].emoji + ' ' + emo + '</option>';
        }
    }
}

let _timeline = null;
let _timelineItems = null;
let _timelineData = null;

async function loadTimeline() {
    if (!S.persona) return;
    const container = document.getElementById('tl-container');
    const loading = document.getElementById('tl-loading');
    if (!container) return;
    const perPage = parseInt(document.getElementById('tl-per-page')?.value || '100');
    const emotion = document.getElementById('tl-emotion')?.value || '';
    const tag = document.getElementById('tl-tag')?.value.trim() || '';
    const minImp = parseFloat(document.getElementById('tl-min-importance')?.value || '0');

    if (loading) loading.style.display = 'flex';

    try {
        let allMemories = [];
        let page = 1;
        let totalPages = 1;
        while (page <= totalPages && page <= 5) {  // max 5 pages
            const resp = await api('/api/observations/' + encodeURIComponent(S.persona) +
                '?page=' + page + '&per_page=' + perPage);
            if (!resp.memories) break;
            allMemories = allMemories.concat(resp.memories);
            totalPages = resp.total_pages || 1;
            page++;
        }

        // Filter client-side
        if (emotion) allMemories = allMemories.filter(m => m.emotion_type === emotion);
        if (tag) allMemories = allMemories.filter(m => (m.tags || []).some(t => t.toLowerCase().includes(tag.toLowerCase())));
        if (minImp > 0) allMemories = allMemories.filter(m => (m.importance || 0) >= minImp);

        _timelineData = allMemories;

        if (loading) loading.style.display = 'none';

        if (_timeline) { _timeline.destroy(); _timeline = null; }

        const items = allMemories.map((m, i) => {
            const style = getEmotionStyle(m.emotion_type || 'neutral');
            const content = (m.content || '').substring(0, 100);
            const imp = m.importance != null ? m.importance : 0.5;
            return {
                id: m.key || i,
                content: style.emoji + ' ' + content,
                start: m.created_at ? new Date(m.created_at) : new Date(),
                title: '<div style="max-width:300px;white-space:normal;font-size:0.78rem;line-height:1.4;">' +
                       esc(m.content || '') + '</div>' +
                       '<div style="font-size:0.68rem;color:var(--text-muted);margin-top:4px;">' +
                       (style.emoji + ' ' + (m.emotion_type || 'neutral') + ' · imp:' + imp.toFixed(2)) + '</div>',
                style: 'background:' + style.bg + ';border-color:' + style.border + ';' +
                       'font-size:' + (0.65 + imp * 0.2) + 'rem;',
            };
        });

        _timelineItems = new vis.DataSet(items);

        const options = {
            height: '100%',
            minHeight: '500px',
            start: items.length > 0 ? new Date(items[items.length-1].start.getTime() - 86400000 * 7) : new Date(),
            end: new Date(),
            zoomable: true,
            moveable: true,
            selectable: true,
            multiselect: false,
            tooltip: { followMouse: true, overflowMethod: 'cap' },
            margin: { item: { vertical: 4 } },
            timeAxis: { scale: 'day', step: 1 },
            orientation: { axis: 'top' },
        };

        _timeline = new vis.Timeline(container, _timelineItems, options);

        _timeline.on('select', function(props) {
            if (props.items.length > 0) {
                const id = props.items[0];
                const mem = _timelineData.find(m => (m.key || '') === id);
                if (mem) showTimelineDetail(mem);
            }
        });

        _timeline.on('doubleClick', function(props) {
            if (props.what === 'background') {
                _timeline.fit();
            }
        });

    } catch (e) {
        if (loading) { loading.textContent = '読み込み失敗: ' + e.message; loading.style.display = 'flex'; }
    }
}

function showTimelineDetail(mem) {
    const panel = document.getElementById('tl-detail-panel');
    if (!panel) return;
    document.getElementById('tl-detail-content').textContent = mem.content || '';
    const style = getEmotionStyle(mem.emotion_type || 'neutral');
    document.getElementById('tl-detail-emotion').innerHTML = style.emoji + ' ' + (mem.emotion_type || 'neutral');
    document.getElementById('tl-detail-importance').textContent = (mem.importance != null ? mem.importance.toFixed(2) : '0.50');
    document.getElementById('tl-detail-time').textContent = mem.created_at
        ? new Date(mem.created_at).toLocaleString('ja-JP') : '—';
    document.getElementById('tl-detail-tags').textContent = (mem.tags || []).join(', ') || '—';

    /* Body State & Emotions bars */
    var bodyHtml = '';
    if (mem.body_state) {
        var bodyKeys = ['fatigue','warmth','arousal','heart_rate','pain'];
        var bodyLabels = {fatigue:'🔥 Fatigue',warmth:'🌸 Warmth',arousal:'⚡ Arousal',heart_rate:'💓 Heart',pain:'💢 Pain'};
        var bodyColors = {fatigue:'linear-gradient(90deg,#f87171,#fca5a5)',warmth:'linear-gradient(90deg,#f9a8d4,#fda4af)',arousal:'linear-gradient(90deg,#a78bfa,#c4b5fd)',heart_rate:'linear-gradient(90deg,#ef4444,#fca5a5)',pain:'linear-gradient(90deg,#f59e0b,#fcd34d)'};
        var hasBody = bodyKeys.some(function(k){ return mem.body_state[k] != null; });
        if (hasBody) {
            bodyHtml += '<div style="margin-bottom:10px;"><div class="tl-detail-label">Body State</div>';
            bodyKeys.forEach(function(k) {
                if (mem.body_state[k] != null) {
                    var val = mem.body_state[k];
                    var pct = Math.round(val * 100);
                    bodyHtml += '<div style="display:flex;align-items:center;gap:6px;margin-top:4px;">';
                    bodyHtml += '<span style="font-size:0.7rem;color:var(--text-muted);min-width:70px">' + bodyLabels[k] + '</span>';
                    bodyHtml += '<div style="flex:1;height:4px;background:rgba(255,255,255,0.1);border-radius:2px;overflow:hidden">';
                    bodyHtml += '<div style="height:100%;width:' + pct + '%;background:' + bodyColors[k] + ';border-radius:2px"></div>';
                    bodyHtml += '</div>';
                    bodyHtml += '<span style="font-size:0.7rem;color:var(--text-muted);min-width:28px;text-align:right">' + pct + '%</span>';
                    bodyHtml += '</div>';
                }
            });
            bodyHtml += '</div>';
        }
    }
    if (mem.emotions && Object.keys(mem.emotions).length > 0) {
        var emoEntries = Object.entries(mem.emotions).filter(function(e){ return e[1] > 0.05; }).sort(function(a,b){ return b[1]-a[1]; }).slice(0, 3);
        if (emoEntries.length > 0) {
            var emoBarColors = {joy:'linear-gradient(90deg,#fbbf24,#fcd34d)',sadness:'linear-gradient(90deg,#60a5fa,#93c5fd)',anger:'linear-gradient(90deg,#ef4444,#fca5a5)',fear:'linear-gradient(90deg,#a855f7,#c4b5fd)',disgust:'linear-gradient(90deg,#22c55e,#86efac)',surprise:'linear-gradient(90deg,#ec4899,#f9a8d4)',love:'linear-gradient(90deg,#fb7185,#fda4af)',trust:'linear-gradient(90deg,#14b8a6,#5eead4)',anticipation:'linear-gradient(90deg,#f97316,#fdba74)',curiosity:'linear-gradient(90deg,#6366f1,#a5b4fc)',neutral:'linear-gradient(90deg,#9ca3af,#d1d5db)',excitement:'linear-gradient(90deg,#f59e0b,#fbbf24)',pride:'linear-gradient(90deg,#818cf8,#a5b4fc)',shame:'linear-gradient(90deg,#fb7185,#fda4af)',nostalgia:'linear-gradient(90deg,#a78bfa,#c4b5fd)',anxiety:'linear-gradient(90deg,#f87171,#fca5a5)',contentment:'linear-gradient(90deg,#86efac,#bbf7d0)',frustration:'linear-gradient(90deg,#fb923c,#fdba74)',loneliness:'linear-gradient(90deg,#94a3b8,#cbd5e1)',awe:'linear-gradient(90deg,#c084fc,#e9d5ff)',relief:'linear-gradient(90deg,#6ee7b7,#a7f3d0)'};
            bodyHtml += '<div><div class="tl-detail-label">Emotions</div>';
            emoEntries.forEach(function(e) {
                var name = e[0], val = e[1];
                var color = emoBarColors[name] || emoBarColors.neutral;
                var pct = Math.round(val * 100);
                bodyHtml += '<div style="display:flex;align-items:center;gap:6px;margin-top:4px;">';
                bodyHtml += '<span style="font-size:0.7rem;color:var(--text-muted);min-width:70px;text-transform:capitalize">' + name + '</span>';
                bodyHtml += '<div style="flex:1;height:4px;background:rgba(255,255,255,0.1);border-radius:2px;overflow:hidden">';
                bodyHtml += '<div style="height:100%;width:' + pct + '%;background:' + color + ';border-radius:2px"></div>';
                bodyHtml += '</div>';
                bodyHtml += '<span style="font-size:0.7rem;color:var(--text-muted);min-width:28px;text-align:right">' + pct + '%</span>';
                bodyHtml += '</div>';
            });
            bodyHtml += '</div>';
        }
    }
    document.getElementById('tl-detail-body').innerHTML = bodyHtml;

    panel.classList.add('open');
}

function closeTimelineDetail() {
    document.getElementById('tl-detail-panel')?.classList.remove('open');
}

// Initialize on tab visibility
document.addEventListener('DOMContentLoaded', () => {
    buildEmotionLegend();
    // Load when timeline tab becomes visible via MutationObserver or tab switch
    const origSwitchTab = switchTab;
    if (typeof switchTab !== 'undefined') {
        switchTab = function(tabId) {
            origSwitchTab(tabId);
            if (tabId === 'timeline') {
                setTimeout(loadTimeline, 200);
            }
        };
    }
});
"""
