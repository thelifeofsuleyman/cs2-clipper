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
.appfoot{max-width:min(1560px,96vw);margin:28px auto 0;padding:16px 24px 34px;color:var(--faint);
  font-size:12px;display:flex;gap:16px;align-items:center;border-top:1px solid var(--line)}
.appfoot a{color:var(--muted)}.appfoot a:hover{color:var(--txt)}
main{width:100%;max-width:min(1560px,96vw);margin:0 auto;padding:clamp(16px,2.2vw,30px) clamp(14px,1.8vw,28px)}
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
.dialog{background:var(--panel);border:1px solid var(--line2);border-radius:var(--r2);
  padding:24px;max-width:430px;box-shadow:var(--shadow)}
.dialog h3{margin:0 0 8px;font-size:17px}
.dialog p{margin:0 0 18px;color:var(--muted);font-size:13.5px;line-height:1.6}
.dialog-actions{display:flex;gap:10px;flex-wrap:wrap}
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
.topbar .settings-link,.topbar .settings-controls{margin-left:auto}
.settings-controls{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.settings-controls .settings-link{margin-left:0}
.settings-controls [hidden]{display:none}
.settings-link{color:var(--txt);background:var(--panel2);border:1px solid var(--line);
  border-radius:var(--r);padding:8px 14px;font-weight:600}
.settings-link:hover{border-color:var(--line2);background:#20252e}
.capture-panel{display:grid;grid-template-columns:minmax(0,1.35fr) minmax(240px,.85fr);
  align-items:center;gap:24px;margin:0 0 26px;padding:clamp(18px,3vw,32px);
  background:linear-gradient(118deg,#1b202a,#13161c 74%);border:1px solid var(--line2);
  border-radius:var(--r2);border-left:3px solid var(--accent)}
.capture-panel h1{font-size:clamp(24px,3vw,38px);line-height:1.12;margin:0 0 9px;letter-spacing:-.035em}
.capture-panel p{margin:0;color:#aeb7c5;max-width:56ch;overflow-wrap:anywhere}
.capture-panel .pills{margin:0 0 12px}
.capture-actions{display:flex;gap:8px;flex-wrap:wrap}
.library-title{font-size:22px;letter-spacing:-.02em;margin:0}
.library-bar{justify-content:space-between}
.library-tools{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.library-tools input{width:min(230px,100%);padding:8px 12px}
.library-tools select{width:auto;padding:8px 10px}
.card button.thumb{display:block;border:0;border-radius:0;padding:0;width:100%;color:var(--txt)}
.thumb:focus-visible .play,.thumb:focus-visible{opacity:1}
.card .thumb img{display:block}
.card .check{z-index:1;pointer-events:none}
.empty{min-height:240px;background:var(--panel);border:1px dashed var(--line2);border-radius:var(--r2)}
.empty .sub{color:var(--muted)}
.loading-msg,.panel-error{grid-column:1/-1;color:var(--muted);padding:24px}
.panel-error{color:var(--warn)}
.modal .player-error{position:absolute;bottom:14%;background:var(--panel);padding:14px;border-radius:var(--r)}
.toast{pointer-events:none;max-width:min(560px,92vw)}
button[aria-busy=true]{cursor:progress}
@media(max-width:720px){.capture-panel{grid-template-columns:1fr;gap:14px}.library-tools{width:100%}}
/* Adapt to any resolution / window size */
@media(max-width:820px){
  header.topbar{flex-wrap:wrap;gap:10px;padding:11px 16px}
  .pills{margin-left:0;width:100%}
  .grid{grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:13px}
  .tabs{overflow-x:auto;white-space:nowrap}
  .appfoot{flex-wrap:wrap;gap:10px}
  .wizard .row{flex-wrap:wrap}
  .wizard .row label{width:100%}
  .wizard .row input,.wizard .row select{max-width:none}
}
@media(max-width:480px){
  .grid{grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px}
  .modal{padding:12px}
}
"""

DASHBOARD_HTML = """<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Aegis Clipper</title><style>%CSS%</style></head><body>
<header class=topbar>
  <div class=brand><svg class=logo width=28 height=28 viewBox="0 0 48 48" fill=none><path d="M24 3 41 9 41 24 C41 35 33 42 24 45 C15 42 7 35 7 24 L7 9 Z" fill="#161b24" stroke="#ff5a3c" stroke-width="2.6"/><path d="M20 16 33 24 20 32 Z" fill="#ff5a3c"/></svg> Aegis Clipper</div>
  <a class=settings-link href="/setup">Settings</a>
</header>
<main>
  <section class=capture-panel aria-label="Capture status">
    <div>
      <h1 id=captureTitle>Connecting to Aegis</h1>
      <p id=captureDetail aria-live=polite>Checking the replay buffer and CS2 connection.</p>
    </div>
    <div>
      <div class=pills id=pills></div>
      <div class=capture-actions>
        <button class=primary id=saveReplay disabled>Save replay</button>
        <a class=settings-link href="/setup#connection" id=connectionLink>CS2 setup</a>
      </div>
    </div>
  </section>
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
  </div>

  <section data-panel=clips>
    <div class="bar library-bar">
      <h2 class=library-title>Clip library</h2>
      <div class=library-tools>
      <input type=search id=clipSearch aria-label="Search clips" placeholder="Search clips">
      <select id=clipFilter aria-label="Filter clips"><option value=all>All clips</option><option value=favorite>Favorites</option><option value=test>Test clips</option></select>
      <button class=ghost id=selBtn><svg class=ico viewBox="0 0 24 24"><polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/></svg> Select clips</button>
      <span class=sel id=selInfo style=display:none></span>
      <button class=primary id=makeMontage style="display:none"><svg class=ico viewBox="0 0 24 24"><rect x=2 y=2 width=20 height=20 rx=2.5/><line x1=7 y1=2 x2=7 y2=22/><line x1=17 y1=2 x2=17 y2=22/><line x1=2 y1=12 x2=22 y2=12/></svg> Build montage</button>
      <button class=ghost id=cancelSel style=display:none>Cancel</button>
      <span class=sel id=clipCount></span>
      </div>
    </div>
    <div class=grid id=clipGrid><div class=loading-msg>Loading clips…</div></div>
  </section>

  <section data-panel=montages style=display:none>
    <div class=grid id=montGrid></div>
  </section>

  <section data-panel=logs style=display:none>
    <div class=bar>
      <button class=ghost id=copyDiagnostics>Copy recorder diagnostics</button>
      <a class=settings-link href="https://github.com/thelifeofsuleyman/cs2-clipper/issues/new?template=recording.yml" target=_blank rel=noopener>Report a recording issue</a>
    </div>
    <div class=logbox id=logBox>Loading…</div>
  </section>
</main>
<footer class=appfoot>
  <span>Aegis Clipper <b>v%VER%</b></span>
  <a href="https://github.com/thelifeofsuleyman/cs2-clipper/releases" target=_blank rel=noopener>Releases</a>
  <button class=ghost id=checkUpd style="padding:5px 11px;font-size:12px">Check for updates</button>
  <span id=updStatus></span>
  <span id=footStatus style=margin-left:auto></span>
</footer>

<div class=modal id=modal role=dialog aria-modal=true aria-label="Video player"><button class=close id=modalClose aria-label="Close video"><svg class=ico viewBox="0 0 24 24"><line x1=18 y1=6 x2=6 y2=18/><line x1=6 y1=6 x2=18 y2=18/></svg></button><video id=player controls playsinline></video><p class=player-error id=playerError hidden>Could not play this video. It may have moved or use an unsupported format.</p></div>
%EXIT_DIALOG%
<div class=toast id=toast role=status></div>

<script>
const $ = selector => document.querySelector(selector);
const $$ = selector => [...document.querySelectorAll(selector)];
%API_JS%
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
let library = [], selected = new Set(), selecting = false, clipRequest = 0, fingerprint = '';
let playerTrigger;
const escape = value => String(value ?? '').replace(/[&<>"']/g, ch => ({
  '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'
}[ch]));
const clipApi = id => '/api/clips/' + encodeURIComponent(id);
const clipMedia = (id, kind) => '/clip/' + encodeURIComponent(id) + '/' + kind;

function openTab(tab) {
  for (const b of $$('.tabs button[data-tab]')) {
    b.classList.toggle('active', b.dataset.tab === tab);
    b.setAttribute('aria-pressed', b.dataset.tab === tab);
  }
  for (const panel of $$('section[data-panel]')) panel.style.display = panel.dataset.panel === tab ? '' : 'none';
  if (tab === 'logs') loadLogs();
  if (tab === 'montages') loadMontages();
}
for (const b of $$('.tabs button[data-tab]')) b.onclick = () => openTab(b.dataset.tab);

async function loadStatus() {
  const s = await api('/api/status');
  const rec = s.recorder || {};
  const replay = $('#saveReplay');
  const states = {
    waiting_game: ['Waiting for CS2', 'Open Counter-Strike 2 to start the rolling replay buffer.'],
    starting: ['Starting capture', 'Aegis is preparing the replay buffer.'],
    error: ['Capture unavailable', rec.detail || 'Check the Activity tab for recording errors.'],
    idle: ['Capture idle', rec.backend === 'obs' ? 'Start the Replay Buffer in OBS.' : 'Open CS2 or check capture settings.']
  };
  const status = s.error ? ['Aegis disconnected', s.error] : s.capturing
    ? ['Replay buffer ready', s.gsi_connected
      ? 'CS2 is connected. Highlights save automatically when your streak ends.'
      : 'You can save replays now. Automatic highlights will start once CS2 sends game updates.']
    : states[rec.state] || states.idle;
  if ($('#captureTitle').textContent !== status[0]) $('#captureTitle').textContent = status[0];
  if ($('#captureDetail').textContent !== status[1]) $('#captureDetail').textContent = status[1];
  const pills = $('#pills');
  pills.replaceChildren();
  if (!s.error) {
    const game = document.createElement('span');
    game.className = 'pill';
    game.innerHTML = '<span class="led ' + (s.gsi_connected ? 'on' : '') + '"></span>' +
      (s.gsi_connected ? 'CS2 connected' : 'Waiting for game updates');
    pills.append(game);
    if (s.pending_kills) {
      const pending = document.createElement('span');
      pending.className = 'pill';
      pending.textContent = s.pending_kills + (s.pending_kills === 1 ? ' kill pending' : ' kills pending');
      pills.append(pending);
    }
  }
  replay.disabled = !s.capturing || replay.getAttribute('aria-busy') === 'true';
  $('#footStatus').textContent = rec.encoder && rec.encoder !== '?' ? rec.encoder +
    (rec.method ? ' · ' + rec.method : '') + (rec.fps ? ' · capture target ' + rec.fps + ' fps' : '') : '';
}

$('#saveReplay').onclick = () => busy($('#saveReplay'), 'Saving replay…', async () => {
  const r = await api('/api/replay', {method:'POST'});
  if (!r.ok) toast(r.error || r.detail || 'Could not save the replay.');
  else {
    await loadClips(true);
    openTab('clips');
    toast('Replay saved to your library.');
    playVideo(clipMedia(r.clip_id, 'video'));
  }
}).finally(loadStatus);

async function loadClips(force = false) {
  const seq = ++clipRequest;
  const r = await api('/api/clips');
  if (seq !== clipRequest) return;
  if (r.error) {
    if (!fingerprint) $('#clipGrid').textContent = r.error;
    if (force) toast(r.error);
    return;
  }
  const version = JSON.stringify(r.clips);
  if (!force && version === fingerprint) return;
  library = r.clips;
  fingerprint = version;
  const available = new Set(library.filter(clip => !clip.missing).map(clip => clip.id));
  for (const id of selected) if (!available.has(id)) selected.delete(id);
  renderClips();
}

function renderClips() {
  const query = $('#clipSearch').value.trim().toLowerCase();
  const filter = $('#clipFilter').value;
  const clips = library.filter(c => {
    const tags = Array.isArray(c.tags) ? c.tags : [];
    return (filter === 'all' || (filter === 'favorite' && c.favorite) || (filter === 'test' && tags.includes('test'))) &&
      (!query || [c.title, c.map, ...tags].join(' ').toLowerCase().includes(query));
  });
  $('#clipCount').textContent = clips.length + (clips.length === 1 ? ' clip' : ' clips');
  $('#selBtn').disabled = !library.some(c => !c.missing);
  const g = $('#clipGrid');
  g.classList.toggle('selmode', selecting);
  if (!clips.length) {
    g.innerHTML = library.length ? '<div class=empty>No clips match your filters.</div>' :
      '<div class=empty>' + ic('film') + '<strong>No replays yet</strong>' +
      '<div class=sub>Play CS2 to save highlights automatically, or save the current replay once the buffer is ready.</div>' +
      '<a href="/setup#capture-test">Test capture in Settings</a></div>';
    updateSelection();
    return;
  }
  g.innerHTML = clips.map(c => {
    const id = escape(c.id), title = escape(c.title || 'Untitled');
    const kill = c.kills >= 5 ? 'ACE' : c.kills ? c.kills + 'K' : '';
    const statuses = Object.entries(c.uploads || {}).filter(([name]) => name !== 'gallery');
    const targets = statuses.map(([name, status]) =>
      '<span class="tg ' + (status === 'ok' ? 'ok' : 'err') + '" title="' + escape(status) + '">' + escape(name) + '</span>').join('');
    return '<article class="card ' + (selected.has(c.id) ? 'sel' : '') + '" data-id="' + id + '">' +
      '<div class=check>' + ic('check') + '</div>' +
      '<button class=thumb data-play aria-label="' + (selecting ? 'Select ' : 'Play ') + title + '"' + (c.missing ? ' disabled' : '') + '>' +
      '<img src="' + clipMedia(c.id, 'thumb') + '" alt="" loading=lazy>' +
      (kill ? '<span class=badge>' + kill + '</span>' : '') +
      (c.duration ? '<span class="badge dur">' + Math.round(c.duration) + 's</span>' : '') + PLAY + '</button>' +
      '<div class=body><div class=title contenteditable=plaintext-only role=textbox aria-label="Clip title" data-title="' +
      title + '">' + title + '</div><div class=meta>' + escape(c.map) +
      '<span class=sep></span>' + (c.missing ? 'File missing' : c.size_mb + ' MB') + '</div>' +
      (targets ? '<div class=targets>' + targets + '</div>' : '') +
      '<div class=actions><button class="btn-icon fav ' + (c.favorite ? 'on' : '') +
      '" data-fav aria-pressed="' + Boolean(c.favorite) + '" aria-label="Favorite" title="Favorite">' + ic('star') +
      '</button><span class=spacer></span><button class=btn-icon aria-label="Share" title="Share" data-share' +
      (c.missing ? ' disabled' : '') + '>' + ic('share') +
      '</button><button class="btn-icon danger" aria-label="Delete" title="Delete" data-delete>' + ic('trash') +
      '</button></div></div></article>';
  }).join('');
  for (const card of $$('#clipGrid .card')) bindCard(card);
  updateSelection();
}

function bindCard(card) {
  const id = card.dataset.id;
  const title = card.querySelector('[data-title]');
  card.querySelector('[data-play]').onclick = event => {
    if (!selecting) return playVideo(clipMedia(id, 'video'));
    if (selected.has(id)) selected.delete(id); else selected.add(id);
    card.classList.toggle('sel', selected.has(id));
    event.currentTarget.setAttribute('aria-pressed', selected.has(id));
    updateSelection();
  };
  if (selecting) card.querySelector('[data-play]').setAttribute('aria-pressed', selected.has(id));
  title.onkeydown = e => { if (e.key === 'Enter') { e.preventDefault(); title.blur(); } };
  title.onblur = async () => {
    const text = title.textContent.trim();
    if (text === title.dataset.title) return;
    const r = await api(clipApi(id), jsonPost({title: text}));
    if (r.error) { title.textContent = title.dataset.title; toast(r.error); }
    else {
      const clip = library.find(c => c.id === id);
      if (clip) clip.title = r.title;
      title.textContent = title.dataset.title = r.title || 'Untitled';
    }
  };
  const favorite = card.querySelector('[data-fav]');
  favorite.onclick = () => busy(favorite, '', async () => {
    const r = await api(clipApi(id), jsonPost({favorite: favorite.getAttribute('aria-pressed') !== 'true'}));
    if (r.error) { toast(r.error); return; }
    const clip = library.find(c => c.id === id);
    if (clip) clip.favorite = r.favorite;
    favorite.classList.toggle('on', r.favorite);
    favorite.setAttribute('aria-pressed', r.favorite);
    if ($('#clipFilter').value === 'favorite') renderClips();
  });
  const share = card.querySelector('[data-share]');
  share.onclick = () => busy(share, '', async () => {
    const r = await api(clipApi(id) + '/share', {method:'POST'}, 320000);
    const statuses = Object.entries(r.results || {}).filter(([name]) => name !== 'gallery');
    toast(r.error || (statuses.length ? statuses.map(([name, status]) => name + ' · ' + status).join(' | ') : 'No sharing destinations are enabled.'));
    await loadClips();
  });
  const remove = card.querySelector('[data-delete]');
  remove.onclick = () => {
    if (!confirm('Delete this clip and its video file?')) return;
    busy(remove, '', async () => {
      const r = await api(clipApi(id), {method:'DELETE'});
      if (r.error) toast(r.error); else { toast('Clip deleted.'); await loadClips(true); }
    });
  };
}

function updateSelection() {
  $('#selBtn').style.display = selecting ? 'none' : '';
  $('#cancelSel').style.display = selecting ? '' : 'none';
  $('#selInfo').textContent = selecting ? selected.size + ' selected' : '';
  $('#selInfo').style.display = selecting ? '' : 'none';
  $('#makeMontage').style.display = selecting && selected.size ? '' : 'none';
}
$('#clipSearch').oninput = renderClips;
$('#clipFilter').onchange = renderClips;
$('#selBtn').onclick = () => { selecting = true; renderClips(); };
$('#cancelSel').onclick = () => { selecting = false; selected.clear(); renderClips(); };
$('#makeMontage').onclick = () => busy($('#makeMontage'), 'Building montage…', async () => {
  const r = await api('/api/montage', jsonPost({clip_ids:[...selected]}), 620000);
  if (!r.ok) { toast(r.error || 'Could not build the montage.'); return; }
  toast('Montage ready.');
  $('#cancelSel').click();
  openTab('montages');
});

async function loadMontages() {
  const r = await api('/api/montages');
  const grid = $('#montGrid');
  grid.replaceChildren();
  if (r.error) { grid.textContent = r.error; return; }
  if (!r.montages.length) {
    grid.innerHTML = '<div class=empty><strong>No montages yet</strong><div class=sub>Select clips from your library to build one.</div></div>';
    return;
  }
  for (const name of r.montages) {
    const button = document.createElement('button');
    button.textContent = name;
    button.onclick = () => playVideo('/montage/' + encodeURIComponent(name));
    grid.append(button);
  }
}
async function loadLogs() {
  const r = await api('/api/logs');
  const box = $('#logBox');
  box.textContent = r.error || (r.lines || []).join('\\n') || 'No activity yet.';
  box.scrollTop = box.scrollHeight;
}
$('#copyDiagnostics').onclick = () => busy($('#copyDiagnostics'), 'Copying…', async () => {
  const diagnostics = await api('/api/diagnostics');
  if (diagnostics.error) { toast(diagnostics.error); return; }
  try {
    await navigator.clipboard.writeText(JSON.stringify(diagnostics, null, 2));
    toast('Recorder diagnostics copied.');
  } catch {
    toast('Could not copy recorder diagnostics.');
  }
});

function playVideo(url) {
  playerTrigger = document.activeElement;
  $('#playerError').hidden = true;
  $('#player').src = url;
  $('#modal').classList.add('show');
  $('#modalClose').focus();
  $('#player').play().catch(() => {});
}
$('#player').onerror = () => {
  if ($('#player').getAttribute('src')) $('#playerError').hidden = false;
};
$('#modalClose').onclick = () => {
  const player = $('#player');
  $('#modal').classList.remove('show');
  player.pause();
  player.removeAttribute('src');
  player.load();
  playerTrigger?.focus();
};
$('#modal').onclick = e => { if (e.target === $('#modal')) $('#modalClose').click(); };
document.addEventListener('keydown', e => {
  if (e.key === 'Escape' && $('#modal').classList.contains('show')) $('#modalClose').click();
});

let updatePoll;
function showUpdate(r) {
  $('#upVer').textContent = 'v' + r.update.version;
  $('#upNotes').textContent = r.update.notes ? ' · ' + r.update.notes.split('\\n')[0].slice(0, 96) : '';
  $('#updateBanner').style.display = 'flex';
}
async function checkUpdate(manual = false) {
  const r = await api('/api/update/check');
  if (r.update) showUpdate(r);
  if (manual) $('#updStatus').textContent = r.error || (r.update ? 'Update available' : 'You’re on the latest version');
  const p = await api('/api/update/progress');
  if (p.state === 'downloading' || p.state === 'installing') pollUpdate();
}
function pollUpdate() {
  clearInterval(updatePoll);
  $('#upBar').style.display = 'block';
  $('#upBtn').disabled = true;
  updatePoll = setInterval(async () => {
    const p = await api('/api/update/progress');
    if (p.state === 'downloading') {
      $('#upBarFill').style.width = (p.pct || 0) + '%';
      $('#upBtn').textContent = p.total ? 'Downloading ' + p.pct + '%' : 'Downloading…';
    } else if (p.state === 'installing') {
      $('#upBarFill').style.width = '100%';
      $('#upBtn').textContent = 'Installing…';
    } else {
      clearInterval(updatePoll);
      $('#upBtn').disabled = false;
      $('#upBtn').textContent = 'Update now';
      $('#upBar').style.display = 'none';
      if (p.error || p.detail) toast(p.error || p.detail);
    }
  }, 750);
}
$('#upDismiss').onclick = () => { $('#updateBanner').style.display = 'none'; };
$('#upBtn').onclick = async () => {
  let started = false;
  await busy($('#upBtn'), 'Starting update…', async () => {
    const r = await api('/api/update/apply', {method:'POST'});
    started = r.ok;
    if (!started) toast(r.detail || r.error || 'Could not start the update.');
  });
  if (started) pollUpdate();
};
$('#checkUpd').onclick = () => busy($('#checkUpd'), 'Checking…', () => checkUpdate(true));
const setupMessage = sessionStorage.getItem('aegisSetupMessage');
if (setupMessage) { toast(setupMessage); sessionStorage.removeItem('aegisSetupMessage'); }
loadStatus();
loadClips();
if (%AUTO_UPDATE%) checkUpdate();
setInterval(loadStatus, 3000);
setInterval(() => {
  if ($('section[data-panel=logs]').style.display !== 'none') loadLogs();
  if ($('section[data-panel=clips]').style.display !== 'none' && !selecting &&
      !$('#clipGrid').contains(document.activeElement)) loadClips();
}, 5000);
</script></body></html>"""

SETUP_HTML = r"""<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Aegis Clipper · Settings</title><style>%CSS%
.wizard{max-width:1060px;display:grid;grid-template-columns:1fr 1fr;gap:16px;align-items:start}
.settings-heading,.settings-actions{grid-column:1/-1}
.settings-heading h1{margin:0;font-size:clamp(27px,4vw,42px);letter-spacing:-.04em}
.settings-heading p,.hint{color:var(--muted);margin:4px 0 14px}
.step{background:var(--panel);border:1px solid var(--line);border-radius:var(--r2);
  padding:clamp(16px,2.4vw,24px);min-width:0;scroll-margin-top:80px}
.step h2{margin:0 0 10px;font-size:18px;letter-spacing:-.015em}
.row{display:grid;grid-template-columns:minmax(124px,1fr) minmax(90px,1.35fr);
  gap:14px;align-items:center;padding:9px 0;border-top:1px solid var(--line)}
.row input[type=checkbox]{width:18px;height:18px;margin:0;accent-color:var(--accent)}
.statusline{font-size:13px;line-height:1.6;color:var(--muted);overflow-wrap:anywhere}
.statusline:empty{display:none}
.statusline.ok{color:var(--ok)}.statusline.err{color:var(--warn)}
.foot{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin:10px 0}
.settings-actions{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;padding:4px 0 24px}
details{margin-top:12px}summary{cursor:pointer;color:var(--txt);padding:4px 0 8px}
.channel{border-top:1px solid var(--line);padding-top:10px;margin-top:8px}
.channel h3{margin:0 0 6px;font-size:14px}
#testVideo{width:100%;margin-top:12px;border-radius:var(--r);background:#000}
@media(max-width:760px){.wizard{grid-template-columns:1fr}}
</style></head><body>
<header class=topbar>
  <div class=brand><svg class=logo width=28 height=28 viewBox="0 0 48 48" fill=none><path d="M24 3 41 9 41 24 C41 35 33 42 24 45 C15 42 7 35 7 24 L7 9 Z" fill="#161b24" stroke="#ff5a3c" stroke-width="2.6"/><path d="M20 16 33 24 20 32 Z" fill="#ff5a3c"/></svg> Aegis Clipper</div>
  <div class=settings-controls>
    <a class=settings-link id=backToLibrary href="/" hidden>Back to library</a>
    <button class=primary id=finishBtn>Save and open library</button>
  </div>
</header>
<main class=wizard>
  <div class=settings-heading><h1 id=settingsTitle>Capture settings</h1><p>Connect CS2 and check that your PC can record a replay.</p></div>
  <section class=step id=connection>
    <h2>Counter-Strike 2</h2>
    <div class=statusline id=detectOut role=status>Checking your Steam libraries…</div>
    <div class=foot>
      <button class=primary id=connectBtn>Connect CS2</button>
      <button class=ghost id=scanBtn>Scan again</button>
    </div>
    <details><summary>Use a custom CS2 installation</summary>
      <div class=row><label for=cs2_cfg_dir>CS2 cfg folder</label><input id=cs2_cfg_dir placeholder="…\csgo\cfg"></div>
    </details>
    <div class=statusline id=gsiOut role=status></div>
  </section>
  <section class=step>
    <h2>Recording</h2>
    <p class=hint>The built-in recorder captures video. Choose OBS if you want game audio in clips.</p>
    <div class=row><label for=rec_preset>Quality</label><select id=rec_preset>
      <option value=low>720p · 30 fps</option><option value=medium selected>900p · 30 fps</option>
      <option value=high>1080p · 60 fps</option><option value=source>Native · 60 fps</option>
    </select></div>
    <div class=row><label for=rec_performance>Prioritize game FPS</label><input type=checkbox id=rec_performance checked></div>
    <p class=hint>Limits capture to 30 fps, records at desktop resolution on the direct GPU path, and skips effects on automatic highlights.</p>
    <div class=row><label for=rec_clip>Replay length (seconds)</label><input type=number id=rec_clip min=5 max=120 value=30></div>
    <div class=row><label for=rec_gate>Capture only while CS2 is open</label><input type=checkbox id=rec_gate checked></div>
    <div class=row><label for=polish_en>Add clip intro and fades</label><input type=checkbox id=polish_en checked></div>
    <details id=obsDetails><summary>Use OBS instead</summary>
      <div class=row><label for=use_obs>Record with OBS</label><input type=checkbox id=use_obs></div>
      <div class=row><label for=obs_replay_dir>Replay folder</label><input id=obs_replay_dir placeholder="C:\Users\you\Videos"></div>
      <div class=row><label for=obs_port>WebSocket port</label><input type=number id=obs_port min=1 max=65535 value=4455></div>
      <div class=row><label for=obs_password>Password</label><input id=obs_password type=password></div>
    </details>
  </section>
  <section class=step id=capture-test>
    <h2>Test recording</h2>
    <p class=hint>Record five seconds of your screen to check video capture. The test is saved to your local library.</p>
    <div class=foot>
      <button class=primary id=captureBtn>Test screen capture</button>
      <button class=ghost id=previewBtn>Create sample clip</button>
    </div>
    <div class=statusline id=testOut role=status></div>
    <video id=testVideo controls playsinline hidden></video>
  </section>
  <section class=step>
    <h2>Automatic highlights</h2>
    <div class=row><label for=debounce>Streak gap (seconds)</label><input id=debounce type=number min=1 max=30 step=.1 value=7></div>
    <div class=row><label for=minkills>Minimum kills</label><input id=minkills type=number min=1 max=10 value=1></div>
    <p class=hint>Aegis saves one clip after you go this long without another kill.</p>
  </section>
  <section class=step style="grid-column:1/-1">
    <details><summary>Sharing destinations</summary>
      <div class=channel><h3>Telegram</h3>
        <div class=row><label for=tg_en>Send to Telegram</label><input type=checkbox id=tg_en></div>
        <div class=row><label for=tg_token>Bot token</label><input id=tg_token type=password></div>
        <div class=row><label for=tg_chat>Chat ID</label><input id=tg_chat placeholder="-100…"></div>
      </div>
      <div class=channel><h3>Discord</h3>
        <div class=row><label for=dc_en>Send to Discord</label><input type=checkbox id=dc_en></div>
        <div class=row><label for=dc_url>Webhook URL</label><input id=dc_url type=password></div>
      </div>
      <div class=channel><h3>YouTube</h3>
        <div class=row><label for=yt_en>Send to YouTube</label><input type=checkbox id=yt_en></div>
        <div class=row><label for=yt_secrets>OAuth credential file</label><input id=yt_secrets placeholder="client_secrets.json"></div>
        <div class=row><label for=yt_privacy>Privacy</label><select id=yt_privacy><option>unlisted</option><option>private</option><option>public</option></select></div>
      </div>
    </details>
  </section>
  <div class=settings-actions>
    <span class=statusline id=saveOut role=status></span>
  </div>
</main>
%EXIT_DIALOG%
<div class=toast id=toast role=status></div>
<script>
const $ = selector => document.querySelector(selector);
%API_JS%
let settingsLoaded = false, settingsBusy = false;
function message(id, text, type = '') {
  const el = $(id);
  el.textContent = text;
  el.className = 'statusline ' + type;
}
async function detect() {
  message('#detectOut', 'Checking your Steam libraries…');
  const d = await api('/api/detect');
  if (d.error) { message('#detectOut', d.error, 'err'); return; }
  if (d.cs2_cfg_dir && !$('#cs2_cfg_dir').value) $('#cs2_cfg_dir').value = d.cs2_cfg_dir;
  if (d.obs_replay_dir && !$('#obs_replay_dir').value) $('#obs_replay_dir').placeholder = d.obs_replay_dir;
  const game = d.gsi_installed ? 'CS2 integration installed.' : d.cs2_cfg_dir
    ? 'CS2 found. Connect it here or finish setup to install the integration.'
    : 'CS2 folder not found. Open the custom installation section to enter the path.';
  message('#detectOut', game + (d.ffmpeg ? ' FFmpeg found.' : ' FFmpeg is missing. Use the Windows installer or configure FFmpeg.'), d.gsi_installed && d.ffmpeg ? 'ok' : '');
}
async function loadExisting() {
  const c = await api('/api/config');
  if (c.error) { message('#saveOut', c.error, 'err'); return; }
  const r = c.recording || {}, o = c.obs || {}, e = c.engine || {}, u = c.uploads || {};
  const tg = u.telegram || {}, dc = u.discord || {}, yt = u.youtube || {};
  $('#settingsTitle').textContent = c.first_run ? 'Set up automatic clipping' : 'Capture settings';
  $('#backToLibrary').hidden = c.first_run;
  $('#rec_preset').value = r.preset || 'medium';
  $('#rec_performance').checked = r.prioritize_game_fps !== false;
  $('#rec_clip').value = r.clip_seconds ?? 30;
  $('#rec_gate').checked = r.only_when_game_running !== false;
  $('#polish_en').checked = (c.polish || {}).enabled !== false;
  $('#use_obs').checked = $('#obsDetails').open = r.backend === 'obs';
  $('#obs_replay_dir').value = o.replay_dir || '';
  $('#obs_port').value = o.port || 4455;
  $('#obs_password').value = o.password || '';
  $('#debounce').value = e.debounce_sec ?? 7;
  $('#minkills').value = e.min_kills ?? 1;
  $('#cs2_cfg_dir').value = e.cs2_cfg_dir || '';
  $('#tg_en').checked = !!tg.enabled;
  $('#tg_token').value = tg.bot_token || '';
  $('#tg_chat').value = tg.chat_id || '';
  $('#dc_en').checked = !!dc.enabled;
  $('#dc_url').value = dc.webhook_url || '';
  $('#yt_en').checked = !!yt.enabled;
  $('#yt_secrets').value = yt.client_secrets || '';
  $('#yt_privacy').value = yt.privacy || 'unlisted';
  settingsLoaded = true;
}
async function save() {
  if (!settingsLoaded) {
    message('#saveOut', 'Could not load settings. Reload this page and try again.', 'err');
    return false;
  }
  for (const field of ['#rec_clip', '#obs_port', '#debounce', '#minkills']) {
    const input = $(field);
    if (!input.value || !input.checkValidity()) {
      input.focus();
      message('#saveOut', 'Enter a value between ' + input.min + ' and ' + input.max + ' for ' + input.labels[0].textContent.toLowerCase() + '.', 'err');
      return false;
    }
  }
  const r = await api('/api/config', jsonPost({
    engine:{debounce_sec:$('#debounce').valueAsNumber, min_kills:$('#minkills').valueAsNumber},
    recording:{backend:$('#use_obs').checked ? 'obs' : 'builtin', preset:$('#rec_preset').value,
      prioritize_game_fps:$('#rec_performance').checked,
      clip_seconds:$('#rec_clip').valueAsNumber, only_when_game_running:$('#rec_gate').checked},
    polish:{enabled:$('#polish_en').checked},
    obs:{replay_dir:$('#obs_replay_dir').value.trim(), port:$('#obs_port').valueAsNumber, password:$('#obs_password').value},
    uploads:{
      telegram:{enabled:$('#tg_en').checked, bot_token:$('#tg_token').value.trim(), chat_id:$('#tg_chat').value.trim()},
      discord:{enabled:$('#dc_en').checked, webhook_url:$('#dc_url').value.trim()},
      youtube:{enabled:$('#yt_en').checked, client_secrets:$('#yt_secrets').value.trim(), privacy:$('#yt_privacy').value}
    }
  }));
  if (!r.ok) {
    message('#saveOut', r.error || 'Could not save settings.', 'err');
    toast(r.error || 'Could not save settings.');
  } else message('#saveOut', 'Settings saved.', 'ok');
  return r.ok;
}
function runSettings(button, label, action) {
  if (settingsBusy) { toast('A settings action is still running.'); return; }
  settingsBusy = true;
  return busy(button, label, action).finally(() => { settingsBusy = false; });
}
$('#scanBtn').onclick = () => runSettings($('#scanBtn'), 'Scanning…', detect);
$('#connectBtn').onclick = () => runSettings($('#connectBtn'), 'Connecting…', async () => {
  const r = await api('/api/install-gsi', jsonPost({cs2_cfg_dir: $('#cs2_cfg_dir').value.trim()}));
  if (!r.ok) { message('#gsiOut', r.error || 'Could not install the CS2 integration.', 'err'); return; }
  message('#gsiOut', r.restart_required ? 'Integration installed. Restart CS2 if it was open.' : 'The integration is already installed.', 'ok');
  await detect();
});
function testClip(button, capture) {
  return runSettings(button, capture ? 'Recording…' : 'Building sample…', async () => {
    if (!(await save())) { message('#testOut', 'Check your settings before testing.', 'err'); return; }
    const video = $('#testVideo');
    video.pause();
    video.hidden = true;
    message('#testOut', capture ? 'Recording five seconds. Aegis will try another capture method if needed.' : 'Generating a sample with a test pattern and tone.');
    const r = await api(capture ? '/api/capture-test' : '/api/test-clip', {method:'POST'}, 100000);
    if (!r.ok) { message('#testOut', r.detail || r.error || 'Could not create the clip.', 'err'); return; }
    video.src = '/clip/' + encodeURIComponent(r.clip_id) + '/video';
    video.hidden = false;
    message('#testOut', capture ? 'Screen test saved. Play it to check the image.' : 'Sample saved to your clip library.', 'ok');
  });
}
$('#captureBtn').onclick = () => testClip($('#captureBtn'), true);
$('#previewBtn').onclick = () => testClip($('#previewBtn'), false);
$('#testVideo').onerror = () => message('#testOut', 'The test was saved but video playback failed.', 'err');
$('#finishBtn').onclick = () => runSettings($('#finishBtn'), 'Saving…', async () => {
  if (!(await save())) return;
  const r = await api('/api/finish-setup', {method:'POST'});
  if (!r.ok) { message('#saveOut', r.error || 'Could not finish setup.', 'err'); return; }
  if (r.warning || r.restart_required) sessionStorage.setItem('aegisSetupMessage',
    r.warning || 'CS2 integration installed. Restart CS2 if it was already open.');
  location.href = '/';
});
loadExisting().then(detect);
</script></body></html>"""

_API_JS = r"""
let toastTimer;
function toast(text) {
  const el = document.querySelector('#toast');
  el.textContent = text;
  el.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('show'), 4200);
}
const jsonPost = body => ({method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
async function api(url, options, timeout = 15000) {
  try {
    const res = await fetch(url, {...options, signal:AbortSignal.timeout(timeout)});
    const payload = await res.json().catch(() => ({}));
    if (!res.ok) return {...payload, ok:false, error:payload.error || payload.detail || 'Request failed (' + res.status + ').'};
    return payload;
  } catch (error) {
    return {ok:false, error:error.name === 'TimeoutError' ? 'Aegis took too long to respond.' : 'Could not connect to Aegis. Check that the app is running.'};
  }
}
async function busy(button, label, action) {
  if (button.getAttribute('aria-busy') === 'true') return;
  const text = button.textContent;
  button.disabled = true;
  button.setAttribute('aria-busy', 'true');
  if (label) button.textContent = label;
  try {
    return await action();
  } catch (error) {
    console.error(error);
    toast('Something went wrong. Check Activity for details.');
  } finally {
    if (label) button.textContent = text;
    button.disabled = false;
    button.removeAttribute('aria-busy');
  }
}
"""

_EXIT_DIALOG = r"""
<div class=modal id=exitDialog role=dialog aria-modal=true aria-labelledby=exitTitle><div class=dialog>
  <h3 id=exitTitle>Close Aegis Clipper?</h3>
  <p>Run Aegis in the background to keep saving highlights while you play.</p>
  <div class=dialog-actions>
    <button class=primary id=bgBtn>Run in background</button>
    <button class=ghost id=quitBtn>Quit</button>
    <button class=ghost id=exitCancel>Cancel</button>
  </div>
</div></div>
<script>
{
  const dialog = document.querySelector('#exitDialog');
  const background = document.querySelector('#bgBtn');
  const cancel = document.querySelector('#exitCancel');
  const quit = document.querySelector('#quitBtn');
  let previous;
  function closeChoice() {
    dialog.classList.remove('show');
    previous?.focus();
  }
  window.__exitChoice = (trayAvailable = true) => {
    previous = document.activeElement;
    background.hidden = !trayAvailable;
    dialog.classList.add('show');
    (trayAvailable ? background : cancel).focus();
    return true;
  };
  dialog.onclick = e => { if (e.target === dialog) closeChoice(); };
  cancel.onclick = closeChoice;
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && dialog.classList.contains('show')) {
      e.stopImmediatePropagation();
      closeChoice();
    }
  });
  background.onclick = () => { closeChoice(); window.pywebview?.api?.background(); };
  quit.onclick = () => {
    quit.disabled = true;
    quit.textContent = 'Quitting…';
    window.pywebview?.api?.quit();
  };
}
</script>
"""

def _shared(page: str) -> str:
    return page.replace("%CSS%", _BASE_CSS).replace("%API_JS%", _API_JS).replace("%EXIT_DIALOG%", _EXIT_DIALOG)


DASHBOARD_HTML = _shared(DASHBOARD_HTML)
SETUP_HTML = _shared(SETUP_HTML)
