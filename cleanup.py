"""
数字永生计划 - 清理检测模块

三大检测（只报告，不删除）：
1. 过期 wiki stub：创建超28天且"后续提及"为空
2. 休眠事实：事实库中状态为"休眠"且最后提及超8周的条目
3. 孤立标签：近7天日记中只出现1次的非标准标签
"""
import re
from datetime import datetime, timedelta
from pathlib import Path

import config
from utils import parse_frontmatter, find_diary_files


def _scan_expired_stubs() -> list[str]:
    """检测过期 wiki stub（创建超28天，后续提及为空）"""
    results = []
    cutoff = datetime.now() - timedelta(days=28)
    wiki_dirs = [
        config.VAULT_ROOT / "wiki" / "entities",
        config.VAULT_ROOT / "wiki" / "concepts",
        config.VAULT_ROOT / "wiki" / "topics",
    ]
    for wiki_dir in wiki_dirs:
        if not wiki_dir.exists():
            continue
        for f in wiki_dir.glob("*.md"):
            if f.name == "INDEX.md":
                continue
            # 解析 frontmatter 获取创建日期
            try:
                text = f.read_text(encoding="utf-8").lstrip("\ufeff")
                fm, body = parse_frontmatter(text)
                created_str = fm.get("created", "")
                if not created_str:
                    continue
                try:
                    created = datetime.strptime(str(created_str), "%Y-%m-%d")
                except ValueError:
                    continue
                if created >= cutoff:
                    continue
                # 检查"后续提及"区域是否为空
                # 匹配 "## 后续提及" 到文件结尾或下一个 "##" 之间
                mention_match = re.search(
                    r"## 后续提及\s*\n(.*?)(?=\n## |\Z)", body, re.DOTALL
                )
                if mention_match:
                    section = mention_match.group(1).strip()
                    # 去掉注释后检查是否有实际内容
                    cleaned = re.sub(r"<!--.*?-->", "", section).strip()
                    if not cleaned:
                        age = (datetime.now() - created).days
                        results.append(f"  [过期stub] {f.stem} — 创建于{created_str}（{age}天前），无后续提及")
            except Exception:
                continue
    return results


def _scan_dormant_facts() -> list[str]:
    """检测事实库中休眠超8周的条目"""
    results = []
    fact_file = config.COGNITIVE_PROFILE_DIR / "事实库.md"
    if not fact_file.exists():
        results.append("  [警告] 事实库.md 不存在")
        return results
    cutoff = datetime.now() - timedelta(weeks=8)
    text = fact_file.read_text(encoding="utf-8").lstrip("\ufeff")
    # 按章节拆分
    sections = re.split(r"^## .+$", text, flags=re.MULTILINE)
    for section in sections:
        lines = section.strip().split("\n")
        # 找表格行
        for line in lines:
            if "|" not in line:
                continue
            cells = [c.strip() for c in line.split("|")]
            # 表格行至少有6列：| 时间 | 事实 | 来源 | 提及次数 | 状态 |
            if len(cells) < 7:
                continue
            status = cells[5] if len(cells) > 5 else ""
            if "休眠" not in status:
                continue
            date_str = cells[1].strip() if len(cells) > 1 else ""
            fact_text = cells[2].strip() if len(cells) > 2 else ""
            try:
                fact_date = datetime.strptime(date_str, "%Y-%m-%d")
                if fact_date < cutoff:
                    age = (datetime.now() - fact_date).days
                    results.append(f"  [休眠事实] {date_str} — {fact_text[:50]}（{age}天未提及）")
            except ValueError:
                continue
    return results


def _scan_orphan_tags() -> list[str]:
    """检测近7天日记中只出现1次的孤立标签"""
    results = []
    files = find_diary_files(days=7)
    tag_counts = {}
    for f in files:
        try:
            text = f.read_text(encoding="utf-8").lstrip("\ufeff")
            fm, _ = parse_frontmatter(text)
            tags = fm.get("tags", [])
            if isinstance(tags, list):
                for t in tags:
                    tag_counts[t] = tag_counts.get(t, 0) + 1
        except Exception:
            continue
    # 标准标签体系（常见维度/状态/情绪标签）
    standard_tags = {
        # 维度
        "学习", "健身", "社交", "赚钱", "阅读", "英语", "ACCA",
        "编程", "web3", "AI", "认知", "输出", "投资",
        # 状态
        "高效", "低效", "拖延", "自律", "放松", "焦虑", "充实",
        # 赛道
        "四赛道", "自媒体", "雅思",
    }
    for tag, count in sorted(tag_counts.items(), key=lambda x: x[1]):
        if count == 1 and tag not in standard_tags:
            results.append(f"  [孤立标签] \"{tag}\" — 近7天只出现1次，考虑合并或标准化")
    return results


def run_cleanup(dry_run=False) -> str:
    """执行清理检测，返回报告字符串。dry_run 参数保留兼容"""
    lines = ["\n===== 清理检测报告 ====="]

    # 1. 过期 wiki stub
    expired = _scan_expired_stubs()
    lines.append(f"\n[1] 过期 wiki stub（创建>28天，无后续提及）: {len(expired)} 个")
    if expired:
        lines.extend(expired)
    else:
        lines.append("  无")

    # 2. 休眠事实
    dormant = _scan_dormant_facts()
    lines.append(f"\n[2] 休眠事实（状态=休眠，最后提及>8周）: {len(dormant)} 个")
    if dormant:
        lines.extend(dormant)
    else:
        lines.append("  无")

    # 3. 孤立标签
    orphans = _scan_orphan_tags()
    lines.append(f"\n[3] 孤立标签（近7天只出现1次）: {len(orphans)} 个")
    if orphans:
        lines.extend(orphans)
    else:
        lines.append("  无")

    lines.append("\n===== 报告结束 =====")
    report = "\n".join(lines)
    print(report)
    return report
