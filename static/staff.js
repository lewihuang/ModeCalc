/**
 * VexFlow 5 大谱表渲染
 * 高音谱 (≥C4) + 低音谱 (<C4)，BRACE 连接
 */

(function () {
  'use strict';

  const C4_MIDI = 60;
  let fontsLoaded = false;

  // ── 字体加载 ──────────────────────────────────────
  //
  // Reuse the local CSS @font-face definitions on both file:// and loopback HTTP.
  // Recheck after bridge injection: WebKit can rebuild CSS-connected font faces.

  function initFonts() {
    // Load the CSS-connected faces themselves. WebKit may resolve a
    // FontFaceSet.load() request without loading an unused fallback face.
    // This also preserves Windows' existing file:// @font-face definitions.
    const faces = Array.from(document.fonts).filter(face => {
      const family = face.family.replace(/^["']|["']$/g, '');
      return family === 'Bravura' || family === 'Academico';
    });
    if (faces.length !== 2) return Promise.reject(new Error('缺少谱表字体定义'));
    return Promise.all(faces.map(face => face.load()));
  }

  function _dbFontOk(ok) {
    var el = document.getElementById('db-font');
    if (el) el.textContent = 'Font: ' + (ok ? 'OK' : 'FAIL');
  }

  function loadStaffFonts() {
    fontsLoaded = false;
    return initFonts().then((faces) => {
      if (faces.some(face => face.status !== 'loaded')) throw new Error("谱表字体未就绪");
      VexFlow.setFonts('Bravura', 'Academico');
      fontsLoaded = true;
      _dbFontOk(true);
      if (window._pendingStaffData) {
        renderStaff(window._pendingStaffData.notes, window._pendingStaffData.keySignature);
      }
      return true;
    }).catch(err => {
      console.warn('[staff] 字体加载失败，尝试无字体渲染:', err.message);
      fontsLoaded = true;
      _dbFontOk(false);
      if (window._pendingStaffData) {
        try { renderStaff(window._pendingStaffData.notes, window._pendingStaffData.keySignature); } catch (_) {}
      }
      return false;
    });
  }
  window.ensureStaffFonts = loadStaffFonts;
  window.modecalcFontsReady = loadStaffFonts();

  // ── 音符格式化 ────────────────────────────────────

  /**
   * 将 chord_engine note_info 转为 VexFlow key 格式
   * {name: 'C', octave: 4, accidental: null}  → 'c/4'
   * {name: 'C#', octave: 4, accidental: 'sharp'} → 'c#/4'  (VexFlow 用 # 后缀)
   * {name: 'Eb', octave: 4, accidental: 'flat'}  → 'eb/4'  (VexFlow 用 b 后缀)
   */
  function toVexKey(note) {
    // note.name 已包含临时升降号 (C#, Eb 等)，小写化即 VexFlow 格式
    return `${note.name.toLowerCase()}/${note.octave}`;
  }

  // ── 公开 API ──────────────────────────────────────

  /**
   * 渲染大谱表
   * @param {Array} activeNotes - chord_engine note_info 数组
   */
  function makeRestNote(factory, key = 'b/4') {
    const note = factory.StaveNote({ keys: [key], duration: 'wr' });
    note.setStyle({ fillStyle: 'transparent', strokeStyle: 'transparent' });
    return note;
  }

  window.renderStaff = function (activeNotes, keySignature) {
    keySignature = keySignature || 'C';
    if (!fontsLoaded) {
      window._pendingStaffData = { notes: activeNotes, keySignature: keySignature };
      return;
    }

    const container = document.getElementById('staff');
    if (!container) return;

    const STAFF_WIDTH = 360;
    const staffHeight = 156;

    const treble = activeNotes.filter(n => n.midi >= C4_MIDI);
    const bass = activeNotes.filter(n => n.midi < C4_MIDI);

    container.innerHTML = '';

    const factory = new VexFlow.Factory({
      renderer: { elementId: 'staff', width: STAFF_WIDTH, height: staffHeight * 2 + 24 },
    });

    // ── 创建声部 ─────────────────────────────────
    const trebleNotes = treble.length
      ? [factory.StaveNote({ keys: treble.map(toVexKey), duration: 'w', clef: 'treble' })]
      : [makeRestNote(factory, 'b/4')];

    const bassNotes = bass.length
      ? [factory.StaveNote({ keys: bass.map(toVexKey), duration: 'w', clef: 'bass' })]
      : [makeRestNote(factory, 'd/3')];

    // ── 手动添加临时升降号 ───────────────────────
    function addAccidentals(note, keys) {
      if (typeof factory.Accidental !== 'function') return;
      keys.forEach((key, i) => {
        const m = /^[a-g][#b]/.exec(key);
        if (m) {
          try { note.addModifier(factory.Accidental({ type: m[0][1] }), i); } catch (_) {}
        }
      });
    }

    if (treble.length) addAccidentals(trebleNotes[0], treble.map(toVexKey));
    if (bass.length) addAccidentals(bassNotes[0], bass.map(toVexKey));

    const trebleVoice = factory.Voice().addTickables(trebleNotes);
    const bassVoice = factory.Voice().addTickables(bassNotes);

    // ── 组装大谱表 ───────────────────────────────
    const system = factory.System({ x: 60, width: STAFF_WIDTH - 72, spaceBetweenStaves: 10 });
    const staveT = system.addStave({
      voices: [trebleVoice],
      options: { rightBarline: 'none', leftBarline: 'none' },
    }).addClef('treble');
    const staveB = system.addStave({
      voices: [bassVoice],
      options: { rightBarline: 'none', leftBarline: 'none' },
    }).addClef('bass');

    // ── 绘制调号 ─────────────────────────────────
    if (keySignature && keySignature !== 'C') {
      staveT.addKeySignature(keySignature, 'C');
      staveB.addKeySignature(keySignature, 'C');
    }

    // ── 排版（用 system.format() 处理 stave Y 定位 + voice 排版）──
    system.format();
    const NS_SHIFT = 84;

    // setXShift 只移 Tickable（音符），不传 modifier（升降号）。
    // modifier 位置用 getAbsoluteX() → 排除 xShift。需单独偏移。
    function shiftTickable(t, shift) {
      if (typeof t.setXShift === 'function') {
        t.setXShift(t.getXShift() + shift);
      }
      if (typeof t.getModifiers === 'function') {
        t.getModifiers().forEach(mod => {
          // Modifier.Position.LEFT === 1，公式: setXShift(V) → x_shift = -V
          if (mod.position === 1 && typeof mod.setXShift === 'function') {
            const cur = mod.getXShift();
            mod.setXShift(-(cur + shift));
          }
        });
      }
    }
    trebleVoice.getTickables().forEach(t => shiftTickable(t, NS_SHIFT));
    bassVoice.getTickables().forEach(t => shiftTickable(t, NS_SHIFT));

    // ── 手动 draw ───────────────────────────────
    const ctx = factory.getContext();
    staveT.draw();
    staveB.draw();
    trebleVoice.draw(ctx, staveT);
    bassVoice.draw(ctx, staveB);
  };

  // 启动时绘制空白大谱表（类似键盘的 createKeyboard）
  window.renderStaff([]);

})();
