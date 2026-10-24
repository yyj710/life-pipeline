"""
基于 tag_diary 的结果，创建和维护 wiki/ 概念页/实体页/主题页
"""
import re
import yaml
from datetime import datetime
from pathlib import Path
from collections import defaultdict

import config
from utils import parse_frontmatter, build_frontmatter
from tag_diary import SEED_ENTITIES


def ensure_wiki_dirs():
    """确保 wiki 子目录存在"""
    for sub in ["concepts", "entities", "topics"]:
        (config.VAULT_ROOT / "wiki" / sub).mkdir(parents=True, exist_ok=True)


def entity_path(name: str, etype: str) -> Path:
    """根据实体类型返回目标文件路径"""
    if etype == "concept":
        sub = "concepts"
    elif etype == "topic":
        sub = "topics"
    else:
        sub = "entities"
    return config.VAULT_ROOT / "wiki" / sub / f"{name}.md"


def page_exists(name: str, etype: str) -> bool:
    """检查实体页面是否已存在"""
    return entity_path(name, etype).exists()


def create_stub(name: str, etype: str, category: str, first_diary: str, context: str):
    """创建 stub 页面"""
    filepath = entity_path(name, etype)
    if filepath.exists():
        return False

    tags = []
    if etype == "concept":
        tags.append("概念")
    elif etype == "topic":
        tags.append("主题")
    else:
        tags.append("实体")
    if category:
        tags.append(category)

    content = f"""---
title: "{name}"
type: {etype}
tags: [{', '.join(tags)}]
created: {datetime.now().strftime('%Y-%m-%d')}
summary: ""
---
# {name}

## 首次提及
- [[日记/{first_diary}|{first_diary[:10]}]]: {context}

## 后续提及
<!-- AI 自动追加 -->
"""
    filepath.write_text(content, encoding="utf-8")
    print(f"  新建 stub: wiki/{entity_path(name, etype).parent.name}/{name}.md")
    return True


def update_existing_page(name: str, etype: str, new_mentions: list[dict]):
    """给已有页面追加新的提及记录"""
    filepath = entity_path(name, etype)
    if not filepath.exists():
        return

    content = filepath.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(content)

    today = datetime.now().strftime("%Y-%m-%d")

    # 在"后续提及"区域追加
    new_lines = []
    for mention in new_mentions:
        diary_name = mention.get("diary", "unknown")
        diary_date = diary_name[:10] if len(diary_name) >= 10 else diary_name
        context = mention.get("context", "")
        line = f"- [[日记/{diary_name}|{diary_date}]]: {context}"
        if line not in body:
            new_lines.append(line)

    if new_lines:
        # 找到"后续提及"标题位置，在后面追加
        if "## 后续提及" in body:
            body = body.replace("## 后续提及\n", "## 后续提及\n\n" + "\n".join(new_lines) + "\n")
        else:
            body += "\n\n## 后续提及\n\n" + "\n".join(new_lines) + "\n"

        new_content = build_frontmatter(fm) + "\n\n" + body
        filepath.write_text(new_content, encoding="utf-8")
        print(f"  更新页面: wiki/{entity_path(name, etype).parent.name}/{name}.md (+{len(new_lines)}条)")



def update_index():
    """更新 wiki/INDEX.md"""
    wiki_dir = config.VAULT_ROOT / "wiki"
    index_path = wiki_dir / "INDEX.md"

    sections = {"concepts": [], "entities": [], "topics": []}

    for sub in sections:
        sd = wiki_dir / sub
        if not sd.exists():
            continue
        for f in sorted(sd.glob("*.md")):
            content = f.read_text(encoding="utf-8")
            fm, _ = parse_frontmatter(content)
            title = fm.get("title", f.stem)
            summary = fm.get("summary", "")
            line = f"- [[{sub}/{f.stem}|{title}]]"
            if summary:
                line += f" — {summary}"
            sections[sub].append(line)

    lines = [
        "---",
        "title: \"Wiki 索引\"",
        "tags: [MOC, wiki, 索引]",
        f"updated: {datetime.now().strftime('%Y-%m-%d')}",
        "type: index",
        "summary: \"Wiki层全局索引\"",
        "---",
        "# Wiki 索引",
        "",
        "## 概念 (concepts/)",
        "",
    ]
    if sections["concepts"]:
        lines.extend(sections["concepts"])
    else:
        lines.append("*暂无条目*")
    lines.extend(["", "## 实体 (entities/)", ""])
    if sections["entities"]:
        lines.extend(sections["entities"])
    else:
        lines.append("*暂无条目*")
    lines.extend(["", "## 主题 (topics/)", ""])
    if sections["topics"]:
        lines.extend(sections["topics"])
    else:
        lines.append("*暂无条目*")
    lines.extend(["", "---", "", "*本索引由 AI 自动维护*"])

    index_path.write_text("\n".join(lines), encoding="utf-8")


def maintain_wiki(new_entities: dict, dry_run: bool = None, existing_mentions: dict = None):
    """维护 wiki：创建 stub + 更新已有页面 + 重建索引"""
    if dry_run is None:
        dry_run = config.DRY_RUN

    print("=" * 50)
    print(f"Wiki 维护 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)

    if existing_mentions is None:
        existing_mentions = {}

    ensure_wiki_dirs()

    created = 0
    for name, info in new_entities.items():
        etype = info.get("type", "entity")
        category = info.get("category", "")
        first_diary = info.get("first_diary", "")
        context = info.get("context", "")

        if not page_exists(name, etype) and info.get("count", 0) >= 2:
            if not dry_run:
                create_stub(name, etype, category, first_diary, context)
            else:
                print(f"  [DRY-RUN] 将创建 stub: wiki/{entity_path(name, etype).parent.name}/{name}.md")
            created += 1

    updated = 0
    for name, mentions in existing_mentions.items():
        if not mentions:
            continue
        # 确定实体类型：先查已有页面，再查 SEED_ENTITIES
        etype = "entity"
        category = ""
        for sub in ["concepts", "entities", "topics"]:
            if (config.VAULT_ROOT / "wiki" / sub / f"{name}.md").exists():
                etype = sub.rstrip("s")
                break
        if name in SEED_ENTITIES:
            etype = SEED_ENTITIES[name].get("type", etype)
            category = SEED_ENTITIES[name].get("category", "")
        # 如果页面不存在，先创建
        if not page_exists(name, etype):
            first_diary = mentions[0].get("diary", "")
            context = mentions[0].get("context", "")
            if not dry_run:
                create_stub(name, etype, category, first_diary, context)
                created += 1
            else:
                print(f"  [DRY-RUN] 将创建 stub: wiki/{entity_path(name, etype).parent.name}/{name}.md")
        # 追加提及
        if not dry_run:
            update_existing_page(name, etype, mentions)
        else:
            print(f"  [DRY-RUN] 将更新页面: {name} (+{len(mentions)}条)")
        updated += 1

    if not dry_run:
        update_index()
    else:
        print(f"  [DRY-RUN] 将更新 wiki/INDEX.md")

    print(f"Wiki 维护完成: 新建 {created} 个页面 | 更新 {updated} 个页面")
    return created


if __name__ == "__main__":
    maintain_wiki({})
