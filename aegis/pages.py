"""Self-contained HTML pages (inline CSS + vanilla JS).

Kept as Python strings so PyInstaller has no template/static files to locate.
The pages are static shells; all data flows through the JSON API in web.py.
"""

_BASE_CSS = """
:root{
  --bg:#0a0c10; --panel:#13161c; --panel2:#191d25; --line:#242932; --line2:#323945;
  --txt:#e8ebf1; --muted:#8d96a5; --faint:#5f6776;
  --accent:#ff5a39; --accent2:#4c9ffe; --ok:#37d67a; --warn:#f5b13d; --err:#ff5a6a;
  --r:10px; --r2:14px; --shadow:0 10px 30px rgba(0,0,0,.45);
}
*{box-sizing:border-box}
html{color-scheme:dark}
body{margin:0;color:var(--txt);background:var(--bg);
  font:14px/1.55 'Segoe UI Variable Text','Segoe UI',system-ui,-apple-system,sans-serif;
  -webkit-font-smoothing:antialiased;
  background-image:radial-gradient(1000px 420px at 50% -260px,rgba(255,90,57,.06),transparent)}
a{color:var(--accent2);text-decoration:none}
.ico{width:18px;height:18px;flex:none;fill:none;stroke:currentColor;stroke-width:2;
  stroke-linecap:round;stroke-linejoin:round}
button{font:inherit;cursor:pointer;border:1px solid var(--line);border-radius:var(--r);
  padding:9px 14px;background:var(--panel2);color:var(--txt);font-weight:500;
  display:inline-flex;align-items:center;gap:8px;transition:.14s}
button:hover{background:#20252e;border-color:var(--line2)}
button:active{transform:translateY(1px)}
button:disabled{opacity:.5;cursor:default}
button.primary{background:var(--accent);border-color:transparent;color:#fff;font-weight:600}
button.primary:hover{background:#ff6c4e}
button.ghost{background:transparent}
.btn-icon{width:34px;height:34px;padding:0;justify-content:center;color:var(--muted)}
.btn-icon:hover{color:var(--txt)}
.btn-icon.danger:hover{color:var(--err);border-color:var(--err)}
input,select{font:inherit;background:#0f1218;border:1px solid var(--line);color:var(--txt);
  border-radius:var(--r);padding:10px 12px;width:100%;transition:.14s}
input:focus,select:focus{outline:none;border-color:var(--accent2);box-shadow:0 0 0 3px rgba(76,159,254,.16)}
header.topbar{display:flex;align-items:center;gap:16px;padding:13px 24px;
  background:rgba(13,16,21,.72);backdrop-filter:blur(14px) saturate(140%);
  border-bottom:1px solid var(--line);position:sticky;top:0;z-index:20}
.brand{display:flex;align-items:center;gap:11px;font-weight:650;font-size:15px;letter-spacing:.2px}
.brand .logo{filter:drop-shadow(0 1px 5px rgba(255,90,57,.35))}
.pills{display:flex;gap:8px;flex-wrap:wrap;margin-left:auto}
.pill{display:flex;align-items:center;gap:7px;background:var(--panel);border:1px solid var(--line);
  padding:6px 11px;border-radius:9px;font-size:12px;color:var(--muted)}
.pill b{color:var(--txt);font-weight:600}
.pill .led{width:7px;height:7px;border-radius:50%;background:var(--faint)}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
.pill .led.on{background:var(--ok);box-shadow:0 0 0 3px rgba(55,214,122,.18);animation:pulse 1.8s infinite}
.pill .led.off{background:var(--err)}
.appfoot{max-width:1180px;margin:28px auto 0;padding:16px 24px 34px;color:var(--faint);
  font-size:12px;display:flex;gap:16px;align-items:center;border-top:1px solid var(--line)}
.appfoot a{color:var(--muted)}.appfoot a:hover{color:var(--txt)}
main{max-width:1180px;margin:0 auto;padding:26px 24px}
.tabs{display:flex;gap:4px;margin-bottom:22px;border-bottom:1px solid var(--line)}
.tabs button{background:transparent;border:none;color:var(--muted);border-radius:0;padding:10px 14px;
  border-bottom:2px solid transparent;margin-bottom:-1px;font-weight:500}
.tabs button:hover{color:var(--txt);background:transparent}
.tabs button.active{color:var(--txt);border-bottom-color:var(--accent)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:16px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:var(--r2);overflow:hidden;
  display:flex;flex-direction:column;transition:transform .16s,box-shadow .16s,border-color .16s}
.card:hover{transform:translateY(-2px);box-shadow:var(--shadow);border-color:var(--line2)}
.card .thumb{position:relative;aspect-ratio:16/9;background:#05070a;cursor:pointer;overflow:hidden}
.card .thumb img{width:100%;height:100%;object-fit:cover;transition:.25s}
.card:hover .thumb img{transform:scale(1.04)}
.card .thumb .play{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
  opacity:0;transition:.16s;background:linear-gradient(transparent,rgba(0,0,0,.25))}
.card .thumb:hover .play{opacity:1}
.play .pbtn{width:46px;height:46px;border-radius:50%;background:rgba(10,12,16,.6);
  backdrop-filter:blur(4px);border:1px solid rgba(255,255,255,.25);display:grid;place-items:center}
.play .ico{width:20px;height:20px;fill:#fff;stroke:none;margin-left:2px}
.badge{position:absolute;top:9px;left:9px;background:var(--accent);color:#fff;font-weight:700;
  font-size:11px;letter-spacing:.3px;padding:3px 8px;border-radius:7px}
.badge.dur{left:auto;right:9px;background:rgba(5,7,10,.78);font-weight:600;color:#d7dce4}
.card .body{padding:13px 14px;display:flex;flex-direction:column;gap:9px}
.card .title{font-weight:600;font-size:14px;outline:none;border-radius:6px;line-height:1.35}
.card .title[contenteditable]:focus{box-shadow:0 0 0 2px var(--accent2);padding:1px 4px;margin:-1px -4px}
.meta{font-size:12px;color:var(--muted);display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.meta .sep{width:3px;height:3px;border-radius:50%;background:var(--faint)}
.targets{display:flex;gap:6px;flex-wrap:wrap}
.tg{font-size:11px;padding:3px 8px 3px 7px;border-radius:20px;border:1px solid var(--line);
  color:var(--muted);display:inline-flex;align-items:center;gap:5px}
.tg::before{content:'';width:6px;height:6px;border-radius:50%;background:var(--faint)}
.tg.ok{color:var(--ok)}.tg.ok::before{background:var(--ok)}
.tg.err{color:var(--err)}.tg.err::before{background:var(--err)}
.card .actions{display:flex;gap:7px;align-items:center;margin-top:2px}
.card .actions .spacer{flex:1}
.fav{color:var(--muted)}.fav.on{color:var(--warn)}.fav.on .ico{fill:var(--warn)}
.empty{grid-column:1/-1;text-align:center;color:var(--muted);padding:48px 20px;
  min-height:48vh;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:6px}
.empty .ico{width:46px;height:46px;stroke:var(--faint);margin-bottom:8px}
.empty .sub{font-size:12.5px;color:var(--faint);max-width:380px}
.logbox{background:#07090d;border:1px solid var(--line);border-radius:var(--r2);padding:16px 18px;
  font-family:'Cascadia Mono',Consolas,monospace;font-size:12.5px;line-height:1.7;color:#b8c0cc;
  height:62vh;overflow:auto;white-space:pre-wrap}
.modal{position:fixed;inset:0;background:rgba(5,7,10,.85);backdrop-filter:blur(6px);display:none;
  align-items:center;justify-content:center;z-index:50;padding:30px}
.modal.show{display:flex}
.modal video{max-width:92vw;max-height:82vh;border-radius:var(--r2);background:#000;box-shadow:var(--shadow)}
.modal .close{position:absolute;top:18px;right:22px;width:40px;height:40px;border-radius:50%;
  background:rgba(255,255,255,.08);border:none;color:#fff;display:grid;place-items:center;cursor:pointer}
.modal .close:hover{background:rgba(255,255,255,.16)}
.bar{display:flex;align-items:center;gap:10px;margin-bottom:18px;flex-wrap:wrap}
.bar .sel{color:var(--muted);font-size:13px}
.card.sel{outline:2px solid var(--accent2);outline-offset:-2px}
.toast{position:fixed;bottom:22px;left:50%;transform:translateX(-50%) translateY(8px);
  background:var(--panel2);border:1px solid var(--line2);padding:12px 18px;border-radius:var(--r);
  box-shadow:var(--shadow);z-index:60;opacity:0;transition:.25s;font-size:13px}
.toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
.check{position:absolute;top:9px;right:9px;width:24px;height:24px;border-radius:7px;
  border:2px solid rgba(255,255,255,.7);background:rgba(5,7,10,.5);display:none;
  align-items:center;justify-content:center;color:#fff}
.check .ico{width:14px;height:14px}
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
    <svg class=ico viewBox="0 0 24 24" style="color:var(--accent2);width:20px;height:20px"><line x1=12 y1=19 x2=12 y2=5/><polyline points="5 12 12 5 19 12"/></svg>
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
    <a href="/setup" style="margin-left:auto"><button class=ghost><svg class=ico viewBox="0 0 24 24"><line x1=4 y1=21 x2=4 y2=14/><line x1=4 y1=10 x2=4 y2=3/><line x1=12 y1=21 x2=12 y2=12/><line x1=12 y1=8 x2=12 y2=3/><line x1=20 y1=21 x2=20 y2=16/><line x1=20 y1=12 x2=20 y2=3/><line x1=1 y1=14 x2=7 y2=14/><line x1=9 y1=8 x2=15 y2=8/><line x1=17 y1=16 x2=23 y2=16/></svg> Settings</button></a>
  </div>

  <section data-panel=clips>
    <div class=bar>
      <button class=ghost id=selBtn><svg class=ico viewBox="0 0 24 24"><polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/></svg> Select clips</button>
      <span class=sel id=selInfo style=display:none></span>
      <button class=primary id=makeMontage style="display:none"><svg class=ico viewBox="0 0 24 24"><rect x=2 y=2 width=20 height=20 rx=2.5/><line x1=7 y1=2 x2=7 y2=22/><line x1=17 y1=2 x2=17 y2=22/><line x1=2 y1=12 x2=22 y2=12/></svg> Build montage</button>
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
  <button class=ghost id=checkUpd style="padding:5px 11px;font-size:12px">Check for updates</button>
  <span id=updStatus></span>
  <span id=footStatus style=margin-left:auto></span>
</footer>

<div class=modal id=modal><button class=close id=modalClose><svg class=ico viewBox="0 0 24 24"><line x1=18 y1=6 x2=6 y2=18/><line x1=6 y1=6 x2=18 y2=18/></svg></button><video id=player controls></video></div>
<div class=toast id=toast></div>

<script>
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
let selMode=false, selected=new Set();
const ICONS={
  play:'<polygon points="6 4 20 12 6 20"></polygon>',
  star:'<polygon points="12 2 15.1 8.3 22 9.3 17 14.1 18.2 21 12 17.8 5.8 21 7 14.1 2 9.3 8.9 8.3 12 2"></polygon>',
  share:'<circle cx="18" cy="5" r="3"></circle><circle cx="6" cy="12" r="3"></circle><circle cx="18" cy="19" r="3"></circle><line x1="8.6" y1="13.5" x2="15.4" y2="17.5"></line><line x1="15.4" y1="6.5" x2="8.6" y2="10.5"></line>',
  trash:'<polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>',
  film:'<rect x="2" y="2" width="20" height="20" rx="2.5"></rect><line x1="7" y1="2" x2="7" y2="22"></line><line x1="17" y1="2" x2="17" y2="22"></line><line x1="2" y1="12" x2="22" y2="12"></line><line x1="2" y1="7" x2="7" y2="7"></line><line x1="2" y1="17" x2="7" y2="17"></line><line x1="17" y1="17" x2="22" y2="17"></line><line x1="17" y1="7" x2="22" y2="7"></line>',
  settings:'<circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"></path>',
  x:'<line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line>',
  layers:'<polygon points="12 2 2 7 12 12 22 7 12 2"></polygon><polyline points="2 17 12 22 22 17"></polyline><polyline points="2 12 12 17 22 12"></polyline>',
  check:'<polyline points="20 6 9 17 4 12"></polyline>'
};
const ic=n=>`<svg class=ico viewBox="0 0 24 24">${ICONS[n]||''}</svg>`;
const PLAY=`<div class=play><div class=pbtn>${ic('play')}</div></div>`;
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
  if(!clips.length){g.innerHTML=`<div class=empty>${ic('film')}<div style="font-size:15px;color:var(--txt);font-weight:600">No clips yet</div><div class=sub>Hop into CS2 and get a kill — your highlights show up here automatically. Or use “Preview a clip” in Settings to test now.</div></div>`;updateSelBar();return;}
  g.innerHTML=clips.map(c=>{
    const kb=c.kills>=5?'ACE':(c.kills?c.kills+'K':'');
    const targets=Object.entries(c.uploads||{}).map(([k,v])=>`<span class="tg ${tgClass(v)}" title="${esc(v)}">${esc(k)}</span>`).join('')||'<span class=tg>not shared</span>';
    return `
    <div class="card ${selected.has(c.id)?'sel':''}" data-id="${c.id}">
      <div class=check>${ic('check')}</div>
      <div class=thumb data-play="${c.id}">
        <img src="/clip/${c.id}/thumb" loading=lazy>
        ${kb?`<span class=badge>${kb}</span>`:''}
        ${c.duration?`<span class="badge dur">${Math.round(c.duration)}s</span>`:''}
        ${PLAY}
      </div>
      <div class=body>
        <div class=title contenteditable=plaintext-only data-edit="${c.id}">${esc(c.title||'Untitled')}</div>
        <div class=meta><span>${esc(c.map)}</span><span class=sep></span><span>${c.size_mb} MB</span>${c.duration?`<span class=sep></span><span>${Math.round(c.duration)}s</span>`:''}</div>
        <div class=targets>${targets}</div>
        <div class=actions>
          <button class="btn-icon fav ${c.favorite?'on':''}" data-fav="${c.id}" title="Favorite">${ic('star')}</button>
          <span class=spacer></span>
          <button class="btn-icon" data-share="${c.id}" title="Share">${ic('share')}</button>
          <button class="btn-icon danger" data-del="${c.id}" title="Delete">${ic('trash')}</button>
        </div>
      </div>
    </div>`;}).join('');
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
    if(!confirm('Delete this clip and its video file? This cannot be undone.'))return;
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
  }finally{btn.disabled=false;btn.innerHTML=ic('film')+' Build montage';}
};

// ----- montages -----
async function loadMontages(){
  const mr=await api('/api/montages');const montages=(mr&&mr.montages)||[];const g=$('#montGrid');
  if(!montages.length){g.innerHTML=`<div class=empty>${ic('layers')}<div style="font-size:15px;color:var(--txt);font-weight:600">No montages yet</div><div class=sub>Select clips on the Clips tab and hit “Build montage”.</div></div>`;return;}
  g.innerHTML=montages.map(m=>`<div class=card><div class=thumb data-mp="${esc(m)}">${PLAY}</div>
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

$('#checkUpd').onclick=async()=>{
  const s=$('#updStatus');s.textContent='Checking…';
  const r=await api('/api/update/check');
  if(r&&r.update){s.textContent='';$('#updateBanner').style.display='flex';checkUpdate();}
  else if(r&&r.error){s.textContent='Couldn’t check — '+r.error;}
  else{s.textContent='You’re on the latest version';}
};
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
      <button class=ghost onclick=testClip()>Preview a clip</button>
      <button class=ghost onclick=captureTest()>Test screen capture</button>
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
    ?`<span class=ok>✓ Captured via ${r.method} — open the Clips tab and confirm it shows your screen (not black)</span>`
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
