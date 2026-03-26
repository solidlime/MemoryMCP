"""Analytics tab section: HTML skeleton and JavaScript for loadAnalytics()."""


def render_analytics_tab() -> str:
    """Return the analytics tab HTML section with skeleton loaders."""
    return """        <!-- ========== ANALYTICS TAB ========== -->
        <section id="tab-analytics" class="tab-panel" role="tabpanel">
            <div id="analytics-content">
                <div class="glass p-6 mb-6"><div class="skeleton skeleton-title"></div><div class="skeleton skeleton-chart"></div></div>
                <div class="glass p-6"><div class="skeleton skeleton-title"></div><div class="skeleton skeleton-chart"></div></div>
            </div>
        </section>"""


def render_analytics_js() -> str:
    """Return the loadAnalytics() JavaScript function as a plain string."""
    return """async function loadAnalytics(days=7) {
    const el = document.getElementById('analytics-content');
    try {
        if (typeof Chart === 'undefined') {
            el.innerHTML = errorCard('Chart.js library not available. Please check internet connectivity.');
            return;
        }
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
        } else if (strCtx) {
            strCtx.parentElement.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--text-muted)">No strength data available</div>';
        }
        updateLastTime();
    } catch (e) {
        el.innerHTML = errorCard('Failed to load analytics: ' + e.message);
    }
}"""
