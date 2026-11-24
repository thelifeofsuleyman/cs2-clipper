"""Self-contained HTML pages (inline CSS + vanilla JS).

Kept as Python strings so PyInstaller has no template/static files to locate.
The pages are static shells; all data flows through the JSON API in web.py.
"""

_BASE_CSS = """
:root{
  --bg:#101216; --panel:#171a20; --panel2:#20242c; --line:#2b303a; --line2:#3b424f;
  --txt:#eff1f5; --muted:#a6afbd; --faint:#858e9e;
  --accent:#ff8b6d; --accent2:#94bcff; --ok:#75dcb5; --warn:#f5bd65; --err:#ff818e;
  --r:10px; --r2:14px; --shadow:0 10px 30px rgba(0,0,0,.45);
}
*{box-sizing:border-box}
html{color-scheme:dark}
body{margin:0;color:var(--txt);background:var(--bg);
  font:14px/1.55 'Segoe UI Variable Text','Segoe UI',system-ui,-apple-system,sans-serif}
[hidden]{display:none!important}
:focus-visible{outline:2px solid var(--accent2);outline-offset:3px}
a{color:var(--accent2);text-decoration:none}
.ico{width:18px;height:18px;flex:none;fill:none;stroke:currentColor;stroke-width:2;
  stroke-linecap:round;stroke-linejoin:round}
button{font:inherit;cursor:pointer;border:1px solid var(--line);border-radius:var(--r);
  padding:9px 14px;background:var(--panel2);color:var(--txt);font-weight:500;
  display:inline-flex;align-items:center;gap:8px;transition:.14s}
button:hover{background:#20252e;border-color:var(--line2)}
button:active{transform:translateY(1px)}
button:disabled{opacity:.5;cursor:default}
button.primary{background:var(--accent);border-color:transparent;color:#21130f;font-weight:700}
button.primary:hover:not(:disabled){background:#ffa389}
button.ghost{background:transparent}
.btn-icon{width:34px;height:34px;padding:0;justify-content:center;color:var(--muted)}
.btn-icon:hover{color:var(--txt)}
.btn-icon.danger:hover{color:var(--err);border-color:var(--err)}
input,select{font:inherit;background:#0f1218;border:1px solid var(--line);color:var(--txt);
  border-radius:var(--r);padding:10px 12px;width:100%;transition:.14s}
input:focus,select:focus{outline:none;border-color:var(--accent2);box-shadow:0 0 0 3px rgba(76,159,254,.16)}
header.topbar{display:flex;align-items:center;gap:16px;padding:13px 24px;
  background:#14171c;
  border-bottom:1px solid var(--line);position:sticky;top:0;z-index:20}
.brand{display:flex;align-items:center;gap:11px;font-weight:650;font-size:15px;letter-spacing:.2px}
.brand .logo{filter:drop-shadow(0 1px 5px rgba(255,90,57,.35))}
main{width:100%;max-width:min(1560px,96vw);margin:0 auto;padding:clamp(16px,2.2vw,30px) clamp(14px,1.8vw,28px)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:16px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:var(--r2);overflow:hidden;
  display:flex;flex-direction:column;transition:border-color .16s}
.card:hover,.card:focus-within{border-color:var(--line2)}
.card .thumb{position:relative;aspect-ratio:16/9;background:#05070a;cursor:pointer;overflow:hidden}
.card .thumb img{width:100%;height:100%;object-fit:cover}
.card .thumb .play{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
  opacity:.8;transition:.16s;background:linear-gradient(transparent,rgba(0,0,0,.25))}
.card .thumb:hover .play,.card .thumb:focus-visible .play{opacity:1}
.play .pbtn{width:46px;height:46px;border-radius:50%;background:rgba(10,12,16,.6);
  backdrop-filter:blur(4px);border:1px solid rgba(255,255,255,.25);display:grid;place-items:center}
.play .ico{width:20px;height:20px;fill:#fff;stroke:none;margin-left:2px}
.badge{position:absolute;top:9px;left:9px;background:var(--accent);color:#21130f;font-weight:700;
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
.toast{position:fixed;bottom:22px;left:50%;transform:translateX(-50%) translateY(8px);
  background:var(--panel2);border:1px solid var(--line2);padding:12px 18px;border-radius:var(--r);
  box-shadow:var(--shadow);z-index:60;opacity:0;transition:.25s;font-size:13px}
.toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
.topbar .settings-link,.topbar .settings-controls{margin-left:auto}
.settings-controls{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.settings-controls .settings-link{margin-left:0}
.settings-controls [hidden]{display:none}
.settings-link{color:var(--txt);background:var(--panel2);border:1px solid var(--line);
  border-radius:var(--r);padding:8px 14px;font-weight:600}
.settings-link:hover{border-color:var(--line2);background:#20252e}
.desktop{min-height:100vh;display:grid;grid-template-columns:210px minmax(0,1fr)}
.rail{position:sticky;top:0;height:100vh;display:flex;flex-direction:column;gap:32px;padding:22px 14px;
  background:#14171c;border-right:1px solid var(--line)}
.rail .brand{padding:0 7px;white-space:nowrap}
.rail nav{display:grid;gap:5px}
.rail-item{display:flex;align-items:center;gap:11px;padding:9px 11px;border:1px solid transparent;
  border-radius:8px;background:transparent;color:var(--muted);font-weight:600;text-align:left}
.rail-item:hover{background:var(--panel2);color:var(--txt)}
.rail-item[aria-current],.rail-item[aria-pressed=true]{background:#30231f;border-color:#523329;color:var(--accent)}
.rail-foot{margin-top:auto;padding:0 7px;display:grid;gap:9px;color:var(--faint);font-size:12px}
.rail-foot button{justify-self:start;padding:6px 9px;font-size:12px;color:var(--muted)}
.workspace{max-width:1440px;padding:clamp(24px,3vw,48px);min-width:0}
.page-heading{margin-bottom:22px}
.page-heading h1{font-size:clamp(30px,4vw,42px);line-height:1.1;letter-spacing:-.045em;margin:0}
.capture-panel{display:flex;align-items:center;justify-content:space-between;gap:18px;
  padding:18px 20px;margin:0 0 28px;background:var(--panel);border:1px solid var(--line);border-radius:var(--r2)}
.capture-info{display:flex;gap:14px;align-items:center;min-width:0}
.capture-symbol,.empty-symbol{display:grid;place-items:center;flex:none;width:42px;height:42px;
  border-radius:11px;background:#30241f;color:var(--accent)}
.capture-panel[data-ready=true] .capture-symbol{background:#1b352e;color:var(--ok)}
.capture-panel h2{font-size:16px;line-height:1.25;margin:0 0 3px}
.capture-panel p{margin:0;color:var(--muted);max-width:62ch;overflow-wrap:anywhere}
.capture-actions{display:flex;gap:9px;align-items:center;flex-wrap:wrap;flex:none}
.library-bar{justify-content:space-between;min-height:43px}
.library-count{color:var(--muted);font-size:13px}
.library-tools{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.search{display:flex;align-items:center;gap:8px;background:#12151b;border:1px solid var(--line);
  border-radius:var(--r);padding-left:11px;color:var(--muted)}
.search:focus-within{border-color:var(--accent2)}
.search input{width:min(210px,45vw);padding:8px 10px 8px 0;background:none;border:0;box-shadow:none}
.library-tools select{width:auto;padding:8px 10px}
.card button.thumb{display:block;border:0;border-radius:0;padding:0;width:100%;color:var(--txt)}
.thumb:focus-visible{outline-offset:-3px;z-index:1}
.card .thumb img{display:block}
.empty{min-height:260px;background:var(--panel);border:1px dashed var(--line2);border-radius:var(--r2)}
.empty-symbol .ico{width:22px;height:22px;color:inherit;stroke:currentColor;margin:0}
.empty strong{font-size:17px;color:var(--txt);margin-top:5px}
.empty a{margin-top:5px}
.empty .sub{color:var(--muted)}
.loading-msg,.panel-error{grid-column:1/-1;color:var(--muted);padding:24px}
.panel-error{color:var(--warn)}
.modal .player-error{position:absolute;bottom:14%;background:var(--panel);padding:14px;border-radius:var(--r)}
.toast{pointer-events:none;max-width:min(560px,92vw)}
button[aria-busy=true]{cursor:progress}
@media(max-width:925px){.capture-panel{align-items:flex-start;flex-direction:column}}
@media(max-width:760px){
  .desktop{display:block}.rail{position:static;height:auto;gap:12px;padding:12px 16px;border-right:0;border-bottom:1px solid var(--line)}
  .rail nav{display:flex;flex-wrap:wrap}.rail-foot{display:flex;flex-wrap:wrap;align-items:center;gap:12px}
  .workspace{padding:22px 16px}.library-tools{width:100%}
}
/* Adapt to any resolution / window size */
@media(max-width:820px){
  header.topbar{flex-wrap:wrap;gap:10px;padding:11px 16px}
  .grid{grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:13px}
}
@media(max-width:480px){
  .grid{grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px}
  .modal{padding:12px}
}
"""

DASHBOARD_HTML = """<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Aegis Clipper</title><style>%CSS%</style></head><body>
<div class=desktop>
<aside class=rail>
  <div class=brand><svg class=logo width=28 height=28 viewBox="0 0 48 48" fill=none><path d="M24 3 41 9 41 24 C41 35 33 42 24 45 C15 42 7 35 7 24 L7 9 Z" fill="#161b24" stroke="#ff5a3c" stroke-width="2.6"/><path d="M20 16 33 24 20 32 Z" fill="#ff5a3c"/></svg> Aegis Clipper</div>
  <nav aria-label="Main navigation">
    <button class=rail-item data-tab=clips aria-pressed=true>%FILM_ICON% Clip library</button>
    <button class=rail-item data-tab=favorites aria-pressed=false>%STAR_ICON% Favorites</button>
    <button class=rail-item data-tab=logs aria-pressed=false>%ACTIVITY_ICON% Activity</button>
    <a class=rail-item href="/setup">%SETTINGS_ICON% Settings</a>
  </nav>
  <div class=rail-foot>
    <a href="https://github.com/thelifeofsuleyman/cs2-clipper/releases" target=_blank rel=noopener>Version %VER%</a>
    <button class=ghost id=checkUpd>Check for updates</button>
    <span id=updStatus role=status></span>
  </div>
</aside>
<main class=workspace>
  <header class=page-heading><h1 id=pageTitle>Clip library</h1></header>
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
  <section class=capture-panel id=capturePanel aria-label="Capture status">
    <div class=capture-info>
      <span class=capture-symbol>%ACTIVITY_ICON%</span>
      <div><h2 id=captureTitle>Connecting to Aegis</h2><p id=captureDetail aria-live=polite>Checking the replay buffer.</p></div>
    </div>
    <div class=capture-actions>
      <a class=settings-link href="/setup#connection" id=connectionLink>CS2 setup</a>
      <button class=primary id=saveReplay disabled>Save replay</button>
    </div>
  </section>

  <section data-panel=clips>
    <div class="bar library-bar">
      <span class=library-count id=clipCount></span>
      <div class=library-tools>
        <label class=search>%SEARCH_ICON%<input type=search id=clipSearch aria-label="Search clips" placeholder="Search clips"></label>
        <select id=clipFilter aria-label="Filter clips"><option value=all>All clips</option><option value=test>Test clips</option></select>
      </div>
    </div>
    <div class=grid id=clipGrid><div class=loading-msg>Loading clips…</div></div>
  </section>

  <section data-panel=logs hidden>
    <div class=bar>
      <button class=ghost id=copyDiagnostics>Copy recorder diagnostics</button>
      <a class=settings-link href="https://github.com/thelifeofsuleyman/cs2-clipper/issues/new?template=recording.yml" target=_blank rel=noopener>Report a recording issue</a>
    </div>
    <p class=library-count id=footStatus></p>
    <div class=logbox id=logBox>Loading…</div>
  </section>
</main>
</div>

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
};
const ic=n=>`<svg class=ico viewBox="0 0 24 24">${ICONS[n]||''}</svg>`;
const PLAY=`<div class=play><div class=pbtn>${ic('play')}</div></div>`;
let library = [], activePage = 'clips', clipRequest = 0, fingerprint = '';
let playerTrigger;
const escape = value => String(value ?? '').replace(/[&<>"']/g, ch => ({
  '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'
}[ch]));
const clipApi = id => '/api/clips/' + encodeURIComponent(id);
const clipMedia = (id, kind) => '/clip/' + encodeURIComponent(id) + '/' + kind;

function openTab(tab) {
  const previous = activePage;
  activePage = tab;
  for (const b of $$('.rail button[data-tab]')) b.setAttribute('aria-pressed', b.dataset.tab === tab);
  $('#pageTitle').textContent = {clips:'Clip library', favorites:'Favorites', logs:'Activity'}[tab];
  $('section[data-panel=clips]').hidden = tab === 'logs';
  $('section[data-panel=logs]').hidden = tab !== 'logs';
  if (tab === 'logs') loadLogs();
  else if (previous !== tab) {
    $('#clipSearch').value = '';
    $('#clipFilter').value = 'all';
    renderClips();
  }
}
for (const b of $$('.rail button[data-tab]')) b.onclick = () => openTab(b.dataset.tab);

async function loadStatus() {
  const s = await api('/api/status');
  const rec = s.recorder || {};
  const replay = $('#saveReplay');
  const states = {
    waiting_game: ['Waiting for CS2', 'Open Counter-Strike 2 to start the rolling replay buffer.'],
    starting: ['Starting capture', 'Aegis is preparing the replay buffer.'],
    error: ['Capture unavailable', rec.detail || 'Open Activity to see recording errors.'],
    idle: ['Capture idle', rec.backend === 'obs' ? 'Start the Replay Buffer in OBS.' : 'Open CS2 or check capture settings.']
  };
  const status = s.error ? ['Aegis disconnected', s.error] : s.capturing
    ? ['Replay buffer ready', s.gsi_connected
      ? 'CS2 is connected. Highlights save automatically when your streak ends.'
      : 'You can save replays now. Automatic highlights will start once CS2 sends game updates.']
    : states[rec.state] || states.idle;
  if ($('#captureTitle').textContent !== status[0]) $('#captureTitle').textContent = status[0];
  const detail = s.pending_kills && s.capturing && s.gsi_connected
    ? s.pending_kills + (s.pending_kills === 1 ? ' kill in the current highlight.' : ' kills in the current highlight.')
    : status[1];
  const audio = rec.audio === 'unavailable' ? ' Speaker audio is unavailable.' : '';
  if ($('#captureDetail').textContent !== detail + audio) $('#captureDetail').textContent = detail + audio;
  $('#capturePanel').dataset.ready = Boolean(s.capturing);
  $('#connectionLink').hidden = Boolean(s.gsi_connected);
  replay.disabled = !s.capturing || replay.getAttribute('aria-busy') === 'true';
  $('#footStatus').textContent = rec.encoder && rec.encoder !== '?' ? rec.encoder +
    (rec.method ? ' · ' + rec.method : '') + (rec.fps ? ' · capture target ' + rec.fps + ' fps' : '') +
    (rec.audio ? ' · speaker audio ' + rec.audio : '') : '';
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
  renderClips();
}

function renderClips() {
  const query = $('#clipSearch').value.trim().toLowerCase();
  const filter = $('#clipFilter').value;
  const favorites = activePage === 'favorites';
  const scope = favorites ? library.filter(c => c.favorite) : library;
  const clips = scope.filter(c => {
    const tags = Array.isArray(c.tags) ? c.tags : [];
    return (filter === 'all' || tags.includes('test')) &&
      (!query || [c.title, c.map, ...tags].join(' ').toLowerCase().includes(query));
  });
  $('#clipCount').textContent = clips.length + (clips.length === 1 ? ' clip' : ' clips');
  const g = $('#clipGrid');
  if (!clips.length) {
    const title = scope.length ? 'No matching clips' : favorites ? 'No favorites yet' : 'Your clips will appear here';
    const detail = scope.length ? 'Try another search or filter.' : favorites ? 'Star a clip to find it here later.' :
      'Play CS2 to capture highlights automatically, or save a replay while the buffer is ready.';
    g.innerHTML = '<div class=empty><span class=empty-symbol>' + ic(favorites ? 'star' : 'film') + '</span><strong>' + title +
      '</strong><div class=sub>' + detail + '</div>' + (!favorites && !scope.length ?
        '<a href="/setup#capture-test">Test your recording setup</a>' : '') + '</div>';
    return;
  }
  g.innerHTML = clips.map(c => {
    const id = escape(c.id), title = escape(c.title || 'Untitled');
    const kill = c.kills === 5 ? 'ACE' : c.kills ? c.kills + 'K' : '';
    const statuses = Object.entries(c.uploads || {}).filter(([name]) => name !== 'gallery');
    const targets = statuses.map(([name, status]) =>
      '<span class="tg ' + (status === 'ok' ? 'ok' : 'err') + '" title="' + escape(status) + '">' + escape(name) + '</span>').join('');
    return '<article class=card data-id="' + id + '">' +
      '<button class=thumb data-play aria-label="Play ' + title + '"' + (c.missing ? ' disabled' : '') + '>' +
      (c.missing ? '' : '<img src="' + clipMedia(c.id, 'thumb') + '" alt="" loading=lazy>') +
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
}

function bindCard(card) {
  const id = card.dataset.id;
  const title = card.querySelector('[data-title]');
  card.querySelector('[data-play]').onclick = () => playVideo(clipMedia(id, 'video'));
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
    if (activePage === 'favorites') renderClips();
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

$('#clipSearch').oninput = renderClips;
$('#clipFilter').onchange = renderClips;
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
  if (activePage === 'logs') loadLogs();
  else if (!$('#clipGrid').contains(document.activeElement)) loadClips();
}, 5000);
</script></body></html>"""

SETUP_HTML = r"""<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Aegis Clipper · Settings</title><style>%CSS%
.wizard{max-width:1010px;padding:clamp(22px,4vw,48px);padding-bottom:22px}
.settings-layout{display:grid;grid-template-columns:170px minmax(0,1fr);gap:24px;align-items:start}
.settings-nav{position:sticky;top:83px;display:grid;gap:5px}
.hint{color:var(--muted);margin:6px 0 16px}
.step{background:var(--panel);border:1px solid var(--line);border-radius:var(--r2);
  padding:clamp(15px,2.5vw,26px);min-width:0}
.step h2{margin:0 0 8px;font-size:20px;letter-spacing:-.02em}
.row{display:grid;grid-template-columns:minmax(120px,1.4fr) minmax(90px,1fr);
  gap:15px;align-items:center;padding:13px 0;border-top:1px solid var(--line)}
.row label{font-weight:600}.row small{display:block;color:var(--muted);font-weight:400;margin-top:2px}
.row input[type=checkbox]{appearance:none;width:38px;height:22px;padding:0;margin:0;justify-self:end;
  border-radius:99px;background:#333944;position:relative;cursor:pointer}
.row input[type=checkbox]::before{content:'';position:absolute;left:3px;top:3px;width:14px;height:14px;border-radius:50%;background:#c4cbd5}
.row input[type=checkbox]:checked{background:var(--accent);border-color:var(--accent)}
.row input[type=checkbox]:checked::before{left:19px;background:#281611}
.row input:disabled,.row select:disabled{opacity:.55}
.statusline{font-size:13px;line-height:1.6;color:var(--muted);overflow-wrap:anywhere}
.statusline:empty{display:none}
.statusline.ok{color:var(--ok)}.statusline.err{color:var(--warn)}
.foot{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin:10px 0}
.settings-actions{position:sticky;bottom:0;z-index:5;display:flex;align-items:center;gap:12px;justify-content:space-between;
  flex-wrap:wrap;padding:12px 14px;margin-top:20px;background:#20242c;border:1px solid var(--line2);border-radius:var(--r2)}
.settings-actions .foot{margin:0 0 0 auto}
details{margin-top:12px;border-top:1px solid var(--line)}summary{cursor:pointer;color:var(--txt);font-weight:600;padding:10px 0}
#testVideo{width:100%;margin-top:12px;border-radius:var(--r);background:#000}
@media(max-width:660px){.settings-layout{display:block}.settings-nav{position:static;display:flex;flex-wrap:wrap;margin-bottom:16px}}
@media(max-width:420px){.row{grid-template-columns:minmax(0,1fr);gap:6px}.row input[type=checkbox]{justify-self:start}}
</style></head><body>
<header class=topbar>
  <div class=brand><svg class=logo width=28 height=28 viewBox="0 0 48 48" fill=none><path d="M24 3 41 9 41 24 C41 35 33 42 24 45 C15 42 7 35 7 24 L7 9 Z" fill="#161b24" stroke="#ff5a3c" stroke-width="2.6"/><path d="M20 16 33 24 20 32 Z" fill="#ff5a3c"/></svg> Aegis Clipper</div>
  <div class=settings-controls>
    <a class=settings-link id=backToLibrary href="/" hidden>Back to library</a>
  </div>
</header>
<main class=wizard>
  <header class=page-heading><h1 id=settingsTitle>Settings</h1></header>
  <div class=settings-layout>
  <nav class=settings-nav aria-label="Settings sections">
    <a class=rail-item href="#recording">Recording</a>
    <a class=rail-item href="#connection">CS2 connection</a>
    <a class=rail-item href="#highlights">Highlights</a>
    <a class=rail-item href="#capture-test">Test recording</a>
    <a class=rail-item href="#sharing">Sharing</a>
  </nav>
  <div>
  <section class=step id=connection data-settings-panel hidden>
    <h2>Counter-Strike 2</h2>
    <p class=hint>Connect CS2 so Aegis knows when to save your highlights.</p>
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
  <section class=step id=recording data-settings-panel hidden>
    <h2>Recording</h2>
    <div class=row><label for=rec_backend>Recorder</label><select id=rec_backend>
      <option value=builtin>Built-in</option><option value=obs>OBS Studio</option>
    </select></div>
    <div id=builtinFields>
    <div class=row><label for=rec_clip>Manual replay length<small>Seconds saved by Save replay.</small></label><input type=number id=rec_clip min=5 max=120 value=30></div>
    <div class=row><label for=speaker_audio>Capture speaker audio<small>Includes all sounds on the default Windows playback device.</small></label><input type=checkbox id=speaker_audio></div>
    <div class=row><label for=rec_performance>Prioritize game FPS<small>Records at up to 30 FPS, uses the GPU directly when supported, and skips highlight effects.</small></label><input type=checkbox id=rec_performance checked></div>
    <div class=row><label for=rec_gate>Capture only while CS2 is open</label><input type=checkbox id=rec_gate checked></div>
    <details id=qualityDetails><summary>Advanced capture quality</summary>
    <div class=row><label for=rec_preset>Quality preset<small id=qualityHint></small></label><select id=rec_preset>
      <option value=low>720p · 30 fps</option><option value=medium selected>900p · 30 fps</option>
      <option value=high>1080p · 60 fps</option><option value=source>Native · 60 fps</option>
    </select></div>
    </details>
    </div>
    <div id=obsFields hidden>
      <p class=hint>Enable Replay Buffer and its WebSocket server in OBS. Set replay length and quality in OBS.</p>
      <div class=row><label for=obs_replay_dir>Replay folder</label><input id=obs_replay_dir placeholder="C:\Users\you\Videos"></div>
      <div class=row><label for=obs_port>WebSocket port</label><input type=number id=obs_port min=1 max=65535 value=4455></div>
      <div class=row><label for=obs_password>Password</label><input id=obs_password type=password></div>
    </div>
  </section>
  <section class=step id=capture-test data-settings-panel hidden>
    <h2>Test recording</h2>
    <p class=hint id=testHelp>Record five seconds of your screen outside a match. Test clips are saved in your library.</p>
    <div class=foot>
      <button class=primary id=captureBtn>Test screen capture</button>
      <button class=ghost id=previewBtn>Create sample clip</button>
    </div>
    <div class=statusline id=testOut role=status></div>
    <video id=testVideo controls playsinline hidden></video>
  </section>
  <section class=step id=highlights data-settings-panel hidden>
    <h2>Automatic highlights</h2>
    <p class=hint>Aegis joins short moments around kills and cuts longer gaps between them.</p>
    <div class=row><label for=debounce>Streak gap in seconds<small>Aegis waits this long after a kill before saving the streak.</small></label><input id=debounce type=number min=1 max=30 step=.1 value=7></div>
    <div class=row><label for=minkills>Minimum kills</label><input id=minkills type=number min=1 max=10 value=1></div>
    <div class=row><label for=polish_en>Add clip intro and fades<small id=effectsHint></small></label><input type=checkbox id=polish_en checked></div>
  </section>
  <section class=step id=sharing data-settings-panel hidden>
    <h2>Sharing destinations</h2>
    <p class=hint>Connect a destination to share clips from your library.</p>
      <details><summary>Telegram</summary>
        <div class=row><label for=tg_en>Send to Telegram</label><input type=checkbox id=tg_en></div>
        <div class=row><label for=tg_token>Bot token</label><input id=tg_token type=password></div>
        <div class=row><label for=tg_chat>Chat ID</label><input id=tg_chat placeholder="-100…"></div>
      </details>
      <details><summary>Discord</summary>
        <div class=row><label for=dc_en>Send to Discord</label><input type=checkbox id=dc_en></div>
        <div class=row><label for=dc_url>Webhook URL</label><input id=dc_url type=password></div>
      </details>
      <details><summary>YouTube</summary>
        <div class=row><label for=yt_en>Send to YouTube</label><input type=checkbox id=yt_en></div>
        <div class=row><label for=yt_secrets>OAuth credential file</label><input id=yt_secrets placeholder="client_secrets.json"></div>
        <div class=row><label for=yt_privacy>Privacy</label><select id=yt_privacy><option>unlisted</option><option>private</option><option>public</option></select></div>
      </details>
  </section>
  </div>
  </div>
  <div class=settings-actions>
    <span class=statusline id=saveOut role=status>Loading settings…</span>
    <div class=foot><button class=ghost id=discardBtn hidden>Discard changes</button>
      <button class=primary id=finishBtn disabled>Save settings</button></div>
  </div>
</main>
%EXIT_DIALOG%
<div class=toast id=toast role=status></div>
<script>
const $ = selector => document.querySelector(selector);
%API_JS%
let savedSettings, firstRun = false, settingsBusy = false;
const panels = [...document.querySelectorAll('[data-settings-panel]')];
const links = [...document.querySelectorAll('.settings-nav a')];
function showSettingsSection(section) {
  if (!panels.some(panel => panel.id === section)) section = firstRun ? 'connection' : 'recording';
  for (const panel of panels) panel.hidden = panel.id !== section;
  for (const link of links) {
    if (link.hash === '#' + section) link.setAttribute('aria-current', 'page');
    else link.removeAttribute('aria-current');
  }
}
window.addEventListener('hashchange', () => showSettingsSection(location.hash.slice(1)));
function message(id, text, type = '') {
  const el = $(id);
  el.textContent = text;
  el.className = 'statusline ' + type;
}
async function detect() {
  message('#detectOut', 'Checking your Steam libraries…');
  const d = await api('/api/detect');
  if (d.error) { message('#detectOut', d.error, 'err'); return; }
  if (d.cs2_cfg_dir) $('#cs2_cfg_dir').placeholder = d.cs2_cfg_dir;
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
  firstRun = c.first_run;
  $('#settingsTitle').textContent = firstRun ? 'Set up Aegis Clipper' : 'Settings';
  $('#backToLibrary').hidden = firstRun;
  $('#finishBtn').textContent = firstRun ? 'Finish setup' : 'Save settings';
  $('#rec_backend').value = r.backend === 'obs' ? 'obs' : 'builtin';
  $('#rec_preset').value = r.preset || 'medium';
  $('#rec_performance').checked = r.prioritize_game_fps !== false;
  $('#speaker_audio').checked = Boolean(r.speaker_audio);
  $('#rec_clip').value = r.clip_seconds ?? 30;
  $('#rec_gate').checked = r.only_when_game_running !== false;
  $('#polish_en').checked = (c.polish || {}).enabled !== false;
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
  savedSettings = readSettings();
  renderSettings();
  showSettingsSection(location.hash.slice(1));
}
function readSettings() {
  const backend = $('#rec_backend').value;
  const clip = $('#rec_clip');
  const port = $('#obs_port');
  return {
    engine:{debounce_sec:$('#debounce').valueAsNumber, min_kills:$('#minkills').valueAsNumber,
      cs2_cfg_dir:$('#cs2_cfg_dir').value.trim()},
    recording:{backend, preset:$('#rec_preset').value,
      prioritize_game_fps:$('#rec_performance').checked,
      speaker_audio:$('#speaker_audio').checked,
      clip_seconds:backend === 'obs' && (!clip.value || !clip.checkValidity()) ? savedSettings?.recording.clip_seconds : clip.valueAsNumber,
      only_when_game_running:$('#rec_gate').checked},
    polish:{enabled:$('#polish_en').checked},
    obs:{replay_dir:$('#obs_replay_dir').value.trim(), password:$('#obs_password').value,
      port:backend === 'builtin' && (!port.value || !port.checkValidity()) ? savedSettings?.obs.port : port.valueAsNumber},
    uploads:{
      telegram:{enabled:$('#tg_en').checked, bot_token:$('#tg_token').value.trim(), chat_id:$('#tg_chat').value.trim()},
      discord:{enabled:$('#dc_en').checked, webhook_url:$('#dc_url').value.trim()},
      youtube:{enabled:$('#yt_en').checked, client_secrets:$('#yt_secrets').value.trim(), privacy:$('#yt_privacy').value}
    }
  };
}
function hasChanges() {
  return Boolean(savedSettings) && JSON.stringify(readSettings()) !== JSON.stringify(savedSettings);
}
function renderSettings(status, type) {
  const obs = $('#rec_backend').value === 'obs';
  const prioritize = $('#rec_performance').checked && !obs;
  $('#builtinFields').hidden = obs;
  $('#obsFields').hidden = !obs;
  $('#captureBtn').hidden = obs;
  $('#qualityHint').textContent = prioritize ? 'Direct GPU capture uses desktop resolution and runs at up to 30 FPS.' : '';
  $('#testHelp').textContent = obs ? 'Start Replay Buffer in OBS, then use Save replay in the library. A sample clip checks playback.' :
    'Check five seconds of screen video outside a match. To check speaker audio, use Save replay while CS2 is open and playing sound.';
  $('#polish_en').disabled = prioritize;
  $('#effectsHint').textContent = prioritize ? 'Paused while Prioritize game FPS is on.' : '';
  if (!savedSettings) return;
  const dirty = hasChanges();
  $('#finishBtn').disabled = settingsBusy || (!firstRun && !dirty);
  $('#discardBtn').hidden = !dirty;
  $('#discardBtn').disabled = settingsBusy;
  if (status !== undefined) message('#saveOut', status, type);
  else if (dirty) message('#saveOut', 'Unsaved changes');
  else message('#saveOut', firstRun ? 'Ready to finish setup' : 'Settings are up to date');
}
async function save() {
  const snapshot = readSettings();
  const obs = snapshot.recording.backend === 'obs';
  for (const field of [obs ? '#obs_port' : '#rec_clip', '#debounce', '#minkills']) {
    const input = $(field);
    if (!input.value || !input.checkValidity()) {
      const section = input.closest('[data-settings-panel]').id;
      history.replaceState(null, '', '#' + section);
      showSettingsSection(section);
      input.focus();
      message('#saveOut', 'Check ' + input.labels[0].childNodes[0].textContent.trim().toLowerCase() + ' (' + input.min + '–' + input.max + ').', 'err');
      return false;
    }
  }
  const patch = {};
  for (const [group, values] of Object.entries(snapshot)) {
    if (JSON.stringify(values) !== JSON.stringify(savedSettings[group])) patch[group] = values;
  }
  if (!Object.keys(patch).length) return true;
  const r = await api('/api/config', jsonPost(patch));
  if (!r.ok) {
    message('#saveOut', r.error || 'Could not save settings.', 'err');
    toast(r.error || 'Could not save settings.');
  } else {
    savedSettings = snapshot;
    renderSettings(hasChanges() ? 'Unsaved changes' : 'Settings saved.', hasChanges() ? '' : 'ok');
  }
  return r.ok;
}
function runSettings(button, label, action) {
  if (settingsBusy) { toast('A settings action is still running.'); return; }
  settingsBusy = true;
  return busy(button, label, action).finally(() => {
    settingsBusy = false;
    $('#finishBtn').disabled = !savedSettings || (!firstRun && !hasChanges());
    $('#discardBtn').disabled = false;
  });
}
document.querySelector('.settings-layout').addEventListener('input', () => renderSettings());
$('#discardBtn').onclick = () => runSettings($('#discardBtn'), 'Restoring…', loadExisting);
$('#backToLibrary').onclick = event => {
  if ((hasChanges() || settingsBusy) && !confirm('Leave settings? Any unsaved changes will be lost.')) event.preventDefault();
};
$('#scanBtn').onclick = () => runSettings($('#scanBtn'), 'Scanning…', detect);
$('#connectBtn').onclick = () => runSettings($('#connectBtn'), 'Connecting…', async () => {
  const path = $('#cs2_cfg_dir').value.trim();
  const r = await api('/api/install-gsi', jsonPost({cs2_cfg_dir: path}));
  if (!r.ok) { message('#gsiOut', r.error || 'Could not install the CS2 integration.', 'err'); return; }
  if (path && savedSettings) {
    savedSettings.engine.cs2_cfg_dir = path;
    renderSettings();
  }
  message('#gsiOut', r.restart_required ? 'Integration installed. Restart CS2 if it was open.' : 'The integration is already installed.', 'ok');
  await detect();
});
function testClip(button, capture) {
  return runSettings(button, capture ? 'Recording…' : 'Building sample…', async () => {
    if (!savedSettings) { message('#testOut', 'Reload this page to load your settings.', 'err'); return; }
    if (hasChanges() && (!confirm('Save these settings and run the test?') || !(await save()) || hasChanges())) return;
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
  if (!(await save()) || !firstRun || hasChanges()) return;
  const r = await api('/api/finish-setup', {method:'POST'});
  if (!r.ok) { message('#saveOut', r.error || 'Could not finish setup.', 'err'); return; }
  if (r.warning || r.restart_required) sessionStorage.setItem('aegisSetupMessage',
    r.warning || 'CS2 integration installed. Restart CS2 if it was already open.');
  location.href = '/';
});
showSettingsSection(location.hash.slice(1));
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
for _name, _path in {
    "FILM": '<rect x="3" y="4" width="18" height="16" rx="3"/><path d="m10 9 5 3-5 3z"/>',
    "STAR": '<path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1 6.2-5.5-3-5.5 3 1-6.2L3 9.6l6.2-.9z"/>',
    "ACTIVITY": '<path d="M3 12h4l3-7 4 14 3-7h4"/>',
    "SETTINGS": '<path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="2.5" fill="#14171c"/><circle cx="15" cy="17" r="2.5" fill="#14171c"/>',
    "SEARCH": '<circle cx="10.5" cy="10.5" r="5.5"/><path d="m15 15 4 4"/>',
}.items():
    DASHBOARD_HTML = DASHBOARD_HTML.replace(
        f"%{_name}_ICON%", f'<svg class=ico viewBox="0 0 24 24" aria-hidden=true>{_path}</svg>'
    )
SETUP_HTML = _shared(SETUP_HTML)
