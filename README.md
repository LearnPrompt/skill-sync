# skill-sync

`skill-sync` 是一个轻量的本地 Skill 管理工具，用来扫描多个 AI Agent 宿主中的 Skill，并把重复安装收敛为“一个 canonical source + 多处软链接”。

## 功能

- 扫描本机多个宿主下的 Skill 安装
- 分类 `shared / duplicate / compatible / specific / mixed`
- 规划缺失软链接
- 自动选择 canonical source
- 将重复副本替换成软链接
- 备份被替换的副本并支持恢复

## 支持扫描的宿主

- `~/.codex/skills`
- `~/.agents/skills`
- `~/.claude/skills`
- `~/.claude/skills/anthropic-skills/skills`
- `~/.config/opencode/skills`
- `~/.openclaw/skills`
- `~/.openclaw/extensions/*/skills`

## 快速开始

在仓库根目录运行：

```bash
python3 scripts/skill_sync.py
```

只预览去重计划：

```bash
python3 scripts/skill_sync.py --dedupe --strategy strict
```

按“保留最新版本”策略执行去重：

```bash
python3 scripts/skill_sync.py --dedupe --strategy prefer-latest --apply
```

恢复最近一次执行：

```bash
python3 scripts/skill_sync.py --restore latest
python3 scripts/skill_sync.py --restore latest --apply
```

## 策略

- `strict`：只处理内容完全一致的可移植 Skill
- `prefer-latest`：同名可移植 Skill 内容不一致时，保留最新修改时间的版本
- `trust-high`：在 `prefer-latest` 基础上，也允许替换更激进的扫描根目录

## 备份

执行 `--apply` 后，备份默认写到：

```bash
~/.skill-sync/backups/<run-id>/
```

其中包含：

- `manifest.json`
- `originals/...`
- `latest` 指针

## 项目结构

```text
.
├── SKILL.md
├── agents/openai.yaml
├── references/compatibility.md
└── scripts/skill_sync.py
```

## License

MIT
