// ── State ──────────────────────────────────────────────────
const srcMap = {a: 'camera', b: 'camera'};
const running = {a: false, b: false};
const dataLoaded = {a: false, b: false};
let pollTimer = null;
let aiTimer = null;
let provKeys = {};
try { provKeys = window._INIT.provKeys || {}; } catch(e) {}
let curProv = (window._INIT && window._INIT.provider) || 'anthropic';

// ── Toast ──────────────────────────────────────────────────
function toast(msg, type='ok', dur=3000) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = `toast ${type} show`;
  setTimeout(() => el.classList.remove('show'), dur);
}

// ── Source tabs ────────────────────────────────────────────
function setSrc(which, src) {
  srcMap[which] = src;
  const ALIAS = {camera:'cam', video:'vid', c3d:'c3d'};
  const prefix = which === 'a' ? 't' : 't';
  ['cam','vid','c3d'].forEach(s => {
    const btn = document.getElementById(`${prefix}${which}-${s}`);
    if(btn) btn.classList.toggle('active', ALIAS[src] === s);
    const el = document.getElementById(`${which}-${s}-opts`);
    if(el) el.style.display = ALIAS[src] === s ? (s==='cam'?'flex':'block') : 'none';
    if(el && s === 'cam') el.style.display = ALIAS[src] === s ? 'flex' : 'none';
    if(el && s !== 'cam') el.style.display = ALIAS[src] === s ? 'block' : 'none';
  });
  
  fetch('/api/set_source', {
    method:'POST', 
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({
      which, 
      source: src,
      camera_idx: parseInt(document.getElementById(`${which}-cam-idx`).value)||0
    })
  });
}

// ── 数据槽 & 分析控制 ──────────────────────────────────────
function updateSideControls(which, loaded, isRunning, nFrames, durSec) {
  const loadBtn = document.getElementById(`${which}-load`);
  const unloadBtn = document.getElementById(`${which}-unload`);
  const runRow = document.getElementById(`${which}-run-row`);
  const startBtn = document.getElementById(`${which}-start`);
  const stopBtn = document.getElementById(`${which}-stop`);
  const info = document.getElementById(`${which}-data-info`);

  if(loadBtn) loadBtn.style.display = loaded ? 'none' : '';
  if(unloadBtn) unloadBtn.style.display = loaded ? '' : 'none';
  if(runRow) runRow.style.display = loaded ? 'flex' : 'none';
  if(startBtn) startBtn.style.display = isRunning ? 'none' : '';
  if(stopBtn) stopBtn.style.display = isRunning ? '' : 'none';
  if(info) info.style.display = loaded ? 'block' : 'none';
  
  if(nFrames !== undefined) {
    const fc = document.getElementById(`${which}-frame-count`);
    if(fc) fc.textContent = nFrames;
    const durEl = document.getElementById(`${which}-data-dur`);
    if(durEl) durEl.textContent = durSec !== undefined ? durSec.toFixed(1) : '0.0';
  }
}

async function loadData(which) {
  const src = srcMap[which];
  if(src === 'c3d') {
    const okBox = document.getElementById(`${which}-c3d-ok`);
    if(!okBox || !okBox.classList.contains('show')) {
      toast('⚠ 请先上传 C3D 文件', 'err'); 
      return;
    }
  }
  
  const camIdx = parseInt(document.getElementById(`${which}-cam-idx`).value) || 0;
  await fetch('/api/set_source', {
    method: 'POST', 
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({which, source: src, camera_idx: camIdx})
  });
  
  const r = await fetch('/api/load_data', {
    method: 'POST', 
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({which})
  });
  const d = await r.json();
  if(!d.ok) { toast('❌ ' + d.msg, 'err'); return; }
  
  dataLoaded[which] = true;
  updateSideControls(which, true, false, 0, 0);
  updatePill(which, 'idle', '已装载，待分析');
  toast(`侧${which.toUpperCase()} 数据槽已就绪`);
  if(!pollTimer) pollTimer = setInterval(pollStatus, 500);
}

async function unloadData(which) {
  if(running[which]) await stopSide(which);
  const r = await fetch('/api/unload_data', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({which})
  });
  const d = await r.json();
  if(!d.ok) { toast('❌ ' + d.msg, 'err'); return; }
  
  dataLoaded[which] = false;
  running[which] = false;
  updateSideControls(which, false, false);
  updatePill(which, 'idle', '就绪');
  toast(`侧${which.toUpperCase()} 数据已卸载`);
}

async function startSide(which) {
  const r = await fetch('/api/start', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({which})
  });
  const d = await r.json();
  if(!d.ok) { toast('❌ ' + d.msg, 'err'); return; }
  running[which] = true;
  updateSideControls(which, true, true);
  updatePill(which, 'live', '分析中...');
  if(!pollTimer) pollTimer = setInterval(pollStatus, 500);
}

async function stopSide(which) {
  await fetch('/api/stop', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({which})
  });
  running[which] = false;
  updateSideControls(which, dataLoaded[which], false);
  const fc = document.getElementById(`${which}-frame-count`);
  updatePill(which, 'idle', `已停止 · ${fc ? fc.textContent : '0'}帧`);
}

function updatePill(which, state, text) {
  const pill = document.getElementById(`pill-${which}`);
  const dot = document.getElementById(`dot-${which}`);
  const lbl = document.getElementById(`lbl-${which}`);
  
  if(!pill) return;
  
  pill.className = `side-pill ${which} ${state==='live'?'live':''}`;
  if(dot) dot.className = `dot ${state==='live'?'pulse':''}`;
  if(lbl) lbl.textContent = `侧${which.toUpperCase()} — ${text}`;
}

// ── Poll ───────────────────────────────────────────────────
let _tsScore = null;

async function pollStatus() {
  try {
    const r = await fetch('/api/status');
    const d = await r.json();
    updateSideUI('a', d.side_a);
    updateSideUI('b', d.side_b);
    updateComparison(d.comparison, d.side_a.detected, d.side_b.detected, _tsScore);
  } catch(e) {}
}

let _tsPollCount = 0;
async function pollTimeSeries() {
  try {
    const r = await fetch('/api/compare_ts');
    _tsScore = await r.json();
    _tsPollCount++;
    const rs = await fetch('/api/status'); 
    const ds = await rs.json();
    updateComparison(ds.comparison, ds.side_a.detected, ds.side_b.detected, _tsScore);
  } catch(e) {}
}
setInterval(pollTimeSeries, 2000);

function updateSideUI(which, s) {
  const wasLoaded = dataLoaded[which];
  dataLoaded[which] = s.data_loaded;
  running[which] = s.running;

  const nF = s.n_frames || 0;
  const dur = nF > 1 ? (nF / 10).toFixed(1) : '0.0';
  updateSideControls(which, s.data_loaded, s.running, nF, parseFloat(dur));

  const fpsEl = document.getElementById(`${which}-fps`);
  if(fpsEl) fpsEl.textContent = Math.round(s.fps) || 30;

  const nd = document.getElementById(`nd-${which}`);
  if(nd) nd.classList.toggle('show', s.running && !s.detected);

  if(s.running && s.detected) updatePill(which, 'detected', `检测中 ${s.fps.toFixed(0)}fps`);
  else if(s.running) updatePill(which, 'live', `分析中 ${s.fps.toFixed(0)}fps`);
  else if(s.data_loaded) updatePill(which, 'idle', `已装载 ${nF}帧`);

  updateJointMini(which, s.angles);
}

// ── Joint mini bars ────────────────────────────────────────
const GRADE_CLR = {
  excellent:'var(--green)',
  good:'var(--cyan)', 
  warning:'var(--amber)', 
  poor:'var(--red)'
};

function updateJointMini(which, angles) {
  const el = document.getElementById(`${which}-joints`);
  if(!el) return;
  
  if(!angles || !Object.keys(angles).length) {
    el.innerHTML = '<div style="color:var(--text-muted);font-size:0.85rem;text-align:center;padding:20px 0">等待检测...</div>';
    return;
  }
  
  el.innerHTML = Object.entries(angles).map(([k,v]) => {
    const pct = (v.angle/180*100).toFixed(1);
    const clr = which==='a' ? 'var(--cyan)' : 'var(--purple)';
    return `<div class="jm-row">
      <span class="jm-name">${v.cn_name}</span>
      <div class="jm-bar-bg"><div class="jm-fill" style="width:${pct}%;background:${clr};box-shadow:0 0 10px ${clr.replace(')', ', 0.5)')}"></div></div>
      <span class="jm-val" style="color:${clr}">${v.angle}°</span>
    </div>`;
  }).join('');
}

// ── Comparison ─────────────────────────────────────────────
function updateScoreRing(score) {
  const arc = document.getElementById('score-arc');
  if(!arc) return;
  const radius = 52;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;
  arc.style.strokeDashoffset = offset;
  
  const glow = score > 80 ? 'rgba(74,222,128,0.5)' :
               score > 60 ? 'rgba(56,189,248,0.5)' :
               score > 40 ? 'rgba(251,191,36,0.5)' :
                            'rgba(248,113,113,0.5)';
  arc.style.filter = `drop-shadow(0 0 6px ${glow})`;
}

function updateComparison(cmp, detA, detB, tsScore) {
  // 控制部位评分卡片显示
  const regionCard = document.getElementById('region-scores-card');
  if (regionCard) {
    // 仅在当时序数据可用且评分有效时显示
    const showRegion = tsScore && tsScore.ok && tsScore.region_scores && 
                       Object.values(tsScore.region_scores).some(r => r.joints_count > 0);
    regionCard.style.display = showRegion ? 'block' : 'none';
  }
  const arc = document.getElementById('score-arc');
  const num = document.getElementById('score-num');
  const badge = document.getElementById('grade-badge');
  const worst = document.getElementById('score-worst');
  const modeEl = document.getElementById('cmp-mode');
  const barsEl = document.getElementById('cmp-bars');
  
  if(!num) return;

  if(!detA || !detB) {
    if(arc) arc.style.strokeDashoffset = 326.73;
    num.textContent = '—';
    if(badge) {
      badge.className = 'badge-poor';
      badge.textContent = '等待双侧数据';
    }
    if(worst) worst.textContent = '两侧均开始分析后显示对比评分';
    if(modeEl) modeEl.textContent = '';
    if(barsEl) barsEl.innerHTML = '<div style="color:var(--text-muted);font-size:0.85rem;text-align:center;padding:40px 0">等待双侧数据...</div>';
    return;
  }

  const tsReady = tsScore && tsScore.ok && tsScore.overall_score > 0;
  const sc = tsReady ? tsScore.overall_score : (cmp ? cmp.overall_score : 0);
  const isTsMode = tsReady;

  updateScoreRing(sc);
  num.textContent = Math.round(sc);
  
  let gradeClass, label;
  if(sc >= 85) { gradeClass = 'badge-excellent'; label = '高度相似'; }
  else if(sc >= 70) { gradeClass = 'badge-good'; label = '比较接近'; }
  else if(sc >= 50) { gradeClass = 'badge-warning'; label = '差距明显'; }
  else { gradeClass = 'badge-poor'; label = '差距较大'; }
  
  if(badge) {
    badge.className = gradeClass;
    badge.textContent = label;
  }

  if(modeEl) {
    if(isTsMode) {
      const nA = tsScore.n_a, nB = tsScore.n_b;
      modeEl.innerHTML = `<span style="color:var(--cyan);font-size:0.8rem">📈 时序拟合 (A:${nA}帧 B:${nB}帧)</span>`;
    } else {
      modeEl.innerHTML = `<span style="color:var(--text-muted);font-size:0.8rem">⏱ 积累中，当前实时帧对比</span>`;
    }
  }

  if(!barsEl) return;

  if(isTsMode) {
    const tjoints = tsScore.joints || {};
    const sorted = Object.values(tjoints).sort((a,b) => a.score - b.score);
    
    if(worst) {
      worst.textContent = sorted.length ? '最差: ' + sorted.slice(0,2).map(j => {
        const pd = j.peak_diff;
        return pd && Math.abs(pd.diff)>=5 ? `${j.cn_name} ${pd.t_label}A${pd.direction}${Math.abs(pd.diff)}°` : `${j.cn_name}(${j.score})`;
      }).join(' / ') : '各关节拟合良好';
    }
    
    barsEl.innerHTML = Object.entries(tjoints).sort((a,b) => a[1].score - b[1].score).map(([k, c]) => {
      const clr = GRADE_CLR[c.grade] || 'var(--text-muted)';
      const scorePct = Math.min(100, c.score).toFixed(1);
      const scaleLabel = c.scale && Math.abs(c.scale - 1.0) > 0.08 ? 
        `<span style="color:var(--amber);font-size:0.7rem;margin-left:6px">${c.scale < 1 ? `▶${(1/c.scale).toFixed(2)}×快` : `▷${c.scale.toFixed(2)}×慢`}</span>` : '';
      const peakLabel = (c.peak_diff && Math.abs(c.peak_diff.diff) >= 5) ? 
        `<div style="font-size:0.75rem;color:var(--text-muted);margin-top:4px;padding-left:4px">${c.peak_diff.t_label} A${c.peak_diff.direction}${Math.abs(c.peak_diff.diff)}° (A:${c.peak_diff.mean_a}° B:${c.peak_diff.mean_b}°)</div>` : '';
      
      return `<div class="cmp-row">
        <div class="cmp-hdr">
          <span class="cmp-name">${c.cn_name}${scaleLabel}</span>
          <span class="cmp-vals" style="color:${clr}">
            <span title="DTW形态分" style="font-size:0.75rem;margin-right:8px">DTW=${c.dtw_score!=null?Math.round(c.dtw_score):'—'}</span>
            <span title="RMSD角度误差" style="font-size:0.75rem;margin-right:8px">±${c.rmsd}°</span>
            <span style="font-weight:700">${c.score}</span>
          </span>
        </div>
        <div class="cmp-bar-bg" title="综合得分">
          <div class="cmp-bar-a" style="width:${scorePct}%;background:${clr}"></div>
        </div>
        ${peakLabel}
      </div>`;
    }).join('');
    // 部位相关性评分展示（v3.1新增）
    const regionPanel = document.getElementById('region-scores-panel');
    if (regionPanel && tsScore.region_scores) {
      const regions = [
        {key: 'upper', icon: '💪', name: '上身', desc: '肩/肘/腕动作一致性'},
        {key: 'core',  icon: '⭕', name: '核心', desc: '躯干稳定性'},
        {key: 'lower', icon: '🦵', name: '下肢', desc: '髋/膝/踝节奏控制'}
      ];
      
      regionPanel.innerHTML = regions.map(r => {
        const data = tsScore.region_scores[r.key];
        if (!data || data.joints_count === 0) return '';
        
        const score = data.score;
        const barColor = score >= 80 ? 'var(--green)' : 
                        score >= 60 ? 'var(--cyan)' : 
                        score >= 45 ? 'var(--amber)' : 'var(--red)';
        
        return `
        <div style="margin-bottom:12px;padding:10px;background:rgba(15,23,42,0.4);border-radius:8px;border-left:3px solid ${barColor};">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
            <div style="display:flex;align-items:center;gap:8px;">
              <span style="font-size:1.2rem;">${r.icon}</span>
              <div>
                <div style="font-weight:600;color:var(--text-primary);font-size:0.9rem;">${r.name}相关性</div>
                <div style="font-size:0.75rem;color:var(--text-muted);">${r.desc} · ${data.joints_count}关节</div>
              </div>
            </div>
            <div style="text-align:right;">
              <div style="font-size:1.25rem;font-weight:700;color:${barColor};font-family:var(--mono);">${Math.round(score)}</div>
              <div style="font-size:0.7rem;color:var(--text-muted);">r=${data.avg_r}</div>
            </div>
          </div>
          <div style="height:6px;background:rgba(255,255,255,0.05);border-radius:3px;overflow:hidden;">
            <div style="width:${score}%;height:100%;background:${barColor};box-shadow:0 0 8px ${barColor.replace(')', ', 0.4)')};transition:width 0.6s cubic-bezier(0.4,0,0.2,1);"></div>
          </div>
          <div style="margin-top:4px;font-size:0.75rem;color:var(--text-muted);text-align:right;">
            权重占比 60%
          </div>
        </div>`;
      }).join('');
      
      // 添加练习重点建议
      const weakest = regions.map(r => ({...r, ...tsScore.region_scores[r.key]}))
        .filter(r => r.joints_count > 0)
        .sort((a,b) => a.score - b.score)[0];
        
      if (weakest && weakest.score < 70) {
        regionPanel.innerHTML += `
        <div style="margin-top:12px;padding:10px;background:rgba(251,191,36,0.1);border:1px solid rgba(251,191,36,0.3);border-radius:8px;font-size:0.85rem;color:var(--amber);">
          <strong>💡 练习重点建议：</strong>${weakest.name}相关性评分较低(${Math.round(weakest.score)}分)，建议优先强化${weakest.desc.replace(/\/.*$/, '')}动作的时序一致性训练。
        </div>`;
      }
    }
  } else {
    if(!cmp) {
      if(worst) worst.textContent = '等待历史数据积累...';
      barsEl.innerHTML = '<div style="color:var(--text-muted);font-size:0.85rem;text-align:center;padding:40px 0">积累中...</div>';
    } else {
      const joints = cmp.joints || {};
      const top2 = Object.values(joints).sort((a,b) => b.deviation - a.deviation).slice(0,2);
      if(worst) worst.textContent = top2.length ? '偏差最大: '+top2.map(j=>`${j.cn_name}(${j.deviation}°)`).join('、') : '各关节偏差正常';
      
      barsEl.innerHTML = Object.entries(joints).map(([k,c]) => {
        const aPct = (c.current/180*100).toFixed(1);
        const bPct = (c.standard/180*100).toFixed(1);
        const clr = GRADE_CLR[c.grade] || 'var(--text-muted)';
        return `<div class="cmp-row">
          <div class="cmp-hdr">
            <span class="cmp-name">${c.cn_name}</span>
            <span class="cmp-vals" style="color:${clr}">
              <span style="color:var(--cyan)">${c.current}°</span>
              vs <span style="color:var(--purple)">${c.standard}°</span>
              <span style="margin-left:6px">${c.deviation>0?'+':''}${c.deviation}°</span>
            </span>
          </div>
          <div class="cmp-bar-bg">
            <div class="cmp-bar-a" style="width:${aPct}%;background:${clr}"></div>
            <div class="cmp-bar-ref" style="left:${bPct}%"></div>
          </div>
        </div>`;
      }).join('');
    }
  }
  updateSymmetry();
}

async function updateSymmetry() {
  try {
    const r = await fetch('/api/status');
    const d = await r.json();
    const sa = d.side_a.symmetry || {};
    const sb = d.side_b.symmetry || {};
    const el = document.getElementById('sym-cmp');
    const keys = new Set([...Object.keys(sa), ...Object.keys(sb)]);
    
    if(!keys.size) {
      if(el) el.innerHTML = '<div style="color:var(--text-muted);font-size:0.85rem;padding:20px 0;text-align:center">等待数据...</div>';
      return;
    }
    
    const html = [...keys].map(n => {
      const a = sa[n];
      const b = sb[n];
      return `<div class="sym-row">
        <span class="sym-n">${n}</span>
        <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
          ${a?`<span class="sym-a">${a.left}°/${a.right}°</span><span class="${a.symmetric?'sym-ok':'sym-warn'}">${a.symmetric?'✓':'⚠'}</span>`:'<span class="sym-a">—</span>'}
          ${b?`<span class="sym-b">${b.left}°/${b.right}°</span><span class="${b.symmetric?'sym-ok':'sym-warn'}">${b.symmetric?'✓':'⚠'}</span>`:'<span class="sym-b">—</span>'}
        </div>
      </div>`;
    }).join('');
    
    if(el) el.innerHTML = html;
  } catch(e) {}
}

// ── Upload video ───────────────────────────────────────────
async function uploadVideo(which, inp) {
  const file = inp.files[0];
  if(!file) return;
  const fd = new FormData();
  fd.append('file', file);
  fd.append('which', which);
  const r = await fetch('/api/upload_video', {method:'POST', body:fd});
  const d = await r.json();
  if(d.ok) {
    const nameEl = document.getElementById(`${which}-vid-name`);
    if(nameEl) nameEl.textContent = `${d.filename} (${d.n_frames}帧)`;
    toast(`✅ 视频已加载`);
    // 注意：不修改任何视频比例相关样式
  } else toast('❌ '+d.msg, 'err');
}

// ── Upload C3D ─────────────────────────────────────────────
function dropC3D(e, which) { 
  e.preventDefault(); 
  const zone = document.getElementById(`${which}-c3d-zone`);
  if(zone) zone.classList.remove('over');
  if(e.dataTransfer.files[0]) uploadC3D(which, e.dataTransfer.files[0]);
}

function toggleCustomMap(which) {
  const el = document.getElementById(`${which}-custom-map`);
  if(el) el.style.display = el.style.display==='none'?'block':'none';
}

async function uploadC3D(which, file) {
  if(!file) return;
  const okBox = document.getElementById(`${which}-c3d-ok`);
  const errBox = document.getElementById(`${which}-c3d-err`);
  
  if(okBox) {
    okBox.style.display = 'block';
    okBox.innerHTML = '⏳ 加载中...';
  }
  if(errBox) errBox.style.display = 'none';
  
  const fd = new FormData();
  fd.append('file', file);
  fd.append('which', which);
  fd.append('preset', document.getElementById(`${which}-c3d-preset`).value);
  const cm = document.getElementById(`${which}-custom-map`);
  if(cm && cm.value.trim()) fd.append('custom_map', cm.value.trim());
  
  const r = await fetch('/api/upload_c3d', {method:'POST', body:fd});
  const d = await r.json();
  
  if(d.ok) {
    if(okBox) {
      okBox.innerHTML = `✅ <strong>${d.filename}</strong> 加载成功<br>帧数:${d.n_frames} | 采样率:${d.fps}Hz<br>关节:${d.loaded_joints.join('、')}${d.missing_joints.length?`<br>⚠ 缺失:${d.missing_joints.join('、')}`:''}`;
      okBox.className = 'c3d-ok show';
    }
    const clearBtn = document.getElementById(`${which}-c3d-clear`);
    if(clearBtn) clearBtn.disabled = false;
    toast(`✅ 侧${which.toUpperCase()} C3D 加载成功`);
  } else {
    if(okBox) okBox.style.display = 'none';
    if(errBox) {
      errBox.innerHTML = '❌ '+d.msg;
      errBox.style.display = 'block';
    }
    toast('❌ 加载失败', 'err');
  }
}

async function clearC3D(which) {
  await fetch('/api/clear_c3d', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({which})
  });
  const okBox = document.getElementById(`${which}-c3d-ok`);
  const errBox = document.getElementById(`${which}-c3d-err`);
  const clearBtn = document.getElementById(`${which}-c3d-clear`);
  const fileInp = document.getElementById(`${which}-c3d-file`);
  
  if(okBox) okBox.style.display = 'none';
  if(errBox) errBox.style.display = 'none';
  if(clearBtn) clearBtn.disabled = true;
  if(fileInp) fileInp.value = '';
  toast('已清除');
}

// ── AI ─────────────────────────────────────────────────────
const PINFO = {
  anthropic:{hint:'Key: <a href="https://console.anthropic.com" target="_blank" style="color:var(--cyan)">console.anthropic.com</a>', ph:'sk-ant-...', dm:'claude-sonnet-4-20250514', url:false},
  deepseek: {hint:'Key: <a href="https://platform.deepseek.com" target="_blank" style="color:var(--cyan)">platform.deepseek.com</a>', ph:'sk-...', dm:'deepseek-chat', url:false},
  openai:   {hint:'Key: <a href="https://platform.openai.com/api-keys" target="_blank" style="color:var(--cyan)">platform.openai.com</a>', ph:'sk-...', dm:'gpt-4o', url:false},
  qwen:     {hint:'Key: <a href="https://dashscope.console.aliyun.com" target="_blank" style="color:var(--cyan)">阿里云百炼</a>', ph:'sk-...', dm:'qwen-plus', url:false},
  doubao:   {hint:'Key: <a href="https://console.volcengine.com/ark" target="_blank" style="color:var(--cyan)">火山引擎ARK</a>', ph:'ARK API Key...', dm:'doubao-1-5-pro-32k-250115', url:false},
  ollama:   {hint:'本地无需Key，确保Ollama已启动 <a href="https://ollama.com" target="_blank" style="color:var(--cyan)">ollama.com</a>', ph:'（无需填写）', dm:'qwen2.5:7b', url:true},
};

function setProv(p) {
  curProv = p;
  document.querySelectorAll('.pbtn').forEach(b => b.classList.remove('active'));
  const btn = document.getElementById(`pb-${p}`);
  if(btn) btn.classList.add('active');
  
  const info = PINFO[p] || PINFO.anthropic;
  const keyInp = document.getElementById('api-key-inp');
  const modelInp = document.getElementById('model-inp');
  const hintEl = document.getElementById('prov-hint');
  const urlRow = document.getElementById('url-row');
  
  if(keyInp) {
    keyInp.placeholder = info.ph;
    keyInp.value = provKeys[p] || '';
  }
  if(modelInp) modelInp.placeholder = info.dm;
  if(hintEl) hintEl.innerHTML = info.hint;
  if(urlRow) urlRow.style.display = info.url ? 'flex' : 'none';
  
  fetch('/api/set_provider', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({
      provider:p,
      model: modelInp ? modelInp.value.trim() : '',
      base_url: document.getElementById('url-inp')?.value || ''
    })
  });
}

function debounceAI() {
  clearTimeout(aiTimer);
  aiTimer = setTimeout(async() => {
    const key = document.getElementById('api-key-inp')?.value.trim() || '';
    const model = document.getElementById('model-inp')?.value.trim() || '';
    const base_url = document.getElementById('url-inp')?.value || '';
    provKeys[curProv] = key;
    
    await fetch('/api/set_apikey', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({provider:curProv, api_key:key})
    });
    await fetch('/api/set_provider', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({provider:curProv, model, base_url})
    });
  }, 600);
}

async function getAdvice() {
  const btn = document.getElementById('advice-btn');
  const box = document.getElementById('advice-box');
  if(btn) btn.disabled = true;
  if(box) {
    box.innerHTML = '<div class="loading"><div class="spin"></div> AI 正在分析双人对比数据，请稍候...</div>';
  }
  
  const extra = document.getElementById('extra-ctx')?.value.trim() || '';
  const r = await fetch('/api/advice', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({extra})
  });
  const d = await r.json();
  
  if(btn) btn.disabled = false;
  if(d.ok) {
    if(box) box.textContent = d.advice;
    toast('✅ AI 建议已生成');
  } else if(box) {
    box.innerHTML = `<span style="color:var(--amber)">${d.msg}</span>`;
  }
}

function exportReport() { 
  window.location.href = '/api/export_report'; 
  toast('📊 下载中...'); 
}

async function installEzc3d() {
  const btn = document.getElementById('install-ezc3d-btn');
  const prog = document.getElementById('install-prog');
  const res = document.getElementById('install-res');
  
  if(btn) btn.disabled = true;
  if(prog) prog.style.display = 'flex';
  if(res) res.style.display = 'none';
  
  const r = await fetch('/api/install_ezc3d', {method:'POST'});
  const d = await r.json();
  
  if(prog) prog.style.display = 'none';
  if(res) {
    res.style.display = 'block';
    res.innerHTML = d.ok ? '<span style="color:var(--green)">✅ 安装成功，请重启程序</span>' : '<span style="color:var(--red)">❌ '+d.msg+'</span>';
  }
  if(!d.ok && btn) btn.disabled = false;
}

// ── Init ──────────────────────────────────────────────────
function showTab(tab) {
  document.getElementById('compare-page').style.display = tab==='compare' ? 'contents' : 'none';
  document.getElementById('analysis-page').style.display = tab==='analysis' ? 'flex' : 'none';
  document.getElementById('nav-compare').classList.toggle('active', tab==='compare');
  document.getElementById('nav-analysis').classList.toggle('active', tab==='analysis');
  if(tab==='analysis') anRefresh();
}

// ── Analysis State ─────────────────────────────────────────
let anSide='a', anJointFilter='all';
let anHistA=[], anHistB=[];
let anHasFramesA=false, anHasFramesB=false;
let tlIdx=0, tlPlaying=false, tlSpeed=1.0, tlRafId=null, tlLastMs=0, tlFpsSrc=10;
let anViewMode='raw', anAligned=null, _alignedFetching=false;

const JOINT_GROUPS={
  all:  ['left_elbow','right_elbow','left_shoulder','right_shoulder','left_hip','right_hip',
         'left_knee','right_knee','left_ankle','right_ankle','left_wrist','right_wrist'],
  arm:  ['left_elbow','right_elbow','left_shoulder','right_shoulder','left_wrist','right_wrist'],
  leg:  ['left_knee','right_knee','left_ankle','right_ankle','left_hip','right_hip'],
  torso:['left_shoulder','right_shoulder','left_hip','right_hip'],
};

const CN={
  left_elbow:'左肘', right_elbow:'右肘', left_shoulder:'左肩', right_shoulder:'右肩',
  left_hip:'左髋', right_hip:'右髋', left_knee:'左膝', right_knee:'右膝',
  left_ankle:'左踝', right_ankle:'右踝', left_wrist:'左腕', right_wrist:'右腕'
};

const JCOLORS=['#38bdf8','#a78bfa','#4ade80','#fbbf24','#f87171','#60a5fa',
               '#34d399','#e879f9','#22d3ee','#a3e635','#fb923c','#818cf8'];

const SKEL_CONN=[[11,13],[13,15],[15,17],[15,19],[17,19],[12,14],[14,16],[16,18],[16,20],[18,20],
 [11,12],[11,23],[12,24],[23,24],[23,25],[25,27],[27,29],[27,31],[29,31],
 [24,26],[26,28],[28,30],[28,32],[30,32]];

// ── Analysis Functions ─────────────────────────────────────
function anSetViewMode(mode) {
  anViewMode = mode;
  ['raw','aligned'].forEach(m => {
    const b = document.getElementById('vm-'+m);
    if(b) b.classList.toggle('active', m===mode);
  });
  const sb = document.getElementById('side-btns');
  if(sb) sb.style.opacity = mode==='aligned' ? '0.4' : '1';
  const ai = document.getElementById('aligned-info');
  if(ai) ai.style.display = mode==='aligned' ? 'flex' : 'none';
  
  if(mode === 'aligned') {
    const st = document.getElementById('ai-status');
    if(st) st.textContent = '正在计算对齐...';
    fetchAligned();
  } else {
    anDraw();
  }
}

async function fetchAligned() {
  if(_alignedFetching) return;
  _alignedFetching = true;
  const status = document.getElementById('ai-status');
  if(status) status.textContent = '正在计算对齐...';
  
  try {
    const r = await fetch('/api/aligned_series');
    anAligned = await r.json();
    if(!anAligned.ok) {
      if(status) status.textContent = anAligned.reason || '数据不足';
      _alignedFetching = false;
      return;
    }
    
    const g = anAligned.global_scale || 1;
    const off = ((anAligned.global_offset_frac || 0) * 100).toFixed(1);
    const bend = ((anAligned.global_b_end_frac || 1) * 100).toFixed(1);
    const sFmt = g < 1 ? `A比B快${(1/g).toFixed(2)}×` : g > 1 ? `A比B慢${g.toFixed(2)}×` : '速度相近';
    
    const scaleEl = document.getElementById('ai-scale');
    const offsetEl = document.getElementById('ai-offset');
    const durEl = document.getElementById('ai-dur');
    
    if(scaleEl) scaleEl.textContent = '速度比: ' + sFmt;
    if(offsetEl) offsetEl.textContent = `B对齐窗口: ${off}%–${bend}%`;
    if(durEl) durEl.textContent = `A:${anAligned.dur_a}s(${anAligned.n_a}帧)  B:${anAligned.dur_b}s(${anAligned.n_b}帧)`;
    if(status) status.textContent = '✓ 对齐完成';
    
    initLegendCheckboxes();
    anDraw();
  } catch(e) {
    if(status) status.textContent = '计算失败: ' + e.message;
  } finally {
    _alignedFetching = false;
  }
}

function anSetSide(s){
  anSide=s;
  ['a','b','ab'].forEach(x=>{
    const btn = document.getElementById('an-btn-'+x);
    if(btn) btn.classList.toggle('active', x===s);
  });
  anRefresh();
}

function anFilterJoint(f){
  anJointFilter=f;
  ['all','arm','leg','torso'].forEach(x=>{
    const btn = document.getElementById('jf-'+x);
    if(btn) btn.classList.toggle('active', x===f);
  });
  initLegendCheckboxes();
  anDraw();
}

async function anRefresh(){
  if(anSide==='a' || anSide==='ab'){
    const r=await fetch('/api/history?which=a&limit=1800');
    const d=await r.json();
    anHistA=d.data||[];
    anHasFramesA=!!d.has_frames;
  }
  if(anSide==='b' || anSide==='ab'){
    const r=await fetch('/api/history?which=b&limit=1800');
    const d=await r.json();
    anHistB=d.data||[];
    anHasFramesB=!!d.has_frames;
  }
  const ref=anHistMain();
  if(ref.length>1) tlFpsSrc=(ref.length-1)/(ref[ref.length-1].t-ref[0].t+0.001);
  renderWaveform();
  initLegendCheckboxes();
  if(anViewMode === 'aligned') {
    fetchAligned();
  } else {
    if(!tlPlaying) tlGoTo(anHistMain().length-1);
    anDraw();
  }
}

function anHistMain(){ return anSide==='b'?anHistB:anHistA; }
function anHasVideo(){ return anSide==='b'?anHasFramesB:anHasFramesA; }

async function anClearHistory(){
  tlPause();
  await fetch('/api/clear_history', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({which:'both'})
  });
  anHistA=[]; anHistB=[]; anHasFramesA=false; anHasFramesB=false;
  tlIdx=0; anDraw(); updateTimeline();
  ['a','b'].forEach(w => {
    const el = document.getElementById(`${w}-frame-count`);
    if(el) el.textContent = '0';
    const d = document.getElementById(`${w}-data-dur`);
    if(d) d.textContent = '0.0';
  });
  toast('历史数据已清除');
}

// ── Timeline ───────────────────────────────────────────────
function tlGoTo(idx){
  if(anViewMode === 'aligned' && anAligned && anAligned.ok) {
    tlIdx = Math.max(0, Math.min(idx, anAligned.n_pts - 1));
    updateAlignedTimeline();
    anDrawFrame();
    return;
  }
  const hist=anHistMain();
  tlIdx = hist.length ? Math.max(0, Math.min(idx, hist.length-1)) : 0;
  updateTimeline();
  anDrawFrame();
}

function tlStep(d){ tlGoTo(Math.round(tlIdx)+d); }

function tlTogglePlay(){ tlPlaying ? tlPause() : tlPlay(); }

function tlPlay(){
  if(!anHistMain().length) return;
  tlPlaying=true;
  const btn = document.getElementById('tl-playbtn');
  if(btn) {
    btn.textContent='⏸';
    btn.style.background='var(--purple)';
    btn.style.boxShadow='0 4px 15px rgba(167,139,250,0.4)';
  }
  tlLastMs=performance.now();
  tlRafId=requestAnimationFrame(tlTick);
}

function tlPause(){
  tlPlaying=false;
  const btn = document.getElementById('tl-playbtn');
  if(btn) {
    btn.textContent='▶';
    btn.style.background='var(--cyan)';
    btn.style.boxShadow='0 4px 15px rgba(56,189,248,0.4)';
  }
  if(tlRafId){cancelAnimationFrame(tlRafId);tlRafId=null;}
}

function tlTick(now){
  if(!tlPlaying) return;
  const elapsed=(now-tlLastMs)/1000;
  tlLastMs=now;
  const maxIdx = (anViewMode==='aligned' && anAligned && anAligned.ok) ? anAligned.n_pts - 1 : anHistMain().length - 1;
  if(maxIdx < 0) { tlPause(); return; }
  const playFps = (anViewMode==='aligned') ? 30 : tlFpsSrc;
  tlIdx += elapsed * tlSpeed * playFps;
  
  const loopCheck = document.getElementById('tl-loop');
  if(tlIdx >= maxIdx) {
    if(loopCheck && loopCheck.checked) { tlIdx=0; }
    else { tlIdx=maxIdx; tlPause(); }
  }
  
  if(anViewMode==='aligned') updateAlignedTimeline();
  else updateTimeline();
  anDrawFrame();
  tlRafId=requestAnimationFrame(tlTick);
}

function tlSetSpeed(s){
  tlSpeed=s;
  document.querySelectorAll('.spd-btn').forEach(b=>b.classList.remove('active'));
  const el = document.getElementById('spd-'+s);
  if(el) {
    el.classList.add('active');
    el.style.background = 'var(--cyan)';
    el.style.color = '#fff';
    el.style.borderRadius = '4px';
    el.style.fontWeight = '600';
  }
  [0.5,1,2].forEach(sp => {
    if(sp !== s) {
      const btn = document.getElementById('spd-'+sp);
      if(btn) {
        btn.style.background = 'transparent';
        btn.style.color = 'var(--text-muted)';
        btn.style.fontWeight = '400';
      }
    }
  });
}

function renderWaveform() {
  const canvas = document.getElementById('tl-waveform');
  if(!canvas) return;
  const rect = canvas.getBoundingClientRect();
  if(rect.width < 10) return;
  const dpr = window.devicePixelRatio || 1;
  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);
  const W=rect.width, H=rect.height;
  
  ctx.fillStyle = 'rgba(15,23,42,0.4)';
  ctx.fillRect(0,0,W,H);
  
  const hist = anHistMain();
  if(!hist.length) return;
  
  const energies = hist.map((h, i) => {
    if(i===0) return 0;
    const prev=hist[i-1].angles, cur=h.angles;
    const keys=Object.keys(cur).filter(k => prev[k]!=null);
    if(!keys.length) return 0;
    return keys.reduce((s,k)=>s+Math.abs(cur[k]-prev[k]),0)/keys.length;
  });
  const maxE = Math.max(...energies,1);
  
  const joints = JOINT_GROUPS[anJointFilter];
  const n = hist.length;
  joints.forEach((key,ji)=>{
    const color=JCOLORS[ji%JCOLORS.length];
    ctx.beginPath();
    ctx.strokeStyle=color;
    ctx.lineWidth=1.5;
    ctx.globalAlpha=0.6;
    let first=true;
    hist.forEach((h,i)=>{
      const ang=h.angles[key];
      if(ang==null){first=true;return;}
      const x=(i/(n-1))*W;
      const y=H-(ang/180)*H;
      first?ctx.moveTo(x,y):ctx.lineTo(x,y);
      first=false;
    });
    ctx.stroke();
  });
  ctx.globalAlpha=1;
  
  energies.forEach((e,i)=>{
    const x=(i/(n-1))*W;
    const barH=(e/maxE)*H*0.35;
    const alpha=Math.min(0.6, e/maxE*0.8+0.05);
    ctx.fillStyle=`rgba(56,189,248,${alpha})`;
    ctx.fillRect(x-0.5,H-barH,1.5,barH);
  });
}

function updateTimeline(){
  const hist=anHistMain(), n=hist.length;
  const idx=Math.min(Math.round(tlIdx),n-1);
  const t=(n&&idx>=0)?hist[idx].t:0, tot=n?hist[n-1].t:0;
  const pct=tot>0?(t/tot*100).toFixed(2):0;
  
  const fill=document.getElementById('tl-fill');
  const thumb=document.getElementById('tl-thumb');
  const curEl=document.getElementById('tl-cur');
  const totEl=document.getElementById('tl-total');
  const frameNum=document.getElementById('tl-frame-num');
  const frameTot=document.getElementById('tl-frame-tot');
  const ts=document.getElementById('frame-timestamp');
  const ph=document.getElementById('tl-playhead');
  
  if(fill) fill.style.width=pct+'%';
  if(thumb) thumb.style.left=pct+'%';
  if(curEl) curEl.textContent=t.toFixed(2)+'s';
  if(totEl) totEl.textContent=tot.toFixed(2)+'s';
  if(frameNum) frameNum.textContent=idx<0?0:idx;
  if(frameTot) frameTot.textContent=n?n-1:0;
  if(ts) ts.textContent=n?`#${idx<0?0:idx}  ${t.toFixed(2)}s`:'';
  if(ph) ph.style.left=pct+'%';
}

function updateAlignedTimeline(){
  if(!anAligned || !anAligned.ok) return;
  const n=anAligned.n_pts;
  const idx=Math.min(Math.round(tlIdx),n-1);
  const pct=(idx/(n-1)*100).toFixed(2);
  
  const fill=document.getElementById('tl-fill');
  const thumb=document.getElementById('tl-thumb');
  const curEl=document.getElementById('tl-cur');
  const totEl=document.getElementById('tl-total');
  const frameNum=document.getElementById('tl-frame-num');
  const frameTot=document.getElementById('tl-frame-tot');
  const ts=document.getElementById('frame-timestamp');
  const ph=document.getElementById('tl-playhead');
  
  if(fill) fill.style.width=pct+'%';
  if(thumb) thumb.style.left=pct+'%';
  if(curEl) curEl.textContent=(idx/(n-1)*100).toFixed(1)+'%';
  if(totEl) totEl.textContent='100%';
  if(frameNum) frameNum.textContent=idx;
  if(frameTot) frameTot.textContent=n-1;
  if(ts) ts.textContent=`#${idx}  ${(idx/(n-1)*100).toFixed(1)}%`;
  if(ph) ph.style.left=pct+'%';
}

// ── Timeline Interactions ──────────────────────────────────
let tlDragging=false;
function tlClickSeek(e){
  const track=document.getElementById('tl-track');
  if(!track) return;
  const rect=track.getBoundingClientRect();
  const pct=Math.max(0,Math.min(1,(e.clientX-rect.left)/rect.width));
  const maxIdx=(anViewMode==='aligned'&&anAligned&&anAligned.ok)?anAligned.n_pts-1:anHistMain().length-1;
  if(maxIdx<0)return;
  tlGoTo(Math.round(pct*maxIdx));
}

function tlDragStart(e){
  tlDragging=true;
  e.preventDefault();
  document.addEventListener('mousemove',tlDragMove);
  document.addEventListener('mouseup',tlDragEnd);
}

function tlDragMove(e){
  if(!tlDragging)return;
  const track=document.getElementById('tl-track');
  if(!track)return;
  const rect=track.getBoundingClientRect();
  const pct=Math.max(0,Math.min(1,(e.clientX-rect.left)/rect.width));
  const maxIdx=(anViewMode==='aligned'&&anAligned&&anAligned.ok)?anAligned.n_pts-1:anHistMain().length-1;
  if(maxIdx<0)return;
  tlIdx=pct*maxIdx;
  if(anViewMode==='aligned')updateAlignedTimeline();
  else updateTimeline();
  anDrawFrame();
}

function tlDragEnd(){
  tlDragging=false;
  document.removeEventListener('mousemove',tlDragMove);
  document.removeEventListener('mouseup',tlDragEnd);
}

function tlHover(e){
  const track=document.getElementById('tl-track');
  const tt=document.getElementById('tl-tooltip');
  if(!track||!tt)return;
  const rect=track.getBoundingClientRect();
  const pct=Math.max(0,Math.min(1,(e.clientX-rect.left)/rect.width));
  const hist=anHistMain();
  if(!hist.length){tt.style.display='none';return;}
  
  let t, idx;
  if(anViewMode==='aligned'&&anAligned&&anAligned.ok){
    idx=Math.round(pct*(anAligned.n_pts-1));
    t=(idx/(anAligned.n_pts-1)*100).toFixed(1)+'%';
  }else{
    idx=Math.round(pct*(hist.length-1));
    t=(hist[idx]?hist[idx].t:0).toFixed(2)+'s';
  }
  
  tt.style.display='block';
  tt.style.left=(pct*100)+'%';
  const timeEl=document.getElementById('tl-tt-time');
  if(timeEl)timeEl.textContent=t+'  #'+idx;
}

function tlHoverEnd(){
  const tt=document.getElementById('tl-tooltip');
  if(tt)tt.style.display='none';
}

function chartClickSeek(e){
  const canvas=document.getElementById('chart-canvas');
  if(!canvas)return;
  const rect=canvas.getBoundingClientRect();
  const PAD_L=42, PAD_R=14;
  const cW=rect.width-PAD_L-PAD_R;
  const x=e.clientX-rect.left-PAD_L;
  const pct=Math.max(0,Math.min(1,x/cW));
  const maxIdx=(anViewMode==='aligned'&&anAligned&&anAligned.ok)?anAligned.n_pts-1:anHistMain().length-1;
  if(maxIdx<0)return;
  tlGoTo(Math.round(pct*maxIdx));
}

// ── Rendering ───────────────────────────────────────────────
function renderAlignedSkeleton(){
  const skelC=document.getElementById('skel-canvas');
  const vidC=document.getElementById('video-canvas');
  if(!skelC||!anAligned||!anAligned.ok)return;
  const W=skelC.width,H=skelC.height;
  const sCtx=skelC.getContext('2d');
  sCtx.clearRect(0,0,W,H);
  
  if(vidC){
    const vCtx=vidC.getContext('2d');
    vCtx.clearRect(0,0,vidC.width,vidC.height);
    vCtx.fillStyle='#0a0b0e';
    vCtx.fillRect(0,0,vidC.width,vidC.height);
    vCtx.strokeStyle='#1e2029';
    vCtx.lineWidth=1;
    for(let x=0;x<vidC.width;x+=36){vCtx.beginPath();vCtx.moveTo(x,0);vCtx.lineTo(x,vidC.height);vCtx.stroke();}
    for(let y=0;y<vidC.height;y+=36){vCtx.beginPath();vCtx.moveTo(0,y);vCtx.lineTo(vidC.width,y);vCtx.stroke();}
    vCtx.fillStyle='rgba(56,189,248,0.2)';
    vCtx.font='12px Inter';
    vCtx.textAlign='center';
    vCtx.fillText('对齐预览', vidC.width/2, vidC.height/2-6);
    vCtx.fillStyle='rgba(56,189,248,0.1)';
    vCtx.fillText('(原始视频帧不可用)', vidC.width/2, vidC.height/2+12);
    vCtx.textAlign='left';
  }
  
  const n=anAligned.n_pts;
  const idx=Math.min(Math.round(tlIdx),n-1);
  const lmA=anAligned.lm_a[idx];
  const lmB=anAligned.lm_b[idx];
  
  if(lmA&&lmA.length>=66)drawSkel(sCtx,lmA,'#38bdf8',W,H,0.92);
  if(lmB&&lmB.length>=66)drawSkel(sCtx,lmB,'#a78bfa',W,H,0.92);
  
  if((!lmA||lmA.length<66)&&(!lmB||lmB.length<66)){
    sCtx.fillStyle='#3a5878';
    sCtx.font='13px Inter';
    sCtx.textAlign='center';
    sCtx.fillText('无骨架数据 (需视频/摄像头输入)',W/2,H/2);
    sCtx.textAlign='left';
  }
}

function renderAlignedChart(){
  const canvas=document.getElementById('chart-canvas');
  if(!canvas)return;
  const rect=canvas.getBoundingClientRect();
  if(rect.width<10||rect.height<10)return;
  const dpr=window.devicePixelRatio||1;
  canvas.width=rect.width*dpr;
  canvas.height=rect.height*dpr;
  const ctx=canvas.getContext('2d');
  ctx.scale(dpr,dpr);
  const W=rect.width,H=rect.height;
  ctx.fillStyle='#0f1828';
  ctx.fillRect(0,0,W,H);
  const PAD={top:18,right:14,bottom:34,left:42};
  const cW=W-PAD.left-PAD.right,cH=H-PAD.top-PAD.bottom;
  
  if(!anAligned||!anAligned.ok){
    ctx.fillStyle='#3a5878';
    ctx.font='13px Inter';
    ctx.textAlign='center';
    ctx.fillText('对齐数据加载中...',W/2,H/2);
    ctx.textAlign='left';
    return;
  }
  
  const n=anAligned.n_pts;
  const joints=getVisibleJoints().filter(k=>anAligned.joints[k]);
  const win=parseInt(document.getElementById('smooth-range')?.value)||3;
  
  [0,30,60,90,120,150,180].forEach(y=>{
    const py=PAD.top+cH*(1-y/180);
    ctx.strokeStyle='#1e2029';
    ctx.lineWidth=1;
    ctx.beginPath();
    ctx.moveTo(PAD.left,py);
    ctx.lineTo(PAD.left+cW,py);
    ctx.stroke();
    ctx.fillStyle='#64748b';
    ctx.font='11px JetBrains Mono';
    ctx.fillText(y+'°',8,py+4);
  });
  
  [0,25,50,75,100].forEach(pct=>{
    const px=PAD.left+cW*pct/100;
    ctx.strokeStyle='#1e2029';
    ctx.beginPath();
    ctx.moveTo(px,PAD.top+cH);
    ctx.lineTo(px,PAD.top+cH+4);
    ctx.stroke();
    ctx.fillStyle='#64748b';
    ctx.font='11px JetBrains Mono';
    ctx.fillText(pct+'%',px-12,H-PAD.bottom+16);
  });
  
  joints.forEach((k,i)=>{
    const jd=anAligned.joints[k];
    const color=JCOLORS[JOINT_GROUPS['all'].indexOf(k)%JCOLORS.length];
    const drawLine=(vals,dash)=>{
      const sm=smooth(vals,win);
      ctx.beginPath();
      ctx.strokeStyle=color;
      ctx.lineWidth=2;
      ctx.setLineDash(dash);
      sm.forEach((v,ii)=>{
        const px=PAD.left+cW*ii/(n-1);
        const py=PAD.top+cH*(1-v/180);
        ii===0?ctx.moveTo(px,py):ctx.lineTo(px,py);
      });
      ctx.stroke();
      ctx.setLineDash([]);
    };
    if(jd.a)drawLine(jd.a,[]);
    if(jd.b)drawLine(jd.b,[5,3]);
  });
  
  const curIdx=Math.min(Math.round(tlIdx),n-1);
  const cx=PAD.left+cW*curIdx/(n-1);
  ctx.strokeStyle='rgba(255,255,255,0.3)';
  ctx.lineWidth=1.5;
  ctx.setLineDash([4,3]);
  ctx.beginPath();
  ctx.moveTo(cx,PAD.top);
  ctx.lineTo(cx,PAD.top+cH);
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.fillStyle='#fff';
  ctx.beginPath();
  ctx.arc(cx,PAD.top,5,0,Math.PI*2);
  ctx.fill();
  
  const pctLabel=(curIdx/(n-1)*100).toFixed(1)+'%';
  ctx.fillStyle='rgba(255,255,255,0.8)';
  ctx.font='bold 11px JetBrains Mono';
  ctx.fillText(pctLabel,Math.min(cx+6,PAD.left+cW-40),PAD.top+14);
  
  const ci=document.getElementById('chart-info');
  if(ci)ci.textContent=`已对齐 ${n}点 | A实线 B虚线`;
}

function renderAlignedJointTable(){
  const el=document.getElementById('an-joint-table');
  if(!el)return;
  if(!anAligned||!anAligned.ok){
    el.innerHTML='<div style="color:var(--text-muted)">等待对齐数据...</div>';
    return;
  }
  const idx=Math.min(Math.round(tlIdx),anAligned.n_pts-1);
  const joints=getVisibleJoints().filter(k=>anAligned.joints[k]);
  el.innerHTML=joints.map((k,i)=>{
    const jd=anAligned.joints[k];
    const va=jd.a?jd.a[idx]:null;
    const vb=jd.b?jd.b[idx]:null;
    const clr=JCOLORS[JOINT_GROUPS['all'].indexOf(k)%JCOLORS.length];
    const aS=va!=null?`<span style="color:var(--cyan);font-family:JetBrains Mono">${va.toFixed(1)}°</span>`:'<span style="color:var(--text-muted)">—</span>';
    const bS=vb!=null?`<span style="color:var(--purple);font-family:JetBrains Mono">${vb.toFixed(1)}°</span>`:'<span style="color:var(--text-muted)">—</span>';
    let diff='';
    if(va!=null&&vb!=null){
      const d=va-vb;
      const c=Math.abs(d)<5?'var(--green)':Math.abs(d)<15?'var(--cyan)':Math.abs(d)<30?'var(--amber)':'var(--red)';
      diff=`<span style="color:${c};margin-left:4px;font-family:JetBrains Mono">${d>=0?'+':''}${d.toFixed(1)}°</span>`;
    }
    return `<div style="display:flex;align-items:center;gap:6px;margin-bottom:4px;padding:4px;border-radius:4px;background:rgba(255,255,255,0.03)">
      <span style="width:8px;height:8px;border-radius:50%;background:${clr};flex-shrink:0"></span>
      <span style="width:40px;color:var(--text-muted);flex-shrink:0;font-size:0.8rem">${jd.cn_name}</span>
      ${aS}${bS}${diff}
    </div>`;
  }).join('');
}

const JOINT_B_IDX={
  left_elbow:13, right_elbow:14, left_shoulder:11, right_shoulder:12,
  left_hip:23, right_hip:24, left_knee:25, right_knee:26,
  left_ankle:27, right_ankle:28, left_wrist:15, right_wrist:16
};

function drawSkel(ctx,lm,color,W,H,alpha,anglesMap){
  if(!lm||lm.length<66)return;
  const pts=[];
  for(let i=0;i<lm.length;i+=2)pts.push([lm[i]*W,lm[i+1]*H]);
  
  ctx.globalAlpha=alpha;
  ctx.strokeStyle=color;
  ctx.lineWidth=3;
  ctx.lineCap='round';
  ctx.lineJoin='round';
  
  for(const [a,b]of SKEL_CONN){
    if(a<pts.length&&b<pts.length){
      ctx.beginPath();
      ctx.moveTo(pts[a][0],pts[a][1]);
      ctx.lineTo(pts[b][0],pts[b][1]);
      ctx.stroke();
    }
  }
  
  ctx.fillStyle=color;
  for(const [x,y]of pts){
    ctx.beginPath();
    ctx.arc(x,y,4,0,Math.PI*2);
    ctx.fill();
    ctx.beginPath();
    ctx.arc(x,y,8,0,Math.PI*2);
    ctx.fillStyle=color.replace(')',', 0.2)').replace('rgb','rgba');
    ctx.fill();
    ctx.fillStyle=color;
  }
  
  if(anglesMap&&Object.keys(anglesMap).length){
    ctx.font='bold 10px JetBrains Mono';
    ctx.textAlign='left';
    ctx.fillStyle='#fff';
    for(const [key,bidx]of Object.entries(JOINT_B_IDX)){
      const ang=anglesMap[key];
      if(ang==null||bidx>=pts.length)continue;
      const [px,py]=pts[bidx];
      const label=`${CN[key]||key}:${ang.toFixed(0)}°`;
      const tm=ctx.measureText(label);
      ctx.fillStyle='rgba(11,17,32,0.8)';
      ctx.fillRect(px+6,py-12,tm.width+8,16);
      ctx.fillStyle=color;
      ctx.fillText(label,px+10,py);
    }
  }
  ctx.globalAlpha=1;
}

const _frameCache={a:new Map(),b:new Map()};
const _CACHE_MAX=60;

function _cacheSet(side,idx,img){
  const m=_frameCache[side];
  if(m.size>=_CACHE_MAX)m.delete(m.keys().next().value);
  m.set(idx,img);
}

async function loadVideoFrame(side,idx){
  const m=_frameCache[side];
  if(m.has(idx))return m.get(idx);
  const loader=document.getElementById('frame-loading');
  if(loader)loader.style.display='flex';
  return new Promise((resolve)=>{
    const img=new Image();
    img.onload=()=>{
      _cacheSet(side,idx,img);
      if(loader)loader.style.display='none';
      resolve(img);
    };
    img.onerror=()=>{
      if(loader)loader.style.display='none';
      resolve(null);
    };
    img.src=`/api/frame?which=${side}&idx=${idx}`;
  });
}

function drawDarkGrid(ctx,W,H){
  ctx.fillStyle='#0a1020';
  ctx.fillRect(0,0,W,H);
  ctx.strokeStyle='#1e293b';
  ctx.lineWidth=1;
  for(let x=0;x<W;x+=40){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,H);ctx.stroke();}
  for(let y=0;y<H;y+=40){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(W,y);ctx.stroke();}
}

async function renderSkeleton(){
  const skelC=document.getElementById('skel-canvas');
  const vidC=document.getElementById('video-canvas');
  if(!skelC)return;
  
  const W=skelC.width,H=skelC.height;
  const sCtx=skelC.getContext('2d');
  const vCtx=vidC?vidC.getContext('2d'):null;
  
  const hist=anHistMain();
  const overlayOn=document.getElementById('overlay-toggle')?.checked;
  const hasVid=anHasVideo();
  const idx=hist.length?Math.max(0,Math.min(Math.round(tlIdx),hist.length-1)):-1;
  
  if(vCtx){
    vCtx.clearRect(0,0,vidC.width,vidC.height);
    if(overlayOn&&hasVid&&idx>=0){
      const side=anSide==='b'?'b':'a';
      const img=await loadVideoFrame(side,idx);
      if(img)vCtx.drawImage(img,0,0,vidC.width,vidC.height);
      else drawDarkGrid(vCtx,vidC.width,vidC.height);
    }else{
      drawDarkGrid(vCtx,vidC.width,vidC.height);
    }
  }
  
  sCtx.clearRect(0,0,W,H);
  
  const hint=document.getElementById('no-frame-hint');
  if(hint)hint.style.display=(overlayOn&&!hasVid&&hist.length)?'inline':'none';
  
  if(!hist.length){
    if(vCtx){
      drawDarkGrid(vCtx,vidC.width,vidC.height);
      vCtx.fillStyle='#64748b';
      vCtx.font='14px Inter';
      vCtx.textAlign='center';
      vCtx.fillText('开始分析后显示骨架',vidC.width/2,vidC.height/2);
      vCtx.textAlign='left';
    }
    return;
  }
  
  const eA=(anSide!=='b'&&anHistA.length&&idx>=0)?anHistA[Math.min(idx,anHistA.length-1)]:null;
  const eB=((anSide==='b'||anSide==='ab')&&anHistB.length&&idx>=0)?anHistB[Math.min(idx,anHistB.length-1)]:null;
  const anglesForLabel=eA?eA.angles:(eB?eB.angles:{});
  
  if(eA)drawSkel(sCtx,eA.lm,'#38bdf8',W,H,anSide==='ab'?0.85:1,anglesForLabel);
  if(eB)drawSkel(sCtx,eB.lm,'#a78bfa',W,H,anSide==='ab'?0.85:1,anSide==='ab'?{}:anglesForLabel);
}

function renderJointTable(){
  const el=document.getElementById('an-joint-table');
  if(!el)return;
  const joints=JOINT_GROUPS[anJointFilter];
  const idx=Math.min(Math.round(tlIdx),anHistMain().length?anHistMain().length-1:0);
  const lastA=(anSide!=='b'&&anHistA.length&&idx>=0)?anHistA[Math.min(idx,anHistA.length-1)].angles:{};
  const lastB=((anSide==='b'||anSide==='ab')&&anHistB.length&&idx>=0)?anHistB[Math.min(idx,anHistB.length-1)].angles:{};
  
  if(!Object.keys(lastA).length&&!Object.keys(lastB).length){
    el.innerHTML='<div style="color:var(--text-muted)">等待数据...</div>';
    return;
  }
  
  el.innerHTML=joints.map((key,i)=>{
    const va=lastA[key],vb=lastB[key],clr=JCOLORS[i%JCOLORS.length];
    const aS=va!=null?`<span style="color:var(--cyan);font-family:JetBrains Mono">${va.toFixed(1)}°</span>`:'<span style="color:var(--text-muted)">—</span>';
    const bS=vb!=null?`<span style="color:var(--purple);font-family:JetBrains Mono">${vb.toFixed(1)}°</span>`:'<span style="color:var(--text-muted)">—</span>';
    let diff='';
    if(va!=null&&vb!=null){
      const d=va-vb;
      const c=Math.abs(d)<5?'var(--green)':Math.abs(d)<15?'var(--cyan)':Math.abs(d)<30?'var(--amber)':'var(--red)';
      diff=`<span style="color:${c};margin-left:4px;font-family:JetBrains Mono">${d>=0?'+':''}${d.toFixed(1)}°</span>`;
    }
    return `<div style="display:flex;align-items:center;gap:6px;margin-bottom:4px;padding:4px 8px;border-radius:4px;background:rgba(255,255,255,0.03)">
      <span style="width:8px;height:8px;border-radius:50%;background:${clr};flex-shrink:0"></span>
      <span style="width:40px;color:var(--text-muted);flex-shrink:0;font-size:0.8rem">${CN[key]||key}</span>
      ${aS}${(anSide==='ab'||anSide==='b')?' '+bS+' '+diff:''}
    </div>`;
  }).join('');
}

function renderStats(){
  const el=document.getElementById('an-stats'),cEl=document.getElementById('stat-count');
  if(!el)return;
  const hist=anHistMain();
  if(!hist.length){
    el.innerHTML='暂无记录数据';
    if(cEl)cEl.textContent='';
    return;
  }
  if(cEl)cEl.textContent=`(${hist.length}帧)`;
  
  const joints=JOINT_GROUPS[anJointFilter];
  const rows=joints.map(key=>{
    const vals=hist.map(h=>h.angles[key]).filter(v=>v!=null);
    if(!vals.length)return null;
    const mn=Math.min(...vals),mx=Math.max(...vals),avg=vals.reduce((a,b)=>a+b,0)/vals.length;
    const std=Math.sqrt(vals.reduce((s,v)=>s+(v-avg)**2,0)/vals.length);
    return `<div style="display:flex;gap:8px;align-items:baseline;margin-bottom:6px;padding:4px 8px;border-radius:4px;background:rgba(255,255,255,0.02)">
      <span style="width:36px;color:var(--text-muted);flex-shrink:0;font-size:0.8rem">${CN[key]||key}</span>
      <span style="font-family:JetBrains Mono;font-size:0.85rem;color:var(--text-primary)">μ${avg.toFixed(1)}°</span>
      <span style="font-family:JetBrains Mono;font-size:0.8rem;color:var(--text-muted)">σ${std.toFixed(1)}</span>
      <span style="font-family:JetBrains Mono;font-size:0.75rem;color:var(--text-muted)">[${mn.toFixed(0)}–${mx.toFixed(0)}]</span>
    </div>`;
  }).filter(Boolean);
  
  el.innerHTML=rows.join('')||'选定关节无数据';
}

function smooth(arr,n){
  if(n<=1)return arr;
  return arr.map((_,i)=>{
    const s=arr.slice(Math.max(0,i-n+1),i+1);
    return s.reduce((a,b)=>a+b,0)/s.length;
  });
}

function initLegendCheckboxes(){
  const joints=JOINT_GROUPS[anJointFilter];
  const cl=document.getElementById('chart-legend');
  if(!cl)return;
  
  const prev={};
  cl.querySelectorAll('input[data-key]').forEach(cb=>{prev[cb.dataset.key]=cb.checked;});
  
  cl.innerHTML=joints.map((k,i)=>{
    const color=JCOLORS[i%JCOLORS.length];
    const chk=(prev[k]!==undefined)?prev[k]:true;
    return `<label style="display:flex;align-items:center;gap:4px;cursor:pointer;user-select:none;padding:4px 10px;border-radius:20px;border:1px solid rgba(255,255,255,0.1);background:rgba(255,255,255,0.05);transition:all 0.2s" onmouseover="this.style.borderColor='${color}'" onmouseout="this.style.borderColor='rgba(255,255,255,0.1)'">
      <input type="checkbox" data-key="${k}" ${chk?'checked':''} onchange="renderChart()" style="accent-color:${color};width:14px;height:14px;cursor:pointer">
      <span style="width:10px;height:3px;background:${color};border-radius:2px"></span>
      <span style="color:${color};font-size:0.75rem">${CN[k]||k}</span>
    </label>`;
  }).join('');
}

function getVisibleJoints(){
  const cl=document.getElementById('chart-legend');
  if(!cl||!cl.querySelector('input'))return JOINT_GROUPS[anJointFilter];
  const checked=[];
  cl.querySelectorAll('input[data-key]').forEach(cb=>{if(cb.checked)checked.push(cb.dataset.key);});
  return checked.length?checked:JOINT_GROUPS[anJointFilter];
}

function toggleAllJoints(on){
  const cl=document.getElementById('chart-legend');
  if(cl)cl.querySelectorAll('input[data-key]').forEach(cb=>cb.checked=on);
  renderChart();
}

function renderChart(){
  const canvas=document.getElementById('chart-canvas');
  if(!canvas)return;
  const rect=canvas.getBoundingClientRect();
  if(rect.width<10||rect.height<10)return;
  
  const dpr=window.devicePixelRatio||1;
  canvas.width=rect.width*dpr;
  canvas.height=rect.height*dpr;
  const ctx=canvas.getContext('2d');
  ctx.scale(dpr,dpr);
  const W=rect.width,H=rect.height;
  
  ctx.fillStyle='#0f1828';
  ctx.fillRect(0,0,W,H);
  
  const PAD={top:18,right:14,bottom:34,left:42};
  const cW=W-PAD.left-PAD.right,cH=H-PAD.top-PAD.bottom;
  const joints=getVisibleJoints();
  const win=parseInt(document.getElementById('smooth-range')?.value)||3;
  
  const sA={},sB={};
  joints.forEach(k=>{sA[k]=[];sB[k]=[];});
  let tMin=Infinity,tMax=-Infinity;
  
  const push=(hist,target)=>hist.forEach(h=>joints.forEach(k=>{if(h.angles[k]!=null)target[k].push({t:h.t,v:h.angles[k]});}));
  if(anSide==='a'||anSide==='ab')push(anHistA,sA);
  if(anSide==='b'||anSide==='ab')push(anHistB,sB);
  
  const refHist=anHistMain();
  if(refHist.length){tMin=refHist[0].t;tMax=refHist[refHist.length-1].t;}
  
  if(!refHist.length){
    ctx.fillStyle='#64748b';
    ctx.font='14px Inter';
    ctx.textAlign='center';
    ctx.fillText('暂无时序数据，开始分析后自动记录',W/2,H/2);
    ctx.textAlign='left';
    const ci=document.getElementById('chart-info');
    if(ci)ci.textContent='—';
    return;
  }
  
  const tRange=tMax-tMin||1;
  
  [0,30,60,90,120,150,180].forEach(y=>{
    const py=PAD.top+cH*(1-y/180);
    ctx.strokeStyle='#1e293b';
    ctx.lineWidth=1;
    ctx.beginPath();
    ctx.moveTo(PAD.left,py);
    ctx.lineTo(PAD.left+cW,py);
    ctx.stroke();
    ctx.fillStyle='#64748b';
    ctx.font='11px JetBrains Mono';
    ctx.fillText(y+'°',8,py+4);
  });
  
  const nT=Math.min(8,Math.floor(cW/60));
  for(let i=0;i<=nT;i++){
    const t=tMin+tRange*i/nT,px=PAD.left+cW*i/nT;
    ctx.strokeStyle='#1e293b';
    ctx.beginPath();
    ctx.moveTo(px,PAD.top+cH);
    ctx.lineTo(px,PAD.top+cH+4);
    ctx.stroke();
    ctx.fillStyle='#64748b';
    ctx.font='11px JetBrains Mono';
    ctx.fillText(t.toFixed(1)+'s',px-14,H-PAD.bottom+16);
  }
  
  joints.forEach((key,i)=>{
    const color=JCOLORS[i%JCOLORS.length];
    const draw=(series,dash)=>{
      const pts=series[key];
      if(!pts.length)return;
      const vs=smooth(pts.map(p=>p.v),win),ts=pts.map(p=>p.t);
      ctx.beginPath();
      ctx.strokeStyle=color;
      ctx.lineWidth=2;
      ctx.setLineDash(dash);
      let first=true;
      ts.forEach((t,ii)=>{
        const px=PAD.left+cW*(t-tMin)/tRange;
        const py=PAD.top+cH*(1-vs[ii]/180);
        first?ctx.moveTo(px,py):ctx.lineTo(px,py);
        first=false;
      });
      ctx.stroke();
      ctx.setLineDash([]);
    };
    if(anSide==='a'||anSide==='ab')draw(sA,[]);
    if(anSide==='b'||anSide==='ab')draw(sB,[5,3]);
  });
  
  const curIdx=Math.min(Math.round(tlIdx),refHist.length-1);
  if(curIdx>=0&&curIdx<refHist.length){
    const curT=refHist[curIdx].t;
    const cx=PAD.left+cW*(curT-tMin)/tRange;
    ctx.strokeStyle='rgba(255,255,255,0.3)';
    ctx.lineWidth=1.5;
    ctx.setLineDash([4,3]);
    ctx.beginPath();
    ctx.moveTo(cx,PAD.top);
    ctx.lineTo(cx,PAD.top+cH);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle='var(--cyan)';
    ctx.beginPath();
    ctx.arc(cx,PAD.top,5,0,Math.PI*2);
    ctx.fill();
    ctx.fillStyle='rgba(255,255,255,0.8)';
    ctx.font='bold 11px JetBrains Mono';
    ctx.fillText(curT.toFixed(2)+'s',Math.min(cx+6,PAD.left+cW-50),PAD.top+14);
  }
  
  const ci=document.getElementById('chart-info');
  if(ci)ci.textContent=`${refHist.length}帧 | ${tRange.toFixed(1)}s`;
}

async function anDrawFrame(){
  if(anViewMode==='aligned'){
    renderAlignedSkeleton();
    renderAlignedJointTable();
    renderAlignedChart();
    updateAlignedTimeline();
  }else{
    await renderSkeleton();
    renderJointTable();
    renderChart();
    updateTimeline();
  }
}

function anDraw(){anDrawFrame();renderStats();}

// ── Initialization ─────────────────────────────────────────
setInterval(()=>{
  if(document.getElementById('analysis-page').style.display!=='none'&&!tlPlaying)anRefresh();
},3000);

const chartObs=new ResizeObserver(()=>{
  if(document.getElementById('analysis-page').style.display!=='none')renderChart();
});

document.addEventListener('DOMContentLoaded',()=>{
  const chartEl=document.getElementById('chart-canvas');
  if(chartEl){
    chartObs.observe(chartEl);
    chartEl.addEventListener('click',chartClickSeek);
  }
  const wfEl=document.getElementById('tl-waveform');
  if(wfEl){
    wfEl.addEventListener('click',(e)=>{
      const rect=wfEl.getBoundingClientRect();
      const pct=Math.max(0,Math.min(1,(e.clientX-rect.left)/rect.width));
      const hist=anHistMain();
      if(!hist.length)return;
      tlGoTo(Math.round(pct*(hist.length-1)));
    });
    wfEl.style.cursor='pointer';
    new ResizeObserver(()=>{renderWaveform();}).observe(wfEl);
  }
  
  // Initialize provider UI
  setProv(curProv);
});