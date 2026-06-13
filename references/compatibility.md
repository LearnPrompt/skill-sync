# Compatibility Model

`skill-sync` uses a simple portability rule:

- A skill directory with `SKILL.md` is treated as portable and eligible for symlink-based sharing.
- A standalone `*.skill` file is treated as Claude-specific.
- A directory without `SKILL.md` is treated as host-specific unless you manually standardize it later.

This heuristic is intentional. It keeps the default sync path safe and predictable.

## Current Host Roots

- `codex`: `~/.codex/skills`
- `agents`: `~/.agents/skills`
- `claude`: `~/.claude/skills`
- `claude-vendor`: `~/.claude/skills/anthropic-skills/skills`
- `hermes`: `~/.hermes/skills` (direct skills plus one level of categorized subfolders)
- `opencode`: `~/.config/opencode/skills`
- `openclaw`: `~/.openclaw/skills`
- `openclaw-plugin`: `~/.openclaw/extensions/*/skills`

Only primary roots are used as symlink destinations:

- `codex`
- `agents`
- `claude`
- `hermes`
- `opencode`
- `openclaw`

Nested vendor/plugin roots are scanned for discovery, but they are not used as sync targets.

## Deduplication Strategies

- `strict`: only dedupe groups whose full portable content hash matches
- `prefer-latest`: dedupe any all-portable `SKILL.md` group and keep the newest real path
- `trust-high`: same canonical source rule as `prefer-latest`, but it may also replace scanned vendor/plugin installs

## Drift Baselines

`--record-baseline` stores the canonical content hash of every discovered skill in `~/.skill-sync/baselines.json` (`SKILL_SYNC_BASELINE_STORE` or `--baseline-store` overrides the location).

Drift states derived from the baseline:

- `pristine`: every portable copy matches the recorded hash
- `dirty`: at least one copy differs from the recorded hash (local edits)
- `local-only`: no baseline recorded for this skill

Dedupe interaction: under `prefer-latest` and `trust-high`, a replacement candidate whose hash matches neither the baseline nor the selected canonical source is treated as dirty and skipped. The plan lists it under `skipped_dirty`, and only `--allow-dirty` lets it be replaced (after backup, as always). `strict` is unaffected because it only ever touches identical copies.

## Backup And Restore

Applied runs are stored under:

- `~/.skill-sync/backups/<run-id>/manifest.json`
- `~/.skill-sync/backups/<run-id>/originals/...`
- `~/.skill-sync/backups/latest`

Restore flow:

1. Preview with `--restore latest`
2. Apply with `--restore latest --apply`

The manifest records:

- action type
- original path
- symlink target
- backup payload path when a duplicate install was replaced
