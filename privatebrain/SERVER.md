# Running PrivateBrain on a server

This takes a fresh Linux server (tested on Ubuntu 24.04) to a PrivateBrain loop that runs as its
own unprivileged user under systemd, restarts itself after a crash or a hang, works with no model,
and uses Claude when credentials are present. Every command below was run on a clean machine on
2026-10-25; see [What was checked](#what-was-checked) for what was and was not.

The layout it sets up:

| Path | What |
|---|---|
| `privatebrain` (system user) | Runs the loop. Owns nothing outside `/var/lib/privatebrain`; no login shell |
| `/var/lib/privatebrain/src` | A clone of this repository |
| `/var/lib/privatebrain/venv` | The Python environment with `privatebrain` installed |
| `/var/lib/privatebrain/.local/bin/claude` | The Claude Code CLI, which every model call goes through |
| `/var/lib/privatebrain/brain` | The brain home (`PRIVATEBRAIN_HOME`): floor, mind, jobs, journal, events |
| `/etc/privatebrain/env` | Credentials and settings, readable by root and the `privatebrain` group only |
| `/usr/local/bin/pb` | Runs one `privatebrain` command as that user, with that environment |

## 1. Requirements

- Linux with systemd. macOS works for development, not for this guide.
- Python 3.12 or 3.13 (`requires-python = ">=3.12,<3.14"`). Ubuntu 24.04 ships 3.12. On a distro
  with an older Python, install [uv](https://docs.astral.sh/uv/) and use
  `uv venv --python 3.12 venv` in step 3 instead of `python3 -m venv venv`.
- `git` (the `harness2` dependency is installed from GitHub).
- Outbound HTTPS to GitHub and PyPI during install, and to `api.anthropic.com` if you want model
  work. With no network at all, the loop still runs its deterministic work (step 6).
- Small: the loop is one Python process using tens of MB; the brain home grows with the journal.

```bash
sudo apt update && sudo apt install -y git python3 python3-venv curl
```

## 2. A dedicated user

```bash
sudo useradd --system --create-home --home-dir /var/lib/privatebrain \
     --shell /usr/sbin/nologin privatebrain
sudo chmod 750 /var/lib/privatebrain
```

Why its own user: the brain's files (journal, memory, approvals, the floor) are then not writable
by your login's other programs, and the brain cannot read your home directory or your credentials.
The unit file in step 5 also confines it to `/var/lib/privatebrain` at the OS level. What this does
*not* do is stop the brain's own user from editing its own floor; see [Safety](#safety-what-stops-what).

Every later command that touches the brain runs as this user. `sudo -u privatebrain -H` does that
for the install steps; the `pb` wrapper (step 4) does it for daily use.

## 3. Install

```bash
sudo -u privatebrain -H bash -c '
  cd ~ &&
  git clone https://github.com/GeneralKnowledge/PrivateMind.git src &&
  python3 -m venv venv &&
  venv/bin/pip install ./src/privatebrain
'
sudo -u privatebrain -H /var/lib/privatebrain/venv/bin/privatebrain --help | head -3
```

To run the offline test suite (77 tests, about 2 s, no model calls):

```bash
sudo -u privatebrain -H bash -c 'cd ~ && venv/bin/pip install "./src/privatebrain[dev]" && cd src/privatebrain && ../../venv/bin/pytest -q'
```

**The model client (optional).** Model work runs through the
[Claude Code CLI](https://docs.claude.com/en/docs/claude-code) with no tools. Without it the brain
still runs and model work waits (`model_client_missing`). Install it for the `privatebrain` user,
so it lands in `~/.local/bin`, which is where the unit file looks:

```bash
sudo -u privatebrain -H bash -c 'curl -fsSL https://claude.ai/install.sh | bash'
# or, if Node.js is installed: sudo -u privatebrain -H npm install -g --prefix ~/.local @anthropic-ai/claude-code
sudo -u privatebrain -H /var/lib/privatebrain/.local/bin/claude --version
```

## 4. Configure

**Settings and credentials** go in one file, read by both the service and `pb`. Use plain
`KEY=value` lines, no quotes and no `export`, because systemd and `sh` both read it.

```bash
sudo install -d -m 755 /etc/privatebrain
sudo install -m 640 -o root -g privatebrain /dev/null /etc/privatebrain/env
sudoedit /etc/privatebrain/env
```

```ini
# Pick one way to authenticate the Claude CLI (or neither, for offline-only):
ANTHROPIC_API_KEY=sk-ant-...
# CLAUDE_CODE_OAUTH_TOKEN=...      # from `claude setup-token`, to use a Claude subscription

PRIVATEBRAIN_DAILY_BUDGET_USD=1.0  # model spend per day before model work waits
PRIVATEBRAIN_CALL_CAP_USD=0.10     # cap per call; a call killed mid-flight is charged at it
# PRIVATEBRAIN_MODEL=              # model for the v0 `tick` executor (default: PRIVATEBRAIN_EVAL_MODEL)
# PRIVATEBRAIN_EVAL_MODEL=claude-haiku-5-5      # model the mind runs on in experiments
# PRIVATEBRAIN_IMPROVER_MODEL=claude-opus-5-5   # harness² editing and GEPA reflection
# HTTPS_PROXY=http://proxy:3128    # only if the server reaches the internet through a proxy
```

The `run` loop's model is its `--model` flag (default `claude-haiku-5-5`); change it in the unit's
`ExecStart` if you want another. If you prefer an interactive login to a key, run
`sudo -u privatebrain -H /var/lib/privatebrain/.local/bin/claude` once and use `/login`; the
credentials then live in `/var/lib/privatebrain/.claude`.

**The `pb` wrapper**, so you never have to remember the user, the home or the environment:

```bash
sudo install -m 755 /var/lib/privatebrain/src/privatebrain/deploy/pb /usr/local/bin/pb
```

`pb` runs `sudo -u privatebrain`, so it needs sudo rights for that user. To allow your own login
without a password for only that, add `youruser ALL=(privatebrain) NOPASSWD: ALL` with
`sudo visudo -f /etc/sudoers.d/privatebrain` (optional; otherwise `pb` asks for your password).

**Create the brain and set the floor.** The floor is the list of boundaries the brain cannot edit.
Read it, change it to say what you mean, then pin it. A floor changed later without
`floor accept` halts all work until you accept it again.

```bash
pb init
sudoedit /var/lib/privatebrain/brain/FLOOR.md
pb floor accept
```

## 5. Run it as a service

The repository ships three units in [`deploy/systemd/`](deploy/systemd/):

| Unit | Does |
|---|---|
| `privatebrain.service` | `privatebrain run --interval 5` as `privatebrain`, `Restart=always`, read-only OS except `/var/lib/privatebrain`, private `/tmp`, `UMask=0077` |
| `privatebrain-watchdog.service` | Asks `privatebrain health`; on exit 1 (holds the lock, heartbeat stale: hung or stopped) it SIGKILLs the loop so the service restarts it |
| `privatebrain-watchdog.timer` | Runs the watchdog every minute |

```bash
sudo cp /var/lib/privatebrain/src/privatebrain/deploy/systemd/privatebrain* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now privatebrain.service privatebrain-watchdog.timer
pb status
```

`systemctl stop privatebrain` sends SIGTERM, and the loop stops cleanly (`health` then says
"stopped cleanly"). A loop that dies is restarted by `Restart=always` within 5 s and recovers on
start (`crash_recovered` in `pb events`); see [SUBSTRATE.md](SUBSTRATE.md#recovery-and-supervision)
for what recovery guarantees. Logs: `journalctl -u privatebrain -f`, plus `pb events`.

If you change paths, change them in all three units and in `pb`. Without systemd,
`scripts/supervise.sh` does the same job as the service plus the watchdog:
`sudo -u privatebrain -H env PATH=/var/lib/privatebrain/.local/bin:/var/lib/privatebrain/venv/bin:/usr/bin:/bin /var/lib/privatebrain/src/privatebrain/scripts/supervise.sh /var/lib/privatebrain/brain 10 --interval 5`
(it does not read `/etc/privatebrain/env`, so set credentials in its environment).

## 6. Use it

While the service runs, use `pb` for everything except `run` (only one loop can hold the queue;
a second `run` exits with "already running").

```bash
pb task "" --capability money.sum_line_items \
   --args '{"items": [{"label": "radiator valve", "quantity": 2, "unit_price": "14.20"}], "currency": "GBP", "budget": "40"}'
pb task "Draft a note to the landlord about the boiler"        # needs the model; waits without one
pb task "What do you know about the boiler?"                   # answered from local memory, no model
pb jobs                       # each job's state, and why it waits or is blocked
pb status                     # running? online? budget? approvals? mind version
pb recall "radiator"          # memory search, no model
pb approve <job>              # a side-effecting job blocked for approval, once
pb events --tail 20
pb capabilities               # the deterministic capabilities and their argument shapes
```

**Offline versus with a model.** Nothing needs configuring: the loop probes connectivity every 30 s.
With no CLI, no credentials or no network, deterministic work (capabilities, calendar clashes,
recall) runs and model work goes to `waiting` with the reason. When the model becomes reachable,
waiting work runs, within `PRIVATEBRAIN_DAILY_BUDGET_USD`. To force offline behaviour, add
`--offline` to `ExecStart`.

**Self-improvement is attended.** The service only runs the substrate loop. Experiments run by hand:

```bash
pb experiment run --budget 60 --repeats 3   # GEPA proposes; the graded gate keeps or rejects
pb mind auto-adopt off                      # then `pb mind approve <experiment>` adopts by hand
pb mind log && pb mind rollback
```

`--allow-unconfined` (on `tick` and on `experiment run --optimizer harness2`) gives a model the
tool-using Claude Code executor with host access: it can read and write anything the
`privatebrain` user can. Use it only at a terminal, never in the unit file.

## Health checks

```bash
pb health; echo $?      # 0 healthy (or inside a model call within its limit), 1 stalled, 2 not running
```

`health` prints JSON (`status`, `heartbeat_age_s`, `busy`, `halted`) and only reads files, so it is
safe for any monitor to call. A heartbeat is stale after `max(30 s, 3 x interval + 10 s)`, which is
30 s with `--interval 5`. `status` says `halted: the floor changed` if `FLOOR.md` was edited
without `pb floor accept`; the loop keeps sensing but does no work until then.

## Safety: what stops what

| Risk | What stops it |
|---|---|
| A model acting on the world unattended | The loop's model calls have no tools (`llm.call`): they read a prompt and return text. Side-effecting tasks wait for `pb approve`, scoped to one attempt |
| A model editing its floor, approvals or queue | No tools, as above; and the floor's hash is pinned, so a changed floor halts work |
| The brain reading your files or credentials | It runs as `privatebrain`, with `ProtectHome=yes` and a read-only OS outside its home |
| Other programs of yours editing the brain | They run as you, not as `privatebrain`; the home is mode 750 and new files 600 |
| Runaway spend | `PRIVATEBRAIN_DAILY_BUDGET_USD` and `PRIVATEBRAIN_CALL_CAP_USD` |
| Unconfined execution | Off unless `--allow-unconfined` is typed for one command |

Not covered: anything running *as* `privatebrain` can still rewrite `FLOOR.md` and `state.json`
together. Making the floor fully OS-enforced (owned by another user, in a directory the brain
cannot write) needs changes to how the brain writes `state.json` and `approvals.jsonl`, and is not
done yet.

## Updating, backup, removal

```bash
sudo -u privatebrain -H bash -c 'cd ~/src && git pull && ~/venv/bin/pip install ./privatebrain'
sudo systemctl restart privatebrain
```

The brain is plain files. Back it up with the service stopped (or accept a copy that may lack the
last few seconds): `sudo tar -C /var/lib/privatebrain -czf brain-$(date +%F).tgz brain`. To remove:
`sudo systemctl disable --now privatebrain privatebrain-watchdog.timer`, delete the three units,
`/usr/local/bin/pb` and `/etc/privatebrain`, then `sudo userdel -r privatebrain`.

## Troubleshooting

| You see | Meaning |
|---|---|
| `waiting ... remote model unavailable: model_client_missing` | `claude` is not on the service's `PATH`. Check `/var/lib/privatebrain/.local/bin/claude` |
| `CLI error: ... Not logged in · Please run /login` | No credentials reached the CLI: check `/etc/privatebrain/env`, then `sudo systemctl restart privatebrain` |
| `mode: degraded; ... recent_calls_failing` | The call breaker is open after failures; it half-opens after 5 minutes |
| `failed ... bad arguments: ...` | The capability's arguments are wrong; `pb capabilities` lists their shapes |
| `budget: ... EXCEEDED: model work waits` | Daily budget reached; work resumes tomorrow (UTC) or when you raise it |
| `halted: the floor changed` | `FLOOR.md` changed; `pb floor show`, then `pb floor accept` if you meant it |
| `... already running` | A loop (probably the service) holds the queue; use `pb` commands other than `run` |

## What was checked

On a clean Ubuntu 24.04 container, 2026-10-25, following this guide: the dedicated user; clone and
`pip install` as that user; the 77 offline tests passing; `init`, `floor accept`, a capability task
done and a model task waiting with no CLI; the CLI installed to `~/.local/bin` (via npm, because
that container could not reach the native installer's host), after which a model task waited with
"Not logged in" and the breaker opened; one real model task through a fresh brain home
($0.0008); `pb` reading `/etc/privatebrain/env`; the loop under the unit's exact environment,
SIGSTOPped (health exit 1 after 31.5 s), killed and restarted (`crash_recovered`), and stopped
cleanly by SIGTERM; `scripts/supervise.sh` restarting a SIGKILLed loop; a root-owned read-only
`FLOOR.md` not stopping the loop; and `systemd-analyze verify` on the three units.

Not checked: the units running under a live systemd (the container had none), the native
installer, and an API key or `setup-token` login for the `privatebrain` user.
