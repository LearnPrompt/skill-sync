# Skill Sync

> Once you have more than a few skills, the biggest problem is not missing tools. It is that every tool exists in five places and nobody knows which copy is real.

One source of truth for local AI agent skills.

`skill-sync` turns a messy multi-agent setup into a maintainable local skill system:

- scan skills across Codex, Claude, Hermes, OpenClaw, OpenCode, workspace `./skills`, and shared agent roots
- score the hygiene of your current setup
- show shared, duplicate, compatible, and host-specific skills
- record a pristine baseline and classify every skill as `pristine`, `dirty`, or `local-only`
- pick a canonical source automatically
- replace duplicate copies with symlinks — but never silently replace a copy you edited
- back up every replaced install so you can restore it later
- export a portable layout manifest and recreate that topology on another machine

## Who This Is For

`skill-sync` is built for people who:

- use more than one AI coding agent
- install lots of local skills
- keep a shared skill library in `~/.agents/skills`
- move between machines or rebuild environments often
- want one canonical skill source instead of version drift everywhere

## The Problem

In a real machine, the same skill often appears in multiple places:

- `~/.codex/skills`
- `~/.claude/skills`
- `~/.openclaw/skills`
- `~/.config/opencode/skills`
- `~/.agents/skills`
- `<workspace>/skills`

That creates drift:

- one copy gets updated, another stays stale
- the same skill gets installed repeatedly
- nobody remembers which copy is the real source of truth

And there is a second, sneakier problem: **skills change while you use them.** You tweak a prompt here, fix a path there. A naive "sync everything" would happily overwrite your local edits with a stale upstream copy — or push your half-finished experiment everywhere. `skill-sync` treats that as the central design problem, not an edge case.

## The Product Promise

`skill-sync` gives you four things that basic skill managers usually do not:

1. Cross-host discovery  
It scans all the common local roots at once instead of showing one host in isolation.

2. Canonical source selection  
It decides which copy should win based on strategy, timestamps, shared roots, and your preferred source order.

3. Safe convergence  
It can turn duplicates into symlinks and centralize ownership without destructive blind replacement.

4. Reversible operations  
Every dedupe run writes a restorable backup manifest under `~/.skill-sync/backups`.

## What Makes It Different

Compared with generic local skill managers, `skill-sync` is specifically about:

- cross-agent skill hygiene
- canonical source adoption
- symlink-based dedupe
- compatible skill diffing
- reversible local convergence

## Supported Skill Roots

- `<current-workdir>/skills`
- `~/.codex/skills`
- `~/.agents/skills`
- `~/.claude/skills`
- `~/.hermes/skills`
- `~/.claude/skills/anthropic-skills/skills`
- `~/.config/opencode/skills`
- `~/.openclaw/skills`
- `~/.openclaw/extensions/*/skills`

## Quick Start

One-line install into all primary hosts:

```bash
git clone https://github.com/LearnPrompt/skill-sync.git && cd skill-sync && ./install.sh --all
```

Or pick your hosts:

```bash
./install.sh --codex --claude --openclaw --agents
```

Scan everything:

```bash
python3 scripts/skill_sync.py
```

Record today's state as the pristine baseline (do this once, right after installing your skills):

```bash
python3 scripts/skill_sync.py --record-baseline
```

Later, check what drifted (report-only, never mutates):

```bash
python3 scripts/skill_sync.py --check-drift
```

Export the current topology as a migration manifest:

```bash
python3 scripts/skill_sync.py \
  --adopt-root agents \
  --export-manifest .skill-sync/agent-layout.json
```

Preview that layout on another machine:

```bash
python3 scripts/skill_sync.py \
  --import-manifest .skill-sync/agent-layout.json
```

Apply it with backups:

```bash
python3 scripts/skill_sync.py \
  --import-manifest .skill-sync/agent-layout.json \
  --apply
```

Show only shared and host-specific skills:

```bash
python3 scripts/skill_sync.py --status shared,specific --list-names
```

Inspect a compatibility conflict:

```bash
python3 scripts/skill_sync.py --diff rapid-ocr
```

Preview safe dedupe:

```bash
python3 scripts/skill_sync.py --dedupe --strategy strict
```

Preview a full convergence onto the shared agent root:

```bash
python3 scripts/skill_sync.py --adopt-root agents
```

Apply that convergence:

```bash
python3 scripts/skill_sync.py --adopt-root agents --apply
```

Restore the latest run:

```bash
python3 scripts/skill_sync.py --restore latest
python3 scripts/skill_sync.py --restore latest --apply
```

## Example Output

```text
Discovered 99 unique skills from 183 installs.
Hygiene score: 46/100 (risky) | shared_ratio=38.4% | review=2 | duplicates=20

RECOMMENDED ACTIONS
- [high] Review 2 compatible skills before dedupe
- [medium] Deduplicate 20 identical multi-host skills
- [low] Preview a single-root convergence plan
```

The point is not just to list skills. The point is to tell you what to do next.

## Validation

Run the fast local checks:

```bash
python3 -m py_compile scripts/skill_sync.py
python3 -m unittest discover -s tests -q
```

## Status Model

- `shared`: multiple hosts already point to the same real path
- `duplicate`: portable installs match exactly but live at different real paths
- `compatible`: portable installs share a name but differ in content
- `specific`: found on only one host
- `mixed`: same name exists with incompatible formats or host-specific layouts

## Strategy Model

- `strict`: only dedupe identical portable skills
- `prefer-latest`: keep the newest portable copy when content differs
- `trust-high`: same canonical logic as `prefer-latest`, but allows more aggressive replacement of scanned roots

## Drift Model: pristine / dirty / local-only

"Newest mtime wins" is a bad rule for things that change while you use them. A freshly reinstalled upstream copy is newer than your customized copy — but your customization is the one that matters.

So `skill-sync` records a baseline. Run this once when your setup is in a known-good state:

```bash
python3 scripts/skill_sync.py --record-baseline
```

That writes the canonical content hash of every discovered skill to `~/.skill-sync/baselines.json` (override with `SKILL_SYNC_BASELINE_STORE` or `--baseline-store`). From then on, every skill has one of three states:

- `pristine`: every copy still matches the baseline. Updating or deduping it can never lose your work.
- `dirty`: some copy differs from the baseline. You edited it. `skill-sync` will list it, show you `--diff`, and refuse to replace it during dedupe unless you explicitly pass `--allow-dirty`.
- `local-only`: no baseline recorded. Treated as your original work — backed up, never auto-overwritten, never assumed to have an upstream.

Check the state of everything at any time:

```bash
python3 scripts/skill_sync.py --check-drift
```

When you decide a dirty skill's local version is the new truth, accept it as the new baseline:

```bash
python3 scripts/skill_sync.py --record-baseline --skill <name>
```

This is the same mental model as dotfiles managers (chezmoi: source of truth + tracked local divergence) and lockfiles (record what was installed, so you can tell intentional change from drift), applied to agent skills.

## Superpowers

### Hygiene Score

Every scan computes a rough operational score so you can tell whether your local skill ecosystem is clean or drifting.

### Recommended Actions

The report suggests next steps instead of dumping raw data only.

### File-Level Diff

Use `--diff <skill>` to compare portable installs against the selected canonical source and see which files changed, were added, or removed.

### Root Adoption

Use `--adopt-root agents` or another root to preview or apply a convergence plan around one canonical host.

### Cross-Machine Migration

Use `--export-manifest` to save the desired symlink topology and `--import-manifest` to recreate that topology elsewhere.

The manifest records:

- which skills are portable enough to converge
- which host should act as canonical source
- which primary hosts should expose each skill

The manifest does not copy skill payloads themselves. On the target machine, the canonical source still needs to exist locally.

## About `~/.agents/skills`

If you already use `~/.agents/skills` as a shared skill library, that works especially well with `skill-sync`.

By default:

- it participates in discovery
- it often becomes the canonical source because it is first in the default source order

That is usually desirable. If you want a different preference order:

```bash
python3 scripts/skill_sync.py --source-order workspace,codex,claude,hermes,agents,opencode,openclaw
```

## About `~/.hermes/skills`

Hermes is treated as a first-class host root.

`skill-sync` scans:

- direct Hermes skills such as `~/.hermes/skills/office-hours`
- one level of categorized Hermes skills such as `~/.hermes/skills/apple/apple-reminders`

It does not currently recurse arbitrarily deep into every Hermes subtree, so nested vendor bundles under custom subfolders may still need explicit future support.

## How To Trigger It

`skill-sync` is a maintenance tool, not a daemon. It should not sit in your agent's head rent-free, and it does not need to. There are two sane ways to run it:

### 1. Explicit ask

Say any of these to your agent and the skill takes over:

- "sync my skills" / "同步我的 skills"
- "check skill drift" / "检查 skill 漂移"
- "dedupe my skills" / "skill 大扫除"
- "which copy of rapid-ocr is canonical?"

### 2. Optional scheduled drift check (you configure it, not us)

**`skill-sync` never installs hooks, cron jobs, or scheduled tasks on its own.** Nothing happens at install time except files landing in a directory. If you want a recurring report, you wire it up yourself.

For Claude Code, a `SessionStart` hook that prints a drift report at the start of each session (report-only — it never modifies anything):

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup",
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.agents/skills/skill-sync/scripts/skill_sync.py --check-drift"
          }
        ]
      }
    ]
  }
}
```

Put it in `~/.claude/settings.json`, adjust the path to wherever you installed skill-sync, and remove it whenever you like. A weekly cron with the same command works equally well for other setups. The drift check exits 0 and touches nothing, so the worst it can do is tell you something you already knew.

## Safety Boundaries

- Every run reports before it mutates. `--apply` is always a separate, explicit decision.
- A `dirty` skill (one that differs from its recorded baseline) is **never** replaced without confirmation. Dedupe skips it, tells you why, and asks you to review `--diff` first; only `--allow-dirty` overrides that.
- `local-only` skills are treated as your original work: backed up, never auto-overwritten.
- Every replaced directory is moved into `~/.skill-sync/backups/<run-id>/originals/...` before the symlink is created, and `--restore` reverses the run.
- Installing skill-sync configures nothing: no hooks, no cron, no background tasks.

## skill-sync And Skill Catalogs

`skill-sync` and a catalog-first registry like [carl-skills](https://github.com/LearnPrompt/carl-skills) solve different halves of the same lifecycle:

- **The registry is the upstream layer.** It records where each skill canonically lives (`canonical_repo`, `source_commit`) and how to install it. It answers: *what should exist, and which version is current?*
- **`skill-sync` is the local layer.** It records where copies actually live on this machine and whether they still match the state you installed (`baselines.json`). It answers: *what do I actually have, did I change it, and which copy wins?*

They meet at the baseline: a registry's `source_commit` says what upstream shipped; your recorded baseline says what landed on disk. Pristine skills can be updated from upstream blindly. Dirty skills are exactly the ones where you must choose between your edits and the new upstream — and that choice should never be made silently by a sync tool.

## Backup Model

Applied runs are written to:

```text
~/.skill-sync/backups/<run-id>/
```

Each run stores:

- `manifest.json`
- `originals/...`
- `latest`

This makes dedupe reversible. A real directory is moved to backup before a symlink replaces it.

## Install Script

`install.sh` supports:

- `--codex`
- `--agents`
- `--claude`
- `--hermes`
- `--opencode`
- `--openclaw`
- `--all`
- `--copy`
- `--force`

Examples:

```bash
./install.sh --all
./install.sh --codex --claude --force
./install.sh --openclaw --copy
```

## Project Layout

```text
.
├── SKILL.md
├── README.md
├── install.sh
├── agents/openai.yaml
├── references/compatibility.md
├── scripts/skill_sync.py
└── tests/test_skill_sync_cli.py
```

## License

MIT
