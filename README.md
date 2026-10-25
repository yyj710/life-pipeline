# life-pipeline · Diary Automation Pipeline

> **中文版本 → [README.zh-CN.md](./README.zh-CN.md)**
>
> One-liner: I journal daily in Obsidian; this Python pipeline **automatically** turns diary entries into tags, wiki pages, weekly reviews, a cognition profile and interview questions — without me editing a word.

![Python](https://img.shields.io/badge/Python-3.x-3776ab)
![Feishu](https://img.shields.io/badge/飞书-Bitable%20API-00d6b9)
![Obsidian](https://img.shields.io/badge/Obsidian-vault-7c3aed)

## What it does

**Pain**: journaling is easy, but entries die after writing — nobody re-reads them, experience doesn't compound, ideas aren't tracked.

**Solution**: one command, `python pipeline.py weekly`, runs 7 automated steps:

```
Your diary (plain text)
  │
  ├─ 1. Tagging       → 2-6 tags + [[bidirectional links]] per entry
  ├─ 2. Wiki building → auto-create pages for mentioned people/concepts
  ├─ 3. Weekly review → draft of "what I did and thought this week"
  ├─ 4. Daily draft   → scans today's entries, produces v0.1 insights
  ├─ 5. Cognition     → detects changes (new decisions/focus/shifts), append-only
  ├─ 6. Business radar→ surfaces business ideas from diary, builds triage list
  └─ 7. Feishu sync   → time records → Feishu Bitable → weekly report
```

**Status**: a production system that has run for months, not a toy script. My diary went from "write and forget" to "a self-growing personal database".

## What's in it for you

Four things you can take directly:

1. **`examples/` = a Feishu (Lark) API cookbook** — runnable samples for messaging, calendar, docs, approvals; faster than the official docs
2. **Rules over models** — tagging uses dictionaries + rules (`config/*.yaml`), not NLP/LLM APIs: zero cost, explainable, debuggable. Rules are enough for most personal automation
3. **The blast-radius table** (below) — check downstream impact before changing code; copyable to your own projects
4. **Pipeline design pattern** — each step runs independently, supports dry-run preview, one step's failure doesn't crash the rest

## File guide (one line per file)

### Entry point
| File | Purpose |
|------|---------|
| `pipeline.py` | CLI entry, chains the 7 steps, supports `weekly` / `--dry-run` |

### The 7-step engine
| File | Purpose |
|------|---------|
| `tag_diary.py` | Scans this week's diary → tags + links → writes back |
| `update_wiki.py` | Creates/maintains wiki concept & entity pages from tag results |
| `analyze_diary.py` | Reads week's diary + time logs → weekly review draft |
| `daily_draft.py` | Scans today's entries → v0.1 insights into the pending pool |
| `update_cognition.py` | Detects weekly cognitive changes → updates cognition profile |
| `dbs_scan.py` | Extracts business signals from diary → triage list |
| `interview_engine.py` | Generates context-aware questions for the weekly deep interview |

### Shared layer (change with care)
| File | Purpose |
|------|---------|
| `config.py` | Global config: paths, constants, interview topics |
| `utils.py` | Shared utils: frontmatter parse/build (6 modules depend on it) |
| `feishu_client.py` | Feishu API wrapper: auth, Bitable read/write |
| `config_loader.py` | Loads `config/*.yaml` rule files |

### Ops & extras
| File | Purpose |
|------|---------|
| `sync_bitable.py` | Feishu Bitable → Obsidian time-record sync |
| `daily_reminder.py` | Daily habit checklist reminder |
| `select_github_projects.py` | Picks GitHub projects worth studying |
| `pipeline_log.py` | Pipeline run logging |
| `cleanup.py` | Periodic cleanup of old files |
| `test_basic.py` | Basic tests |

### Rules & docs
| File | Purpose |
|------|---------|
| `config/*.yaml` | Tag dictionary, business signals, entity dictionary — the rule engine's "database" |
| `pipeline_rules.md` | Metrics-driven + failure-handling rules |
| `interview_rules.md` | Weekly deep-interview process |
| `examples/*.py` | Runnable Feishu API samples: IM/calendar/docs/approval |

## Blast-radius table

Required reading before editing — the most copyable engineering practice here:

| If you change | Downstream impact | Risk |
|---------------|-------------------|------|
| `utils.py` | 6 engine modules | **High** |
| `config.py` | Nearly everything | **Critical** |
| `feishu_client.py` | sync_bitable / pipeline | **High** |
| `config_loader.py` | tag_diary / analyze_diary | Medium |
| Other modules | only called by pipeline | Low |

Rule: touching anything marked High/Critical requires a `python pipeline.py weekly --dry-run` first.

## Quick start

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in Feishu credentials and vault path
python pipeline.py weekly --dry-run   # preview without writing
python pipeline.py weekly             # run the 7 steps
```

## Design principles

- **No entity without necessity** — if rules solve it, don't add a model
- **Less over more** — 2-6 tags per entry, priority-ordered
- **Append, never rewrite** — the cognition profile keeps its evolution history
- **Dry-run first** — every write operation can be previewed
