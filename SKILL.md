---
name: skill-sync
description: "One source of truth for local AI agent skills: audit Codex, Claude, Hermes, OpenClaw, OpenCode, workspace skills, and shared roots; score hygiene, diff conflicting installs, classify drift as pristine/dirty/local-only against recorded baselines, deduplicate into one canonical source with symlinks, and migrate the same layout across machines with restorable backups. Trigger when the user says things like 'sync my skills', '同步我的 skills', 'check skill drift', '检查 skill 漂移', 'dedupe my skills', 'skill 大扫除', 'audit my skills', 'which copy of this skill is canonical', or wants one source of truth across multiple agents. Do NOT trigger for installing a brand-new skill from a catalog or registry, for editing one skill's content, or for single-host questions that need no cross-host comparison."
homepage: https://github.com/LearnPrompt/skill-sync
---

# Skill Sync

## When To Use

Use this skill when the user wants to:

- scan local skills across Codex, Claude, Hermes, OpenClaw, OpenCode, workspace `./skills`, and shared roots
- see which skills are `shared`, `duplicate`, `compatible`, `specific`, or `mixed`
- check skill drift: which skills are still `pristine`, which are `dirty` (locally edited), which are `local-only`
- choose one canonical source and replace duplicate copies with symlinks
- preview or apply convergence onto one preferred root such as `~/.agents/skills`
- export a portable layout manifest and import the same topology on another machine
- restore a previous dedupe or import run

Typical trigger phrases: "sync my skills", "同步我的 skills", "check skill drift", "检查 skill 漂移", "dedupe my skills", "skill 大扫除", "audit my skill installs".

Do not use this skill when:

- the task is only about one host and no cross-host comparison or symlink management is needed
- the user wants to install a brand-new skill from a catalog or registry (that is distribution, e.g. [carl-skills](https://github.com/LearnPrompt/carl-skills); skill-sync manages local copies after installation)
- the user wants to edit the content of a single skill

## Fast Path

Scan the machine and get the hygiene score plus recommended actions:

```bash
python3 scripts/skill_sync.py
```

List only shared and host-specific skills:

```bash
python3 scripts/skill_sync.py --status shared,specific --list-names
```

Record the current state as the pristine baseline (do this once after installing skills):

```bash
python3 scripts/skill_sync.py --record-baseline
```

Check drift against the recorded baseline (report-only, never mutates):

```bash
python3 scripts/skill_sync.py --check-drift
```

Inspect one conflicting portable skill:

```bash
python3 scripts/skill_sync.py --diff rapid-ocr
```

Preview safe dedupe:

```bash
python3 scripts/skill_sync.py --dedupe --strategy strict
```

Preview a single-root convergence plan:

```bash
python3 scripts/skill_sync.py --adopt-root agents
```

Apply convergence with backups:

```bash
python3 scripts/skill_sync.py --adopt-root agents --apply
```

Restore the latest run:

```bash
python3 scripts/skill_sync.py --restore latest
python3 scripts/skill_sync.py --restore latest --apply
```

## Workflow

1. Scan first.
   Run `python3 scripts/skill_sync.py` and read the hygiene score and recommended actions.
2. Record a baseline when the setup is in a known-good state.
   Run `--record-baseline` so future runs can tell pristine copies from local edits.
3. Check drift before touching anything.
   Run `--check-drift` and review every `dirty` skill with `--diff <skill>` before deciding what wins.
4. Review risky groups before mutation.
   Use `--status compatible --list-names`, `--status mixed --list-names`, and `--diff <skill>`.
5. Preview convergence.
   Use `--dedupe --strategy strict` for identical groups, or `--adopt-root <platform>` to converge around one root.
6. Apply only when the plan looks right.
   Add `--apply` to execute symlink creation or replacement. Dirty copies are skipped unless the user explicitly confirms with `--allow-dirty`.
7. Export or import machine layouts when needed.
   Use `--export-manifest` and `--import-manifest` for cross-machine reuse.
8. Restore from backup if needed.
   Use `--restore <run-id|latest>` and add `--apply` to roll back.

## Drift Model

Once a baseline is recorded (`~/.skill-sync/baselines.json`), every skill falls into one of three states:

- `pristine`: every portable copy matches the recorded baseline. Safe to dedupe or replace with a newer version.
- `dirty`: at least one copy differs from the baseline. The user edited it locally. Never overwrite without showing the diff and getting explicit confirmation (`--allow-dirty`).
- `local-only`: no baseline recorded. Treat as the user's original work: back it up, never auto-overwrite, never assume an upstream exists.

After the user reviews a dirty skill and decides the local version is the new truth, re-run `--record-baseline --skill <name>` to accept it as the new pristine state.

## Safety Rules

- The script always scans and reports before mutation.
- `--check-drift` and `--record-baseline` never modify any skill; they only read and write `~/.skill-sync/baselines.json`.
- It only auto-links portable directory-based skills that contain `SKILL.md`.
- It never overwrites an existing destination without first moving it into `~/.skill-sync/backups/<run-id>/originals/...`.
- It never replaces a `dirty` copy (one that differs from its recorded baseline) unless `--allow-dirty` is passed after the user reviewed the diff.
- `--strategy strict` only dedupes identical portable skills.
- `--strategy prefer-latest` and `--strategy trust-high` may select the newest portable copy when content differs.
- `--restore latest --apply` replays the last backup manifest in reverse.
- This skill never installs hooks, cron jobs, or scheduled tasks on its own. If the user wants a recurring drift check, point them to the hook recipe in the README and let them configure it themselves.

## Roots Scanned

- `<current-workdir>/skills`
- `~/.codex/skills`
- `~/.agents/skills`
- `~/.claude/skills`
- `~/.hermes/skills`
- `~/.claude/skills/anthropic-skills/skills`
- `~/.config/opencode/skills`
- `~/.openclaw/skills`
- `~/.openclaw/extensions/*/skills`

## Status Model

- `shared`: the same real directory is visible from multiple hosts, usually through symlinks
- `duplicate`: multiple hosts have the same portable skill content, but not via the same real path yet
- `compatible`: multiple hosts have portable `SKILL.md` skills with the same name, but different content
- `specific`: the skill appears on only one host
- `mixed`: the same skill name exists on multiple hosts, but with different formats or incompatible content

If you need the detection details or compatibility notes, read [references/compatibility.md](./references/compatibility.md).
