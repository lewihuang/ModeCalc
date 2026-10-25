/**
 * ModeCalc 前端主控
 * WebSocket 连接 → 30ms debounce → 协调三区显示
 */

(function () {
  'use strict';

  // ── 状态 ──────────────────────────────────────────
  let ws = null;
  let reconnectTimer = null;
  let debounceTimer = null;
  const RECONNECT_DELAY = 2000;

  const elChord = document.getElementById('chord-name');
  const elModePanel = document.getElementById('mode-panel');
  const elMatchesList = document.getElementById('matches-list');
  const elSettingsView = document.getElementById('settings-view');
  const elSettingsRows = document.getElementById('settings-rows');
  const elSettingsCount = document.getElementById('settings-count');
  const elSettingsError = document.getElementById('settings-error');
  const elSettingsNotice = document.getElementById('settings-notice');
  const elScaleSearch = document.getElementById('scale-search');

  let selectedMatch = null;
  var _lastActiveNotes = [];
  var _lastModeMatches = [];
  var _lastDerivedMatches = [];

  let analysisMode = 'chord';
  let settingsOpen = false;
  let latestState = null;
  let lastSequence = -1;
  let desktopInitializing = false;
  var scaleRows = [];
  var scaleSearch = '';
  var libraryLoaded = false;
  var expandedGroups = {};

  // ── 分析模式切换 ──────────────────────────────────

  function sendAnalysisMode() {
    if (window.pywebview && window.pywebview.api.set_analysis_mode) {
      window.pywebview.api.set_analysis_mode(analysisMode, null);
    } else if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: 'set_analysis_mode',
        mode: analysisMode,
      }));
    }
  }

  function sendPinnedScale() {
    var pcs = selectedMatch ? selectedMatch.pcs : null;
    var tonicPc = selectedMatch ? selectedMatch.tonic_pc : null;
    if (window.pywebview && window.pywebview.api.set_pinned_scale) {
      window.pywebview.api.set_pinned_scale(pcs, tonicPc);
    } else if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: 'set_pinned_scale',
        pcs: pcs,
        tonic_pc: tonicPc,
      }));
    }
  }

  function updateSettingsButton() {
    var gear = document.getElementById('open-settings');
    if (gear) gear.classList.toggle('hidden', analysisMode !== 'mode');
  }

  function bindAnalysisControls() {
    document.querySelectorAll('#analysis-toggle input[name=analysis]').forEach(function (radio) {
      radio.addEventListener('change', function () {
        if (!radio.checked) return;
        analysisMode = radio.value;
        elModePanel.classList.toggle('hidden', analysisMode !== 'mode');
        updateSettingsButton();
        if (analysisMode === 'chord') {
          selectedMatch = null;
          sendPinnedScale();
        }
        sendAnalysisMode();
      });
    });
  }

  // ── 音阶侧栏（只读） ──────────────────────────────

  function renderScaleSidebar() {
    var container = document.getElementById('scale-sidebar');
    if (!container) return;
    container.innerHTML = '';

    var enabled = scaleRows.filter(function (row) { return row.enabled; });
    if (!enabled.length) {
      var empty = document.createElement('div');
      empty.className = 'scale-sidebar-empty';
      if (!window.pywebview) {
        empty.textContent = '浏览器调试模式暂不支持音阶设置。';
      } else if (!libraryLoaded) {
        empty.textContent = '正在加载音阶库…';
      } else {
        empty.textContent = '未启用任何音阶，点击上方「音阶设置」开启。';
      }
      container.appendChild(empty);
      return;
    }

    var sections = {};
    enabled.forEach(function (row) {
      var section = sections[row.section];
      if (!section) {
        section = sections[row.section] = {
          label: row.section_label,
          order: row.section_order,
          groups: {},
          groupOrder: [],
        };
      }
      if (!section.groups[row.group]) {
        section.groups[row.group] = [];
        section.groupOrder.push(row.group);
      }
      section.groups[row.group].push(row);
    });

    Object.keys(sections)
      .sort(function (a, b) { return sections[a].order - sections[b].order; })
      .forEach(function (sectionKey) {
        var section = sections[sectionKey];
        if (sectionKey === 'world' || sectionKey === 'custom') {
          var sectionTitle = document.createElement('div');
          sectionTitle.className = 'scale-sidebar-section';
          sectionTitle.textContent = section.label;
          container.appendChild(sectionTitle);
        }

        section.groupOrder.forEach(function (groupName) {
          var rows = section.groups[groupName];

          var group = document.createElement('div');
          group.className = 'scale-group';

          var header = document.createElement('div');
          header.className = 'group-header';
          var label = document.createElement('span');
          label.className = 'group-label';
          label.textContent = groupName + ' (' + rows.length + ')';
          var toggle = document.createElement('span');
          toggle.className = 'group-toggle';
          toggle.textContent = '▼';
          header.appendChild(label);
          header.appendChild(toggle);

          var body = document.createElement('div');
          body.className = 'group-body scale-sidebar-body';

          rows.forEach(function (row) {
            var item = document.createElement('div');
            item.className = 'scale-sidebar-item';
            var name = document.createElement('span');
            name.className = 'scale-sidebar-name';
            name.textContent = row.name;
            item.appendChild(name);
            body.appendChild(item);
          });

          header.addEventListener('click', function () {
            body.classList.toggle('collapsed');
            toggle.classList.toggle('collapsed');
          });

          group.appendChild(header);
          group.appendChild(body);
          container.appendChild(group);
        });
      });
  }

  // ── 音阶设置 ──────────────────────────────────────

  function setSettingsError(message) {
    if (elSettingsError) elSettingsError.textContent = message || '';
  }

  function setSettingsNotice(message) {
    if (elSettingsNotice) elSettingsNotice.textContent = message || '';
  }

  function applyLibraryResult(result) {
    if (!result) return false;
    if (result.ok === false) {
      setSettingsError(result.error || '操作失败');
      return false;
    }
    scaleRows = result.rows || [];
    setSettingsError('');
    if (result.copied) {
      setSettingsNotice('默认音阶已保留；修改已保存为「Custom」中的新音阶。');
    } else {
      setSettingsNotice('');
    }
    renderScaleSidebar();
    if (settingsOpen) renderSettings();
    if (result.copied && result.new_id && elSettingsRows) {
      var copied = elSettingsRows.querySelectorAll('.scale-row');
      for (var i = 0; i < copied.length; i++) {
        if (copied[i].dataset.id === result.new_id) {
          copied[i].scrollIntoView({ block: 'nearest' });
          break;
        }
      }
    }
    return true;
  }

  function loadScaleLibrary() {
    if (!(window.pywebview && window.pywebview.api && window.pywebview.api.get_scale_library)) {
      renderScaleSidebar();
      return Promise.resolve(false);
    }
    try {
      return window.pywebview.api.get_scale_library().then(function (payload) {
        if (payload && Array.isArray(payload.rows)) {
          scaleRows = payload.rows;
          libraryLoaded = true;
          renderScaleSidebar();
          if (settingsOpen) renderSettings();
        }
        return true;
      }).catch(function () {
        libraryLoaded = true;
        setSettingsError('读取音阶库失败');
        renderScaleSidebar();
        return false;
      });
    } catch (e) {
      return Promise.resolve(false);
    }
  }

  function callScaleApi(method) {
    if (!(window.pywebview && window.pywebview.api && window.pywebview.api[method])) {
      setSettingsError('设置仅桌面版可用');
      return Promise.resolve(false);
    }
    var args = Array.prototype.slice.call(arguments, 1);
    try {
      return window.pywebview.api[method].apply(window.pywebview.api, args)
        .then(function (result) {
          var ok = applyLibraryResult(result);
          if (!ok) loadScaleLibrary();  // 回滚到服务端状态
          return ok;
        })
        .catch(function () {
          setSettingsError('操作失败');
          loadScaleLibrary();
          return false;
        });
    } catch (e) {
      setSettingsError('操作失败');
      return Promise.resolve(false);
    }
  }

  function openSettings() {
    settingsOpen = true;
    if (elSettingsView) elSettingsView.classList.remove('hidden');
    selectedMatch = null;
    sendPinnedScale();
    _lastDerivedMatches = [];
    setSettingsError('');
    setSettingsNotice('');
    scaleSearch = '';
    if (elScaleSearch) elScaleSearch.value = '';
    renderSettings();
    loadScaleLibrary();
  }

  function closeSettings() {
    settingsOpen = false;
    if (elSettingsView) elSettingsView.classList.add('hidden');
    _lastDataStr = '';
    loadScaleLibrary();
    if (latestState) updateUI(latestState, true);
  }

  function buildMiniKeyboard(pcs, onChange) {
    var selected = {};
    pcs.forEach(function (pc) { selected[pc] = true; });

    var W = 34, H = 46, BW = 21, BH = 30;
    var ns = 'http://www.w3.org/2000/svg';
    var svg = document.createElementNS(ns, 'svg');
    svg.setAttribute('viewBox', '0 0 ' + (7 * W) + ' ' + H);
    svg.setAttribute('width', String(7 * W));
    svg.setAttribute('height', String(H));
    svg.classList.add('mini-kb');

    function toggle(pc) {
      if (pc === 0) {
        setSettingsError('根音 C 固定，不能取消');
        return;
      }
      var next = Object.keys(selected)
        .map(Number)
        .filter(function (value) { return value !== pc; });
      if (!selected[pc]) next.push(pc);
      next = Array.from(new Set(next)).sort(function (a, b) { return a - b; });
      if (next.length < 3) {
        setSettingsError('音阶至少需要 3 个音');
        return;
      }
      setSettingsError('');
      onChange(next);
    }

    var whitePcs = [0, 2, 4, 5, 7, 9, 11];
    var whiteLabels = ['C', 'D', 'E', 'F', 'G', 'A', 'B'];

    whitePcs.forEach(function (pc, index) {
      var rect = document.createElementNS(ns, 'rect');
      rect.setAttribute('x', String(index * W));
      rect.setAttribute('y', '0');
      rect.setAttribute('width', String(W));
      rect.setAttribute('height', String(H));
      rect.setAttribute('rx', '2');
      rect.setAttribute('ry', '2');
      rect.setAttribute('fill', selected[pc] ? '#64b5f6' : '#ffffff');
      rect.setAttribute('stroke', '#333333');
      rect.setAttribute('stroke-width', '0.6');
      rect.classList.add('mini-kb-key');
      rect.addEventListener('click', function () { toggle(pc); });
      svg.appendChild(rect);

      var text = document.createElementNS(ns, 'text');
      text.setAttribute('x', String(index * W + W / 2));
      text.setAttribute('y', String(H - 3));
      text.setAttribute('text-anchor', 'middle');
      text.setAttribute('font-size', '7');
      text.setAttribute('font-family', 'Segoe UI, system-ui, sans-serif');
      text.setAttribute('fill', pc === 0 ? '#1565c0' : '#888');
      text.textContent = whiteLabels[index];
      text.classList.add('mini-kb-label');
      svg.appendChild(text);
    });

    var blackPcs = [1, 3, 6, 8, 10];
    var blackAfter = { 1: 0, 3: 1, 6: 3, 8: 4, 10: 5 };
    blackPcs.forEach(function (pc) {
      var rect = document.createElementNS(ns, 'rect');
      rect.setAttribute('x', String((blackAfter[pc] + 1) * W - BW / 2));
      rect.setAttribute('y', '0');
      rect.setAttribute('width', String(BW));
      rect.setAttribute('height', String(BH));
      rect.setAttribute('rx', '1.5');
      rect.setAttribute('ry', '1.5');
      rect.setAttribute('fill', selected[pc] ? '#1565c0' : '#2a2a2a');
      rect.setAttribute('stroke', '#111111');
      rect.setAttribute('stroke-width', '0.6');
      rect.classList.add('mini-kb-key');
      rect.addEventListener('click', function () { toggle(pc); });
      svg.appendChild(rect);
    });

    return svg;
  }

  function buildScaleRow(row) {
    var el = document.createElement('div');
    el.className = 'scale-row' + (row.enabled ? '' : ' is-off');
    el.dataset.id = row.id;
    el.dataset.section = row.section;
    el.dataset.group = row.group;

    // 使用
    var checkCell = document.createElement('div');
    checkCell.className = 'scale-cell scale-cell-check';
    var checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.checked = !!row.enabled;
    checkbox.title = '参与识别并在左侧列表显示';
    checkbox.addEventListener('change', function () {
      callScaleApi('set_scale_enabled', row.id, checkbox.checked);
    });
    checkCell.appendChild(checkbox);

    // 名称
    var nameCell = document.createElement('div');
    nameCell.className = 'scale-cell scale-cell-name';
    var input = document.createElement('input');
    input.type = 'text';
    input.className = 'scale-name-input';
    input.value = row.name;
    input.maxLength = 40;
    input.addEventListener('keydown', function (event) {
      if (event.key === 'Enter') {
        input.blur();
      } else if (event.key === 'Escape') {
        input.value = row.name;
        input.blur();
      }
    });
    input.addEventListener('change', function () {
      var value = input.value.trim();
      if (value === row.name) return;
      if (!value) {
        setSettingsError('名称不能为空');
        input.value = row.name;
        return;
      }
      setSettingsError('');
      callScaleApi('update_scale', row.id, value, null).then(function (ok) {
        if (!ok) input.value = row.name;
      });
    });
    nameCell.appendChild(input);

    var badgeText = row.is_alias ? '别名' : (row.builtin ? '' : '自定义');
    if (badgeText) {
      var badge = document.createElement('span');
      badge.className = 'scale-kind-badge';
      badge.textContent = badgeText;
      badge.title = row.is_alias ? ('同于 ' + (row.alias_of_name || '')) : '用户自定义音阶';
      nameCell.appendChild(badge);
    }

    // 音阶
    var kbCell = document.createElement('div');
    kbCell.className = 'scale-cell scale-cell-kb';
    kbCell.appendChild(buildMiniKeyboard(row.pcs, function (next) {
      callScaleApi('update_scale', row.id, null, next);
    }));

    // 信息（绝对示例 / 别名）
    var infoCell = document.createElement('div');
    infoCell.className = 'scale-cell scale-cell-info';
    var infoText = document.createElement('span');
    infoText.className = 'scale-info-text';
    infoText.textContent = row.info || '';
    infoText.title = row.info || '';
    infoCell.appendChild(infoText);

    // 删除
    var deleteCell = document.createElement('div');
    deleteCell.className = 'scale-cell scale-cell-delete';
    var deleteBtn = document.createElement('button');
    deleteBtn.type = 'button';
    deleteBtn.className = 'scale-delete-btn';
    deleteBtn.textContent = '×';
    if (row.builtin) {
      deleteBtn.disabled = true;
      deleteBtn.title = '默认音阶不可删除；可用「使用」关闭';
    } else {
      deleteBtn.title = '删除自定义音阶';
      deleteBtn.addEventListener('click', function () {
        var message = '删除「' + row.name + '」这个自定义音阶？';
        if (!window.confirm(message)) return;
        callScaleApi('delete_scale', row.id);
      });
    }
    deleteCell.appendChild(deleteBtn);

    el.appendChild(checkCell);
    el.appendChild(nameCell);
    el.appendChild(kbCell);
    el.appendChild(infoCell);
    el.appendChild(deleteCell);
    return el;
  }

  function groupKey(section, group) {
    return section + '|' + group;
  }

  function buildGroupHeader(section, group, rows) {
    var allGroupRows = scaleRows.filter(function (row) {
      return row.section === section && row.group === group;
    });
    var enabledCount = allGroupRows.filter(function (row) {
      return row.enabled;
    }).length;
    var key = groupKey(section, group);
    var expanded = expandedGroups[key];
    if (expanded === undefined) {
      expanded = section === 'natural';
    }
    if (scaleSearch.trim()) expanded = true;

    var groupEl = document.createElement('div');
    groupEl.className = 'settings-group';

    var header = document.createElement('div');
    header.className = 'settings-group-header';

    var checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.className = 'settings-group-check';
    checkbox.checked = enabledCount === allGroupRows.length && allGroupRows.length > 0;
    checkbox.indeterminate = enabledCount > 0 && enabledCount < allGroupRows.length;
    checkbox.title = '全选/取消本组';
    checkbox.addEventListener('change', function () {
      callScaleApi('set_group_enabled', section, group, checkbox.checked);
    });

    var label = document.createElement('span');
    label.className = 'settings-group-label';
    label.textContent = group + ' (' + allGroupRows.length + ')';

    var count = document.createElement('span');
    count.className = 'settings-group-count';
    count.textContent = '已启用 ' + enabledCount;

    var toggle = document.createElement('span');
    toggle.className = 'settings-group-toggle' + (expanded ? '' : ' collapsed');
    toggle.textContent = '▼';

    header.appendChild(checkbox);
    header.appendChild(label);
    header.appendChild(count);
    header.appendChild(toggle);

    var body = document.createElement('div');
    body.className = 'settings-group-body' + (expanded ? '' : ' collapsed');

    header.addEventListener('click', function (event) {
      if (event.target === checkbox) return;
      var isExpanded = expandedGroups[key];
      if (isExpanded === undefined) isExpanded = section === 'natural';
      expandedGroups[key] = !isExpanded;
      body.classList.toggle('collapsed', isExpanded);
      toggle.classList.toggle('collapsed', isExpanded);
    });

    rows.forEach(function (row) {
      body.appendChild(buildScaleRow(row));
    });

    groupEl.appendChild(header);
    groupEl.appendChild(body);
    return groupEl;
  }

  function renderSettings() {
    if (!elSettingsRows) return;
    var scrollHost = elSettingsRows.parentElement;
    var scrollTop = scrollHost ? scrollHost.scrollTop : 0;

    var query = scaleSearch.trim().toLowerCase();
    var visible = scaleRows.filter(function (row) {
      if (!query) return true;
      return row.name.toLowerCase().indexOf(query) !== -1 ||
        row.group.toLowerCase().indexOf(query) !== -1 ||
        row.section_label.toLowerCase().indexOf(query) !== -1 ||
        (row.info || '').toLowerCase().indexOf(query) !== -1;
    });

    var sections = {};
    visible.forEach(function (row) {
      if (row.section === 'custom') return;
      var section = sections[row.section];
      if (!section) {
        section = sections[row.section] = {
          label: row.section_label,
          order: row.section_order,
          groups: {},
          groupOrder: [],
          groupOrderValue: {},
        };
      }
      if (!section.groups[row.group]) {
        section.groups[row.group] = [];
        section.groupOrder.push(row.group);
        section.groupOrderValue[row.group] = row.group_order;
      }
      section.groups[row.group].push(row);
    });

    elSettingsRows.innerHTML = '';
    Object.keys(sections)
      .sort(function (a, b) { return sections[a].order - sections[b].order; })
      .forEach(function (sectionKey) {
        var section = sections[sectionKey];
        if (sectionKey === 'world') {
          var title = document.createElement('div');
          title.className = 'settings-section-title';
          title.textContent = section.label;
          elSettingsRows.appendChild(title);
        }
        section.groupOrder
          .sort(function (a, b) {
            return section.groupOrderValue[a] - section.groupOrderValue[b];
          })
          .forEach(function (group) {
            elSettingsRows.appendChild(
              buildGroupHeader(sectionKey, group, section.groups[group])
            );
          });
      });

    // Custom 始终显示，与 World Music 同级；为空时标题栏也不消失
    var customAll = scaleRows.filter(function (row) { return row.section === 'custom'; });
    var customVisible = visible.filter(function (row) { return row.section === 'custom'; });
    var customEnabled = customAll.filter(function (row) { return row.enabled; }).length;

    var customTitle = document.createElement('div');
    customTitle.className = 'settings-section-title settings-custom-title';

    var customCheck = document.createElement('input');
    customCheck.type = 'checkbox';
    customCheck.className = 'settings-group-check';
    customCheck.disabled = customAll.length === 0;
    customCheck.checked = customAll.length > 0 && customEnabled === customAll.length;
    customCheck.indeterminate = customEnabled > 0 && customEnabled < customAll.length;
    customCheck.title = '全选/取消 Custom 中的音阶';
    customCheck.addEventListener('change', function () {
      callScaleApi('set_group_enabled', 'custom', 'Custom', customCheck.checked);
    });

    var customLabel = document.createElement('span');
    customLabel.className = 'settings-group-label';
    customLabel.textContent = 'Custom (' + customAll.length + ')';

    customTitle.appendChild(customCheck);
    customTitle.appendChild(customLabel);

    if (customAll.length === 0) {
      var emptyHint = document.createElement('span');
      emptyHint.className = 'settings-custom-hint';
      emptyHint.textContent = '点击上方「添加音阶」新建';
      customTitle.appendChild(emptyHint);
    } else if (query && customVisible.length === 0) {
      var noMatch = document.createElement('span');
      noMatch.className = 'settings-custom-hint';
      noMatch.textContent = '无匹配';
      customTitle.appendChild(noMatch);
    }

    elSettingsRows.appendChild(customTitle);
    customVisible.forEach(function (row) {
      elSettingsRows.appendChild(buildScaleRow(row));
    });

    var enabled = scaleRows.filter(function (row) { return row.enabled; }).length;
    if (elSettingsCount) {
      elSettingsCount.textContent = '已启用 ' + enabled + ' / ' + scaleRows.length;
    }

    if (scrollHost) scrollHost.scrollTop = scrollTop;
  }

  function addScale() {
    scaleSearch = '';
    if (elScaleSearch) elScaleSearch.value = '';
    renderSettings();
    callScaleApi('add_scale', null, null).then(function (ok) {
      if (!ok) return;
      var customRows = elSettingsRows.querySelectorAll('.scale-row[data-section="custom"]');
      var last = customRows[customRows.length - 1];
      if (last) {
        last.scrollIntoView({ block: 'nearest' });
        var input = last.querySelector('.scale-name-input');
        if (input) {
          input.focus();
          input.select();
        }
      }
    });
  }

  function bindSettings() {
    var openBtn = document.getElementById('open-settings');
    var closeBtn = document.getElementById('settings-close');
    var addBtn = document.getElementById('scale-add');
    var resetBtn = document.getElementById('scale-reset');

    if (openBtn) {
      openBtn.addEventListener('click', function () {
        if (analysisMode !== 'mode') return;
        if (!(window.pywebview && window.pywebview.api)) {
          window.alert('音阶设置仅桌面版可用');
          return;
        }
        openSettings();
      });
    }
    if (closeBtn) closeBtn.addEventListener('click', closeSettings);
    if (addBtn) addBtn.addEventListener('click', addScale);
    if (resetBtn) {
      resetBtn.addEventListener('click', function () {
        if (!window.confirm('恢复所有内置音阶的默认名称、音集与使用状态？\n默认只启用 Natural Mode 的 7 个调式，Custom 音阶保留。')) return;
        callScaleApi('reset_scale_library');
      });
    }
    if (elScaleSearch) {
      elScaleSearch.addEventListener('input', function () {
        scaleSearch = elScaleSearch.value;
        renderSettings();
      });
    }
    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && settingsOpen) closeSettings();
    });
  }

  // ── Match 点击选中调式（钢琴键盘高亮/辅助创作）─

  function onMatchClick(match) {
    if (!match.pcs || match.pcs.length === 0) return;
    if (selectedMatch && match.name === selectedMatch.name) {
      selectedMatch = null;         // toggle off
    } else {
      selectedMatch = match;        // new selection / pin
    }
    sendPinnedScale();
    _lastDerivedMatches = [];       // 等下一次推送按新固定音阶重算
    updateKeyboardHighlight();

    // re-render matches list to update pin position
    if (_lastModeMatches.length > 0 || selectedMatch) {
      renderMatches(_lastModeMatches);
    } else {
      clearMatches();
    }
  }

  function updateKeyboardHighlight() {
    var activeMidi = _lastActiveNotes;
    var scaleMidi = [];
    if (selectedMatch) {
      var pcsSet = {};
      selectedMatch.pcs.forEach(function (pc) { pcsSet[pc] = true; });
      for (var n = 21; n <= 108; n++) {
        if (pcsSet[n % 12]) scaleMidi.push(n);
      }
    }
    highlightKeys(activeMidi, scaleMidi);

    // 指板高亮：合并 active + scale MIDI，精确八度映射
    if (typeof highlightFretboardFromMidi === 'function') {
      var allMidi = [];
      var seenMidi = {};
      activeMidi.forEach(function (m) {
        if (!seenMidi[m]) { seenMidi[m] = true; allMidi.push(m); }
      });
      scaleMidi.forEach(function (m) {
        if (!seenMidi[m]) { seenMidi[m] = true; allMidi.push(m); }
      });
      highlightFretboardFromMidi(allMidi);
    }
  }

  // ── WebSocket (仅浏览器模式使用) ──────────────────

  function connect() {
    if (location.hash === '#desktop' || location.protocol === 'file:' || window.pywebview) {
      return;
    }

    if (ws && ws.readyState === WebSocket.OPEN) return;

    try {
      ws = new WebSocket(`ws://${location.host}/ws`);
    } catch (e) {
      console.error('[ws] 连接失败:', e);
      return;
    }

    ws.onopen = () => {
      sendAnalysisMode();
    };

    ws.onmessage = (e) => {
      const data = JSON.parse(e.data);
      // 非状态消息（如 MIDI 设备列表）直达处理
      if (data.type === 'midi_ports') {
        setMidiPorts(data.ports);
        return;
      }
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => updateUI(data), 30);
    };

    ws.onclose = () => {
      scheduleReconnect();
    };

    ws.onerror = () => {};
  }

  function scheduleReconnect() {
    if (reconnectTimer) return;
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      connect();
    }, RECONNECT_DELAY);
  }

  // ── UI 更新 (含去重) ──────────────────────────────

  var _lastDataStr = '';
  function updateUI(data, replay) {
    if (typeof data.sequence === 'number') {
      if (!replay && data.sequence <= lastSequence) return;
      lastSequence = data.sequence;
    }
    latestState = data;
    if (data.midi) applyMidiStatus(Object.assign({}, data.midi, { sequence: data.sequence }));
    if (settingsOpen) return;

    var s = JSON.stringify(data);
    if (s === _lastDataStr) return;
    _lastDataStr = s;

    _lastActiveNotes = (data.active_notes || []).map(function(n) { return n.midi; });
    _lastModeMatches = data.mode_matches || [];
    _lastDerivedMatches = data.derived_matches || [];

    // 顶部始终显示和弦透镜
    if (data.result_type === 'none') {
      elChord.textContent = '';
      elChord.style.opacity = '1';
    } else if (data.result_type === 'unknown') {
      elChord.textContent = data.result?.name || '';
      elChord.style.opacity = '0.4';
    } else if (data.result) {
      elChord.textContent = data.result.name;
      elChord.style.opacity = '1';
      if (data.result_type === 'chord' && data.result.is_incomplete) {
        elChord.textContent += ' ?';
      }
    }

    // 侧栏 Matches：选中调式永远在首位，无音符也显示
    const hasNotes = (data.active_notes || []).length > 0;
    if (data.analysis_mode === 'mode' && (hasNotes || selectedMatch)) {
      renderMatches(_lastModeMatches);
    } else if (hasNotes && data.result) {
      renderMatches([{ name: data.result.name }]);
    } else {
      clearMatches();
    }

    if (typeof highlightKeys === 'function') {
      updateKeyboardHighlight();
    }

    if (typeof renderStaff === 'function') {
      renderStaff(data.active_notes || [], data.key_sig || 'C');
    }

    var susEl = document.getElementById('sustain-indicator');
    if (susEl) susEl.classList.toggle('active', !!data.sustain);

    setDebug('db-notes', (data.active_notes || []).map(function(n) { return n.midi; }).join(',') || '-');
    setDebug('db-sus', data.sustain ? 'SUS' : '');
  }

  function renderMatches(matches) {
    if (!elMatchesList) return;
    elMatchesList.innerHTML = '';

    var shown = {};

    // 选中调式：永远钉在第一条
    if (selectedMatch) {
      const li = document.createElement('li');
      li.textContent = selectedMatch.name;
      li.classList.add('selected');
      li.dataset.pcs = JSON.stringify(selectedMatch.pcs || []);
      li.addEventListener('click', function () { onMatchClick(selectedMatch); });
      elMatchesList.appendChild(li);
      shown[selectedMatch.name] = true;
    }

    // 派生调式（红音触发）：紧跟在固定调式下方
    _lastDerivedMatches.forEach(function (m) {
      if (shown[m.name]) return;
      shown[m.name] = true;
      const li = document.createElement('li');
      li.textContent = '↳ ' + m.name;
      li.classList.add('derived');
      li.dataset.pcs = JSON.stringify(m.pcs || []);
      li.addEventListener('click', function () { onMatchClick(m); });
      elMatchesList.appendChild(li);
    });

    // 其余匹配（跳过已显示的固定/派生项）
    matches.forEach(function (m) {
      if (shown[m.name]) return;
      shown[m.name] = true;
      const li = document.createElement('li');
      li.textContent = m.name;
      li.dataset.pcs = JSON.stringify(m.pcs || []);
      li.addEventListener('click', function () { onMatchClick(m); });
      elMatchesList.appendChild(li);
    });
  }

  function clearMatches() {
    if (elMatchesList) elMatchesList.innerHTML = '';
  }

  // ── 调试栏 ──────────────────────────────────────────

  function setDebug(id, text) {
    var el = document.getElementById(id);
    if (el) el.textContent = text;
  }
  window._debugBar = function(text) { setDebug('db-midi', text); };

  // ── 调号更改 ──────────────────────────────────────────

  function bindKeySelector() {
    var el = document.getElementById('key-select');
    if (!el) return;
    el.addEventListener('change', function () {
      var keySig = el.value;
      if (window.pywebview && window.pywebview.api.set_key_signature) {
        window.pywebview.api.set_key_signature(keySig);
      }
    });
  }

  // ── 菜单栏 ──────────────────────────────────────────

  function syncKeyMenuSelection() {
    var el = document.getElementById('key-select');
    var val = el ? el.value : 'C';
    document.querySelectorAll('#key-menu .menu-option').forEach(function (opt) {
      opt.classList.toggle('selected', opt.dataset.value === val);
    });
  }

  function bindMenuBar() {
    // 点击触发按钮 → 切换下拉
    document.querySelectorAll('.menu-trigger').forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        var menuId = btn.dataset.menu;
        var dropdown = document.getElementById(menuId);
        var isOpen = dropdown.classList.contains('open');

        // 关闭其他所有下拉
        document.querySelectorAll('.menu-dropdown.open').forEach(function (d) {
          d.classList.remove('open');
        });
        document.querySelectorAll('.menu-trigger.active').forEach(function (b) {
          b.classList.remove('active');
        });

        if (!isOpen) {
          dropdown.classList.add('open');
          btn.classList.add('active');
          syncKeyMenuSelection();
        }
      });
    });

    // 点击调性选项
    document.querySelectorAll('#key-menu .menu-option').forEach(function (opt) {
      opt.addEventListener('click', function () {
        var val = opt.dataset.value;
        var sel = document.getElementById('key-select');
        if (sel) {
          sel.value = val;
          sel.dispatchEvent(new Event('change'));
        }
        closeAllMenus();
      });
    });

    // 点击帮助选项
    document.querySelectorAll('#help-menu .menu-option').forEach(function (opt) {
      opt.addEventListener('click', function () {
        var action = opt.dataset.action;
        closeAllMenus();
        if (action === 'usage-guide') {
          var overlay = document.getElementById('modal-overlay');
          if (overlay) overlay.classList.remove('hidden');
        }
      });
    });

    // 点击外部 → 关闭所有
    document.addEventListener('click', function () {
      closeAllMenus();
    });
  }

  // ── 帮助弹窗 ──────────────────────────────────────────

  function bindModal() {
    var overlay = document.getElementById('modal-overlay');
    var closeBtn = document.getElementById('modal-close');
    if (!overlay || !closeBtn) return;
    closeBtn.addEventListener('click', function () { overlay.classList.add('hidden'); });
    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) overlay.classList.add('hidden');
    });
  }

  function closeAllMenus() {
    document.querySelectorAll('.menu-dropdown.open').forEach(function (d) {
      d.classList.remove('open');
    });
    document.querySelectorAll('.menu-trigger.active').forEach(function (b) {
      b.classList.remove('active');
    });
  }

  // ── MIDI 设备列表 ──────────────────────────────────

  var _midiPorts = null; // First empty enumeration must still build All / Refresh.
  var _selectedMidiPort = null; // null = All
  var _lastMidiSequence = -1;

  function setMidiPorts(ports) {
    _midiPorts = ports;
    var menu = document.getElementById('midi-menu');
    if (!menu) return;
    menu.innerHTML = '';

    // All MIDI Input
    var all = document.createElement('div');
    all.className = 'menu-option';
    all.dataset.port = '';
    all.textContent = 'All MIDI Input';
    menu.appendChild(all);

    // 分割线
    var sep = document.createElement('div');
    sep.className = 'menu-separator';
    menu.appendChild(sep);

    // 具体设备
    ports.forEach(function (name) {
      var opt = document.createElement('div');
      opt.className = 'menu-option';
      opt.dataset.port = name;
      opt.textContent = name;
      menu.appendChild(opt);
    });

    // 绑定点击
    menu.querySelectorAll('.menu-option').forEach(function (opt) {
      opt.addEventListener('click', function () {
        var port = opt.dataset.port;
        selectMidiPort(port);
        closeAllMenus();
      });
    });

    if (window.pywebview && window.pywebview.api.refresh_midi_ports) {
      var refresh = document.createElement('div');
      refresh.className = 'menu-option';
      refresh.textContent = '刷新设备';
      refresh.addEventListener('click', function () {
        window.pywebview.api.refresh_midi_ports().then(applyMidiStatus)
          .catch(function (e) { setDebug('db-midi', e.message); });
        closeAllMenus();
      });
      menu.appendChild(refresh);
    }
    // 标记当前选中
    syncMidiMenuSelection();
  }

  function applyMidiStatus(status) {
    if (typeof status.sequence === 'number') {
      if (status.sequence < _lastMidiSequence) return;
      _lastMidiSequence = status.sequence;
    }
    _selectedMidiPort = status.selected || null;
    var ports = status.available || [];
    if (JSON.stringify(ports) !== JSON.stringify(_midiPorts)) setMidiPorts(ports);
    syncMidiMenuSelection();
    var opened = status.opened || [];
    var label = opened.length ? ('MIDI: ' + opened.join(', ')) : 'MIDI: 等待设备';
    if (status.error) label += ' · ' + status.error;
    setDebug('db-midi', label);
  }

  function selectMidiPort(port) {
    var requested = port || null;
    if (window.pywebview && window.pywebview.api.select_midi_port) {
      setDebug('db-midi', 'MIDI: 正在连接…');
      window.pywebview.api.select_midi_port(requested).then(function (result) {
        if (result && typeof result.sequence === 'number' && result.sequence < _lastMidiSequence) return;
        if (result && result.state) applyMidiStatus(result);
        if (!result || !result.ok) setDebug('db-midi', 'MIDI: ' + ((result && result.error) || '连接失败'));
      }).catch(function (error) { setDebug('db-midi', 'MIDI: ' + error.message); });
    } else if (ws && ws.readyState === WebSocket.OPEN) {
      _selectedMidiPort = requested;
      ws.send(JSON.stringify({ type: 'select_midi_port', port: requested }));
      syncMidiMenuSelection();
    }
  }

  function syncMidiMenuSelection() {
    var menu = document.getElementById('midi-menu');
    if (!menu) return;
    menu.querySelectorAll('.menu-option').forEach(function (opt) {
      if (opt.dataset.port === undefined) return;
      var val = opt.dataset.port || null;
      opt.classList.toggle('selected', val === _selectedMidiPort);
    });
  }

  // 暴露给 pywebview evaluate_js
  window.setMidiPorts = setMidiPorts;

  window.updateUI = updateUI;

  // ── 启动 ──────────────────────────────────────────

  async function initializeDesktop() {
    if (desktopInitializing || !(window.pywebview && window.pywebview.api)) return;
    desktopInitializing = true;
    try {
      var fontsOk = await window.ensureStaffFonts();
      var initial = await window.pywebview.api.frontend_ready({ fonts: !!fontsOk });
      var branding = document.querySelector('#branding > div');
      if (branding) branding.textContent = 'ModeCalc v' + initial.version;
      scaleRows = initial.library.rows || [];
      libraryLoaded = true;
      renderScaleSidebar();
      if (initial.state && initial.state.sequence) updateUI(initial.state);
      window.__modecalcReady = true;
      if (!fontsOk) setSettingsError('谱表字体加载失败，请重新安装完整应用');
    } catch (error) {
      desktopInitializing = false;
      setDebug('db-midi', '启动失败: ' + error.message);
      console.error('[desktop]', error);
    }
  }

  window.addEventListener('pywebviewready', initializeDesktop);
  initializeDesktop();
  if (location.hash !== '#desktop' && location.protocol !== 'file:') loadScaleLibrary();
  if (location.hash === '#desktop') setTimeout(function () {
    if (!window.__modecalcReady) setDebug('db-midi', '启动超时，请查看应用日志并重新启动');
  }, 15000);

  document.addEventListener('keydown', function (event) {
    if (event.metaKey && event.key === ',') {
      event.preventDefault();
      openSettings();
    }
  });

  var resizeTimer;
  if (typeof ResizeObserver === 'function') new ResizeObserver(function () {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(function () {
      createKeyboard('keyboard');
      createFretboard('fretboard');
      updateKeyboardHighlight();
    }, 80);
  }).observe(document.getElementById('keyboard'));

  bindAnalysisControls();
  updateSettingsButton();
  bindSettings();
  bindKeySelector();
  bindMenuBar();
  bindModal();
  connect();

})();
