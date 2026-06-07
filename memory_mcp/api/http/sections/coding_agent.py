"""Coding Agent Floating Panel for MemoryMCP Dashboard."""


def render_coding_agent_panel() -> str:
    """Return HTML+CSS+JS for the Coding Agent floating panel."""
    return _CA_HTML


def render_coding_agent_css() -> str:
    return ""  # embedded in panel HTML


def render_coding_agent_js() -> str:
    return ""  # embedded in panel HTML


_CA_HTML = """\
<style>
/* === Coding Agent Floating Panel === */
#ca-panel {
  position: fixed;
  bottom: 80px;
  right: 20px;
  width: 640px;
  height: 440px;
  min-width: 280px;
  min-height: 220px;
  z-index: 8000;
  display: none;
  flex-direction: column;
  background: rgba(13,13,26,0.97);
  border: 1px solid var(--glass-border, rgba(96,165,250,0.20));
  border-radius: 10px;
  box-shadow: 0 8px 40px rgba(0,0,0,0.60), 0 0 0 1px rgba(96,165,250,0.08);
  overflow: hidden;
  animation: caSlideIn 0.18s ease;
}
#ca-panel.ca-open { display: flex; }
@keyframes caSlideIn {
  from { opacity:0; transform: translateY(14px); }
  to   { opacity:1; transform: translateY(0); }
}

/* Header */
#ca-header {
  height: 40px;
  min-height: 40px;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 0 10px;
  background: #0d0d1a;
  border-bottom: 1px solid var(--glass-border, rgba(96,165,250,0.16));
  cursor: grab;
  user-select: none;
  flex-shrink: 0;
}
#ca-header:active { cursor: grabbing; }
.ca-title {
  font-size: 12px;
  font-weight: 700;
  color: var(--accent-blue, #60a5fa);
  letter-spacing: 0.4px;
  white-space: nowrap;
  margin-right: 6px;
}
.ca-tab-btn {
  background: transparent;
  border: 1px solid transparent;
  color: #64748b;
  border-radius: 5px;
  padding: 3px 10px;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}
.ca-tab-btn:hover { color: #94a3b8; border-color: rgba(96,165,250,0.20); }
.ca-tab-btn.ca-tab-active {
  color: var(--accent-blue, #60a5fa);
  background: rgba(96,165,250,0.10);
  border-color: rgba(96,165,250,0.30);
}
#ca-close-btn {
  margin-left: auto;
  background: transparent;
  border: 1px solid transparent;
  color: #64748b;
  border-radius: 5px;
  width: 26px;
  height: 26px;
  font-size: 14px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
  flex-shrink: 0;
}
#ca-close-btn:hover { color: #fca5a5; border-color: rgba(248,113,113,0.30); background: rgba(248,113,113,0.10); }

/* Body */
#ca-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
}
.ca-tab-pane { display: none; flex-direction: column; flex: 1; min-height: 0; overflow: hidden; }
.ca-tab-pane.ca-pane-active { display: flex; }

/* === Terminal Tab === */
#ca-tab-terminal { padding: 8px; gap: 6px; }
.ca-lang-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.ca-lang-row label { font-size: 11px; color: #64748b; }
#ca-lang-select {
  background: rgba(96,165,250,0.07);
  border: 1px solid rgba(96,165,250,0.20);
  color: #e2e8f0;
  border-radius: 5px;
  padding: 3px 8px;
  font-size: 11px;
  font-family: 'Fira Code', 'Noto Sans Mono CJK JP', monospace;
  cursor: pointer;
  outline: none;
}
#ca-lang-select option { background: #0d0d1a; color: #e2e8f0; }
#ca-run-btn {
  background: rgba(16,185,129,0.12);
  border: 1px solid rgba(16,185,129,0.28);
  color: #4ade80;
  border-radius: 5px;
  padding: 3px 12px;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.15s;
}
#ca-run-btn:hover { background: rgba(16,185,129,0.22); border-color: rgba(16,185,129,0.50); }
#ca-run-btn:disabled { opacity: 0.45; cursor: not-allowed; }
#ca-code-area {
  flex-shrink: 0;
  width: 100%;
  height: 130px;
  resize: none;
  background: rgba(0,0,0,0.35);
  border: 1px solid rgba(96,165,250,0.15);
  border-radius: 6px;
  color: #e2e8f0;
  font-family: 'Fira Code', 'Cascadia Code', 'Noto Sans Mono CJK JP', monospace;
  font-size: 12px;
  line-height: 1.55;
  padding: 8px 10px;
  outline: none;
  box-sizing: border-box;
  transition: border-color 0.2s;
}
#ca-code-area:focus { border-color: rgba(96,165,250,0.38); }
#ca-output-area {
  flex: 1;
  overflow-y: auto;
  background: rgba(0,0,0,0.30);
  border: 1px solid rgba(96,165,250,0.10);
  border-radius: 6px;
  padding: 8px 10px;
  font-family: 'Fira Code', 'Cascadia Code', 'Noto Sans Mono CJK JP', monospace;
  font-size: 11px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
  min-height: 60px;
}
.ca-out-stdout { color: #d1fae5; }
.ca-out-stderr { color: #fca5a5; }
.ca-out-info   { color: #94a3b8; }
.ca-out-error  { color: #f87171; font-weight: 600; }
.ca-artifacts  { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; flex-shrink: 0; }
.ca-artifacts img { max-width: 100%; max-height: 200px; border-radius: 4px; border: 1px solid rgba(96,165,250,0.15); }

/* === Files Tab === */
#ca-tab-files { padding: 8px; gap: 6px; }
.ca-files-toolbar {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}
.ca-files-toolbar span { font-size: 11px; color: #64748b; flex: 1; }
.ca-icon-btn {
  background: rgba(96,165,250,0.07);
  border: 1px solid rgba(96,165,250,0.18);
  color: #94a3b8;
  border-radius: 5px;
  padding: 3px 8px;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.15s;
}
.ca-icon-btn:hover { background: rgba(96,165,250,0.15); color: #e2e8f0; }
#ca-file-list {
  flex: 1;
  overflow-y: auto;
  background: rgba(0,0,0,0.25);
  border: 1px solid rgba(96,165,250,0.10);
  border-radius: 6px;
  padding: 4px;
  min-height: 60px;
}
.ca-file-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.12s;
  font-size: 11px;
  color: #cbd5e1;
}
.ca-file-item:hover { background: rgba(96,165,250,0.08); }
.ca-file-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ca-file-size { color: #475569; font-size: 10px; flex-shrink: 0; }
.ca-del-btn {
  background: transparent;
  border: none;
  color: #475569;
  cursor: pointer;
  font-size: 12px;
  padding: 0 2px;
  line-height: 1;
  transition: color 0.15s;
  flex-shrink: 0;
}
.ca-del-btn:hover { color: #f87171; }
.ca-drop-zone {
  border: 1px dashed rgba(96,165,250,0.22);
  border-radius: 6px;
  padding: 10px;
  text-align: center;
  font-size: 11px;
  color: #475569;
  transition: all 0.2s;
  flex-shrink: 0;
  cursor: pointer;
}
.ca-drop-zone.ca-drag-over {
  border-color: var(--accent-blue, #60a5fa);
  background: rgba(96,165,250,0.07);
  color: #94a3b8;
}
.ca-empty { color: #475569; font-size: 11px; padding: 12px; text-align: center; }

/* Resize handle */
#ca-resize-handle {
  position: absolute;
  bottom: 0;
  right: 0;
  width: 16px;
  height: 16px;
  cursor: se-resize;
  opacity: 0.45;
}
#ca-resize-handle::after {
  content: '';
  position: absolute;
  bottom: 4px;
  right: 4px;
  width: 8px;
  height: 8px;
  border-right: 2px solid var(--accent-blue, #60a5fa);
  border-bottom: 2px solid var(--accent-blue, #60a5fa);
  border-radius: 1px;
}
</style>

<div id="ca-panel">
  <div id="ca-header">
    <span class="ca-title"><i data-lucide=&quot;zap&quot;></i> Coding Agent</span>
    <button class="ca-tab-btn ca-tab-active" data-tab="terminal"><i data-lucide=&quot;monitor&quot;></i> Terminal</button>
    <button class="ca-tab-btn" data-tab="files"><i data-lucide=&quot;folder&quot;></i> Files</button>
    <button id="ca-close-btn" title="Close"><i data-lucide=&quot;x&quot;></i></button>
  </div>

  <div id="ca-body">
    <!-- Terminal Tab -->
    <div id="ca-tab-terminal" class="ca-tab-pane ca-pane-active">
      <div class="ca-lang-row">
        <label>Lang:</label>
        <select id="ca-lang-select">
          <option value="python" selected>Python</option>
          <option value="bash">Bash</option>
        </select>
        <button id="ca-run-btn"><i data-lucide="play"></i> Run</button>
      </div>
      <textarea id="ca-code-area" spellcheck="false" placeholder="# Enter code here&#10;# Ctrl+Enter to run"></textarea>
      <div id="ca-output-area"><span class="ca-out-info">Ready.</span></div>
      <div class="ca-artifacts" id="ca-artifacts"></div>
    </div>

    <!-- Files Tab -->
    <div id="ca-tab-files" class="ca-tab-pane">
      <div class="ca-files-toolbar">
        <span><i data-lucide=&quot;folder-open&quot;></i> Workspace files</span>
        <button class="ca-icon-btn" id="ca-files-refresh"><i data-lucide=&quot;refresh-cw&quot;></i> Reload</button>
      </div>
      <div id="ca-file-list"><div class="ca-empty">Loading...</div></div>
      <div class="ca-drop-zone" id="ca-drop-zone">
        <i data-lucide="upload"></i> Drop files here to upload
        <input type="file" id="ca-file-input" multiple style="display:none">
      </div>
    </div>
  </div>

  <div id="ca-resize-handle"></div>
</div>

<script>
(function() {
  'use strict';

  // ===== State =====
  var _open = false;
  var _dragging = false, _dragOX = 0, _dragOY = 0;
  var _resizing = false, _resW = 0, _resH = 0, _resX = 0, _resY = 0;

  // ===== DOM refs =====
  var panel, header, closeBtn, runBtn, codeArea, outputArea, artifacts,
      langSelect, tabBtns, fileList, dropZone, fileInput, filesRefresh;

  function _initDom() {
    panel       = document.getElementById('ca-panel');
    header      = document.getElementById('ca-header');
    closeBtn    = document.getElementById('ca-close-btn');
    runBtn      = document.getElementById('ca-run-btn');
    codeArea    = document.getElementById('ca-code-area');
    outputArea  = document.getElementById('ca-output-area');
    artifacts   = document.getElementById('ca-artifacts');
    langSelect  = document.getElementById('ca-lang-select');
    tabBtns     = document.querySelectorAll('.ca-tab-btn');
    fileList    = document.getElementById('ca-file-list');
    dropZone    = document.getElementById('ca-drop-zone');
    fileInput   = document.getElementById('ca-file-input');
    filesRefresh = document.getElementById('ca-files-refresh');
  }

  // ===== Drag =====
  function _initDrag() {
    header.addEventListener('mousedown', function(e) {
      if (e.target.tagName === 'BUTTON') return;
      _dragging = true;
      var r = panel.getBoundingClientRect();
      _dragOX = e.clientX - r.left;
      _dragOY = e.clientY - r.top;
      document.body.style.userSelect = 'none';
      e.preventDefault();
    });
    document.addEventListener('mousemove', function(e) {
      if (!_dragging) return;
      var x = e.clientX - _dragOX;
      var y = e.clientY - _dragOY;
      x = Math.max(0, Math.min(window.innerWidth  - panel.offsetWidth,  x));
      y = Math.max(0, Math.min(window.innerHeight - panel.offsetHeight, y));
      panel.style.left   = x + 'px';
      panel.style.top    = y + 'px';
      panel.style.right  = 'auto';
      panel.style.bottom = 'auto';
    });
    document.addEventListener('mouseup', function() {
      if (_dragging) { _dragging = false; document.body.style.userSelect = ''; }
    });
  }

  // ===== Resize =====
  function _initResize() {
    var handle = document.getElementById('ca-resize-handle');
    handle.addEventListener('mousedown', function(e) {
      _resizing = true;
      _resW = panel.offsetWidth;
      _resH = panel.offsetHeight;
      _resX = e.clientX;
      _resY = e.clientY;
      document.body.style.userSelect = 'none';
      document.body.style.cursor = 'se-resize';
      e.preventDefault();
      e.stopPropagation();
    });
    document.addEventListener('mousemove', function(e) {
      if (!_resizing) return;
      var w = Math.max(280, _resW + (e.clientX - _resX));
      var h = Math.max(220, _resH + (e.clientY - _resY));
      panel.style.width  = w + 'px';
      panel.style.height = h + 'px';
    });
    document.addEventListener('mouseup', function() {
      if (_resizing) {
        _resizing = false;
        document.body.style.userSelect = '';
        document.body.style.cursor = '';
      }
    });
  }

  // ===== Tabs =====
  function _initTabs() {
    tabBtns.forEach(function(btn) {
      btn.addEventListener('click', function() {
        var tab = btn.dataset.tab;
        tabBtns.forEach(function(b) { b.classList.remove('ca-tab-active'); });
        btn.classList.add('ca-tab-active');
        document.querySelectorAll('.ca-tab-pane').forEach(function(p) {
          p.classList.remove('ca-pane-active');
        });
        var pane = document.getElementById('ca-tab-' + tab);
        if (pane) pane.classList.add('ca-pane-active');
        if (tab === 'files') _loadFiles();
      });
    });
  }

  // ===== Terminal =====
  function _appendOutput(text, cls) {
    var span = document.createElement('span');
    span.className = cls;
    span.textContent = text;
    outputArea.appendChild(span);
    outputArea.scrollTop = outputArea.scrollHeight;
  }

  function _clearOutput() {
    outputArea.innerHTML = '';
    artifacts.innerHTML = '';
  }

  async function _runCode() {
    var code = codeArea.value;
    var language = langSelect.value;
    if (!code.trim()) return;
    runBtn.disabled = true;
    _clearOutput();
    _appendOutput('Running...\n', 'ca-out-info');
    var persona = (window.S && S.persona) ? S.persona : 'default';
    try {
      var resp = await fetch('/api/chat/' + persona + '/sandbox/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: code, language: language })
      });
      var data = await resp.json();
      _clearOutput();
      if (data.stdout) _appendOutput(data.stdout, 'ca-out-stdout');
      if (data.stderr) _appendOutput(data.stderr, 'ca-out-stderr');
      if (!data.stdout && !data.stderr) _appendOutput('(no output)\n', 'ca-out-info');
      if (data.exit_code !== 0) {
        _appendOutput('\nExit code: ' + data.exit_code + '\n', 'ca-out-error');
      }
      if (data.artifacts && data.artifacts.length) {
        data.artifacts.forEach(function(b64) {
          var img = document.createElement('img');
          img.src = 'data:image/png;base64,' + b64;
          artifacts.appendChild(img);
        });
      }
      console.log('[sandbox]', { language: language, code_preview: code.slice(0, 100), stdout: data.stdout, stderr: data.stderr, exit_code: data.exit_code });
    } catch (e) {
      _clearOutput();
      _appendOutput('Error: ' + e.message + '\n', 'ca-out-error');
    } finally {
      runBtn.disabled = false;
    }
  }

  function _initTerminal() {
    runBtn.addEventListener('click', _runCode);
    codeArea.addEventListener('keydown', function(e) {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault();
        _runCode();
      }
    });
  }

  // ===== Files =====
  function _fmtSize(n) {
    if (n == null) return '';
    if (n < 1024) return n + ' B';
    if (n < 1048576) return (n / 1024).toFixed(1) + ' KB';
    return (n / 1048576).toFixed(1) + ' MB';
  }

  async function _loadFiles() {
    var persona = (window.S && S.persona) ? S.persona : 'default';
    fileList.innerHTML = '<div class="ca-empty">Loading...</div>';
    try {
      var resp = await fetch('/api/chat/' + persona + '/sandbox/files');
      var data = await resp.json();
      var files = data.files || data.tree || data || [];
      if (!Array.isArray(files) || files.length === 0) {
        fileList.innerHTML = '<div class="ca-empty">No files in workspace.</div>';
        return;
      }
      fileList.innerHTML = '';
      files.forEach(function(f) {
        var name = f.name || f.path || f;
        var size = f.size;
        var item = document.createElement('div');
        item.className = 'ca-file-item';
        item.innerHTML =
          '<span class="ca-file-name" title="' + name + '">' + name + '</span>' +
          '<span class="ca-file-size">' + _fmtSize(size) + '</span>' +
          '<button class="ca-del-btn" data-name="' + name + '" title="Delete"><i data-lucide=&quot;trash-2&quot;></i></button>';
        item.querySelector('.ca-file-name').addEventListener('click', function() {
          _downloadFile(name);
        });
        item.querySelector('.ca-del-btn').addEventListener('click', function(e) {
          e.stopPropagation();
          _deleteFile(name);
        });
        fileList.appendChild(item);
      });
    } catch (e) {
      fileList.innerHTML = '<div class="ca-empty" style="color:#f87171">Error: ' + e.message + '</div>';
    }
  }

  function _downloadFile(name) {
    var persona = (window.S && S.persona) ? S.persona : 'default';
    var a = document.createElement('a');
    a.href = '/api/chat/' + persona + '/sandbox/files/' + encodeURIComponent(name);
    a.download = name;
    a.click();
  }

  async function _deleteFile(name) {
    var persona = (window.S && S.persona) ? S.persona : 'default';
    try {
      await fetch('/api/chat/' + persona + '/sandbox/files/' + encodeURIComponent(name), { method: 'DELETE' });
      _loadFiles();
    } catch (e) {
      console.error('Delete failed:', e);
    }
  }

  async function _uploadFiles(fileObjs) {
    var persona = (window.S && S.persona) ? S.persona : 'default';
    var arr = Array.from(fileObjs);
    for (var i = 0; i < arr.length; i++) {
      var fd = new FormData();
      fd.append('file', arr[i]);
      try {
        await fetch('/api/chat/' + persona + '/sandbox/upload', { method: 'POST', body: fd });
      } catch (e) {
        console.error('Upload failed:', e);
      }
    }
    _loadFiles();
  }

  function _initFiles() {
    filesRefresh.addEventListener('click', _loadFiles);

    dropZone.addEventListener('click', function() { fileInput.click(); });
    fileInput.addEventListener('change', function() {
      if (fileInput.files.length) _uploadFiles(fileInput.files);
      fileInput.value = '';
    });

    dropZone.addEventListener('dragover', function(e) {
      e.preventDefault();
      dropZone.classList.add('ca-drag-over');
    });
    dropZone.addEventListener('dragleave', function() {
      dropZone.classList.remove('ca-drag-over');
    });
    dropZone.addEventListener('drop', function(e) {
      e.preventDefault();
      dropZone.classList.remove('ca-drag-over');
      if (e.dataTransfer.files.length) _uploadFiles(e.dataTransfer.files);
    });
  }

  // ===== Init =====
  function _init() {
    _initDom();
    closeBtn.addEventListener('click', function() { window.closeCodingAgent(); });
    _initDrag();
    _initResize();
    _initTabs();
    _initTerminal();
    _initFiles();
    document.addEventListener('keydown', function(e) {
      if (e.key === 'Escape' && _open) {
        window.closeCodingAgent();
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', _init);
  } else {
    _init();
  }

  // ===== Global API =====
  window.openCodingAgent = function(options) {
    if (!panel) _init();
    options = options || {};
    panel.classList.add('ca-open');
    _open = true;
    if (options.code != null) codeArea.value = options.code;
    if (options.language != null) langSelect.value = options.language;
    // Toggle Code button active state
    const btn = document.getElementById('sandbox-toggle-btn');
    if (btn) btn.classList.add('active');
  };

  window.closeCodingAgent = function() {
    if (panel) panel.classList.remove('ca-open');
    _open = false;
    const btn = document.getElementById('sandbox-toggle-btn');
    if (btn) btn.classList.remove('active');
  };

  window.isCodingAgentOpen = function() {
    return _open;
  };

})();
</script>
"""
