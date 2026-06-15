"""Activity tab section – session event history timeline.

Vertical timeline showing all session events (tool calls, chat messages,
LLM responses, session lifecycle) across platforms in chronological order.

API consumed:
    GET /api/session-events/{persona}?limit=50&offset=0&event_type=&order=desc
"""


def render_activity_tab() -> str:
    """Return the HTML for the Activity tab panel."""
    return r"""
        <section id="tab-activity" class="tab-panel" role="tabpanel">
            <div style="margin-bottom:16px; padding-bottom:12px; border-bottom:1px solid var(--glass-border);">
                <h2 style="font-size:1.25rem; font-weight:700; color:var(--text-primary); display:flex; align-items:center; gap:10px;">
                    <span style="font-size:1.4rem;"><i data-lucide="activity"></i></span> Activity
                </h2>
            </div>
            <style>
                /* Filter toolbar */
                #act-toolbar {
                    display:flex; flex-wrap:wrap; gap:10px; align-items:flex-end;
                    margin-bottom:16px; padding:10px 14px;
                    background:rgba(255,255,255,0.03); border:1px solid var(--glass-border);
                    border-radius:10px;
                }
                #act-toolbar label {
                    font-size:0.72rem; color:var(--text-muted);
                    display:flex; flex-direction:column; gap:3px;
                }
                #act-toolbar select, #act-toolbar button {
                    background:rgba(255,255,255,0.05); border:1px solid var(--glass-border);
                    border-radius:6px; padding:4px 10px; color:var(--text-primary);
                    font-size:0.75rem; font-family:inherit; cursor:pointer; outline:none;
                }
                #act-toolbar select:focus, #act-toolbar button:focus {
                    border-color:var(--accent-purple);
                }
                #act-toolbar button.act-filter-active {
                    background:var(--accent-purple); color:#fff; border-color:var(--accent-purple);
                }
                /* Event type color coding */
                .act-event { --act-color: var(--accent-blue); }
                .act-event.type-tool\.called { --act-color: var(--accent-blue); }
                .act-event.type-chat\.message { --act-color: var(--accent-green); }
                .act-event.type-chat\.llm_response { --act-color: var(--accent-purple); }
                .act-event.type-session\.started { --act-color: var(--accent-yellow); }
                .act-event.type-session\.compact { --act-color: var(--accent-orange); }
                .act-event.type-events\.ingested { --act-color: var(--text-muted); }
                /* Session card */
                .act-session {
                    border:1px solid var(--glass-border); border-radius:10px;
                    margin-bottom:10px; overflow:hidden;
                    background:rgba(255,255,255,0.02);
                }
                .act-session-header {
                    display:flex; align-items:center; gap:10px;
                    padding:10px 14px; cursor:pointer;
                    background:rgba(255,255,255,0.04);
                    transition:background 0.15s;
                }
                .act-session-header:hover { background:rgba(255,255,255,0.07); }
                .act-session-header .act-session-id {
                    font-family:monospace; font-size:0.8rem; color:var(--accent-purple);
                    flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
                }
                .act-session-header .act-session-meta {
                    font-size:0.72rem; color:var(--text-muted);
                    display:flex; align-items:center; gap:8px;
                }
                .act-session-header .act-chevron {
                    transition:transform 0.2s; font-size:0.8rem; color:var(--text-muted);
                }
                .act-session.open .act-chevron { transform:rotate(90deg); }
                .act-session-body {
                    display:none; padding:6px 0;
                }
                .act-session.open .act-session-body { display:block; }
                /* Individual event row */
                .act-event {
                    display:flex; align-items:flex-start; gap:10px;
                    padding:8px 14px 8px 10px; border-left:3px solid var(--act-color);
                    margin-left:10px; transition:background 0.12s;
                }
                .act-event:hover { background:rgba(255,255,255,0.03); }
                .act-event .act-event-icon {
                    font-size:0.9rem; width:20px; text-align:center; flex-shrink:0;
                    margin-top:1px;
                }
                .act-event .act-event-body { flex:1; min-width:0; }
                .act-event .act-event-summary {
                    font-size:0.8rem; color:var(--text-primary);
                    word-break:break-word;
                }
                .act-event .act-event-time {
                    font-size:0.68rem; color:var(--text-muted);
                    margin-top:2px;
                }
                .act-event .act-event-detail {
                    display:none; margin-top:6px; padding:8px 10px;
                    background:rgba(255,255,255,0.03); border-radius:6px;
                    font-size:0.75rem; color:var(--text-secondary);
                    white-space:pre-wrap; word-break:break-word;
                    max-height:200px; overflow-y:auto;
                }
                .act-event.expanded .act-event-detail { display:block; }
                .act-event .act-event-summary { cursor:pointer; }
                /* Platform badge */
                .act-platform-badge {
                    display:inline-flex; align-items:center; gap:3px;
                    font-size:0.65rem; padding:1px 6px; border-radius:4px;
                    background:rgba(255,255,255,0.08);
                }
                /* Empty state */
                .act-empty {
                    text-align:center; padding:40px 20px; color:var(--text-muted);
                }
                .act-empty i { font-size:2.5rem; margin-bottom:12px; display:block; opacity:0.4; }
                /* Load more */
                .act-load-more {
                    display:block; width:100%; padding:10px; margin-top:8px;
                    background:rgba(255,255,255,0.04); border:1px solid var(--glass-border);
                    border-radius:8px; color:var(--text-secondary); font-size:0.8rem;
                    cursor:pointer; text-align:center; transition:background 0.15s;
                }
                .act-load-more:hover { background:rgba(255,255,255,0.08); }
            </style>
            <!-- Toolbar -->
            <div id="act-toolbar">
                <label>Event type
                    <select id="act-filter-type">
                        <option value="">All</option>
                        <option value="tool.called">Tool Calls</option>
                        <option value="chat.message">Chat Messages</option>
                        <option value="chat.llm_response">LLM Responses</option>
                        <option value="session.started">Session Starts</option>
                        <option value="session.compact">Compressions</option>
                        <option value="events.ingested">External Events</option>
                    </select>
                </label>
                <label>Order
                    <select id="act-filter-order">
                        <option value="desc">Newest first</option>
                        <option value="asc">Oldest first</option>
                    </select>
                </label>
                <button id="act-btn-refresh" onclick="loadActivity(true)" style="margin-left:auto;">
                    <i data-lucide="refresh-cw"></i> Refresh
                </button>
            </div>
            <!-- Feed container -->
            <div id="act-feed"></div>
            <!-- Load more button (inserted dynamically) -->
        </section>
        """


def render_activity_js() -> str:
    """Return the JavaScript for the Activity tab."""
    return r"""
/* =================================================================
   ACTIVITY TAB
   ================================================================= */
const ACT = {
    limit: 50,
    offset: 0,
    total: 0,
    filterType: '',
    filterOrder: 'desc',
    sessions: {}  // session_id -> { open: bool, events: [], platform }
};

const ACT_ICONS = {
    'tool.called':        '<i data-lucide=&quot;wrench&quot;></i>',
    'chat.message':       '<i data-lucide=&quot;message-square&quot;></i>',
    'chat.llm_response':  '<i data-lucide=&quot;bot&quot;></i>',
    'session.started':    '<i data-lucide=&quot;play&quot;></i>',
    'session.compact':    '<i data-lucide=&quot;shrink&quot;></i>',
    'events.ingested':    '<i data-lucide=&quot;upload&quot;></i>',
};

const ACT_LABELS = {
    'tool.called':        'Tool',
    'chat.message':       'You',
    'chat.llm_response':  'AI',
    'session.started':    'Start',
    'session.compact':    'Compress',
    'events.ingested':    'External',
};

const ACT_PLATFORM_ICONS = {
    'webui':    '<i data-lucide=&quot;globe&quot;></i>',
    'opencode': '<i data-lucide=&quot;terminal&quot;></i>',
    'mcp':      '<i data-lucide=&quot;plug&quot;></i>',
    'plugin':   '<i data-lucide=&quot;puzzle&quot;></i>',
};

async function loadActivity(reset = false) {
    if (reset) { ACT.offset = 0; ACT.sessions = {}; }

    const typeEl = document.getElementById('act-filter-type');
    const orderEl = document.getElementById('act-filter-order');
    ACT.filterType = typeEl ? typeEl.value : '';
    ACT.filterOrder = orderEl ? orderEl.value : 'desc';

    let url = '/api/session-events/' + encodeURIComponent(S.persona) +
        '?limit=' + ACT.limit + '&offset=' + ACT.offset + '&order=' + ACT.filterOrder;
    if (ACT.filterType) url += '&event_type=' + encodeURIComponent(ACT.filterType);

    try {
        const data = await api(url);
        ACT.total = data.total;
        const events = data.events || [];

        if (reset) {
            ACT.offset = 0;
            ACT.sessions = {};
            document.getElementById('act-feed').innerHTML = '';
        }

        if (events.length === 0 && ACT.offset === 0) {
            document.getElementById('act-feed').innerHTML =
                '<div class="act-empty"><i data-lucide=&quot;inbox&quot;></i><p>No activity yet. Events will appear here as you use MemoryMCP.</p></div>';
            if (typeof lucide !== 'undefined') lucide.createIcons();
            return;
        }

        // Group events by session_id
        for (const ev of events) {
            const sid = ev.session_id;
            if (!ACT.sessions[sid]) {
                ACT.sessions[sid] = {
                    open: Object.keys(ACT.sessions).length === 0 && ACT.offset === 0,
                    events: [],
                    platform: (ev.metadata && ev.metadata.platform) || 'webui',
                };
            }
            ACT.sessions[sid].events.push(ev);
        }

        renderActivityFeed();
        ACT.offset += events.length;

        // Load more button
        const hasMore = data.has_more;
        let loadMoreEl = document.getElementById('act-load-more');
        if (hasMore) {
            if (!loadMoreEl) {
                loadMoreEl = document.createElement('button');
                loadMoreEl.id = 'act-load-more';
                loadMoreEl.className = 'act-load-more';
                loadMoreEl.textContent = 'Load more...';
                loadMoreEl.onclick = () => loadActivity(false);
                document.getElementById('act-feed').appendChild(loadMoreEl);
            }
        } else if (loadMoreEl) {
            loadMoreEl.remove();
        }

        if (typeof lucide !== 'undefined') lucide.createIcons();
    } catch (e) {
        document.getElementById('act-feed').innerHTML =
            '<div class="act-empty"><i data-lucide=&quot;alert-triangle&quot;></i><p>Failed to load: ' + esc(e.message) + '</p></div>';
    }
}

function renderActivityFeed() {
    const feed = document.getElementById('act-feed');
    // Remove old load-more button before re-rendering
    const oldBtn = document.getElementById('act-load-more');
    if (oldBtn) oldBtn.remove();

    let html = '';

    // Iterate sessions in current display order
    const sessionIds = Object.keys(ACT.sessions);
    // Sort by first event timestamp
    sessionIds.sort((a, b) => {
        const ta = ACT.sessions[a].events[0]?.timestamp || '';
        const tb = ACT.sessions[b].events[0]?.timestamp || '';
        return ACT.filterOrder === 'desc' ? tb.localeCompare(ta) : ta.localeCompare(tb);
    });

    for (const sid of sessionIds) {
        const sess = ACT.sessions[sid];
        const platformIcon = ACT_PLATFORM_ICONS[sess.platform] || '';
        const firstTs = sess.events[0]?.timestamp || '';
        const eventCount = sess.events.length;
        const openClass = sess.open ? ' open' : '';

        html += '<div class="act-session' + openClass + '" data-session="' + esc(sid) + '">';
        html += '<div class="act-session-header" onclick="toggleActivitySession(\'' + esc(sid) + '\')">';
        html += '<span class="act-chevron">▶</span>';
        html += '<span class="act-session-id">' + esc(sid) + '</span>';
        html += '<span class="act-session-meta">';
        if (platformIcon) html += '<span class="act-platform-badge">' + platformIcon + ' ' + esc(sess.platform) + '</span>';
        html += '<span>' + eventCount + ' event' + (eventCount !== 1 ? 's' : '') + '</span>';
        html += '<span>' + relativeTime(firstTs) + '</span>';
        html += '</span></div>';

        html += '<div class="act-session-body">';
        // Sort events within session by timestamp
        const sorted = [...sess.events];
        sorted.sort((a, b) => {
            return ACT.filterOrder === 'desc'
                ? b.timestamp.localeCompare(a.timestamp)
                : a.timestamp.localeCompare(b.timestamp);
        });
        for (const ev of sorted) {
            const icon = ACT_ICONS[ev.event_type] || '<i data-lucide=&quot;circle&quot;></i>';
            const label = ACT_LABELS[ev.event_type] || ev.event_type;
            const hasDetail = ev.detail && ev.detail.length > 0;
            html += '<div class="act-event type-' + esc(ev.event_type) + '"';
            if (hasDetail) html += ' onclick="toggleActivityDetail(this)" style="cursor:pointer"';
            html += '>';
            html += '<span class="act-event-icon">' + icon + '</span>';
            html += '<div class="act-event-body">';
            html += '<div class="act-event-summary"><span style="font-size:0.68rem;color:var(--act-color);font-weight:600">' + esc(label) + '</span> ' + esc(ev.summary) + '</div>';
            html += '<div class="act-event-time">' + new Date(ev.timestamp).toLocaleString('ja-JP') + '</div>';
            if (hasDetail) {
                html += '<div class="act-event-detail">' + esc(ev.detail) + '</div>';
            }
            html += '</div></div>';
        }
        html += '</div></div>';
    }

    feed.innerHTML = html;
    if (typeof lucide !== 'undefined') lucide.createIcons();
}

function toggleActivitySession(sid) {
    const sessionEl = document.querySelector('.act-session[data-session="' + CSS.escape(sid) + '"]');
    if (!sessionEl) return;
    ACT.sessions[sid].open = !ACT.sessions[sid].open;
    if (ACT.sessions[sid].open) {
        sessionEl.classList.add('open');
        // Update chevron
        const body = sessionEl.querySelector('.act-session-body');
        if (body && body.innerHTML.trim() === '') {
            // Lazy render events
            const sess = ACT.sessions[sid];
            const sorted = [...sess.events];
            sorted.sort((a, b) => ACT.filterOrder === 'desc'
                ? b.timestamp.localeCompare(a.timestamp)
                : a.timestamp.localeCompare(b.timestamp));
            let h = '';
            for (const ev of sorted) {
                const icon = ACT_ICONS[ev.event_type] || '<i data-lucide=&quot;circle&quot;></i>';
                const label = ACT_LABELS[ev.event_type] || ev.event_type;
                const hasDetail = ev.detail && ev.detail.length > 0;
                h += '<div class="act-event type-' + esc(ev.event_type) + '"';
                if (hasDetail) h += ' onclick="toggleActivityDetail(this)" style="cursor:pointer"';
                h += '>';
                h += '<span class="act-event-icon">' + icon + '</span>';
                h += '<div class="act-event-body">';
                h += '<div class="act-event-summary"><span style="font-size:0.68rem;color:var(--act-color);font-weight:600">' + esc(label) + '</span> ' + esc(ev.summary) + '</div>';
                h += '<div class="act-event-time">' + new Date(ev.timestamp).toLocaleString('ja-JP') + '</div>';
                if (hasDetail) h += '<div class="act-event-detail">' + esc(ev.detail) + '</div>';
                h += '</div></div>';
            }
            body.innerHTML = h;
            if (typeof lucide !== 'undefined') lucide.createIcons();
        }
    } else {
        sessionEl.classList.remove('open');
    }
}

function toggleActivityDetail(el) {
    el.classList.toggle('expanded');
}
"""
