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
    var persona = S.persona;
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
    var persona = S.persona;
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
          '<button class="ca-del-btn" data-name="' + name + '" title="Delete"><i data-lucide="trash-2"></i></button>';
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
    var persona = S.persona;
    var a = document.createElement('a');
    a.href = '/api/chat/' + persona + '/sandbox/files/' + encodeURIComponent(name);
    a.download = name;
    a.click();
  }

  async function _deleteFile(name) {
    var persona = S.persona;
    try {
      await fetch('/api/chat/' + persona + '/sandbox/files/' + encodeURIComponent(name), { method: 'DELETE' });
      _loadFiles();
    } catch (e) {
      console.error('Delete failed:', e);
    }
  }

  async function _uploadFiles(fileObjs) {
    var persona = S.persona;
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
