"""
检测本周认知变化，自动更新认知画像
对比：本周日记标签 + wiki 实体 vs 现有认知画像
"""
import re
import yaml
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

import config
from tag_diary import scan_and_tag
from utils import parse_frontmatter



def load_latest_profile() -> tuple[Path, str] | None:
    """加载最新认知画像"""
    profile_dir = config.DIGITAL_IMMORTALITY_DIR / "认知模型"
    if not profile_dir.exists():
        return None

    # 找最新的认知画像文件
    latest = None
    latest_date = ""
    for f in profile_dir.glob("认知画像-*.md"):
        match = re.search(r"(\d{4}-\d{2}-\d{2})", f.name)
        if match and match.group(1) > latest_date:
            latest_date = match.group(1)
            latest = f

    if latest:
        return latest, latest.read_text(encoding="utf-8")
    return None


def load_interview_insights(days: int = 30) -> list[dict]:
    """从访谈记录目录加载最近的访谈摘要数据"""
    records_dir = config.INTERVIEW_RECORDS_DIR
    if not records_dir.exists():
        return []

    insights = []
    since = datetime.now() - timedelta(days=days)

    for f in sorted(records_dir.glob("*.md")):
        # 从文件名提取日期
        m = re.search(r"(\d{4}-\d{2}-\d{2})", f.name)
        if not m:
            continue
        try:
            file_date = datetime.strptime(m.group(1), "%Y-%m-%d")
        except ValueError:
            continue
        if file_date < since:
            continue

        content = f.read_text(encoding="utf-8").lstrip("\ufeff")
        # 提取 frontmatter 中的 summary
        fm, body = parse_frontmatter(content)
        summary = fm.get("summary", "")
        # 提取关键发现（假设有“## 关键发现”或“## 访谈摘要”章节）
        key_findings = []
        in_findings = False
        for line in body.split("\n"):
            if line.startswith("## ") and any(k in line for k in ["关键发现", "访谈摘要", "核心发现", "摘要"]):
                in_findings = True
                continue
            elif line.startswith("## "):
                in_findings = False
                continue
            if in_findings and line.strip().startswith("- "):
                key_findings.append(line.strip()[2:])

        insights.append({
            "date": m.group(1),
            "file": f.name,
            "summary": summary,
            "key_findings": key_findings,
        })

    return insights


def analyze_diary_tags(results: list[dict]) -> dict:
    """汇总本周日记的标签统计"""
    stats = {
        "total_diaries": len(results),
        "tag_counts": defaultdict(int),
        "emotion_tags": defaultdict(int),
        "track_tags": defaultdict(int),
        "all_entities": set(),
        "new_concepts": [],
        "value_shifts": [],
    }

    for r in results:
        for tag in r.get("all_tags", []):
            stats["tag_counts"][tag] += 1

        for tag in ["兴奋", "焦虑", "愤怒", "失落", "恐惧", "平静"]:
            if tag in r.get("all_tags", []):
                stats["emotion_tags"][tag] += 1

        for track in ["生产输出", "英语", "财务CPA", "区块链技术"]:
            if track in r.get("all_tags", []):
                stats["track_tags"][track] += 1

        for entity in r.get("entities_found", []):
            stats["all_entities"].add(entity)

    stats["all_entities"] = list(stats["all_entities"])
    return stats


def detect_changes(stats: dict, profile_text: str) -> list[dict]:
    """对比统计数据与现有认知画像，检测变化"""
    changes = []

    # 1. 情感模式：检测情感标签
    total_emotional = sum(stats["emotion_tags"].values())
    if total_emotional >= 3:
        top_emotions = sorted(stats["emotion_tags"].items(), key=lambda x: x[1], reverse=True)
        changes.append({
            "dimension": "情感模式",
            "type": "新数据",
            "detail": f"本周检测到 {total_emotional} 条情感标签: {', '.join(f'{k}({v})' for k, v in top_emotions[:3])}",
            "importance": "high" if total_emotional >= 5 else "medium",
        })

    # 2. 赛道活跃度变化
    for track, count in stats["track_tags"].items():
        if count >= 3:
            changes.append({
                "dimension": "执行风格",
                "type": "赛道活跃",
                "detail": f"「{track}」赛道本周活跃 ({count} 次提及)",
                "importance": "low",
            })

    # 3. 检测"幻想→纠偏"模式
    fantasy_count = stats["tag_counts"].get("幻想", 0)
    correction_count = stats["tag_counts"].get("纠偏", 0)
    if fantasy_count > 0 and correction_count > 0:
        changes.append({
            "dimension": "思维模式",
            "type": "自我纠偏",
            "detail": f"本周出现 「幻想→纠偏」模式 ({fantasy_count}次幻想 + {correction_count}次纠偏)",
            "importance": "medium",
        })

    # 4. 检测突破
    if stats["tag_counts"].get("突破", 0) >= 2:
        changes.append({
            "dimension": "执行风格",
            "type": "突破",
            "detail": f"本周 {stats['tag_counts']['突破']} 次「突破」标签，可能有重要进展",
            "importance": "high",
        })

    # 5. 检测低谷
    if stats["tag_counts"].get("低谷", 0) >= 2:
        changes.append({
            "dimension": "情感模式",
            "type": "低谷",
            "detail": f"本周 {stats['tag_counts']['低谷']} 次「低谷」标签，关注是否有持续下滑趋势",
            "importance": "high",
        })

    # 6. 新实体：之前认知画像中未提及的实体
    existing_profile_entities = set()
    for m in re.finditer(r"\[\[([^\]]+)\]\]", profile_text):
        existing_profile_entities.add(m.group(1))
    new_in_week = [e for e in stats["all_entities"] if e not in existing_profile_entities]
    if len(new_in_week) >= 3:
        changes.append({
            "dimension": "经历完整性",
            "type": "新实体",
            "detail": f"本周出现 {len(new_in_week)} 个新实体: {', '.join(new_in_week[:5])}",
            "importance": "medium",
        })

    return changes


def update_profile(profile_path: Path, profile_text: str, changes: list[dict]):
    """在认知画像末尾追加本周变化"""
    today = datetime.now().strftime("%Y-%m-%d")
    week_start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    if not changes:
        print("  无显著认知变化，跳过更新")
        return

    # 只保留 medium 及以上重要性的变化
    significant = [c for c in changes if c["importance"] in ("high", "medium")]
    if not significant:
        print("  仅有轻微变化，跳过更新")
        return

    lines = [
        "",
        f"### 更新 {today}",
        f"",
        f"> 数据区间: {week_start} ~ {today}",
        "",
    ]

    for c in significant:
        lines.append(f"- **[{c['dimension']}]** {c['type']}: {c['detail']}")

    lines.append("")

    new_content = profile_text.rstrip() + "\n" + "\n".join(lines) + "\n"

    if config.DRY_RUN:
        print(f"  [DRY-RUN] 将更新认知画像: {profile_path.name} ({len(significant)} 条变化)")
        return

    profile_path.write_text(new_content, encoding="utf-8")
    print(f"  已更新认知画像: {profile_path.name} ({len(significant)} 条变化)")


def detect_and_update(dry_run: bool = None, tag_results: list[dict] = None):
    """执行认知变化检测并更新画像

    Args:
        dry_run: 预览模式
        tag_results: 来自 tag_diary.scan_and_tag() 的结果，提供后跳过重复扫描
    """
    if dry_run is None:
        dry_run = config.DRY_RUN

    print("=" * 50)
    print(f"认知变化检测 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)

    # 1. 获取标签结果（优先使用预计算数据）
    if tag_results is not None:
        results = tag_results
        new_entities = {}
        print("  使用已缓存的标签扫描结果")
    else:
        results, new_entities, _ = scan_and_tag(days=7, dry_run=dry_run)

    # 2. 汇总标签统计
    stats = analyze_diary_tags(results)
    print(f"\n标签统计: {dict(stats['tag_counts'])}")
    print(f"情感标签: {dict(stats['emotion_tags'])}")
    print(f"赛道标签: {dict(stats['track_tags'])}")

    # 3. 加载认知画像
    profile = load_latest_profile()
    if not profile:
        print("  未找到认知画像，跳过变化检测")
        return

    profile_path, profile_text = profile

    # 4. 检测变化
    changes = detect_changes(stats, profile_text)
    print(f"\n检测到 {len(changes)} 条变化:")
    for c in changes:
        print(f"  [{c['importance']}] [{c['dimension']}] {c['detail']}")

    # 4.5 访谈数据回注
    interview_insights = load_interview_insights()
    if interview_insights:
        print(f"\n访谈记录: 加载 {len(interview_insights)} 份")
        for iv in interview_insights:
            print(f"  {iv['date']}: {iv['summary']}")
            if iv['key_findings']:
                changes.append({
                    "dimension": "经历完整性",
                    "type": "访谈回注",
                    "detail": f"访谈({iv['date']}): {'; '.join(iv['key_findings'][:3])}",
                    "importance": "high",
                })
    else:
        print("\n访谈记录: 无最近访谈数据")

    # 5. 更新画像
    update_profile(profile_path, profile_text, changes)

    return changes


if __name__ == "__main__":
    detect_and_update()
