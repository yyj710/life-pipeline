"""
扫描本周日记 → 自动打标签 + 加双链 + 回写原文件
不新增 NLP 依赖，基于词典 + 模式匹配
"""
import re
import yaml
import json
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

import config
from utils import parse_frontmatter, build_frontmatter
from config_loader import load_tag_rules, load_seed_entities


# ============================================================
# 种子知识库 — 从 vault 现有内容提取
# ============================================================

SEED_ENTITIES = {
    # 人物
    "李笑来": {"type": "entity", "category": "人物", "aliases": ["笑来"]},
    "CZ": {"type": "entity", "category": "人物", "aliases": ["赵长鹏", "cz"]},
    "王振宇": {"type": "entity", "category": "人物"},
    "邓云瀚": {"type": "entity", "category": "人物"},
    "张行": {"type": "entity", "category": "人物"},
    "蔡垒磊": {"type": "entity", "category": "人物"},
    "广智": {"type": "entity", "category": "人物"},
    # 组织
    "深大": {"type": "entity", "category": "组织", "aliases": ["深圳大学"]},
    "安永": {"type": "entity", "category": "组织"},
    "德勤": {"type": "entity", "category": "组织"},
    "四大": {"type": "entity", "category": "组织"},
    "APEC": {"type": "entity", "category": "组织"},
    # 工具/平台
    "Claude": {"type": "entity", "category": "工具", "aliases": ["Claude Code", "claude"]},
    "Codex": {"type": "entity", "category": "工具"},
    "DeepSeek": {"type": "entity", "category": "工具", "aliases": ["deepseek"]},
    "Obsidian": {"type": "entity", "category": "工具", "aliases": ["ob"]},
    "飞书": {"type": "entity", "category": "工具", "aliases": ["feishu", "lark"]},
    "GitHub": {"type": "entity", "category": "工具", "aliases": ["github"]},
    "Cursor": {"type": "entity", "category": "工具"},
    # 概念
    "价值交换": {"type": "concept", "category": "概念"},
    "杠铃策略": {"type": "concept", "category": "概念"},
    "37%理论": {"type": "concept", "category": "概念"},
    "结果导向": {"type": "concept", "category": "概念"},
    "生产优先": {"type": "concept", "category": "概念"},
    "长期主义": {"type": "concept", "category": "概念"},
    "注意力保护": {"type": "concept", "category": "概念"},
    "资产思维": {"type": "concept", "category": "概念"},
    "一五计划": {"type": "concept", "category": "概念"},
    "数字永生": {"type": "concept", "category": "概念", "aliases": ["数字生命"]},
    "信息节食": {"type": "concept", "category": "概念"},
    "母问题子问题": {"type": "concept", "category": "概念"},
    "被动收入": {"type": "concept", "category": "概念"},
    "财务自由": {"type": "concept", "category": "概念"},
    # 项目
    "jellyAI": {"type": "entity", "category": "项目"},
    "公众号": {"type": "entity", "category": "项目", "aliases": ["自媒体"]},
    "创英前后端": {"type": "entity", "category": "项目", "aliases": ["前后端部署"]},
    "ACCA JHC": {"type": "entity", "category": "项目"},
    # 课程/考试
    "ACCA": {"type": "entity", "category": "课程", "aliases": ["FA", "MA", "LW"]},
    "高等数学": {"type": "entity", "category": "课程", "aliases": ["高数"]},
    "管理学原理": {"type": "entity", "category": "课程"},
    "会计学原理": {"type": "entity", "category": "课程"},
    "雅思": {"type": "entity", "category": "考试", "aliases": ["IELTS"]},
    "四级": {"type": "entity", "category": "考试", "aliases": ["CET4", "六级", "CET6"]},
    # 赛道
    "生产输出": {"type": "topic", "category": "赛道"},
    "英语": {"type": "topic", "category": "赛道"},
    "财务CPA": {"type": "topic", "category": "赛道"},
    "区块链技术": {"type": "topic", "category": "赛道"},
}


# ============================================================
# 标签检测规则
# ============================================================

TAG_RULES = {
    # 维度标签
    "思维模式": ["意识到", "原来", "想通了", "突然明白", "懂了", "思维方式", "思考框架"],
    "价值观": ["价值观", "原则", "重要", "优先级", "更看重", "值得"],
    "情感": ["开心", "难过", "焦虑", "害怕", "喜欢", "感动", "愤怒", "烦躁",
             "失望", "兴奋", "紧张", "担忧", "恐惧", "孤独", "累", "烦", "哭", "崩溃"],
    "决策": ["决定", "以后", "从现在开始", "不再", "改成", "选择", "选"],
    "执行": ["做了", "完成了", "开始做", "在弄", "搞了", "部署", "搭建", "配置"],
    # 情绪标签（细分）
    "兴奋": ["兴奋", "激动", "太好了", "牛逼", "厉害", "终于"],
    "焦虑": ["焦虑", "担心", "怕", "紧张", "压力"],
    "愤怒": ["生气", "愤怒", "恶心", "受不了", "烦死"],
    "失落": ["失落", "难过", "伤心", "失望", "沮丧", "崩溃"],
    "恐惧": ["害怕", "恐惧", "怕", "不安"],
    # 状态标签
    "幻想": ["幻想", "想象", "要是", "如果有一天", "以后我要", "发财了"],
    "纠偏": ["拉回现实", "现实是", "先别想", "脚踏实地", "务实", "实际"],
    "突破": ["突破", "第一次", "终于", "成功了", "拿到", "做到了"],
    "低谷": ["崩了", "失败", "没做好", "不行", "做不到", "放弃了"],
}


def _apply_external_config():
    """尝试从 YAML 配置文件加载，覆盖默认值"""
    global SEED_ENTITIES, TAG_RULES
    ext_entities = load_seed_entities()
    if ext_entities:
        # YAML 格式: {category: {name: {aliases: [...]}}}
        merged = dict(SEED_ENTITIES)
        for category, entities in ext_entities.items():
            etype = "entity"
            if category == "概念":
                etype = "concept"
            elif category == "赛道":
                etype = "topic"
            for name, info in (entities or {}).items():
                info = info or {}
                entry = {"type": info.get("type", etype), "category": category}
                if info.get("aliases"):
                    entry["aliases"] = info["aliases"]
                merged[name] = entry
        SEED_ENTITIES = merged
        print(f"  已从 config/seed_entities.yaml 加载 {len(ext_entities)} 个分类")

    ext_rules = load_tag_rules()
    if ext_rules:
        merged_rules = dict(TAG_RULES)
        for section in ["dimension_tags", "emotion_tags", "state_tags"]:
            if section in ext_rules:
                merged_rules.update(ext_rules[section])
        TAG_RULES = merged_rules
        print(f"  已从 config/tag_rules.yaml 加载标签规则")


def _file_hash(filepath: Path) -> str:
    """计算文件的 SHA-256 哈希（前16位）"""
    return hashlib.sha256(filepath.read_bytes()).hexdigest()[:16]


def _save_knowledge_cache(knowledge: dict):
    """保存知识库缓存，包含所有文件的 hash"""
    cache_path = Path(__file__).parent / ".knowledge_cache.json"

    diary_hashes = {}
    for f in config.DIARY_DIR.glob("*.md"):
        if f.stem == "index":
            continue
        diary_hashes[str(f.relative_to(config.VAULT_ROOT))] = _file_hash(f)

    wiki_hashes = {}
    wiki_dir = config.VAULT_ROOT / "wiki"
    for subdir in ["entities", "concepts", "topics"]:
        for f in (wiki_dir / subdir).glob("*.md"):
            wiki_hashes[str(f.relative_to(config.VAULT_ROOT))] = _file_hash(f)

    cache = {
        "version": 1,
        "last_build": datetime.now().isoformat(),
        "diary_hashes": diary_hashes,
        "wiki_hashes": wiki_hashes,
        "knowledge": knowledge,
    }
    cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def load_vault_knowledge() -> dict:
    """扫描 vault 中已有的实体页面，补充种子知识库（增量更新版）

    原理：缓存上次扫描结果 + 各文件 hash。只处理新增或修改的文件，
    避免每次全量扫描80+篇日记。
    """
    cache_path = Path(__file__).parent / ".knowledge_cache.json"
    knowledge = dict(SEED_ENTITIES)
    cached_hashes = {}

    # 尝试加载缓存
    if cache_path.exists():
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
            if cache.get("version") == 1 and "knowledge" in cache:
                knowledge = cache["knowledge"]
                cached_hashes = {**cache.get("diary_hashes", {}), **cache.get("wiki_hashes", {})}
                print(f"  加载知识库缓存 ({len(knowledge)} 个实体)")
        except (json.JSONDecodeError, KeyError):
            pass  # 缓存损坏，重新构建

    link_pattern = re.compile(r"\[\[([^\]|#]+)(?:[|#][^\]]+)?\]\]")
    wiki_changed = False
    diary_changed = False

    # 扫描 wiki/ 下已有页面（增量）
    wiki_dir = config.VAULT_ROOT / "wiki"
    for subdir in ["entities", "concepts", "topics"]:
        sd = wiki_dir / subdir
        if not sd.exists():
            continue
        for f in sd.glob("*.md"):
            file_key = str(f.relative_to(config.VAULT_ROOT))
            current_hash = _file_hash(f)
            if file_key not in cached_hashes or cached_hashes[file_key] != current_hash:
                name = f.stem
                if name not in knowledge:
                    knowledge[name] = {"type": subdir.rstrip("s"), "category": subdir}
                wiki_changed = True

    # 扫描日记中的 wikilink（增量）
    diary_dir = config.DIARY_DIR
    for f in diary_dir.glob("*.md"):
        if f.stem == "index":
            continue
        file_key = str(f.relative_to(config.VAULT_ROOT))
        current_hash = _file_hash(f)
        if file_key not in cached_hashes or cached_hashes[file_key] != current_hash:
            content = f.read_text(encoding="utf-8")
            for match in link_pattern.finditer(content):
                name = match.group(1).strip()
                if "/" in name or "\\" in name or "#" in name:
                    continue
                if name not in knowledge and len(name) >= 2:
                    knowledge[name] = {"type": "entity", "category": "未分类"}
            diary_changed = True

    if wiki_changed or diary_changed:
        print(f"  知识库更新: wiki变化={wiki_changed}, 日记变化={diary_changed}, 共 {len(knowledge)} 个实体")
        _save_knowledge_cache(knowledge)
    else:
        print(f"  知识库缓存命中，无变化 ({len(knowledge)} 个实体)")

    return knowledge



def detect_tags(body: str) -> list[str]:
    """检测日记内容，返回标签列表"""
    tags = set()
    body_lower = body.lower()

    for tag, keywords in TAG_RULES.items():
        for kw in keywords:
            if kw.lower() in body_lower:
                tags.add(tag)
                break

    # 赛道标签 — 必须在维度标签中出现"执行"、"决策"等才会打上赛道标签
    track_keywords = {
        "生产输出": ["公众号", "自媒体", "写作", "文章", "日更", "输出", "内容创作"],
        "英语": ["英语", "雅思", "听力", "口语", "英文", "单词", "reader"],
        "财务CPA": ["ACCA", "CPA", "会计", "审计", "四大", "财务", "财会", "考试", "绩点", "期末", "FA", "MA", "LW"],
        "区块链技术": ["编程", "代码", "部署", "开发", "web3", "区块链", "AI", "Claude", "技术", "前后端", "Codex"],
    }
    for track, keywords in track_keywords.items():
        for kw in keywords:
            if kw.lower() in body_lower:
                tags.add(track)
                break

    # 关系标签
    relation_keywords = {
        "家人": ["爸", "妈", "父母", "家", "回家", "家里"],
        "朋友": ["朋友", "兄弟", "闺蜜", "俊翰", "俊熙"],
        "恋人": ["女朋友", "恋爱", "约会", "张行", "找女朋友"],
        "导师": ["老师", "教授", "导师"],
        "同学": ["同学", "室友", "舍友", "班级"],
    }
    for rel, keywords in relation_keywords.items():
        for kw in keywords:
            if kw.lower() in body_lower:
                tags.add(rel)
                tags.add("人际关系")
                break

    # 过滤：保留 2-6 个最重要的标签
    priority_order = ["思维模式", "价值观", "情感", "决策", "执行",
                      "兴奋", "焦虑", "愤怒", "失落", "恐惧",
                      "幻想", "纠偏", "突破", "低谷",
                      "生产输出", "英语", "财务CPA", "区块链技术",
                      "家人", "朋友", "恋人", "导师", "同学", "人际关系"]

    final_tags = []
    for tag in priority_order:
        if tag in tags and len(final_tags) < 6:
            final_tags.append(tag)

    return final_tags


def find_entities_in_text(body: str, knowledge: dict) -> list[dict]:
    """在文本中匹配已知实体，返回 [{name, type, category, positions}]"""
    found = []
    # 按实体名长度降序排列，优先匹配长名称
    sorted_entities = sorted(knowledge.items(), key=lambda x: len(x[0]), reverse=True)

    for name, info in sorted_entities:
        positions = []
        # 匹配实体名本身
        for m in re.finditer(re.escape(name), body):
            positions.append(m.start())
        # 匹配别名（短别名加单词边界，避免误匹配）
        for alias in info.get("aliases", []):
            if len(alias) < 3:
                # 短别名使用单词边界
                for m in re.finditer(rf"\b{re.escape(alias)}\b", body, re.IGNORECASE):
                    positions.append(m.start())
            else:
                for m in re.finditer(re.escape(alias), body):
                    positions.append(m.start())

        if positions:
            found.append({
                "name": name,
                "type": info["type"],
                "category": info.get("category", ""),
                "count": len(positions),
            })

    return found


def _get_linked_ranges(text: str) -> list[tuple[int, int]]:
    """扫描文本中已有的 [[...]] 区间，返回 [(start, end), ...]"""
    ranges = []
    for m in re.finditer(r"\[\[.+?\]\]", text):
        ranges.append((m.start(), m.end()))
    return ranges


def _is_in_linked_range(pos: int, ranges: list[tuple[int, int]]) -> bool:
    """检查位置是否落在某个已有链接区间内"""
    for start, end in ranges:
        if start <= pos < end:
            return True
    return False


def add_wikilinks(body: str, entities: list[dict]) -> str:
    """在文本中为实体添加 [[wikilink]]"""
    modified = body

    # 先处理书名《》
    def replace_book(match):
        title = match.group(1)
        return f"[[{title}]]"

    modified = re.sub(r"《([^》]+)》", replace_book, modified)

    # 扫描已有链接区间
    linked_ranges = _get_linked_ranges(modified)

    # 为实体添加 wikilink（只替换第一次出现，避免过度链接）
    for entity in entities:
        name = entity["name"]
        # 只链接已经在 vault 中有页面的实体，或出现 2 次以上的
        if entity["count"] < 2 and entity["type"] == "entity":
            continue

        # 避免重复链接：检查是否已经在 [[]] 中
        if f"[[{name}]]" in modified or f"[[{name}|" in modified:
            continue

        # 找到第一次出现的纯文本实体名，且不在已有链接区间内
        pattern = re.escape(name)
        for m in re.finditer(pattern, modified):
            if not _is_in_linked_range(m.start(), linked_ranges):
                # 执行替换，同时更新链接区间
                modified = modified[:m.start()] + f"[[{name}]]" + modified[m.end():]
                # 更新区间：新链接增加了 4 个字符（[[和]]）
                new_ranges = []
                offset = 4
                for s, e in linked_ranges:
                    if e <= m.start():
                        new_ranges.append((s, e))
                    elif s >= m.end():
                        new_ranges.append((s + offset, e + offset))
                    else:
                        # 区间重叠（理论上不应发生），保留原区间
                        new_ranges.append((s, e))
                linked_ranges = new_ranges
                linked_ranges.append((m.start(), m.start() + len(name) + 4))
                break

    return modified


def build_entity_page(entity: dict) -> str:
    """为实体创建 stub 页面内容"""
    name = entity["name"]
    etype = entity["type"]
    category = entity.get("category", "")

    # 确定目标路径
    if etype == "concept":
        target_dir = "concepts"
    elif etype == "topic":
        target_dir = "topics"
    else:
        target_dir = "entities"

    tags = [target_dir.rstrip("s")]
    if category:
        tags.append(category)

    return f"""---
title: "{name}"
type: {etype}
tags: [{', '.join(tags)}]
created: {datetime.now().strftime('%Y-%m-%d')}
summary: ""
---
# {name}

## 首次提及
- [[日记/{entity.get('first_diary', 'unknown')}|{entity.get('first_diary_date', '')}]]: {entity.get('context', '')}

## 后续提及
<!-- AI 自动追加 -->
"""


def tag_diary(filepath: Path, knowledge: dict, dry_run: bool = False) -> dict:
    """处理单篇日记：打标签 + 加双链 + 回写

    Returns:
        {filepath, new_tags, entities_found, wikilinks_added, modified}
    """
    original = filepath.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(original)

    # 1. 检测标签
    new_tags = detect_tags(body)
    old_tags = fm.get("tags", [])
    if isinstance(old_tags, str):
        old_tags = [old_tags]
    merged_tags = list(dict.fromkeys(old_tags + new_tags))  # 保留旧标签，去重

    # 2. 识别实体
    entities = find_entities_in_text(body, knowledge)

    # 3. 添加 wikilink
    modified_body = add_wikilinks(body, entities)

    # 4. 更新 frontmatter
    fm["tags"] = merged_tags

    # 5. 重建文件
    new_content = build_frontmatter(fm) + "\n\n" + modified_body

    result = {
        "filepath": filepath,
        "new_tags": [t for t in new_tags if t not in (old_tags or [])],
        "all_tags": merged_tags,
        "entities_found": [e["name"] for e in entities],
        "entities_detail": entities,
        "wikilinks_added": modified_body != body,
        "modified": new_content != original,
    }

    if not dry_run and result["modified"]:
        filepath.write_text(new_content, encoding="utf-8")
        print(f"  已更新: {filepath.name} | 标签: {merged_tags} | 实体: {result['entities_found']}")

    return result


def scan_and_tag(days: int = 7, dry_run: bool = None):
    """扫描最近 N 天日记，打标签 + 加双链"""
    if dry_run is None:
        dry_run = config.DRY_RUN

    print("=" * 50)
    print(f"日记标签与双链处理 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)

    # 加载外部配置（如有）
    _apply_external_config()

    # 加载知识库
    knowledge = load_vault_knowledge()
    print(f"知识库实体数: {len(knowledge)}")

    # 找到最近 N 天的日记
    diary_dir = config.DIARY_DIR
    since = datetime.now() - timedelta(days=days)
    diary_files = []
    for f in sorted(diary_dir.glob("*.md")):
        # 排除 index.md
        if f.stem == "index":
            continue
        match = re.match(r"(\d{4}-\d{2}-\d{2})", f.stem)
        if match:
            try:
                date = datetime.strptime(match.group(1), "%Y-%m-%d")
                if date >= since:
                    diary_files.append(f)
            except ValueError:
                pass

    print(f"处理 {len(diary_files)} 篇日记\n")

    results = []
    new_entities = defaultdict(lambda: {"count": 0, "type": "entity", "category": "未分类", "first_diary": "", "context": ""})
    existing_mentions = defaultdict(list)

    for f in diary_files:
        result = tag_diary(f, knowledge, dry_run)
        results.append(result)

        for entity in result["entities_detail"]:
            name = entity["name"]
            if name not in knowledge and entity["count"] >= 2:
                new_entities[name]["count"] += entity["count"]
                new_entities[name]["type"] = entity["type"]
                new_entities[name]["category"] = entity.get("category", "")
                if not new_entities[name]["first_diary"]:
                    new_entities[name]["first_diary"] = f.stem
                    new_entities[name]["first_diary_date"] = f.stem[:10]
                    new_entities[name]["context"] = f"在日记中首次提及"
            elif name in knowledge:
                existing_mentions[name].append({
                    "diary": f.stem,
                    "context": f"在日记中提及",
                })

    # 统计
    total_tags_added = sum(len(r["new_tags"]) for r in results)
    total_wikilinks = sum(1 for r in results if r["wikilinks_added"])
    total_modified = sum(1 for r in results if r["modified"])

    print(f"\n处理完成: {total_modified} 篇有变化 | {total_tags_added} 个新标签 | {total_wikilinks} 篇加双链")

    return results, dict(new_entities), dict(existing_mentions)


if __name__ == "__main__":
    scan_and_tag()
