---
name: skill-sync
description: One source of truth for local AI agent skills: audit Codex, Claude, OpenClaw, OpenCode, workspace skills, and shared roots; score hygiene, diff conflicting installs, deduplicate into one canonical source, and migrate the same layout across machines with restoreable backups.
homepage: https://github.com/LearnPrompt/skill-sync
---

# Skill Sync

## Overview

Use this skill when you want one lightweight workflow for:

- discovering skills installed across multiple AI agent hosts on the same machine
- seeing which skills are already shared by symlink
- finding duplicated installs that can be consolidated
- selecting one canonical source when the same portable skill exists in multiple places
- identifying platform-specific skills that should stay local
- safely filling missing installs with symlinks instead of copying files
- backing up replaced installs and restoring them later if needed
- exporting a portable layout manifest and importing it on another machine

The workflow is intentionally conservative:

- it scans first
- it reports before mutating anything
- it only auto-links portable directory-based skills with `SKILL.md`
- it never overwrites an existing destination path without first moving it to backup storage

## Quick Start

Run the scanner from any directory:

```bash
python3 scripts/skill_sync.py
```

Show the hygiene score plus recommended actions:

```bash
python3 scripts/skill_sync.py
```

Preview missing symlink opportunities for one skill:

```bash
python3 scripts/skill_sync.py \
  --skill playwright \
  --sync-missing
```

Preview canonical dedupe using the safest strategy:

```bash
python3 scripts/skill_sync.py \
  --dedupe \
  --strategy strict
```

Apply canonical dedupe while preserving backups:

```bash
python3 scripts/skill_sync.py \
  --dedupe \
  --strategy prefer-latest \
  --apply
```

Apply missing symlinks without replacing existing installs:

```bash
python3 scripts/skill_sync.py \
  --sync-missing \
  --strategy strict \
  --apply
```

Restore a previous run:

```bash
python3 scripts/skill_sync.py \
  --restore latest
```

Preview a one-root convergence plan:

```bash
python3 scripts/skill_sync.py \
  --adopt-root agents
```

Export a migration manifest:

```bash
python3 scripts/skill_sync.py \
  --adopt-root agents \
  --export-manifest .skill-sync/agent-layout.json
```

Preview or apply that topology on another machine:

```bash
python3 scripts/skill_sync.py \
  --import-manifest .skill-sync/agent-layout.json

python3 scripts/skill_sync.py \
  --import-manifest .skill-sync/agent-layout.json \
  --apply
```

Inspect a compatible skill with file-level diff:

```bash
python3 scripts/skill_sync.py \
  --diff rapid-ocr
```

Get machine-readable output:

```bash
python3 scripts/skill_sync.py \
  --format json
```

## What The Script Detects

The script scans these host roots when they exist:

- `<current-workdir>/skills`
- `~/.codex/skills`
- `~/.agents/skills`
- `~/.claude/skills`
- `~/.claude/skills/anthropic-skills/skills`
- `~/.config/opencode/skills`
- `~/.openclaw/skills`
- `~/.openclaw/extensions/*/skills`

It classifies each discovered skill into one of four states:

- `shared`: the same real directory is visible from multiple hosts, usually through symlinks
- `duplicate`: multiple hosts have the same portable skill content, but not via the same real path yet
- `compatible`: multiple hosts have portable `SKILL.md` skills with the same name, but different content
- `specific`: the skill appears on only one host
- `mixed`: the same skill name exists on multiple hosts, but with different formats or incompatible content

The report also computes:

- a hygiene score
- recommended next actions
- a canonical source preference order
- dedupe and propagation plans

## Strategy Rules

When `--strategy strict` is used:

- only fully identical portable skills are deduped
- `compatible` groups are reported, not replaced

When `--strategy prefer-latest` is used:

- any all-portable `SKILL.md` group can get a canonical source
- the newest real path wins
- older duplicates are moved to backup storage before replacement

When `--strategy trust-high` is used:

- canonical source selection is the same as `prefer-latest`
- replacement can also target non-primary scanned roots such as vendor/plugin skill directories

## Execution Rules

When `--sync-missing` is enabled, the script:

- picks one source install using a host priority order
- only considers groups eligible under the current strategy
- only targets primary host roots, not nested vendor/plugin bundles
- skips any host that already has the skill somewhere
- skips destinations that already exist on disk

When `--dedupe` is enabled, the script:

- chooses one canonical source
- moves each replaced install to `~/.skill-sync/backups/<run-id>/originals/...`
- creates a symlink at the original path
- writes `manifest.json` so the run can be restored later

When `--export-manifest` is enabled, the script:

- records the canonical source choice for each portable skill
- records which primary hosts should expose each skill
- writes a portable JSON manifest that can be imported on another machine

When `--import-manifest` is enabled, the script:

- finds matching local canonical sources on the current machine
- previews missing roots and missing sources before mutating anything
- creates or replaces host installs with symlinks to match the manifest layout
- reuses the same backup-and-restore flow as local dedupe

If you need the detection details or compatibility notes, read [references/compatibility.md](./references/compatibility.md).
