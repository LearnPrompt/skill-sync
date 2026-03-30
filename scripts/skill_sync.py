#!/usr/bin/env python3
"""
Discover, deduplicate, and safely share local skills across AI agent hosts.

Examples:
    python3 skill_sync.py
    python3 skill_sync.py --sync-missing
    python3 skill_sync.py --dedupe --strategy strict
    python3 skill_sync.py --dedupe --strategy prefer-latest --apply
    python3 skill_sync.py --restore latest
    python3 skill_sync.py --restore 20260330-203000 --apply
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


IGNORE_NAMES = {".DS_Store", "__pycache__"}
PRIMARY_PLATFORMS = ("agents", "codex", "claude", "opencode", "openclaw")
STATUS_ORDER = ("shared", "duplicate", "compatible", "specific", "mixed")
SCRIPT_PATH = Path(__file__).resolve()


@dataclass(frozen=True)
class RootSpec:
    platform: str
    label: str
    path: Path
    link_target: bool


@dataclass(frozen=True)
class SkillEntry:
    name: str
    platform: str
    root_label: str
    path: Path
    resolved_path: Path
    format: str
    portable: bool
    symlinked: bool
    link_target: bool
    content_hash: str | None
    latest_mtime_ns: int


def env_path(name: str, default: str) -> Path:
    return Path(os.environ.get(name, default)).expanduser()


def build_root_specs() -> list[RootSpec]:
    home = Path.home()
    roots: list[RootSpec] = []

    primary_roots = [
        RootSpec(
            platform="codex",
            label="home",
            path=env_path("SKILL_SYNC_CODEX_ROOT", str(home / ".codex" / "skills")),
            link_target=True,
        ),
        RootSpec(
            platform="agents",
            label="shared",
            path=env_path("SKILL_SYNC_AGENTS_ROOT", str(home / ".agents" / "skills")),
            link_target=True,
        ),
        RootSpec(
            platform="claude",
            label="home",
            path=env_path("SKILL_SYNC_CLAUDE_ROOT", str(home / ".claude" / "skills")),
            link_target=True,
        ),
        RootSpec(
            platform="opencode",
            label="home",
            path=env_path(
                "SKILL_SYNC_OPENCODE_ROOT",
                str(home / ".config" / "opencode" / "skills"),
            ),
            link_target=True,
        ),
        RootSpec(
            platform="openclaw",
            label="home",
            path=env_path(
                "SKILL_SYNC_OPENCLAW_ROOT",
                str(home / ".openclaw" / "skills"),
            ),
            link_target=True,
        ),
    ]

    roots.extend(root for root in primary_roots if root.path.is_dir())

    claude_vendor = env_path(
        "SKILL_SYNC_CLAUDE_VENDOR_ROOT",
        str(home / ".claude" / "skills" / "anthropic-skills" / "skills"),
    )
    if claude_vendor.is_dir():
        roots.append(
            RootSpec(
                platform="claude",
                label="vendor",
                path=claude_vendor,
                link_target=False,
            )
        )

    openclaw_extensions_root = env_path(
        "SKILL_SYNC_OPENCLAW_EXTENSIONS_ROOT",
        str(home / ".openclaw" / "extensions"),
    )
    if openclaw_extensions_root.is_dir():
        for skills_root in sorted(openclaw_extensions_root.glob("*/skills")):
            plugin_name = skills_root.parent.name
            roots.append(
                RootSpec(
                    platform="openclaw",
                    label=f"plugin:{plugin_name}",
                    path=skills_root,
                    link_target=False,
                )
            )

    return roots


def iter_root_entries(root: RootSpec) -> Iterable[Path]:
    try:
        children = sorted(root.path.iterdir(), key=lambda item: item.name.lower())
    except OSError:
        return []

    return [child for child in children if not child.name.startswith(".")]


def hash_file(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def hash_directory(path: Path) -> str | None:
    try:
        digest = hashlib.sha256()
        digest.update(b"skill-sync-directory-v1\n")

        for current_root, dirnames, filenames in os.walk(
            path, topdown=True, followlinks=False
        ):
            current = Path(current_root)
            latest_dirs: list[str] = []

            filtered_dirs = sorted(name for name in dirnames if name not in IGNORE_NAMES)
            for name in filtered_dirs:
                full_path = current / name
                relative = full_path.relative_to(path).as_posix()
                if full_path.is_symlink():
                    digest.update(
                        f"L {relative} -> {os.readlink(full_path)}\n".encode("utf-8")
                    )
                else:
                    digest.update(f"D {relative}\n".encode("utf-8"))
                    latest_dirs.append(name)
            dirnames[:] = latest_dirs

            filtered_files = sorted(
                name for name in filenames if name not in IGNORE_NAMES
            )
            for name in filtered_files:
                full_path = current / name
                relative = full_path.relative_to(path).as_posix()
                if full_path.is_symlink():
                    digest.update(
                        f"L {relative} -> {os.readlink(full_path)}\n".encode("utf-8")
                    )
                    continue

                digest.update(f"F {relative}\n".encode("utf-8"))
                digest.update(full_path.read_bytes())
                digest.update(b"\n")
    except OSError:
        return None

    return digest.hexdigest()


def latest_mtime_ns(path: Path) -> int:
    try:
        latest = path.lstat().st_mtime_ns
    except OSError:
        return 0

    if not path.is_dir():
        return latest

    for current_root, dirnames, filenames in os.walk(path, topdown=True, followlinks=False):
        current = Path(current_root)
        dirnames[:] = sorted(name for name in dirnames if name not in IGNORE_NAMES)
        filenames = sorted(name for name in filenames if name not in IGNORE_NAMES)

        for name in dirnames:
            try:
                latest = max(latest, (current / name).lstat().st_mtime_ns)
            except OSError:
                continue

        for name in filenames:
            try:
                latest = max(latest, (current / name).lstat().st_mtime_ns)
            except OSError:
                continue

    return latest


def analyze_path(
    path: Path,
    entry_format: str,
    portable: bool,
    cache: dict[str, tuple[str | None, int]],
) -> tuple[str | None, int]:
    cache_key = f"{path}:{entry_format}:{portable}"
    if cache_key in cache:
        return cache[cache_key]

    if portable and path.is_dir():
        result = (hash_directory(path), latest_mtime_ns(path))
    elif path.is_file():
        result = (hash_file(path), latest_mtime_ns(path))
    else:
        result = (None, latest_mtime_ns(path))

    cache[cache_key] = result
    return result


def detect_entry(path: Path) -> tuple[str, bool] | None:
    if path.is_file() and path.suffix == ".skill":
        return ("claude-skill-file", False)

    if not path.is_dir():
        return None

    if (path / "SKILL.md").is_file():
        return ("skill-md", True)

    if (path / "_meta.json").is_file():
        return ("openclaw-meta", False)

    embedded_skill_files = sorted(path.glob("*.skill"))
    if embedded_skill_files:
        return ("claude-skill-bundle", False)

    if (path / "skills").is_dir():
        return None

    try:
        has_visible_content = any(not part.name.startswith(".") for part in path.iterdir())
    except OSError:
        has_visible_content = False

    if has_visible_content:
        return ("directory-unknown", False)

    return None


def discover_skills(roots: list[RootSpec], skill_filter: set[str]) -> list[SkillEntry]:
    entries: list[SkillEntry] = []
    cache: dict[str, tuple[str | None, int]] = {}

    for root in roots:
        for path in iter_root_entries(root):
            detected = detect_entry(path)
            if detected is None:
                continue

            name = path.stem if path.is_file() else path.name
            if skill_filter and name not in skill_filter:
                continue

            entry_format, portable = detected
            try:
                resolved_path = path.resolve(strict=False)
            except OSError:
                resolved_path = path

            content_hash, last_mtime = analyze_path(
                resolved_path,
                entry_format=entry_format,
                portable=portable,
                cache=cache,
            )

            entries.append(
                SkillEntry(
                    name=name,
                    platform=root.platform,
                    root_label=root.label,
                    path=path,
                    resolved_path=resolved_path,
                    format=entry_format,
                    portable=portable,
                    symlinked=path.is_symlink(),
                    link_target=root.link_target,
                    content_hash=content_hash,
                    latest_mtime_ns=last_mtime,
                )
            )

    return entries


def classify_group(entries: list[SkillEntry]) -> dict:
    portable_entries = [entry for entry in entries if entry.portable]
    resolved_paths = {str(entry.resolved_path) for entry in entries}
    content_hashes = {
        entry.content_hash for entry in portable_entries if entry.content_hash is not None
    }
    platforms = sorted({entry.platform for entry in entries})

    if len(entries) == 1:
        status = "specific"
        reason = "only found on one host"
    elif len(resolved_paths) == 1:
        status = "shared"
        reason = "all hosts point to the same real path"
    elif portable_entries and len(portable_entries) == len(entries) and len(content_hashes) == 1:
        status = "duplicate"
        reason = "portable skill content matches across multiple real paths"
    elif portable_entries and len(portable_entries) == len(entries):
        status = "compatible"
        reason = "portable skill exists on multiple hosts but content differs"
    else:
        status = "mixed"
        reason = "same skill name exists with incompatible formats or host-specific content"

    return {
        "status": status,
        "reason": reason,
        "platforms": platforms,
    }


def should_use_group_for_canonical(status: str, strategy: str, allow_specific: bool) -> bool:
    if allow_specific and status == "specific":
        return True
    if strategy == "strict":
        return status in {"shared", "duplicate"}
    return status in {"shared", "duplicate", "compatible"}


def choose_canonical_source(
    entries: list[SkillEntry],
    source_order: list[str],
    strategy: str,
    allow_specific: bool = False,
) -> dict | None:
    summary = classify_group(entries)
    if not should_use_group_for_canonical(summary["status"], strategy, allow_specific):
        return None

    portable_entries = [entry for entry in entries if entry.portable]
    if not portable_entries:
        return None

    order_index = {platform: index for index, platform in enumerate(source_order)}
    candidates: list[dict] = []
    grouped_by_real_path: dict[str, list[SkillEntry]] = defaultdict(list)
    for entry in portable_entries:
        grouped_by_real_path[str(entry.resolved_path)].append(entry)

    for resolved_path, candidate_entries in grouped_by_real_path.items():
        representative = sorted(
            candidate_entries,
            key=lambda entry: (
                0 if not entry.symlinked else 1,
                order_index.get(entry.platform, len(order_index) + 1),
                -entry.latest_mtime_ns,
                str(entry.path),
            ),
        )[0]
        candidates.append(
            {
                "display_path": str(representative.path),
                "source_path": resolved_path,
                "resolved_path": resolved_path,
                "platform": representative.platform,
                "root_label": representative.root_label,
                "shared_count": len(candidate_entries),
                "content_hash": representative.content_hash,
                "latest_mtime_ns": max(
                    entry.latest_mtime_ns for entry in candidate_entries
                ),
                "platform_rank": min(
                    order_index.get(entry.platform, len(order_index) + 1)
                    for entry in candidate_entries
                ),
            }
        )

    if not candidates:
        return None

    if strategy == "strict":
        selected = sorted(
            candidates,
            key=lambda item: (
                -item["shared_count"],
                item["platform_rank"],
                -item["latest_mtime_ns"],
                item["source_path"],
            ),
        )[0]
        selected_by = "strict: shared-count then source-order"
    else:
        selected = sorted(
            candidates,
            key=lambda item: (
                -item["latest_mtime_ns"],
                -item["shared_count"],
                item["platform_rank"],
                item["source_path"],
            ),
        )[0]
        selected_by = f"{strategy}: latest-mtime then shared-count"

    selected["selected_by"] = selected_by
    selected["group_status"] = summary["status"]
    return selected


def build_missing_link_plan(
    grouped_entries: dict[str, list[SkillEntry]],
    roots: list[RootSpec],
    source_order: list[str],
    strategy: str,
) -> list[dict]:
    primary_roots = {
        root.platform: root
        for root in roots
        if root.link_target and root.platform in PRIMARY_PLATFORMS
    }

    plans: list[dict] = []
    for name, entries in sorted(grouped_entries.items()):
        source = choose_canonical_source(
            entries,
            source_order=source_order,
            strategy=strategy,
            allow_specific=True,
        )
        if source is None:
            continue

        existing_platforms = {entry.platform for entry in entries}
        destinations: list[dict] = []
        for platform in PRIMARY_PLATFORMS:
            if platform in existing_platforms:
                continue

            destination_root = primary_roots.get(platform)
            if destination_root is None:
                continue

            destination_path = destination_root.path / name
            if destination_path.exists() or destination_path.is_symlink():
                continue

            destinations.append(
                {
                    "platform": platform,
                    "path": str(destination_path),
                }
            )

        if destinations:
            plans.append(
                {
                    "name": name,
                    "group_status": source["group_status"],
                    "source_platform": source["platform"],
                    "source_root_label": source["root_label"],
                    "source_display_path": source["display_path"],
                    "source_path": source["source_path"],
                    "selected_by": source["selected_by"],
                    "destinations": destinations,
                }
            )

    return plans


def can_replace_entry(entry: SkillEntry, strategy: str) -> bool:
    return entry.portable and (entry.link_target or strategy == "trust-high")


def build_dedupe_plan(
    grouped_entries: dict[str, list[SkillEntry]],
    source_order: list[str],
    strategy: str,
) -> list[dict]:
    plans: list[dict] = []

    for name, entries in sorted(grouped_entries.items()):
        if len(entries) < 2:
            continue

        source = choose_canonical_source(
            entries,
            source_order=source_order,
            strategy=strategy,
            allow_specific=False,
        )
        if source is None:
            continue

        replacements: list[dict] = []
        for entry in sorted(
            entries,
            key=lambda item: (item.platform, item.root_label, str(item.path)),
        ):
            if not can_replace_entry(entry, strategy):
                continue
            if str(entry.resolved_path) == source["resolved_path"]:
                continue

            replacements.append(
                {
                    "platform": entry.platform,
                    "root_label": entry.root_label,
                    "path": str(entry.path),
                    "resolved_path": str(entry.resolved_path),
                    "symlinked": entry.symlinked,
                }
            )

        if replacements:
            plans.append(
                {
                    "name": name,
                    "group_status": source["group_status"],
                    "source_platform": source["platform"],
                    "source_root_label": source["root_label"],
                    "source_display_path": source["display_path"],
                    "source_path": source["source_path"],
                    "selected_by": source["selected_by"],
                    "replacements": replacements,
                }
            )

    return plans


def build_report(
    entries: list[SkillEntry],
    roots: list[RootSpec],
    source_order: list[str],
    strategy: str,
) -> dict:
    grouped_entries: dict[str, list[SkillEntry]] = defaultdict(list)
    for entry in entries:
        grouped_entries[entry.name].append(entry)

    groups: list[dict] = []
    for name in sorted(grouped_entries):
        entries_for_name = sorted(
            grouped_entries[name],
            key=lambda entry: (entry.platform, entry.root_label, str(entry.path)),
        )
        summary = classify_group(entries_for_name)
        groups.append(
            {
                "name": name,
                "status": summary["status"],
                "reason": summary["reason"],
                "platforms": summary["platforms"],
                "entries": [
                    {
                        "platform": entry.platform,
                        "root_label": entry.root_label,
                        "path": str(entry.path),
                        "resolved_path": str(entry.resolved_path),
                        "format": entry.format,
                        "portable": entry.portable,
                        "symlinked": entry.symlinked,
                        "link_target": entry.link_target,
                        "content_hash": entry.content_hash,
                        "latest_mtime_ns": entry.latest_mtime_ns,
                    }
                    for entry in entries_for_name
                ],
            }
        )

    status_counts: dict[str, int] = defaultdict(int)
    for group in groups:
        status_counts[group["status"]] += 1

    planned_links = build_missing_link_plan(
        grouped_entries,
        roots=roots,
        source_order=source_order,
        strategy=strategy,
    )
    dedupe_plan = build_dedupe_plan(
        grouped_entries,
        source_order=source_order,
        strategy=strategy,
    )

    return {
        "roots": [
            {
                "platform": root.platform,
                "label": root.label,
                "path": str(root.path),
                "link_target": root.link_target,
            }
            for root in roots
        ],
        "summary": {
            "total_skills": len(groups),
            "status_counts": {
                status: status_counts.get(status, 0) for status in STATUS_ORDER
            },
            "discovered_entries": len(entries),
            "planned_missing_links": sum(
                len(item["destinations"]) for item in planned_links
            ),
            "planned_dedupe_replacements": sum(
                len(item["replacements"]) for item in dedupe_plan
            ),
        },
        "groups": groups,
        "planned_links": planned_links,
        "dedupe_plan": dedupe_plan,
        "strategy": strategy,
    }


def build_operations(report: dict, sync_missing: bool, dedupe: bool) -> list[dict]:
    operations: list[dict] = []

    if dedupe:
        for plan in report["dedupe_plan"]:
            for replacement in plan["replacements"]:
                operations.append(
                    {
                        "action": "replace_with_symlink",
                        "name": plan["name"],
                        "strategy": report["strategy"],
                        "path": replacement["path"],
                        "target_path": plan["source_path"],
                        "target_is_directory": True,
                    }
                )

    if sync_missing:
        for plan in report["planned_links"]:
            for destination in plan["destinations"]:
                operations.append(
                    {
                        "action": "create_symlink",
                        "name": plan["name"],
                        "strategy": report["strategy"],
                        "path": destination["path"],
                        "target_path": plan["source_path"],
                        "target_is_directory": True,
                    }
                )

    return operations


def make_run_id(backup_root: Path) -> str:
    base = datetime.now().strftime("%Y%m%d-%H%M%S")
    candidate = base
    suffix = 1
    while (backup_root / candidate).exists():
        suffix += 1
        candidate = f"{base}-{suffix:02d}"
    return candidate


def absolute_to_backup_path(run_dir: Path, original_path: Path) -> Path:
    absolute = Path(os.path.abspath(str(original_path.expanduser())))
    relative = Path(str(absolute).lstrip("/"))
    return run_dir / "originals" / relative


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def update_latest_pointer(backup_root: Path, run_dir: Path) -> None:
    latest = backup_root / "latest"
    try:
        if latest.is_symlink() or latest.is_file():
            latest.unlink()
        elif latest.is_dir():
            return
    except OSError:
        return

    try:
        latest.symlink_to(run_dir, target_is_directory=True)
    except OSError:
        return


def apply_operations(operations: list[dict], backup_root: Path) -> dict | None:
    if not operations:
        return None

    backup_root.mkdir(parents=True, exist_ok=True)
    run_id = make_run_id(backup_root)
    run_dir = backup_root / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    manifest = {
        "version": 1,
        "run_id": run_id,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "backup_root": str(backup_root),
        "run_dir": str(run_dir),
        "actions": [],
    }
    manifest_path = run_dir / "manifest.json"
    write_json(manifest_path, manifest)

    for operation in operations:
        destination = Path(operation["path"])
        target_path = Path(operation["target_path"])
        action_record = dict(operation)
        action_record["target_path"] = str(target_path)

        if operation["action"] == "replace_with_symlink":
            backup_path = absolute_to_backup_path(run_dir, destination)
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(destination), str(backup_path))
            destination.symlink_to(
                target_path,
                target_is_directory=bool(operation["target_is_directory"]),
            )
            action_record["backup_path"] = str(backup_path)
        elif operation["action"] == "create_symlink":
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.symlink_to(
                target_path,
                target_is_directory=bool(operation["target_is_directory"]),
            )
        else:
            raise ValueError(f"Unsupported action: {operation['action']}")

        manifest["actions"].append(action_record)
        write_json(manifest_path, manifest)

    update_latest_pointer(backup_root, run_dir)
    return manifest


def resolve_run_dir(backup_root: Path, run_id: str) -> Path:
    if run_id == "latest":
        latest = backup_root / "latest"
        if latest.is_symlink():
            return latest.resolve(strict=False)
        raise SystemExit("No latest backup run is available")

    run_dir = backup_root / run_id
    if not run_dir.is_dir():
        raise SystemExit(f"Backup run not found: {run_id}")
    return run_dir


def restore_run(run_dir: Path, apply: bool) -> dict:
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.is_file():
        raise SystemExit(f"Missing manifest: {manifest_path}")

    manifest = json.loads(manifest_path.read_text())
    actions = manifest.get("actions", [])

    if not apply:
        return manifest

    for action in reversed(actions):
        destination = Path(action["path"])

        if destination.is_symlink():
            destination.unlink()
        elif destination.exists():
            raise SystemExit(
                f"Restore blocked because destination is no longer a symlink: {destination}"
            )

        backup_path = action.get("backup_path")
        if backup_path:
            source_backup = Path(backup_path)
            if not source_backup.exists() and not source_backup.is_symlink():
                raise SystemExit(f"Missing backup payload: {source_backup}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source_backup), str(destination))

    manifest["restored_at"] = datetime.now().isoformat(timespec="seconds")
    write_json(manifest_path, manifest)
    return manifest


def format_text(report: dict, sync_missing: bool, dedupe: bool, apply: bool) -> str:
    lines: list[str] = []
    summary = report["summary"]

    lines.append(
        "Discovered "
        f"{summary['total_skills']} unique skills from "
        f"{summary['discovered_entries']} installs."
    )
    lines.append(f"Strategy: {report['strategy']}")
    counts = summary["status_counts"]
    lines.append(
        "Status counts: "
        + ", ".join(f"{key}={counts.get(key, 0)}" for key in STATUS_ORDER)
    )
    lines.append("")

    for status in STATUS_ORDER:
        matching = [group for group in report["groups"] if group["status"] == status]
        if not matching:
            continue

        lines.append(status.upper())
        for group in matching:
            lines.append(
                f"- {group['name']}: {', '.join(group['platforms'])} "
                f"({group['reason']})"
            )
        lines.append("")

    if dedupe:
        title = "APPLIED DEDUPE" if apply else "PLANNED DEDUPE"
        lines.append(title)
        if not report["dedupe_plan"]:
            lines.append("- none")
        else:
            for plan in report["dedupe_plan"]:
                replacements = ", ".join(
                    f"{item['platform']}:{item['path']}" for item in plan["replacements"]
                )
                lines.append(
                    f"- {plan['name']}: keep {plan['source_path']} "
                    f"({plan['selected_by']}) | replace {replacements}"
                )
        lines.append("")

    if sync_missing:
        title = "APPLIED MISSING LINKS" if apply else "PLANNED MISSING LINKS"
        lines.append(title)
        if not report["planned_links"]:
            lines.append("- none")
        else:
            for plan in report["planned_links"]:
                destinations = ", ".join(
                    f"{item['platform']}:{item['path']}" for item in plan["destinations"]
                )
                lines.append(
                    f"- {plan['name']}: source {plan['source_path']} "
                    f"({plan['selected_by']}) | add {destinations}"
                )

    if apply and report.get("run"):
        lines.append("")
        lines.append("BACKUP RUN")
        lines.append(f"- run_id: {report['run']['run_id']}")
        lines.append(f"- backup_root: {report['run']['backup_root']}")
        lines.append(
            f"- restore: python3 {SCRIPT_PATH} --restore {report['run']['run_id']}"
        )

    return "\n".join(lines).strip()


def format_restore_text(manifest: dict, apply: bool) -> str:
    lines = [
        f"Restore run: {manifest['run_id']}",
        f"Created at: {manifest['created_at']}",
        f"Backup root: {manifest['backup_root']}",
        f"Actions: {len(manifest.get('actions', []))}",
        "",
    ]

    lines.append("RESTORE ACTIONS" if apply else "RESTORE PREVIEW")
    if not manifest.get("actions"):
        lines.append("- none")
    else:
        for action in manifest["actions"]:
            if action["action"] == "replace_with_symlink":
                lines.append(
                    f"- restore {action['name']}: {action['path']} "
                    f"from {action['backup_path']}"
                )
            else:
                lines.append(f"- remove created link {action['name']}: {action['path']}")

    if apply and manifest.get("restored_at"):
        lines.append("")
        lines.append(f"Restored at: {manifest['restored_at']}")

    return "\n".join(lines).strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format",
    )
    parser.add_argument(
        "--skill",
        action="append",
        default=[],
        help="Limit to one or more skill names",
    )
    parser.add_argument(
        "--sync-missing",
        action="store_true",
        help="Plan or create symlinks for missing host installs",
    )
    parser.add_argument(
        "--dedupe",
        action="store_true",
        help="Plan or replace duplicate installs with symlinks to a canonical source",
    )
    parser.add_argument(
        "--strategy",
        choices=("strict", "prefer-latest", "trust-high"),
        default="strict",
        help="Canonical source selection and replacement policy",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Execute the requested sync or dedupe plan",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Explicitly request preview mode",
    )
    parser.add_argument(
        "--restore",
        help="Restore a previous backup run id or 'latest'",
    )
    parser.add_argument(
        "--backup-root",
        default=str(env_path("SKILL_SYNC_BACKUP_ROOT", str(Path.home() / ".skill-sync" / "backups"))),
        help="Directory for backup runs and restore manifests",
    )
    parser.add_argument(
        "--source-order",
        default="agents,codex,claude,opencode,openclaw",
        help="Preferred source host order when timestamps are tied",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    backup_root = Path(args.backup_root).expanduser()

    if args.restore:
        run_dir = resolve_run_dir(backup_root, args.restore)
        manifest = restore_run(run_dir, apply=args.apply)
        if args.format == "json":
            print(json.dumps(manifest, indent=2, ensure_ascii=False))
        else:
            print(format_restore_text(manifest, apply=args.apply))
        return 0

    if args.apply and not (args.sync_missing or args.dedupe):
        raise SystemExit("--apply requires --sync-missing or --dedupe")

    skill_filter = {item.strip() for item in args.skill if item.strip()}
    roots = build_root_specs()
    source_order = [
        platform.strip()
        for platform in args.source_order.split(",")
        if platform.strip()
    ]
    entries = discover_skills(roots, skill_filter)
    report = build_report(
        entries,
        roots=roots,
        source_order=source_order,
        strategy=args.strategy,
    )

    if args.apply and not args.dry_run:
        operations = build_operations(
            report,
            sync_missing=args.sync_missing,
            dedupe=args.dedupe,
        )
        manifest = apply_operations(operations, backup_root=backup_root)
        if manifest:
            report["run"] = {
                "run_id": manifest["run_id"],
                "backup_root": manifest["backup_root"],
            }

    if args.format == "json":
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0

    print(
        format_text(
            report,
            sync_missing=args.sync_missing,
            dedupe=args.dedupe,
            apply=args.apply and not args.dry_run,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
