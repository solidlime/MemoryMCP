"""Knowledge Graph tab section for the MemoryMCP Dashboard.

Interactive visualization of memory relationships using vis-network.
Provides a force-directed graph where nodes represent memories and
edges represent semantic/tag-based relationships. Supports filtering
by tag and emotion, adjustable node limits, physics toggle, and a
slide-out detail panel for inspecting individual memories.

API consumed:
    GET /api/graph/{persona}?limit={limit}

Response shape:
    {
        "persona": "xxx",
        "nodes": [{ "key", "content", "tags", "emotion_type", "importance" }],
        "edges": [{ "source", "target", "type", "tag?" }],
        "node_count": int,
        "edge_count": int
    }
"""


def render_graph_tab() -> str:
    """Return the HTML for the Knowledge Graph tab panel.

    Includes:
    - Toolbar with tag/emotion filters, node-limit buttons, physics toggle, refresh
    - vis-network container (600px height)
    - Slide-out detail panel (right side, 400px)
    - Scoped styles for spinner, active limit button, and panel overlay
    """
    return """
        <!-- ========== KNOWLEDGE GRAPH TAB ========== -->
        <section id="tab-graph" class="tab-panel" role="tabpanel">
          <style>
            /* Spinner animation for graph loading */
            @keyframes graph-spin {
              to { transform: rotate(360deg); }
            }
            .graph-spinner {
              width: 36px; height: 36px;
              border: 3px solid rgba(167,139,250,0.2);
              border-top-color: var(--accent-purple, #a78bfa);
              border-radius: 50%;
              animation: graph-spin 0.8s linear infinite;
            }

            /* Active state for node-limit buttons */
            .graph-limit-btn.active {
              background: rgba(167,139,250,0.35);
              border-color: var(--accent-purple, #a78bfa);
              box-shadow: 0 0 12px rgba(167,139,250,0.15);
            }

            /* Detail panel backdrop - respects light/dark via variable */
            #graph-panel-overlay {
              backdrop-filter: blur(2px);
            }

            /* Multi-select tweak: show scrollbar when expanded */
            #graph-tag-filter {
              scrollbar-width: thin;
            }
            #graph-tag-filter:focus {
              max-height: 160px !important;
            }

            /* Make vis-network canvas fill container */
            #graph-container .vis-network {
              outline: none;
            }
          </style>

          <div id="graph-content">
            <!-- Toolbar -->
            <div class="glass" style="padding:16px;margin-bottom:16px">
              <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">
                <!-- Tag filter: multi-select -->
                <select id="graph-tag-filter" class="glass-input" multiple
                        style="min-width:150px;max-height:36px"
                        title="Filter by tags (hold Ctrl/Cmd to select multiple)">
                  <option value="">All Tags</option>
                </select>

                <!-- Emotion filter -->
                <select id="graph-emotion-filter" class="glass-input"
                        style="min-width:140px">
                  <option value="">All Emotions</option>
                </select>

                <!-- Node limit buttons -->
                <div style="display:flex;gap:4px">
                  <button class="glass-btn graph-limit-btn" data-limit="50"
                          style="padding:6px 14px;font-size:0.82rem">50</button>
                  <button class="glass-btn graph-limit-btn active" data-limit="100"
                          style="padding:6px 14px;font-size:0.82rem">100</button>
                  <button class="glass-btn graph-limit-btn" data-limit="200"
                          style="padding:6px 14px;font-size:0.82rem">200</button>
                </div>

                <!-- Physics toggle -->
                <label style="display:flex;align-items:center;gap:6px;color:var(--text-secondary);font-size:0.85rem;cursor:pointer;user-select:none">
                  <input type="checkbox" id="graph-physics-toggle" checked
                         style="accent-color:var(--accent-purple)"> Physics
                </label>

                <!-- Refresh -->
                <button id="graph-refresh-btn" class="glass-btn"
                        title="Refresh graph"
                        style="padding:6px 14px;font-size:0.82rem">🔄 Refresh</button>

                <!-- Stats (pushed to right) -->
                <span id="graph-stats"
                      style="color:var(--text-muted);font-size:0.8rem;margin-left:auto"></span>
              </div>
            </div>

            <!-- Graph container -->
            <div id="graph-container" class="glass"
                 style="height:600px;position:relative;overflow:hidden">
              <!-- vis-network renders here -->
              <div id="graph-loading"
                   style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;z-index:10">
                <div style="text-align:center">
                  <div class="graph-spinner" style="margin:0 auto 12px"></div>
                  <span style="color:var(--text-muted)">Loading graph...</span>
                </div>
              </div>
            </div>

            <!-- Detail side panel -->
            <div id="graph-detail-panel"
                 style="position:fixed;top:0;right:-400px;width:400px;max-width:90vw;height:100vh;z-index:1000;transition:right 0.3s ease;overflow-y:auto">
              <div style="background:var(--bg-primary);border-left:1px solid var(--glass-border);height:100%;padding:24px">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
                  <h3 style="font-size:1.1rem;font-weight:600;color:var(--text-primary)">Memory Details</h3>
                  <button id="graph-panel-close" class="glass-btn"
                          style="padding:4px 10px;font-size:0.9rem">✕</button>
                </div>
                <div id="graph-panel-body"></div>
              </div>
            </div>
            <div id="graph-panel-overlay"
                 style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.3);z-index:999"></div>
          </div>
        </section>"""


def render_graph_js() -> str:
    """Return the JavaScript for the Knowledge Graph tab.

    Defines:
    - ``loadGraph()``              — main entry; fetches data, builds graph
    - ``populateGraphFilters()``   — populates tag/emotion <select> from node data
    - ``buildVisData()``           — converts API nodes/edges → vis-network format
    - ``buildTooltip()``           — HTML tooltip for node hover
    - ``applyGraphFilters()``      — client-side tag/emotion filtering
    - ``renderNetwork()``          — creates / re-creates vis.Network instance
    - ``openGraphDetailPanel()``   — shows slide-out detail panel for a node
    - ``closeGraphDetailPanel()``  — hides the detail panel
    - IIFE ``setupGraphEvents()``  — wires toolbar event listeners

    No ``<script>`` tags — the string is concatenated by ``dashboard.py``.
    """
    return """
/* ================================================================
 *  Knowledge Graph — vis-network interactive memory visualization
 * ================================================================ */

let graphNetwork = null;
let graphData = null;
let graphNodeLimit = 100;

/* ---- Helpers ---- */

function _graphFontColor() {
    return document.documentElement.classList.contains('light') ? '#1e1b4b' : '#f1f5f9';
}

/* ---- Main loader ---- */

async function loadGraph() {
    var el = document.getElementById('graph-content');
    var container = document.getElementById('graph-container');
    var loading = document.getElementById('graph-loading');
    var statsEl = document.getElementById('graph-stats');

    if (loading) loading.style.display = 'flex';

    try {
        var data = await api(
            '/api/graph/' + encodeURIComponent(S.persona) + '?limit=' + graphNodeLimit
        );
        graphData = data;

        populateGraphFilters(data.nodes);

        var built = buildVisData(data.nodes, data.edges);
        var filtered = applyGraphFilters(built.visNodes, built.visEdges);

        renderNetwork(container, filtered.nodes, filtered.edges);

        if (statsEl) {
            statsEl.textContent = filtered.nodes.length + ' nodes \u00b7 ' + filtered.edges.length + ' edges';
        }

    } catch (e) {
        if (container) container.innerHTML = errorCard('Failed to load graph: ' + e.message);
    } finally {
        var l = document.getElementById('graph-loading');
        if (l) l.style.display = 'none';
        if (loading) loading.style.display = 'none';
    }
}

/* ---- Populate filter dropdowns ---- */

function populateGraphFilters(nodes) {
    var tagSet = new Set();
    var emotionSet = new Set();
    nodes.forEach(function(n) {
        (n.tags || []).forEach(function(t) { tagSet.add(t); });
        if (n.emotion_type) emotionSet.add(n.emotion_type);
    });

    var tagFilter = document.getElementById('graph-tag-filter');
    var emotionFilter = document.getElementById('graph-emotion-filter');
    if (!tagFilter || !emotionFilter) return;
    var currentTags = Array.from(tagFilter.selectedOptions).map(function(o) { return o.value; }).filter(Boolean);
    tagFilter.innerHTML = '<option value="">All Tags</option>' +
        Array.from(tagSet).sort().map(function(t) {
            return '<option value="' + esc(t) + '"' +
                   (currentTags.includes(t) ? ' selected' : '') + '>' + esc(t) + '</option>';
        }).join('');

    var currentEmo = emotionFilter.value;
    emotionFilter.innerHTML = '<option value="">All Emotions</option>' +
        Array.from(emotionSet).sort().map(function(e) {
            return '<option value="' + esc(e) + '"' +
                   (currentEmo === e ? ' selected' : '') + '>' + esc(e) + '</option>';
        }).join('');
}

/* ---- Build vis-network DataSet arrays ---- */

function buildVisData(nodes, edges) {
    var fontColor = _graphFontColor();

    var visNodes = nodes.map(function(n) {
        var emoColor = EMOTION_COLORS[n.emotion_type] || '#94a3b8';
        var sz = 10 + (n.importance || 0.5) * 30;
        return {
            id: n.key,
            label: truncate(n.content, 20),
            title: buildTooltip(n),
            size: sz,
            color: {
                background: emoColor,
                border: emoColor,
                highlight: { background: emoColor, border: '#fff' },
                hover:     { background: emoColor, border: '#fff' }
            },
            font: { color: fontColor, size: 11, face: 'system-ui' },
            borderWidth: 2,
            shadow: { enabled: true, color: emoColor, size: 8, x: 0, y: 0 },
            _data: n
        };
    });

    var visEdges = edges.map(function(e, i) {
        var isRelated = (e.type === 'related');
        return {
            id: 'e' + i,
            from: e.source,
            to: e.target,
            dashes: !isRelated,
            width: isRelated ? 2.5 : 1,
            color: {
                color:     isRelated ? 'rgba(167,139,250,0.5)' : 'rgba(148,163,184,0.25)',
                highlight: isRelated ? '#a78bfa' : '#94a3b8',
                hover:     isRelated ? '#a78bfa' : '#94a3b8'
            },
            smooth: { type: 'continuous' },
            _type: e.type,
            _tag:  e.tag || '',
            _from: e.source,
            _to:   e.target
        };
    });

    return { visNodes: visNodes, visEdges: visEdges };
}

/* ---- Tooltip HTML ---- */

function buildTooltip(n) {
    var h = '<div style="max-width:280px;padding:8px;font-size:12px">';
    h += '<div style="margin-bottom:6px;font-weight:600;color:#f1f5f9">' + esc(truncate(n.content, 100)) + '</div>';
    if (n.tags && n.tags.length) {
        h += '<div style="margin-bottom:4px">\\ud83c\\udff7\\ufe0f ' + n.tags.map(function(t) { return esc(t); }).join(', ') + '</div>';
    }
    if (n.emotion_type) {
        h += '<div style="margin-bottom:4px">\\ud83d\\udcad ' + esc(n.emotion_type) + '</div>';
    }
    h += '<div>\\u2b50 Importance: ' + ((n.importance || 0) * 100).toFixed(0) + '%</div>';
    h += '</div>';
    return h;
}

/* ---- Client-side filtering ---- */

function applyGraphFilters(visNodes, visEdges) {
    var tagFilter     = document.getElementById('graph-tag-filter');
    var emotionFilter = document.getElementById('graph-emotion-filter');
    var selectedTags  = Array.from(tagFilter.selectedOptions).map(function(o) { return o.value; }).filter(Boolean);
    var selectedEmo   = emotionFilter.value;

    var filtered = visNodes;

    if (selectedTags.length > 0) {
        filtered = filtered.filter(function(n) {
            var tags = n._data.tags || [];
            return selectedTags.some(function(t) { return tags.includes(t); });
        });
    }
    if (selectedEmo) {
        filtered = filtered.filter(function(n) { return n._data.emotion_type === selectedEmo; });
    }

    var visibleIds = new Set(filtered.map(function(n) { return n.id; }));
    var filteredEdges = visEdges.filter(function(e) {
        return visibleIds.has(e._from) && visibleIds.has(e._to);
    });

    return { nodes: filtered, edges: filteredEdges };
}

/* ---- Render / re-render vis.Network ---- */

function renderNetwork(container, nodes, edges) {
    var loading = document.getElementById('graph-loading');

    /* Empty state */
    if (nodes.length === 0) {
        if (graphNetwork) { graphNetwork.destroy(); graphNetwork = null; }
        if (loading) loading.style.display = 'none';
        container.innerHTML =
            '<div style="display:flex;align-items:center;justify-content:center;height:100%;' +
            'color:var(--text-muted);text-align:center;padding:40px">' +
            '<div><div style="font-size:3rem;margin-bottom:16px">\\ud83d\\udd78\\ufe0f</div>' +
            '<p style="font-size:1.1rem">No memories found. Create some memories first!</p></div></div>';
        return;
    }

    var dataSet = {
        nodes: new vis.DataSet(nodes),
        edges: new vis.DataSet(edges)
    };

    var physicsEnabled = document.getElementById('graph-physics-toggle').checked;

    var options = {
        physics: {
            enabled: physicsEnabled,
            barnesHut: {
                gravitationalConstant: -3000,
                centralGravity: 0.3,
                springLength: 120,
                springConstant: 0.04,
                damping: 0.09
            },
            stabilization: { iterations: 150, fit: true }
        },
        interaction: {
            hover: true,
            tooltipDelay: 200,
            hideEdgesOnDrag: true,
            hideEdgesOnZoom: true,
            multiselect: false
        },
        nodes: {
            shape: 'dot',
            scaling: { min: 10, max: 40 },
            font: { color: _graphFontColor(), size: 11 }
        },
        edges: {
            smooth: { type: 'continuous', roundness: 0.2 }
        },
        layout: {
            improvedLayout: (nodes.length < 150)
        }
    };

    if (graphNetwork) { graphNetwork.destroy(); }

    graphNetwork = new vis.Network(container, dataSet, options);

    /* Click → open side panel */
    graphNetwork.on('click', function(params) {
        if (params.nodes.length > 0) {
            var nodeId = params.nodes[0];
            var node = dataSet.nodes.get(nodeId);
            if (node && node._data) {
                openGraphDetailPanel(node._data);
            }
        } else {
            closeGraphDetailPanel();
        }
    });

    /* Double-click → open full modal via openMemModal */
    graphNetwork.on('doubleClick', function(params) {
        if (params.nodes.length > 0) {
            var nodeId = params.nodes[0];
            var node = dataSet.nodes.get(nodeId);
            if (node && node._data) {
                var d = node._data;
                openMemModal({
                    memory_key:  d.key,
                    content:     d.content,
                    tags:        d.tags,
                    emotion_type: d.emotion_type,
                    importance:  d.importance
                });
            }
        }
    });

    /* Stabilization done → stop physics jitter */
    graphNetwork.once('stabilizationIterationsDone', function() {
        graphNetwork.setOptions({ physics: { stabilization: { enabled: false } } });
    });
}

/* ---- Detail side panel ---- */

function openGraphDetailPanel(data) {
    var panel   = document.getElementById('graph-detail-panel');
    var overlay = document.getElementById('graph-panel-overlay');
    var body    = document.getElementById('graph-panel-body');

    var tags = (data.tags || []).map(function(t) {
        return '<span class="badge badge-purple">' + esc(t) + '</span>';
    }).join(' ');

    var emoColor = EMOTION_COLORS[data.emotion_type] || '#94a3b8';

    var html = '';
    /* Key */
    html += '<div style="margin-bottom:16px">';
    html += '  <div style="font-size:0.75rem;color:var(--text-muted);margin-bottom:4px">Key</div>';
    html += '  <div style="font-family:monospace;font-size:0.8rem;color:var(--accent-purple);word-break:break-all">' + esc(data.key) + '</div>';
    html += '</div>';

    /* Content */
    html += '<div style="margin-bottom:16px">';
    html += '  <div style="font-size:0.75rem;color:var(--text-muted);margin-bottom:4px">Content</div>';
    html += '  <div style="color:var(--text-primary);line-height:1.6;white-space:pre-wrap">' + esc(data.content) + '</div>';
    html += '</div>';

    /* Tags */
    if (tags) {
        html += '<div style="margin-bottom:16px">';
        html += '  <div style="font-size:0.75rem;color:var(--text-muted);margin-bottom:6px">Tags</div>';
        html += '  <div style="display:flex;flex-wrap:wrap;gap:4px">' + tags + '</div>';
        html += '</div>';
    }

    /* Emotion */
    if (data.emotion_type) {
        html += '<div style="margin-bottom:16px">';
        html += '  <div style="font-size:0.75rem;color:var(--text-muted);margin-bottom:4px">Emotion</div>';
        html += '  <div style="display:flex;align-items:center;gap:6px">';
        html += '    <span style="width:10px;height:10px;border-radius:50%;background:' + emoColor + ';display:inline-block"></span>';
        html += '    <span style="color:var(--text-secondary)">' + esc(data.emotion_type) + '</span>';
        html += '  </div>';
        html += '</div>';
    }

    /* Importance bar */
    if (data.importance != null) {
        var pct = (data.importance * 100).toFixed(0);
        html += '<div style="margin-bottom:16px">';
        html += '  <div style="font-size:0.75rem;color:var(--text-muted);margin-bottom:4px">Importance</div>';
        html += '  <div style="display:flex;align-items:center;gap:8px">';
        html += '    <div style="flex:1;height:6px;background:rgba(255,255,255,0.1);border-radius:3px;overflow:hidden">';
        html += '      <div style="width:' + pct + '%;height:100%;background:var(--accent-yellow);border-radius:3px"></div>';
        html += '    </div>';
        html += '    <span style="color:var(--accent-yellow);font-size:0.85rem">' + pct + '%</span>';
        html += '  </div>';
        html += '</div>';
    }

    body.innerHTML = html;
    panel.style.right = '0';
    overlay.style.display = 'block';
}

function closeGraphDetailPanel() {
    var panel   = document.getElementById('graph-detail-panel');
    var overlay = document.getElementById('graph-panel-overlay');
    if (panel)   panel.style.right = '-400px';
    if (overlay) overlay.style.display = 'none';
}

/* ---- Helper: re-apply filters without refetch ---- */

function _graphRefilter() {
    if (!graphData) return;
    var built    = buildVisData(graphData.nodes, graphData.edges);
    var filtered = applyGraphFilters(built.visNodes, built.visEdges);
    renderNetwork(document.getElementById('graph-container'), filtered.nodes, filtered.edges);
    var statsEl = document.getElementById('graph-stats');
    if (statsEl) {
        statsEl.textContent = filtered.nodes.length + ' nodes \\u00b7 ' + filtered.edges.length + ' edges';
    }
}

/* ---- Event wiring (runs once at parse time) ---- */

(function setupGraphEvents() {
    /* Limit buttons */
    document.querySelectorAll('.graph-limit-btn').forEach(function(btn) {
        btn.addEventListener('click', function() {
            document.querySelectorAll('.graph-limit-btn').forEach(function(b) {
                b.classList.remove('active');
            });
            this.classList.add('active');
            graphNodeLimit = parseInt(this.dataset.limit, 10);
            loadGraph();
        });
    });

    /* Tag filter → re-apply (no refetch) */
    document.getElementById('graph-tag-filter').addEventListener('change', _graphRefilter);

    /* Emotion filter → re-apply (no refetch) */
    document.getElementById('graph-emotion-filter').addEventListener('change', _graphRefilter);

    /* Physics toggle */
    document.getElementById('graph-physics-toggle').addEventListener('change', function() {
        if (graphNetwork) {
            graphNetwork.setOptions({ physics: { enabled: this.checked } });
        }
    });

    /* Refresh button */
    document.getElementById('graph-refresh-btn').addEventListener('click', loadGraph);

    /* Close panel */
    document.getElementById('graph-panel-close').addEventListener('click', closeGraphDetailPanel);
    document.getElementById('graph-panel-overlay').addEventListener('click', closeGraphDetailPanel);

    /* ESC key closes panel */
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            var panel = document.getElementById('graph-detail-panel');
            if (panel && panel.style.right === '0px') {
                closeGraphDetailPanel();
            }
        }
    });
})();
"""
