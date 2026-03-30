# skill-sync

Unify local AI Agent skills across Codex, Claude, OpenClaw, OpenCode, and shared skill directories.

`skill-sync` scans the skill roots on your machine, tells you which skills are already shared, which are duplicated, which are compatible-but-different, and can safely converge duplicate installs into one canonical source plus symlinks.

## Why

When you use multiple AI coding agents, the same skill often ends up installed several times:

- one copy in `~/.codex/skills`
- another in `~/.claude/skills`
- another in `~/.openclaw/skills`
- sometimes a shared copy in `~/.agents/skills`

That creates three problems:

- updates drift across platforms
- reinstalling the same skill wastes time
- it becomes hard to tell which copy is the real source of truth

`skill-sync` fixes that by turning repeated local installs into:

- one canonical source
- multiple symlinks
- a reversible backup trail

## What It Does

- Discover skills across multiple local AI agent hosts
- Classify each skill as `shared`, `duplicate`, `compatible`, `specific`, or `mixed`
- Plan missing symlink installs
- Choose a canonical source automatically
- Replace duplicate copies with symlinks
- Back up replaced installs into a dedicated restoreable run directory

## Supported Skill Roots

- `~/.codex/skills`
- `~/.agents/skills`
- `~/.claude/skills`
- `~/.claude/skills/anthropic-skills/skills`
- `~/.config/opencode/skills`
- `~/.openclaw/skills`
- `~/.openclaw/extensions/*/skills`

## Install

Clone the repo and install by symlink:

```bash
git clone git@github.com:LearnPrompt/skill-sync.git
cd skill-sync
./install.sh --codex
```

Install into multiple hosts at once:

```bash
./install.sh --codex --claude --openclaw --agents
```

See all install options:

```bash
./install.sh --help
```

## Quick Start

Scan local skills:

```bash
python3 scripts/skill_sync.py
```

Preview dedupe with the safest policy:

```bash
python3 scripts/skill_sync.py --dedupe --strategy strict
```

Dedupe by keeping the newest portable version:

```bash
python3 scripts/skill_sync.py --dedupe --strategy prefer-latest --apply
```

Plan missing installs using the same canonical source logic:

```bash
python3 scripts/skill_sync.py --sync-missing --strategy prefer-latest
```

Restore the latest run:

```bash
python3 scripts/skill_sync.py --restore latest
python3 scripts/skill_sync.py --restore latest --apply
```

## How It Classifies Skills

- `shared`: multiple hosts already point to the same real path
- `duplicate`: multiple portable installs have identical content but different real paths
- `compatible`: multiple portable installs share the same skill name but differ in content
- `specific`: only found on one host
- `mixed`: same name exists, but with incompatible formats or host-specific structure

## Strategies

- `strict`: only dedupe identical portable skills
- `prefer-latest`: for portable duplicates with differences, keep the newest real path
- `trust-high`: same canonical selection as `prefer-latest`, but allows more aggressive replacement of scanned roots

## Backup Model

Applied runs are stored under:

```text
~/.skill-sync/backups/<run-id>/
```

Each run includes:

- `manifest.json`
- `originals/...`
- `latest` symlink

That means dedupe is reversible. Replaced directories are moved before a symlink is created in their original location.

## Example Workflow

1. Install the skill into your main hosts with `./install.sh`.
2. Run `python3 scripts/skill_sync.py` to inspect the current state.
3. Run `python3 scripts/skill_sync.py --dedupe --strategy strict` to preview safe convergences.
4. If you want newest-wins behavior, run `python3 scripts/skill_sync.py --dedupe --strategy prefer-latest --apply`.
5. If needed, restore with `python3 scripts/skill_sync.py --restore latest --apply`.

## Project Layout

```text
.
├── SKILL.md
├── README.md
├── install.sh
├── agents/openai.yaml
├── references/compatibility.md
└── scripts/skill_sync.py
```

## License

MIT
