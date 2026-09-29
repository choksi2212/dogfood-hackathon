# HACK HAMSTER 2026 — MIHIR: MACHINE SETUP

**Do this by Sep 21. Not on kickoff day.**
Every minute spent installing at 18:05 UTC on Sep 26 is a minute off the 72 hours, and
installers fail in ways that take an hour to unpick.

None of this touches the competition repo, so all of it is legal under Rule 04.

---

## 0. The one command that checks everything

Paste this into Git Bash. Every line must print a version.

```bash
for c in docker node npm git curl python3; do printf '%-10s ' "$c"; $c --version 2>/dev/null | head -1 || echo "NOT FOUND"; done; printf '%-10s ' "compose"; docker compose version 2>/dev/null | head -1 || echo "NOT FOUND"
```

Target versions:

| Tool | Minimum | Why |
|---|---|---|
| Docker Desktop | 24+ | the whole product runs in it |
| `docker compose` | v2+ | must be the plugin form (`docker compose`, not `docker-compose`) |
| Node | 20 LTS or newer | Next.js frontend |
| npm | ships with Node | |
| Git | 2.40+ | |
| curl | any | you will use it to prove the API refuses you |
| **python3** | **3.10+** | **`run.py` runs on the host — the spec is explicit: "Any Python 3, including the one already on your Mac. Standard library only, nothing to install."** |

If all seven print versions, jump to §5.

---

## 1. Docker Desktop

Install from docker.com. **Enable the WSL 2 backend** when asked — the Hyper-V backend is
slower and has more filesystem edge cases on Windows.

After install, launch it once and leave it running. Then:

```bash
docker run --rm hello-world
```

If this fails, nothing else in this hackathon works. Fix it now, not on Friday.

**Resource settings** — Docker Desktop → Settings → Resources. Give it at least **4 GB RAM
and 2 CPUs**. The default is sometimes low enough that Postgres plus the app container
thrashes.

### 1.1 Pre-pull the images — do it today (Sep 23)

The spec is live a day early; the stack is unchanged from what we planned. Pull today.
Pulling on the 23rd costs a few minutes and means kickoff is not spent staring at a
download bar on bad wifi.

```bash
docker pull postgres:16-alpine
docker pull python:3.12-slim
docker pull node:22-alpine
```

Manas will confirm the exact tags if they differ from these.

---

## 2. Node

Install the current **LTS** from nodejs.org. Not the "Current" build — LTS.

```bash
node --version   # v20.x or v22.x
npm --version
```

If you already have an older Node from a previous project, upgrade it. Next.js 15 wants 20+.

---

## 3. Git and the line-ending trap

This is the single most common way a Windows teammate creates conflicts in files they never
touched.

```bash
git config --global core.autocrlf false
git config --global core.longpaths true
git config --global init.defaultBranch main
git config --global pull.rebase false
```

**Set your own identity** — and check it is the right one, not a leftover from a work
machine or a college account:

```bash
git config --global user.name "Mihir Rabari"
git config --global user.email "<the email on your GitHub account>"
git config --global --get user.name
git config --global --get user.email
```

If the email does not match your GitHub account, your commits will not be attributed to you,
and the judges read commit history. Fix it before the first commit, because rewriting it
afterwards is painful.

### 3.1 Confirm you can push, this week

The worst possible time to discover a credentials problem is at hour 20 with work sitting
uncommitted. Test it now in a scratch repo you own — **not** in `hack-hamster-hackathon`:

```bash
mkdir -p ~/scratch/push-test && cd ~/scratch/push-test
git init && echo test > a.txt && git add a.txt && git commit -m "test"
# add a remote to a throwaway repo of your own, push, confirm it lands, then delete it
```

You need push access to `github.com/choksi2212/dogfood-hackathon` before kickoff. Ask Manas to
add you as a collaborator **this week** and accept the invite. Do not clone or push anything
to it yet.

---

## 4. Editor

VS Code, with:
- ESLint
- Prettier
- Docker
- **A line-ending indicator visible in the status bar** — you want to see "LF" and notice when
  something says "CRLF"

Set VS Code default end-of-line to `\n`:
Settings → search `files.eol` → set to `\n`.

---

## 5. Browser

Chrome or Edge with DevTools you are fluent in. You will live in the Network tab proving that
the frontend only calls documented endpoints.

Also install a second browser (or use a private window) — you will need **two simultaneous
sessions as different roles** constantly: judge in one, organizer in the other. A private
window and a normal window is enough.

---

## 6. Ports

The stack will want these free:

| Port | Service |
|---|---|
| 3000 | Next.js dev server |
| 8000 | Django |
| 5432 | Postgres |

Check nothing is already holding them:

```bash
netstat -ano | grep -E ':(3000|8000|5432)\s' || echo "all free"
```

If something is listening, find what it is and stop it. **Verify a kill by PID, not by image
name** — killing by name can hit the wrong process:

```bash
netstat -ano | grep ':5432'       # note the PID in the last column
tasklist | grep <PID>             # confirm what it is before killing
taskkill //PID <PID> //F
```

A local Postgres installed from a previous project squatting on 5432 is the classic one. It
will make the container's database unreachable in a way that looks like a code bug.

---

## 7. Clock

Sounds trivial, matters here. Deadline enforcement is a graded T1 feature, the freeze is at a
fixed UTC time, and JWT/session expiry breaks in confusing ways when the clock drifts.

Windows Settings → Time & language → set time automatically **on**, and click "Sync now".

Know your local offset from UTC and write it at the top of your notes. Kickoff is
**Sep 26, 18:00 UTC**; freeze is **Sep 29, 18:00 UTC**. Every deadline in the brief is UTC.

```bash
date -u                            # always reason in this
```

---

## 8. Throwaway practice repo

For all pre-kickoff fluency work:

```bash
mkdir -p ~/scratch/hack-hamster-practice && cd ~/scratch/hack-hamster-practice
```

**Rules for it:**
- It never gets a remote pointing at `hack-hamster-hackathon`
- Nothing in it is copied into the real repo at kickoff
- You rebuild from empty on Sep 26 — what carries over is your fluency, not your files

Practice until each is boring: a Next.js app from scratch, an API client layer with a mock
adapter you can switch, form validation, a table with sort and filter, and reading an
OpenAPI spec.

---

## 9. Final gate — what "ready" looks like

Run through this on **Sep 21** and again on **Sep 23**. Every box ticked, no exceptions.

- [ ] `docker run --rm hello-world` succeeds
- [ ] `docker compose version` prints v2 or later
- [ ] The base images are pulled (**Sep 23 check — spec is live, stack is confirmed**)
- [ ] `node --version` is 20+
- [ ] `git config --global core.autocrlf` prints `false`
- [ ] `git config --global user.email` is your GitHub email
- [ ] `python3 --version` prints 3.10+
- [ ] You have accepted the collaborator invite to `hack-hamster-hackathon`
- [ ] You have pushed to a scratch repo successfully this week
- [ ] Ports 3000, 8000, 5432 are free
- [ ] Clock synced, and you know your offset from UTC
- [ ] VS Code default EOL is `\n`
- [ ] You are in the HACK HAMSTER Discord
- [ ] You have read `HACK HAMSTER-PLAN.md` and `HACK HAMSTER-MIHIR.md` end to end
- [ ] You have read `spec.md` (Sep 23 — already live) and we have re-planned against it

---

## 10. What NOT to do before kickoff

- **Do not commit or push anything to `hack-hamster-hackathon`.** Rule 04: any project code committed
  before Sep 26 18:00 UTC is **disqualification**. The repo is empty and stays empty.
- Do not "get a head start" by writing components you plan to paste in. That is the exact
  thing the rule forbids, and the commit timestamps are public.
- Do not install a local Postgres. It runs in Docker; a host install only fights you for
  port 5432.
- Do not upgrade Windows, Docker Desktop, or Node in the last 48 hours before kickoff.
  **Freeze your machine now** — Sep 23. An update that breaks the WSL backend on Sep 26 is
  a lost hackathon.
- Do not skip the spec read. It is **already live (Sep 23)**; both docs have been re-planned
  against it.
