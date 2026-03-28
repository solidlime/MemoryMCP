"""Overview tab section: HTML skeleton and JavaScript for loadOverview()."""


def render_overview_tab() -> str:
    """Return the overview tab HTML section with skeleton loaders and block modal."""
    return """        <!-- ========== OVERVIEW TAB ========== -->
        <section id="tab-overview" class="tab-panel active" role="tabpanel">
            <div id="overview-content">
                <div class="glass p-6 mb-6"><div class="skeleton skeleton-title"></div><div class="skeleton skeleton-text" style="width:70%"></div></div>
                <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
                    <div class="glass p-6"><div class="skeleton skeleton-title"></div><div class="skeleton skeleton-text" style="width:80%"></div><div class="skeleton skeleton-text" style="width:60%"></div><div class="skeleton skeleton-text" style="width:70%"></div></div>
                    <div class="glass p-6"><div class="skeleton skeleton-title"></div><div class="skeleton skeleton-text" style="width:90%"></div><div class="skeleton skeleton-text" style="width:75%"></div></div>
                </div>
                <div class="glass p-6 mb-6"><div class="skeleton skeleton-title"></div><div class="skeleton skeleton-text"></div><div class="skeleton skeleton-text" style="width:85%"></div></div>
                <div class="glass p-6 mb-6"><div class="skeleton skeleton-title"></div><div class="skeleton skeleton-text" style="width:70%"></div></div>
                <div class="glass p-6 mb-6"><div class="skeleton skeleton-title"></div><div class="skeleton skeleton-text" style="width:80%"></div></div>
                <div class="grid grid-cols-1 lg:grid-cols-2 gap-6"><div class="glass p-6"><div class="skeleton skeleton-chart"></div></div><div class="glass p-6"><div class="skeleton skeleton-chart"></div></div></div>
            </div>
        </section>"""


def render_overview_js() -> str:
    """Return the loadOverview() JavaScript function and helpers as a plain string."""
    return """

// --- Block CRUD helpers (global scope) ---
function showCreateBlock() {
    document.getElementById('block-modal-title').textContent = '\u270f\ufe0f New Block';
    document.getElementById('block-modal-mode').value = 'create';
    document.getElementById('block-modal-name').value = '';
    document.getElementById('block-modal-name').disabled = false;
    document.getElementById('block-modal-content').value = '';
    document.getElementById('block-modal-priority').value = '0';
    document.getElementById('block-edit-modal').style.display = 'flex';
}

function showEditBlock(name, content, priority) {
    document.getElementById('block-modal-title').textContent = '\u270f\ufe0f Edit Block: ' + name;
    document.getElementById('block-modal-mode').value = 'edit';
    document.getElementById('block-modal-name').value = name;
    document.getElementById('block-modal-name').disabled = true;
    document.getElementById('block-modal-content').value = content || '';
    document.getElementById('block-modal-priority').value = priority || 0;
    document.getElementById('block-edit-modal').style.display = 'flex';
}

function hideBlockModal() {
    document.getElementById('block-edit-modal').style.display = 'none';
}

async function saveBlock() {
    var name = document.getElementById('block-modal-name').value.trim();
    var content = document.getElementById('block-modal-content').value.trim();
    var priority = parseInt(document.getElementById('block-modal-priority').value) || 0;
    if (!name || !content) { toast('Block name and content required', 'error'); return; }
    try {
        await api('/api/blocks/' + encodeURIComponent(S.persona), {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({block_name: name, content: content, priority: priority})
        });
        hideBlockModal();
        toast('Block saved!', 'success');
        loadOverview();
    } catch (e) { toast('Failed to save block: ' + e.message, 'error'); }
}

async function deleteBlock(name) {
    if (!confirm('Delete block "' + name + '"?')) return;
    try {
        await api('/api/blocks/' + encodeURIComponent(S.persona) + '/' + encodeURIComponent(name), {method: 'DELETE'});
        toast('Block deleted', 'success');
        loadOverview();
    } catch (e) { toast('Failed: ' + e.message, 'error'); }
}

// --- Inventory CRUD helpers (global scope) ---
async function deleteItem(itemName) {
    if (!confirm('Delete item: ' + itemName + '?')) return;
    try {
        await api('/api/items/' + encodeURIComponent(S.persona) + '/' + encodeURIComponent(itemName), {method:'DELETE'});
        loadOverview();
    } catch (e) {
        alert('Failed to delete item: ' + e.message);
    }
}

function openAddItemModal() {
    const m = document.getElementById('add-item-modal');
    if (m) { m.style.display = 'flex'; }
}

function closeAddItemModal() {
    const m = document.getElementById('add-item-modal');
    if (m) { m.style.display = 'none'; }
    ['new-item-name','new-item-category','new-item-desc','new-item-qty'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = id === 'new-item-qty' ? '1' : '';
    });
}

async function saveNewItem() {
    const nameEl = document.getElementById('new-item-name');
    const name = (nameEl ? nameEl.value : '').trim();
    if (!name) { alert('Item name is required'); return; }
    const category = (document.getElementById('new-item-category') || {}).value || '';
    const desc = (document.getElementById('new-item-desc') || {}).value || '';
    const qty = parseInt((document.getElementById('new-item-qty') || {}).value || '1', 10) || 1;
    try {
        await api('/api/items/' + encodeURIComponent(S.persona), {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify({item_name: name, category: category || null, description: desc || null, quantity: qty})
        });
        closeAddItemModal();
        loadOverview();
    } catch (e) {
        alert('Failed to add item: ' + e.message);
    }
}

async function changeEquipSlot(slot, itemName) {
    try {
        const body = {};
        body[slot] = itemName;
        await api('/api/items/' + encodeURIComponent(S.persona) + '/equip', {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify(body)
        });
        loadOverview();
    } catch (e) {
        alert('Failed to change equipment: ' + e.message);
    }
}

async function unequipSlot(slot) {
    try {
        await api('/api/items/' + encodeURIComponent(S.persona) + '/unequip', {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify({slots: [slot]})
        });
        loadOverview();
    } catch (e) {
        alert('Failed to unequip: ' + e.message);
    }
}

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

        // --- Equipment display ---
        const EQUIP_SLOTS = ['top','bottom','shoes','outer','accessories','head'];
        let equipHtml = '<div style="display:grid;gap:6px;margin-top:8px">';
        EQUIP_SLOTS.forEach(slot => {
            const current = equip[slot];
            const itemName = typeof current === 'string' ? current : (current ? (current.name || '') : '');
            equipHtml += '<div style="display:flex;align-items:center;gap:8px">';
            equipHtml += '<span class="badge badge-blue" style="min-width:80px;text-align:center">' + esc(slot) + '</span>';
            if (itemName) {
                equipHtml += '<span style="flex:1;font-size:0.85rem;color:var(--text-secondary)">' + esc(itemName) + '</span>';
                equipHtml += '<button data-slot="' + esc(slot) + '" onclick="unequipSlot(this.dataset.slot)" style="font-size:0.72rem;padding:2px 8px;border-radius:4px;border:1px solid rgba(255,255,255,0.15);background:rgba(255,255,255,0.05);color:var(--text-muted);cursor:pointer" title="Unequip">✕</button>';
            } else {
                equipHtml += '<span style="flex:1;font-size:0.82rem;color:var(--text-muted);font-style:italic">empty</span>';
                const slotItems = items.filter(it => it.name);
                if (slotItems.length > 0) {
                    equipHtml += '<select data-slot="' + esc(slot) + '" onchange="if(this.value) changeEquipSlot(this.dataset.slot, this.value)" style="font-size:0.78rem;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.15);border-radius:4px;color:var(--text-secondary);padding:2px 4px"><option value="">equip...</option>';
                    slotItems.forEach(it => { equipHtml += '<option value="' + esc(it.name) + '">' + esc(it.name) + '</option>'; });
                    equipHtml += '</select>';
                }
            }
            equipHtml += '</div>';
        });
        equipHtml += '</div>';

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
                blocksHtml += '<div style="display:flex;gap:6px;margin-left:auto">';
                blocksHtml += '<button class="glass-btn" data-bname="' + esc(name) + '" data-bcontent="' + esc(content) + '" data-bpriority="' + (priority || 0) + '" onclick="var el=this;showEditBlock(el.dataset.bname,el.dataset.bcontent,parseInt(el.dataset.bpriority||0))" style="padding:3px 10px;font-size:0.75rem">\u270f\ufe0f Edit</button>';
                blocksHtml += '<button class="glass-btn" data-bname="' + esc(name) + '" onclick="deleteBlock(this.dataset.bname)" style="padding:3px 10px;font-size:0.75rem;color:var(--accent-red)">&#128465; Delete</button>';
                blocksHtml += '</div>';
                blocksHtml += '</div>';
                if (content) blocksHtml += '<div style="font-size:0.82rem;color:var(--text-muted)">' + esc(truncate(String(content), 80)) + '</div>';
                blocksHtml += '</div>';
            });
        } else {
            blocksHtml = '<span style="color:var(--text-muted)">No core memory blocks</span>';
        }

        // --- Goals & Promises ---
        function getStatusIcon(status) {
            if (status === 'active') return '🔄';
            if (status === 'achieved' || status === 'fulfilled') return '✅';
            if (status === 'cancelled') return '❌';
            return '🔄';
        }

        function renderGoalItems(goalItems, label) {
            if (!goalItems || goalItems.length === 0) return '<span style="color:var(--text-muted)">No ' + label + '</span>';
            let html = '';
            goalItems.forEach(item => {
                const content = typeof item === 'string' ? item : (item.content || item.description || item.title || JSON.stringify(item));
                const status = typeof item === 'object' ? (item.status || 'active').toLowerCase() : 'active';
                const icon = getStatusIcon(status);
                html += '<div style="display:flex;align-items:center;gap:8px;padding:6px 0">';
                html += '<span>' + icon + '</span>';
                html += '<span style="flex:1;font-size:0.85rem;color:var(--text-secondary)">' + esc(content) + '</span>';
                const ts = typeof item === 'object' && (item.created_at || item.date);
                if (ts) html += '<span style="font-size:0.72rem;color:var(--text-muted)">' + relativeTime(ts) + '</span>';
                html += '</div>';
            });
            return html;
        }

        const effectiveGoals = data.goals || [];
        const effectivePromises = data.promises || [];

        // --- Profile: user_info / persona_info / relationship ---
        const userInfo = ctx.user_info || {};
        const personaInfo = ctx.persona_info || {};
        const relStatus = ctx.relationship_status || ctx.relationship_type || '--';

        // --- Inventory items HTML ---
        let invHtml = '';
        if (items.length === 0) {
            invHtml = '<span style="color:var(--text-muted)">No items in inventory</span>';
        } else {
            invHtml = '<div style="display:grid;gap:4px">';
            items.forEach(it => {
                const desc = it.description || '';
                const truncDesc = desc.length > 40 ? desc.slice(0, 40) + '...' : desc;
                invHtml += '<div style="display:flex;align-items:center;gap:8px;padding:6px 0;border-bottom:1px solid rgba(255,255,255,0.04)">';
                invHtml += '<span class="badge badge-blue">' + esc(it.category || 'item') + '</span>';
                invHtml += '<span style="flex:1;font-size:0.85rem;color:var(--text-secondary)" title="' + esc(desc) + '">' + esc(it.name) + '</span>';
                if (it.quantity > 1) invHtml += '<span style="font-size:0.78rem;color:var(--text-muted)">x' + it.quantity + '</span>';
                if (truncDesc) invHtml += '<span class="badge badge-purple" title="' + esc(desc) + '">' + esc(truncDesc) + '</span>';
                invHtml += '<button data-item="' + esc(it.name) + '" onclick="deleteItem(this.dataset.item)" style="padding:2px 8px;border-radius:4px;border:1px solid rgba(255,100,100,0.3);background:rgba(255,100,100,0.08);color:#f87171;cursor:pointer;font-size:0.78rem" title="Delete item">🗑️</button>';
                invHtml += '</div>';
            });
            invHtml += '</div>';
        }

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

        // --- Render (new section order) ---
        el.innerHTML = `
        <!-- Goals & Promises -->
        <div class="glass p-6 mb-6">
            <div class="card-title">🎯 Goals & Promises</div>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                    <div style="font-size:0.8rem;font-weight:600;color:var(--accent-green);margin-bottom:8px">Goals</div>
                    ${renderGoalItems(effectiveGoals, 'goals')}
                </div>
                <div>
                    <div style="font-size:0.8rem;font-weight:600;color:var(--accent-pink);margin-bottom:8px">Promises</div>
                    ${renderGoalItems(effectivePromises, 'promises')}
                </div>
            </div>
        </div>
        <!-- Emotion / State -->
        <div class="glass p-6 mb-6">
            <div class="card-title">💫 Emotion &amp; State</div>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                    <div style="font-size:2rem;font-weight:700;color:var(--accent-yellow);margin-bottom:4px">${esc(ctx.emotion || '--')}</div>
                    <div style="font-size:0.78rem;color:var(--text-muted);margin-bottom:12px">Emotion${ctx.emotion_intensity != null ? ' · ' + (ctx.emotion_intensity * 100).toFixed(0) + '% intensity' : ''}</div>
                    <div style="display:flex;flex-direction:column;gap:6px">
                        <div><span style="font-size:0.78rem;color:var(--text-muted)">Physical: </span><span style="font-size:0.85rem">${esc(ctx.physical_state || '--')}</span></div>
                        <div><span style="font-size:0.78rem;color:var(--text-muted)">Mental: </span><span style="font-size:0.85rem">${esc(ctx.mental_state || '--')}</span></div>
                        <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap"><span style="font-size:0.78rem;color:var(--text-muted);min-width:78px">🌍 Env:</span>${stats.environment ? '<span class="badge badge-blue">' + esc(stats.environment) + '</span>' : '<span style="color:var(--text-muted);font-size:0.82rem">--</span>'}</div>
                        <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap"><span style="font-size:0.78rem;color:var(--text-muted);min-width:78px">🎬 Action:</span>${stats.action_tag ? '<span class="badge badge-green">' + esc(stats.action_tag) + '</span>' : '<span style="color:var(--text-muted);font-size:0.82rem">--</span>'}</div>
                        <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap"><span style="font-size:0.78rem;color:var(--text-muted);min-width:78px">💬 Speech:</span>${stats.speech_style ? '<span class="badge badge-purple">' + esc(stats.speech_style) + '</span>' : '<span style="color:var(--text-muted);font-size:0.82rem">--</span>'}</div>
                    </div>
                </div>
                <div>
                    <div style="font-size:0.78rem;color:var(--text-muted);margin-bottom:8px;font-weight:600">Equipment</div>
                    ${equipHtml}
                </div>
            </div>
            <div style="margin-top:16px;border-top:1px solid rgba(255,255,255,0.06);padding-top:14px">
                <div style="font-size:0.78rem;color:var(--text-muted);font-weight:600;margin-bottom:10px">Body Sensations</div>
                <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:16px">
                    <div>
                        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:5px">
                            <span style="font-size:0.78rem;color:var(--text-muted)">🔥 Fatigue</span>
                            <span style="font-size:0.78rem;color:var(--text-secondary);font-weight:600">${stats.fatigue != null ? (stats.fatigue * 100).toFixed(0) + '%' : '--'}</span>
                        </div>
                        <div style="height:6px;background:rgba(255,255,255,0.08);border-radius:3px;overflow:hidden">
                            <div style="height:100%;width:${stats.fatigue != null ? (stats.fatigue * 100).toFixed(1) : 0}%;background:linear-gradient(90deg,#f87171,#fca5a5);border-radius:3px;transition:width 0.4s ease"></div>
                        </div>
                    </div>
                    <div>
                        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:5px">
                            <span style="font-size:0.78rem;color:var(--text-muted)">🌸 Warmth</span>
                            <span style="font-size:0.78rem;color:var(--text-secondary);font-weight:600">${stats.warmth != null ? (stats.warmth * 100).toFixed(0) + '%' : '--'}</span>
                        </div>
                        <div style="height:6px;background:rgba(255,255,255,0.08);border-radius:3px;overflow:hidden">
                            <div style="height:100%;width:${stats.warmth != null ? (stats.warmth * 100).toFixed(1) : 0}%;background:linear-gradient(90deg,#f9a8d4,#fda4af);border-radius:3px;transition:width 0.4s ease"></div>
                        </div>
                    </div>
                    <div>
                        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:5px">
                            <span style="font-size:0.78rem;color:var(--text-muted)">⚡ Arousal</span>
                            <span style="font-size:0.78rem;color:var(--text-secondary);font-weight:600">${stats.arousal != null ? (stats.arousal * 100).toFixed(0) + '%' : '--'}</span>
                        </div>
                        <div style="height:6px;background:rgba(255,255,255,0.08);border-radius:3px;overflow:hidden">
                            <div style="height:100%;width:${stats.arousal != null ? (stats.arousal * 100).toFixed(1) : 0}%;background:linear-gradient(90deg,#a78bfa,#c4b5fd);border-radius:3px;transition:width 0.4s ease"></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        <!-- Core Memory Blocks -->
        <div class="glass p-6 mb-6">
            <div class="card-title" style="justify-content:space-between">
                <span>&#129504; Core Memory Blocks</span>
                <button onclick="showCreateBlock()" class="glass-btn" style="padding:4px 12px;font-size:0.78rem">&#65291; New Block</button>
            </div>
            ${blocksHtml}
        </div>
        <!-- Profile & Relationship -->
        <div class="glass p-6 mb-6">
            <div class="card-title">👤 Profile &amp; Relationship</div>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                    <div style="font-size:0.78rem;color:var(--text-muted);margin-bottom:8px;font-weight:600">Relationship</div>
                    <div style="font-size:0.9rem;color:var(--accent-pink);font-weight:600;margin-bottom:12px">${esc(relStatus)}</div>
                    <div style="font-size:0.78rem;color:var(--text-muted);margin-bottom:6px;font-weight:600">User Info</div>
                    ${Object.entries(userInfo).length ? Object.entries(userInfo).map(([k,v]) => `<div style="display:flex;gap:8px;padding:4px 0;font-size:0.85rem"><span style="color:var(--text-muted);min-width:120px">${esc(k.replace(/_/g,' '))}</span><span style="color:var(--text-secondary)">${esc(String(v))}</span></div>`).join('') : '<span style="color:var(--text-muted)">No user info</span>'}
                </div>
                <div>
                    <div style="font-size:0.78rem;color:var(--text-muted);margin-bottom:6px;font-weight:600">Persona Info</div>
                    ${(() => { const _GOALS_KEYS = new Set(['goals','promises','active_promises','current_goals']); const filtered = Object.entries(personaInfo).filter(([k]) => !_GOALS_KEYS.has(k)); return filtered.length ? filtered.map(([k,v]) => `<div style="display:flex;gap:8px;padding:4px 0;font-size:0.85rem"><span style="color:var(--text-muted);min-width:120px">${esc(k.replace(/_/g,' '))}</span><span style="color:var(--accent-purple)">${esc(String(v))}</span></div>`).join('') : '<span style="color:var(--text-muted)">No persona info</span>'; })()}
                </div>
            </div>
        </div>
        <!-- Memory Stats -->
        <div class="glass p-6 mb-6">
            <div class="card-title">📈 Memory Stats</div>
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                <div><div class="stat-value">${stats.total_count ?? '--'}</div><div class="stat-label">Total Memories</div></div>
                <div><div class="stat-value" style="color:var(--accent-green)">${str.avg ?? '--'}</div><div class="stat-label">Avg Strength</div></div>
                <div><div class="stat-value" style="color:var(--accent-blue)">${stats.tagged_ratio != null ? (stats.tagged_ratio * 100).toFixed(1) + '%' : '--'}</div><div class="stat-label">Tagged</div></div>
                <div><div class="stat-value" style="color:var(--accent-yellow)">${stats.linked_ratio != null ? (stats.linked_ratio * 100).toFixed(1) + '%' : '--'}</div><div class="stat-label">Linked</div></div>
            </div>
            <div style="margin-bottom:10px">
                <div style="font-size:0.78rem;color:var(--text-muted);margin-bottom:6px">Top Tags</div>
                <div style="display:flex;flex-wrap:wrap;gap:6px">${topTags.length ? topTags.map(([t,c]) => '<span class="badge badge-purple">' + esc(t) + ' <span style="opacity:0.7">(' + c + ')</span></span>').join('') : '<span style="color:var(--text-muted)">--</span>'}</div>
            </div>
            <div>
                <div style="font-size:0.78rem;color:var(--text-muted);margin-bottom:6px">Top Emotions</div>
                <div style="display:flex;flex-wrap:wrap;gap:6px">${topEmo.length ? topEmo.map(([e,c]) => '<span class="badge badge-pink">' + esc(e) + ' <span style="opacity:0.7">(' + c + ')</span></span>').join('') : '<span style="color:var(--text-muted)">--</span>'}</div>
            </div>
        </div>
        <!-- Inventory -->
        <div class="glass p-6 mb-6">
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px">
                <div class="card-title" style="margin-bottom:0">🎒 Inventory</div>
                <button onclick="openAddItemModal()" style="padding:4px 14px;border-radius:6px;border:1px solid rgba(167,139,250,0.4);background:rgba(167,139,250,0.1);color:var(--accent-purple);cursor:pointer;font-size:0.82rem;font-weight:600">+ Add Item</button>
            </div>
            ${invHtml}
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
        </div>
        <!-- Add Item Modal -->
        <div id="add-item-modal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.75);z-index:1000;align-items:center;justify-content:center">
            <div style="background:#1e1b2e;border:1px solid rgba(167,139,250,0.3);border-radius:14px;padding:28px;width:420px;max-width:92vw;box-shadow:0 24px 64px rgba(0,0,0,0.6)">
                <div style="font-weight:700;font-size:1.05rem;margin-bottom:18px;color:var(--accent-purple)">➕ Add Inventory Item</div>
                <div style="display:flex;flex-direction:column;gap:12px">
                    <input id="new-item-name" type="text" placeholder="Item name *" style="width:100%;padding:8px 12px;border-radius:7px;border:1px solid rgba(255,255,255,0.15);background:rgba(255,255,255,0.07);color:var(--text-primary);font-size:0.88rem;outline:none;box-sizing:border-box">
                    <input id="new-item-category" type="text" placeholder="Category (e.g. clothing, weapon)" style="width:100%;padding:8px 12px;border-radius:7px;border:1px solid rgba(255,255,255,0.15);background:rgba(255,255,255,0.07);color:var(--text-primary);font-size:0.88rem;outline:none;box-sizing:border-box">
                    <input id="new-item-desc" type="text" placeholder="Description" style="width:100%;padding:8px 12px;border-radius:7px;border:1px solid rgba(255,255,255,0.15);background:rgba(255,255,255,0.07);color:var(--text-primary);font-size:0.88rem;outline:none;box-sizing:border-box">
                    <input id="new-item-qty" type="number" value="1" min="1" placeholder="Quantity" style="width:100%;padding:8px 12px;border-radius:7px;border:1px solid rgba(255,255,255,0.15);background:rgba(255,255,255,0.07);color:var(--text-primary);font-size:0.88rem;outline:none;box-sizing:border-box">
                </div>
                <div style="display:flex;gap:10px;justify-content:flex-end;margin-top:20px">
                    <button onclick="closeAddItemModal()" style="padding:7px 18px;border-radius:7px;border:1px solid rgba(255,255,255,0.15);background:rgba(255,255,255,0.05);color:var(--text-muted);cursor:pointer;font-size:0.88rem">Cancel</button>
                    <button onclick="saveNewItem()" style="padding:7px 18px;border-radius:7px;border:1px solid rgba(167,139,250,0.5);background:rgba(167,139,250,0.2);color:var(--accent-purple);cursor:pointer;font-size:0.88rem;font-weight:600">Save</button>
                </div>
            </div>
        </div>
        <!-- Block Edit Modal -->
        <div id="block-edit-modal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.6);backdrop-filter:blur(8px);z-index:1000;align-items:center;justify-content:center">
            <div class="glass p-6" style="max-width:500px;width:90%;border-radius:16px;max-height:80vh;overflow-y:auto">
                <h3 style="font-size:1.2rem;font-weight:600;color:var(--text-primary);margin-bottom:16px">
                    <span id="block-modal-title">&#9999;&#65039; New Block</span></h3>
                <input type="hidden" id="block-modal-mode" value="create">
                <div style="margin-bottom:12px">
                    <label style="display:block;font-size:0.85rem;color:var(--text-muted);margin-bottom:4px">Block Name</label>
                    <input type="text" id="block-modal-name" class="glass-input" style="width:100%;padding:8px 12px;box-sizing:border-box" placeholder="e.g. system_notes">
                </div>
                <div style="margin-bottom:12px">
                    <label style="display:block;font-size:0.85rem;color:var(--text-muted);margin-bottom:4px">Content</label>
                    <textarea id="block-modal-content" class="glass-input" rows="6" style="width:100%;padding:8px 12px;box-sizing:border-box;resize:vertical"></textarea>
                </div>
                <div style="margin-bottom:16px">
                    <label style="display:block;font-size:0.85rem;color:var(--text-muted);margin-bottom:4px">Priority (0-100)</label>
                    <input type="number" id="block-modal-priority" class="glass-input" style="width:100%;padding:8px 12px;box-sizing:border-box" value="0" min="0" max="100">
                </div>
                <div style="display:flex;gap:12px;justify-content:flex-end">
                    <button onclick="hideBlockModal()" class="glass-btn" style="padding:8px 20px">Cancel</button>
                    <button onclick="saveBlock()" class="glass-btn" style="padding:8px 20px;background:var(--accent);color:white">Save</button>
                </div>
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
