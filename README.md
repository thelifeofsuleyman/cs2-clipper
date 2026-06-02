# CS2 auto-clipper

Auto-saves OBS Replay Buffer clips on every kill streak in CS2 and uploads
them to a Telegram channel.

**Mode: debounce-bundle.** Each kill resets a 7-second timer. When the timer
expires (no kill for 7 sec), one clip covering all kills in the streak is
saved and uploaded.

Result: solo kill = one clip. Ace = one clip with all 5 kills, not five
separate files.

## Setup — first time only

### 1. Python deps

You need Python 3.10+. From this folder:

```powershell
# Create venv (one time)
python -m venv .venv

# Activate it
.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

### 2. Telegram bot

1. Open Telegram → search `@BotFather` → message `/newbot`
2. Pick a name + username → BotFather sends you a **token** (looks like
   `123456:ABC-DEF...`). Save it.
3. Create a private channel (e.g. "CS2 Highlights")
4. Channel → Settings → Administrators → Add Admin → search your bot →
   give it post permission
5. Get the channel's chat ID:
   - Easy way: add `@userinfobot` to the channel briefly, it'll DM you the
     ID. Channel IDs are negative numbers starting with `-100`.
   - Remove `@userinfobot` after.

### 3. OBS setup

#### Replay Buffer
1. OBS → Settings → **Output** tab → Output Mode: **Advanced**
2. Switch to the **Replay Buffer** tab
3. Check **Enable Replay Buffer**
4. Maximum Replay Time: **45** seconds (covers a full multi-kill streak)
5. Encoder: **NVIDIA NVENC H.264** (uses GPU silicon, ~5% load — leave CPU
   free for CS2)
6. Apply, OK.

#### WebSocket server
1. OBS → **Tools** menu → **WebSocket Server Settings**
2. Check **Enable WebSocket server**
3. Server port: 4455 (default)
4. Authentication: optional. If you set a password, put it in `.env` as
   `OBS_PASSWORD`.
5. Apply.

#### Start Replay Buffer
- In the main OBS window, click **Start Replay Buffer** (bottom right) at
  the start of every CS2 session.
- To make it auto-start: OBS → Settings → General → check
  **Automatically start replay buffer when OBS starts**.

### 4. CS2 Game State Integration

Copy the GSI config into CS2's cfg folder:

```powershell
copy cfg\gamestate_integration_aegis_clipper.cfg "C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive\game\csgo\cfg\"
```

CS2 will load the config on next launch. No game restart needed if it was
already closed; just launch the next time.

### 5. Configure the clipper

```powershell
copy .env.example .env
```

Edit `.env` and fill in:
- `TG_BOT_TOKEN`        from BotFather
- `TG_CHAT_ID`          from step 2
- `OBS_REPLAY_DIR`      verify this matches OBS Settings → Output →
                        Recording → Recording Path
- `OBS_PASSWORD`        if you set one

The other values have safe defaults.

## Running

```powershell
.venv\Scripts\Activate.ps1
python clipper.py
```

Or use the convenience launcher (no venv activation needed):

```powershell
.\run.bat
```

The console will print every kill it detects and every clip it saves. Leave
it running while you play CS2.

Verify it's listening:
```powershell
curl http://127.0.0.1:3000/health
```
Should return `{"ok": true, "obs_connected": true, ...}`.

## How it works

```
CS2 (every ~100ms)
  ──POST──> Flask :3000  ──> debounce timer (7 sec)
                              │
                              ├─ kill resets timer
                              ├─ kill resets timer
                              │
                          (no kill for 7s)
                              │
                              ▼
                          OBS WebSocket:
                          SaveReplayBuffer
                              │
                              ▼
                      Watch OBS output dir
                      for new .mp4/.mkv
                              │
                              ▼
                      POST to Telegram API:
                      sendVideo + caption
```

Captions auto-generated from kill count:

- `Kill on de_dust2 (round 4, T-side)`
- `Double tap on de_mirage (round 9, CT-side)`
- `TRIPLE on de_inferno (round 14, T-side)`
- `QUAD on de_nuke (round 22, CT-side)`
- `ACE on de_dust2 (round 15, T-side)`

## Resource impact

On your GTX 1650 + i7-6700 + 16 GB during CS2:

| Component                  | CPU       | GPU            | RAM       |
| -------------------------- | --------- | -------------- | --------- |
| OBS Replay Buffer (NVENC)  | ~0%       | ~5% (NVENC)    | ~500 MB   |
| Flask GSI listener         | <1%       | 0%             | ~50 MB    |
| Telegram upload (per clip) | 1-2 sec   | 0%             | <50 MB    |

NVENC is a separate silicon block from your gaming cores, so the encode is
basically free during CS2.

## Troubleshooting

| Symptom                           | Fix                                                                                          |
| --------------------------------- | -------------------------------------------------------------------------------------------- |
| No clips appearing                | Make sure **Start Replay Buffer** was clicked in OBS before joining the match.               |
| "OBS WebSocket unreachable"       | OBS Tools → WebSocket Server Settings → Enable Server. Restart OBS.                          |
| "No new clip appeared"            | Check `OBS_REPLAY_DIR` in `.env` matches OBS Settings → Output → Recording → Recording Path. |
| Clip saves but Telegram errors    | Double-check `TG_BOT_TOKEN` and `TG_CHAT_ID`. Test the bot manually with `curl` first.       |
| GSI not POSTing                   | Verify the `.cfg` is in CS2's `csgo\cfg\` folder and CS2 was launched after copying.         |
| Clips include too many rounds     | Lower `DEBOUNCE_SEC` (try 5).                                                                |
| Solo kills feel like spam         | Set `MIN_KILLS=2` to only clip doubles and above.                                            |

## Caveats

- **Replay Buffer must be ON** in OBS before the round starts. The script
  can't enable it for you — it's an OBS-side toggle.
- **Telegram free limit is 2 GB per file.** A 45-sec NVENC clip at 1080p60
  is usually 30-80 MB — well within range, no compression needed.
- **Captions are best-effort.** Round number resets when CS2 thinks a new
  match started; that detection isn't perfect on warmup matchmaking.
- The script **does NOT touch CS2's memory or any game files.** GSI is
  Valve's official API. Anti-cheat safe.

## Files in this project

```
cs2-clipper/
├── README.md                            ← this file
├── clipper.py                           ← main script
├── requirements.txt                     ← pip dependencies
├── .env.example                         ← config template (copy to .env)
├── .gitignore                           ← keeps .env out of git
├── run.bat                              ← convenience launcher
└── cfg/
    └── gamestate_integration_aegis_clipper.cfg   ← copy to CS2's cfg folder
```
