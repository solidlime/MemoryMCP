"""Overview tab section: HTML skeleton and JavaScript for loadOverview()."""


def render_overview_tab() -> str:
    """Return the overview tab HTML section with skeleton loaders."""
    return """        <!-- ========== OVERVIEW TAB ========== -->
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
        </section>"""


def render_overview_js() -> str:
    """Return the loadOverview() JavaScript function as a plain string."""
    return """async function loadOverview() {
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
                    <div><div class="stat-value" style="font-size:1.3rem">${esc(ctx.emotion || '--')}</div><div class="stat-label">Current Emotion${ctx.emotion_intensity != null ? ' (' + (ctx.emotion_intensity * 100).toFixed(0) + '%)' : ''}</div></div>
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
}"""
