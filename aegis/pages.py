"""Self-contained HTML pages (inline CSS + vanilla JS).

Kept as Python strings so PyInstaller has no template/static files to locate.
The pages are static shells; all data flows through the JSON API in web.py.
"""

_BASE_CSS = """
:root{
  --bg:#0d1017; --panel:#161b24; --panel2:#1e2530; --line:#2a323f;
  --txt:#e6ebf2; --muted:#8b97a8; --accent:#ff5a3c; --accent2:#3ca0ff;
  --ok:#37d67a; --warn:#ffb020; --err:#ff5470;
}
*{box-sizing:border-box}
body{margin:0;font:14px/1.55 'Segoe UI',system-ui,sans-serif;color:var(--txt);
  background:radial-gradient(1100px 560px at 50% -12%, #151c29 0%, var(--bg) 62%) fixed}
a{color:var(--accent2);text-decoration:none}
button{font:inherit;cursor:pointer;border:none;border-radius:9px;padding:8px 14px;
  background:var(--panel2);color:var(--txt);transition:.15s}
button:hover{background:#2a323f}
button.primary{background:linear-gradient(135deg,#ff6a3c,#ff4d6d);color:#fff;font-weight:600;
  box-shadow:0 6px 18px rgba(255,77,109,.25)}
button.primary:hover{filter:brightness(1.07)}
.brand .logo{filter:drop-shadow(0 0 7px rgba(255,90,60,.45))}
button.ghost{background:transparent;border:1px solid var(--line)}
input,select{font:inherit;background:var(--panel2);border:1px solid var(--line);
  color:var(--txt);border-radius:8px;padding:9px 11px;width:100%}
header.topbar{display:flex;align-items:center;gap:16px;padding:14px 24px;
  background:rgba(22,27,36,.82);backdrop-filter:blur(8px);
  border-bottom:1px solid var(--line);position:sticky;top:0;z-index:20}
.brand{display:flex;align-items:center;gap:10px;font-weight:700;font-size:16px}
.brand .dot{width:10px;height:10px;border-radius:50%;background:var(--accent);box-shadow:0 0 10px var(--accent)}
.pills{display:flex;gap:8px;flex-wrap:wrap;margin-left:auto}
.pill{display:flex;align-items:center;gap:6px;background:var(--panel2);border:1px solid var(--line);
  padding:5px 10px;border-radius:20px;font-size:12px;color:var(--muted)}
.pill b{color:var(--txt)}
.pill .led{width:8px;height:8px;border-radius:50%;background:var(--muted)}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.35}}
.pill .led.on{background:var(--ok);box-shadow:0 0 8px var(--ok);animation:pulse 1.6s infinite}
.pill .led.off{background:var(--err)}
.appfoot{max-width:1200px;margin:0 auto;padding:18px 24px 32px;color:var(--muted);
  font-size:12px;display:flex;gap:14px;align-items:center;border-top:1px solid var(--line)}
.appfoot a{color:var(--muted)}.appfoot a:hover{color:var(--txt)}
main{max-width:1200px;margin:0 auto;padding:24px}
.tabs{display:flex;gap:6px;margin-bottom:20px}
.tabs button{background:transparent;color:var(--muted);border-radius:0;border-bottom:2px solid transparent;padding:8px 14px}
.tabs button.active{color:var(--txt);border-bottom-color:var(--accent)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:18px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;overflow:hidden;
  display:flex;flex-direction:column;transition:transform .15s,box-shadow .15s,border-color .15s}
.card:hover{transform:translateY(-3px);box-shadow:0 12px 30px rgba(0,0,0,.38);border-color:#33414f}
.card .thumb{position:relative;aspect-ratio:16/9;background:#000;cursor:pointer;overflow:hidden}
.card .thumb img{width:100%;height:100%;object-fit:cover}
.card .thumb .play{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
  font-size:34px;color:#fff;opacity:0;transition:.15s;background:rgba(0,0,0,.25)}
.card .thumb:hover .play{opacity:1}
.badge{position:absolute;top:8px;left:8px;background:var(--accent);color:#fff;font-weight:700;
  font-size:12px;padding:3px 8px;border-radius:6px}
.badge.dur{left:auto;right:8px;background:rgba(0,0,0,.7);font-weight:500}
.card .body{padding:12px 14px;display:flex;flex-direction:column;gap:8px}
.card .title{font-weight:600;outline:none}
.card .title[contenteditable]:focus{border-bottom:1px dashed var(--accent2)}
.meta{font-size:12px;color:var(--muted);display:flex;gap:10px;flex-wrap:wrap}
.targets{display:flex;gap:6px;flex-wrap:wrap}
.tg{font-size:11px;padding:2px 7px;border-radius:5px;border:1px solid var(--line);color:var(--muted)}
.tg.ok{color:var(--ok);border-color:var(--ok)}
.tg.err{color:var(--err);border-color:var(--err)}
.card .actions{display:flex;gap:6px;margin-top:2px}
.card .actions button{padding:6px 9px;font-size:13px;flex:1}
.fav{color:var(--muted)}.fav.on{color:var(--warn)}
.empty{grid-column:1/-1;text-align:center;color:var(--muted);padding:60px 20px;
  min-height:46vh;display:flex;flex-direction:column;align-items:center;justify-content:center}
.logbox{background:#0a0d12;border:1px solid var(--line);border-radius:12px;padding:14px;
  font-family:Consolas,monospace;font-size:12.5px;height:60vh;overflow:auto;white-space:pre-wrap}
.modal{position:fixed;inset:0;background:rgba(0,0,0,.8);display:none;align-items:center;
  justify-content:center;z-index:50;padding:24px}
.modal.show{display:flex}
.modal video{max-width:90vw;max-height:80vh;border-radius:12px;background:#000}
.modal .close{position:absolute;top:18px;right:24px;font-size:30px;color:#fff;cursor:pointer}
.bar{display:flex;align-items:center;gap:12px;margin-bottom:18px;flex-wrap:wrap}
.bar .sel{color:var(--muted);font-size:13px}
.card.sel{outline:2px solid var(--accent2)}
.toast{position:fixed;bottom:20px;left:50%;transform:translateX(-50%);background:var(--panel2);
  border:1px solid var(--line);padding:12px 18px;border-radius:10px;z-index:60;opacity:0;transition:.3s}
.toast.show{opacity:1}
.check{position:absolute;top:8px;right:8px;width:22px;height:22px;border-radius:6px;
  border:2px solid #fff;background:rgba(0,0,0,.5);display:none;align-items:center;justify-content:center}
.selmode .check{display:flex}
.card.sel .check{background:var(--accent2);border-color:var(--accent2)}
"""

DASHBOARD_HTML = """<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Aegis Clipper</title><style>%CSS%</style></head><body>
<header class=topbar>
  <div class=brand><svg class=logo width=28 height=28 viewBox="0 0 48 48" fill=none><path d="M24 3 41 9 41 24 C41 35 33 42 24 45 C15 42 7 35 7 24 L7 9 Z" fill="#161b24" stroke="#ff5a3c" stroke-width="2.6"/><path d="M20 16 33 24 20 32 Z" fill="#ff5a3c"/></svg> Aegis Clipper</div>
  <div class=pills id=pills></div>
</header>
<main>
  <div id=updateBanner style="display:none;flex-wrap:wrap;align-items:center;gap:12px;background:#1a2433;
    border:1px solid var(--accent2);border-radius:12px;padding:12px 16px;margin-bottom:18px">
    <span style="font-size:18px">⬆️</span>
    <div style="flex:1;min-width:200px"><b id=upVer></b> is available <span id=upNotes style="color:var(--muted)"></span></div>
    <button class=primary id=upBtn>Update now</button>
    <button class=ghost id=upDismiss>Later</button>
    <div id=upBar style="display:none;flex-basis:100%;height:8px;background:var(--line);border-radius:4px;overflow:hidden">
      <div id=upBarFill style="height:100%;width:0%;background:var(--accent2);transition:width .3s"></div>
    </div>
  </div>
  <div class=tabs>
    <button class=active data-tab=clips>Clips</button>
    <button data-tab=montages>Montages</button>
    <button data-tab=logs>Activity</button>
    <a href="/setup" style="margin-left:auto"><button class=ghost>⚙ Settings</button></a>
  </div>

  <section data-panel=clips>
    <div class=bar>
      <button class=ghost id=selBtn>Select for montage</button>
      <span class=sel id=selInfo style=display:none></span>
      <button class=primary id=makeMontage style="display:none">🎬 Build montage</button>
      <button class=ghost id=cancelSel style=display:none>Cancel</button>
      <span class=sel id=clipCount style=margin-left:auto></span>
    </div>
    <div class=grid id=clipGrid></div>
  </section>

  <section data-panel=montages style=display:none>
    <div class=grid id=montGrid></div>
  </section>

  <section data-panel=logs style=display:none>
    <div class=logbox id=logBox>Loading…</div>
  </section>
</main>
<footer class=appfoot>
  <span>Aegis Clipper <b>v%VER%</b></span>
  <a href="https://github.com/thelifeofsuleyman/cs2-clipper/releases" target=_blank rel=noopener>Releases</a>
  <a href="/setup">Settings</a>
  <span id=footStatus style=margin-left:auto></span>
</footer>

<div class=modal id=modal><span class=close id=modalClose>×</span><video id=player controls></video></div>
<div class=toast id=toast></div>

<script>
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
let selMode=false, selected=new Set();
function toast(m){const t=$('#toast');t.textContent=m;t.classList.add('show');setTimeout(()=>t.classList.remove('show'),2200);}
async function api(u,o){try{const r=await fetch(u,o);if(!r.ok)return null;return await r.json();}catch(e){return null;}}

// ----- tabs -----
$$('.tabs button[data-tab]').forEach(b=>b.onclick=()=>{
  $$('.tabs button[data-tab]').forEach(x=>x.classList.remove('active'));
  b.classList.add('active');
  $$('section[data-panel]').forEach(s=>s.style.display='none');
  $(`section[data-panel=${b.dataset.tab}]`).style.display='';
  if(b.dataset.tab==='logs')loadLogs();
  if(b.dataset.tab==='montages')loadMontages();
});

// ----- status pills -----
async function loadStatus(){
  const s=await api('/api/status');
  if(!s)return;
  const led=(on)=>`<span class="led ${on?'on':'off'}"></span>`;
  const rec=s.recorder||{};
  const encTxt=rec.encoder&&rec.encoder!=='?'?` · ${rec.encoder}`:'';
  $('#pills').innerHTML=
    `<span class=pill>${led(s.capturing)} ${s.capturing?'Recording':'Idle'}${encTxt}</span>`+
    `<span class=pill>Pending kills <b>${s.pending_kills}</b></span>`+
    `<span class=pill>Targets <b>${(s.enabled_targets||[]).join(', ')||'none'}</b></span>`;
  const fs=$('#footStatus');
  if(fs)fs.textContent=rec.backend?('recorder: '+rec.backend+(rec.encoder&&rec.encoder!=='?'?' · '+rec.encoder:'')):'';
}

// ----- clips -----
function tgClass(v){return v==='ok'?'ok':(v?'err':'');}
async function loadClips(){
  const r=await api('/api/clips');
  const clips=(r&&r.clips)||[];
  const g=$('#clipGrid');
  $('#clipCount').textContent=clips.length?`${clips.length} clip${clips.length===1?'':'s'}`:'';
  if(!clips.length){g.innerHTML='<div class=empty><div style="font-size:42px;margin-bottom:8px">🎬</div>No clips yet. Hop into CS2 and get a kill — your highlights show up here automatically.<br><span style="font-size:12px">Tip: use “Send a test clip” in Settings to check your setup now.</span></div>';return;}
  g.innerHTML=clips.map(c=>`
    <div class="card ${selected.has(c.id)?'sel':''}" data-id="${c.id}">
      <div class=check>✓</div>
      <div class=thumb data-play="${c.id}">
        <img src="/clip/${c.id}/thumb" loading=lazy>
        <span class=badge>${c.kills}K</span>
        ${c.duration?`<span class="badge dur">${Math.round(c.duration)}s</span>`:''}
        <div class=play>▶</div>
      </div>
      <div class=body>
        <div class=title contenteditable data-edit="${c.id}">${esc(c.title||'Untitled')}</div>
        <div class=meta><span>${esc(c.map)}</span>${c.round?`<span>round ${c.round} · ${esc(c.side)}</span>`:''}<span>${c.size_mb} MB</span></div>
        <div class=targets>${Object.entries(c.uploads||{}).map(([k,v])=>`<span class="tg ${tgClass(v)}" title="${esc(v)}">${k}</span>`).join('')||'<span class=tg>not shared</span>'}</div>
        <div class=actions>
          <button class="fav ${c.favorite?'on':''}" data-fav="${c.id}">★</button>
          <button data-share="${c.id}">Share</button>
          <button data-del="${c.id}">🗑</button>
        </div>
      </div>
    </div>`).join('');
  bindCards();
  updateSelBar();   // keep the montage bar in sync after a re-render
}
function esc(s){return (s||'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));}

function bindCards(){
  $('#clipGrid').classList.toggle('selmode',selMode);
  $$('[data-play]').forEach(el=>el.onclick=()=>{
    const id=el.dataset.play;
    if(selMode){toggleSel(id);return;}
    $('#player').src=`/clip/${id}/video`;$('#modal').classList.add('show');$('#player').play().catch(()=>{});
  });
  $$('[data-edit]').forEach(el=>el.onblur=()=>{
    api(`/api/clips/${el.dataset.edit}`,{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({title:el.textContent.trim()})}).then(()=>toast('Saved'));
  });
  $$('[data-fav]').forEach(b=>b.onclick=async()=>{
    const card=b.closest('.card');const on=!b.classList.contains('on');
    await api(`/api/clips/${b.dataset.fav}`,{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({favorite:on})});b.classList.toggle('on',on);
  });
  $$('[data-share]').forEach(b=>b.onclick=async()=>{
    b.disabled=true;b.textContent='…';
    try{
      const r=await api(`/api/clips/${b.dataset.share}/share`,{method:'POST'});
      toast(r&&r.results?('Shared: '+Object.keys(r.results).join(', ')):'Share failed');
    }finally{b.disabled=false;b.textContent='Share';loadClips();}
  });
  $$('[data-del]').forEach(b=>b.onclick=async()=>{
    if(!confirm('Delete this clip from the library? (the video file stays on disk)'))return;
    await fetch(`/api/clips/${b.dataset.del}`,{method:'DELETE'});loadClips();
  });
}
function toggleSel(id){selected.has(id)?selected.delete(id):selected.add(id);
  $(`.card[data-id="${id}"]`).classList.toggle('sel');updateSelBar();}
function updateSelBar(){$('#selInfo').textContent=`${selected.size} selected`;
  $('#selInfo').style.display=selected.size?'':'none';
  $('#makeMontage').style.display=selected.size?'':'none';}

$('#selBtn').onclick=()=>{selMode=true;$('#selBtn').style.display='none';$('#cancelSel').style.display='';bindCards();};
$('#cancelSel').onclick=()=>{selMode=false;selected.clear();$('#selBtn').style.display='';
  $('#cancelSel').style.display='none';updateSelBar();loadClips();};
$('#makeMontage').onclick=async()=>{
  const btn=$('#makeMontage');btn.disabled=true;btn.textContent='Building… (up to a minute)';
  try{
    const r=await api('/api/montage',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({clip_ids:[...selected]})});
    if(r&&r.ok){toast('Montage ready!');$('#cancelSel').click();}
    else{toast((r&&r.error)||'Montage failed');}
  }finally{btn.disabled=false;btn.textContent='🎬 Build montage';}
};

// ----- montages -----
async function loadMontages(){
  const mr=await api('/api/montages');const montages=(mr&&mr.montages)||[];const g=$('#montGrid');
  if(!montages.length){g.innerHTML='<div class=empty>No montages yet. Select clips on the Clips tab and hit “Build montage”.</div>';return;}
  g.innerHTML=montages.map(m=>`<div class=card><div class=thumb data-mp="${esc(m)}"><div class=play>▶</div></div>
    <div class=body><div class=title>${esc(m)}</div></div></div>`).join('');
  $$('[data-mp]').forEach(el=>el.onclick=()=>{$('#player').src='/montage/'+encodeURIComponent(el.dataset.mp);
    $('#modal').classList.add('show');$('#player').play().catch(()=>{});});
}

// ----- logs -----
async function loadLogs(){const lr=await api('/api/logs');const lines=(lr&&lr.lines)||[];
  const b=$('#logBox');b.textContent=lines.join('\\n');b.scrollTop=b.scrollHeight;}

// ----- modal -----
$('#modalClose').onclick=()=>{$('#modal').classList.remove('show');const p=$('#player');p.pause();p.removeAttribute('src');p.load();};
$('#modal').onclick=e=>{if(e.target===$('#modal')){$('#modalClose').onclick();}};
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&$('#modal').classList.contains('show'))$('#modalClose').onclick();});

// ----- auto-update -----
async function checkUpdate(){
  try{
    const r=await api('/api/update/check');
    if(!r.update)return;
    $('#upVer').textContent='v'+r.update.version;
    $('#upNotes').textContent=r.update.notes?('— '+r.update.notes.split('\\n')[0].slice(0,80)):'';
    $('#updateBanner').style.display='flex';
    $('#upBtn').onclick=startUpdate;
    $('#upDismiss').onclick=()=>$('#updateBanner').style.display='none';
    // If a download/install is already running (e.g. you opened Settings and came
    // back — that's a full page reload), resume the progress UI instead of
    // showing a fresh "Update now" button over a download that's still going.
    const p=await api('/api/update/progress');
    if(p&&(p.state==='downloading'||p.state==='installing')){
      $('#upBtn').disabled=true;$('#upBar').style.display='block';$('#upDismiss').style.display='none';
      pollUpdate();
    }
  }catch(e){}
}
async function startUpdate(){
  $('#upBtn').disabled=true;$('#upBtn').textContent='Starting…';
  const res=await api('/api/update/apply',{method:'POST'});
  if(!res.ok){toast(res.detail||'Update failed');$('#upBtn').textContent='Update now';$('#upBtn').disabled=false;return;}
  $('#upBar').style.display='block';$('#upDismiss').style.display='none';
  pollUpdate();
}
function pollUpdate(){
  const mb=b=>(b/1048576).toFixed(0);
  const iv=setInterval(async()=>{
    let p;
    try{p=await api('/api/update/progress');}
    catch(e){ // server exited during install -> expected
      clearInterval(iv);
      $('#upBarFill').style.width='100%';
      $('#upBtn').textContent='Restarting…';
      $('#upNotes').textContent='Installing — the app will reopen on the new version.';
      return;
    }
    if(p.state==='downloading'){
      $('#upBarFill').style.width=(p.pct||0)+'%';
      $('#upBtn').textContent=p.total?`Downloading ${p.pct}%`:'Downloading…';
      $('#upNotes').textContent=p.total?`${mb(p.downloaded)} / ${mb(p.total)} MB`:'';
    }else if(p.state==='installing'){
      $('#upBarFill').style.width='100%';
      $('#upBtn').textContent='Installing — restarting…';
      $('#upNotes').textContent='The app will close and reopen on the new version.';
    }else if(p.state==='error'){
      clearInterval(iv);toast('Update failed: '+(p.detail||''));
      $('#upBtn').textContent='Update now';$('#upBtn').disabled=false;
      $('#upBar').style.display='none';$('#upDismiss').style.display='';
    }
  },600);
}

loadStatus();loadClips();checkUpdate();
setInterval(loadStatus,4000);
setInterval(()=>{
  if($('section[data-panel=clips]').style.display==='none')return;
  if(selMode)return;                                   // don't disrupt montage selection
  if($('#clipGrid').contains(document.activeElement))return; // don't clobber an in-progress title edit
  loadClips();
},10000);
</script></body></html>"""

SETUP_HTML = """<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Aegis Clipper — Setup</title><style>%CSS%
.wizard{max-width:680px;margin:0 auto}
.step{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:22px;margin-bottom:18px}
.step h3{margin:0 0 4px;display:flex;align-items:center;gap:10px}
.step .hint{color:var(--muted);font-size:13px;margin:0 0 16px}
.row{display:flex;gap:10px;align-items:center;margin-bottom:12px}
.row label{width:150px;color:var(--muted);flex-shrink:0}
.statusline{font-size:13px;margin-top:6px}
.ok{color:var(--ok)}.err{color:var(--err)}
.toggle{display:flex;align-items:center;gap:10px;margin-bottom:14px;font-weight:600}
.collapse{padding-left:4px;border-left:2px solid var(--line);margin-left:6px;padding-bottom:2px}
.foot{display:flex;justify-content:space-between;align-items:center;margin-top:8px}
.num{width:26px;height:26px;border-radius:50%;background:var(--accent);color:#fff;display:inline-flex;
  align-items:center;justify-content:center;font-size:14px;font-weight:700}
</style></head><body>
<header class=topbar><div class=brand><svg class=logo width=28 height=28 viewBox="0 0 48 48" fill=none><path d="M24 3 41 9 41 24 C41 35 33 42 24 45 C15 42 7 35 7 24 L7 9 Z" fill="#161b24" stroke="#ff5a3c" stroke-width="2.6"/><path d="M20 16 33 24 20 32 Z" fill="#ff5a3c"/></svg> Aegis Clipper — Setup</div></header>
<main><div class=wizard>

  <div class=step>
    <h3><span class=num>1</span> System check</h3>
    <p class=hint>Aegis records and clips right on your PC — no OBS needed. We check the essentials automatically.</p>
    <div class=statusline id=detectOut>Checking…</div>
    <div class=foot><button class=ghost onclick=detect()>Re-scan</button></div>
  </div>

  <div class=step>
    <h3><span class=num>2</span> Recording</h3>
    <p class=hint>Pick the quality that fits your PC. Aegis keeps a short rolling buffer and saves the moment automatically when you frag.</p>
    <div class=row><label>Quality</label><select id=rec_preset>
      <option value=low>Low-end — 720p, 30fps (lightest)</option>
      <option value=medium selected>Balanced — 900p, 30fps</option>
      <option value=high>High — 1080p, 60fps</option>
      <option value=source>Native resolution — 60fps</option>
    </select></div>
    <div class=row><label>Clip length</label><input id=rec_clip value=30> <span class=hint style=margin:0>seconds saved per kill streak</span></div>
    <div class=row><label>Record only in-game</label><input type=checkbox id=rec_gate checked style="width:auto"> <span class=hint style=margin:0>only capture while CS2 is open (saves resources)</span></div>
    <div class=row><label>Polished clips</label><input type=checkbox id=polish_en checked style="width:auto"> <span class=hint style=margin:0>add a Steam name + avatar + “ACE” intro and smooth fades to every clip</span></div>
    <div class=statusline id=encOut></div>
    <details style="margin-top:12px">
      <summary style="cursor:pointer;color:var(--muted)">Prefer OBS? Use it instead (advanced)</summary>
      <div class=collapse style=margin-top:10px>
        <div class=toggle><input type=checkbox id=use_obs> Record with OBS instead of the built-in recorder</div>
        <div class=row><label>Replay folder</label><input id=obs_replay_dir placeholder="C:\\Users\\you\\Videos"></div>
        <div class=row><label>WebSocket port</label><input id=obs_port value=4455></div>
        <div class=row><label>Password</label><input id=obs_password type=password placeholder="(blank if none)"></div>
      </div>
    </details>
  </div>

  <div class=step>
    <h3><span class=num>3</span> CS2 Game Integration</h3>
    <p class=hint>One click copies the GSI config into CS2 so the clipper can see your kills. Restart CS2 afterwards.</p>
    <div class=row><label>CS2 cfg folder</label><input id=cs2_cfg_dir placeholder="…\\csgo\\cfg"></div>
    <div class=foot><button class=primary onclick=installGsi()>Install GSI config</button>
      <span class=statusline id=gsiOut></span></div>
  </div>

  <div class=step>
    <h3><span class=num>4</span> Where to send clips</h3>
    <p class=hint>Clips are always saved to your local library. Turn on any extra destinations.</p>

    <div class=toggle><input type=checkbox id=tg_en> Telegram</div>
    <div class=collapse>
      <div class=row><label>Bot token</label><input id=tg_token placeholder="123456:ABC…"></div>
      <div class=row><label>Chat ID</label><input id=tg_chat placeholder="-100…"></div>
    </div>

    <div class=toggle style=margin-top:14px><input type=checkbox id=dc_en> Discord</div>
    <div class=collapse>
      <div class=row><label>Webhook URL</label><input id=dc_url placeholder="https://discord.com/api/webhooks/…"></div>
      <p class=hint>Server → Edit Channel → Integrations → Webhooks → New Webhook → Copy URL. Clips over 25 MB are auto-shrunk to fit.</p>
    </div>

    <div class=toggle style=margin-top:14px><input type=checkbox id=yt_en> YouTube <span style="font-weight:400;color:var(--muted)">(advanced)</span></div>
    <div class=collapse>
      <div class=row><label>client_secrets.json</label><input id=yt_secrets placeholder="path to your OAuth desktop credentials"></div>
      <div class=row><label>Privacy</label><select id=yt_privacy><option>unlisted</option><option>private</option><option>public</option></select></div>
      <p class=hint>Create a Google Cloud project, enable “YouTube Data API v3”, make a Desktop OAuth client, and point here at the downloaded file. A browser opens once to authorize.</p>
    </div>

    <div class=foot style="margin-top:16px;flex-wrap:wrap;gap:10px">
      <button class=ghost onclick=testClip()>🎬 Preview a clip (with ACE intro)</button>
      <button class=ghost onclick=captureTest()>🖥️ Test screen capture</button>
      <span class=statusline id=testOut></span>
    </div>
  </div>

  <div class=step>
    <h3><span class=num>5</span> Clip behaviour</h3>
    <div class=row><label>Bundle window</label><input id=debounce value=7> <span class=hint style=margin:0>sec of no-kill before a streak is clipped</span></div>
    <div class=row><label>Min kills</label><input id=minkills value=1> <span class=hint style=margin:0>2 = only doubles and up</span></div>
  </div>

  <div class=foot style=margin-bottom:40px>
    <span class=statusline id=saveOut></span>
    <button class=primary onclick=finish()>Save &amp; open dashboard →</button>
  </div>
</div></main>
<div class=toast id=toast></div>

<script>
const $=s=>document.querySelector(s);
async function api(u,o){try{const r=await fetch(u,o);if(!r.ok)return null;return await r.json();}catch(e){return null;}}
function toast(m){const t=$('#toast');t.textContent=m;t.classList.add('show');setTimeout(()=>t.classList.remove('show'),2200);}

async function detect(){
  $('#detectOut').textContent='Checking…';
  const d=await api('/api/detect');
  if(d.cs2_cfg_dir&&!$('#cs2_cfg_dir').value)$('#cs2_cfg_dir').value=d.cs2_cfg_dir;
  if(d.obs_replay_dir&&!$('#obs_replay_dir').value)$('#obs_replay_dir').value=d.obs_replay_dir;
  $('#detectOut').innerHTML=
    `<div class="${d.ffmpeg?'ok':'err'}">${d.ffmpeg?'✓ Recorder ready':'✗ ffmpeg missing — recording/montages disabled'}</div>`+
    `<div class="${d.gpu_accel?'ok':''}">${d.gpu_accel?'✓ GPU encoding available ('+d.encoder+') — near-zero CPU cost while you play':'• Software encoding (no GPU encoder found) — works fine, uses a little more CPU'}</div>`+
    `<div class="${d.cs2_cfg_dir?'ok':'err'}">${d.cs2_cfg_dir?'✓ CS2 found':'✗ CS2 cfg folder not found — set it in step 3'}</div>`;
  $('#encOut').innerHTML=d.encoder?`<span class="${d.gpu_accel?'ok':''}">Encoder: ${d.encoder} ${d.gpu_accel?'(GPU)':'(software)'}</span>`:'';
}

async function loadExisting(){
  const c=await api('/api/config')||{};
  const r=c.recording||{}, o=c.obs||{}, e=c.engine||{}, u=c.uploads||{};
  const tg=u.telegram||{}, dc=u.discord||{}, yt=u.youtube||{};
  $('#rec_preset').value=r.preset||'medium'; $('#rec_clip').value=r.clip_seconds||30;
  $('#rec_gate').checked=r.only_when_game_running!==false;
  $('#polish_en').checked=(c.polish||{}).enabled!==false;
  $('#use_obs').checked=(r.backend==='obs');
  $('#obs_replay_dir').value=o.replay_dir||'';
  $('#obs_port').value=o.port||4455; $('#obs_password').value=o.password||'';
  $('#debounce').value=e.debounce_sec||7; $('#minkills').value=e.min_kills||1;
  $('#tg_en').checked=!!tg.enabled; $('#tg_token').value=tg.bot_token||''; $('#tg_chat').value=tg.chat_id||'';
  $('#dc_en').checked=!!dc.enabled; $('#dc_url').value=dc.webhook_url||'';
  $('#yt_en').checked=!!yt.enabled; $('#yt_secrets').value=yt.client_secrets||'';
  $('#yt_privacy').value=yt.privacy||'unlisted';
}

function gather(){return {
  engine:{debounce_sec:parseFloat($('#debounce').value)||7, min_kills:parseInt($('#minkills').value)||1},
  recording:{backend:$('#use_obs').checked?'obs':'builtin', preset:$('#rec_preset').value,
       clip_seconds:parseInt($('#rec_clip').value)||30, only_when_game_running:$('#rec_gate').checked},
  polish:{enabled:$('#polish_en').checked},
  obs:{replay_dir:$('#obs_replay_dir').value.trim(), port:parseInt($('#obs_port').value)||4455,
       password:$('#obs_password').value},
  uploads:{
    telegram:{enabled:$('#tg_en').checked, bot_token:$('#tg_token').value.trim(), chat_id:$('#tg_chat').value.trim()},
    discord:{enabled:$('#dc_en').checked, webhook_url:$('#dc_url').value.trim()},
    youtube:{enabled:$('#yt_en').checked, client_secrets:$('#yt_secrets').value.trim(), privacy:$('#yt_privacy').value},
  }};}

async function save(){
  try{
    const r=await api('/api/config',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify(gather())});
    if(!r.ok){toast('Could not save settings — check the app log');return false;}
    return true;
  }catch(e){toast('Could not save settings — is the app still running?');return false;}
}

async function testClip(){
  $('#testOut').textContent='Building a preview clip with the ACE intro…';
  if(!(await save()))return;
  const r=await api('/api/test-clip',{method:'POST'});
  if(!r||!r.ok){$('#testOut').innerHTML=`<span class=err>✗ ${(r&&r.detail)||'failed'}</span>`;return;}
  const lines=Object.entries(r.results||{}).map(([k,v])=>`${k}: ${v}`).join(' · ');
  $('#testOut').innerHTML=`<span class=ok>✓ Done — open the Clips tab to watch it. ${lines}</span>`;
}
async function captureTest(){
  $('#testOut').textContent='Recording 5s of your real screen…';
  if(!(await save()))return;
  const r=await api('/api/capture-test',{method:'POST'});
  $('#testOut').innerHTML=r&&r.ok
    ?'<span class=ok>✓ Screen captured — open the Clips tab to confirm it recorded your screen</span>'
    :`<span class=err>✗ ${(r&&r.detail)||'capture failed (see Activity log)'}</span>`;
}

async function installGsi(){
  $('#gsiOut').textContent='Installing…';
  await save();
  const r=await api('/api/install-gsi',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({cs2_cfg_dir:$('#cs2_cfg_dir').value.trim()})});
  $('#gsiOut').innerHTML=r.ok?`<span class=ok>✓ Installed to ${r.path}</span>`:`<span class=err>✗ ${r.error}</span>`;
}

async function finish(){
  if(!(await save()))return;          // don't mark setup complete if the save failed
  await api('/api/finish-setup',{method:'POST'});
  location.href='/';
}

loadExisting().then(detect).catch(detect);
</script></body></html>"""

# Inline the shared CSS into both pages.
DASHBOARD_HTML = DASHBOARD_HTML.replace("%CSS%", _BASE_CSS)
SETUP_HTML = SETUP_HTML.replace("%CSS%", _BASE_CSS)
