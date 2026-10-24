"""
每日0.1版自动产出 — 不需要人参与，AI自动扫描当天日记/事实库，产出0.1版洞察到待处理池

用法:
  python daily_draft.py              处理今天
  python daily_draft.py --dry-run    预览不写入
  python daily_draft.py --date 2026-07-25  指定日期

输出: 数字永生计划/0.1版待处理池/YYYY-MM-DD.md
"""
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

import config
from utils import find_diary_files, read_file_content, parse_frontmatter


# ============================================================
# 0.1版待处理池目录
# ============================================================
DRAFT_POOL_DIR = config.DIGITAL_IMMORTALITY_DIR / "0.1版待处理池"


def find_today_diary(target_date: str = None) -> list[Path]:
    """找到目标日期的日记文件"""
    if target_date:
        since = datetime.strptime(target_date, "%Y-%m-%d")
        end = since + timedelta(days=1)
    else:
        since = datetime.now() - timedelta(days=1)
        end = datetime.now() + timedelta(days=1)

    diary_dir = config.DIARY_DIR
    if not diary_dir.exists():
        return []

    found = []
    for f in sorted(diary_dir.glob("*.md")):
        if f.stem == "index":
            continue
        match = re.match(r"(\d{4}-\d{2}-\d{2})", f.stem)
        if match:
            try:
                date = datetime.strptime(match.group(1), "%Y-%m-%d")
                if since <= date < end:
                    found.append(f)
            except ValueError:
                pass
    return found


def extract_daily_signals(diary_files: list[Path]) -> dict:
    """从当天日记提取信号"""
    signals = {
        "tags": defaultdict(int),
        "emotions": defaultdict(int),
        "states": defaultdict(int),
        "tracks": defaultdict(int),
        "entities": [],
        "decisions": [],
        "goals": [],
        "breakthroughs": [],
        "concerns": [],
        "raw_paragraphs": [],
    }

    dimension_tags = {"思维模式", "价值观", "情感", "决策", "执行"}
    emotion_tags = {"兴奋", "焦虑", "愤怒", "失落", "恐惧"}
    state_tags = {"幻想", "纠偏", "突破", "低谷"}
    track_tags = {"生产输出", "英语", "财务CPA", "区块链技术"}

    for fpath in diary_files:
        content = read_file_content(fpath)
        if not content:
            continue

        paragraphs = [p.strip() for p in content.split("\n") if p.strip()]
        signals["raw_paragraphs"].extend(paragraphs)

        # 标签检测（复用dbs_scan的逻辑）
        fm, body = parse_frontmatter(fpath.read_text(encoding="utf-8"))
        existing_tags = fm.get("tags", [])
        if isinstance(existing_tags, str):
            existing_tags = [existing_tags]

        for tag in existing_tags:
            signals["tags"][tag] += 1
            if tag in dimension_tags:
                pass  # 已计入
            if tag in emotion_tags:
                signals["emotions"][tag] += 1
            if tag in state_tags:
                signals["states"][tag] += 1
            if tag in track_tags:
                signals["tracks"][tag] += 1

        # 关键句提取
        for line in paragraphs:
            if any(kw in line for kw in ["决定", "以后", "从现在开始", "不再", "改成"]):
                if len(line) > 10:
                    signals["decisions"].append(line[:150])
            if any(kw in line for kw in ["目标", "计划", "要做", "准备", "打算"]):
                if len(line) > 8:
                    signals["goals"].append(line[:150])
            if any(kw in line for kw in ["突破", "突破", "搞懂", "想通", "明白了"]):
                if len(line) > 8:
                    signals["breakthroughs"].append(line[:150])
            if any(kw in line for kw in ["担心", "害怕", "焦虑", "压力", "纠结", "犹豫"]):
                if len(line) > 8:
                    signals["concerns"].append(line[:150])

    # 去重
    for key in ["decisions", "goals", "breakthroughs", "concerns"]:
        seen = set()
        unique = []
        for item in signals[key]:
            if item[:50] not in seen:
                seen.add(item[:50])
                unique.append(item)
        signals[key] = unique

    return signals


def detect_daily_business_signals(diary_files: list[Path]) -> list[dict]:
    """检测当天日记中的商业主题信号（轻量版，不依赖dbs_scan模块）"""
    if not diary_files:
        return []

    # 精简版商业信号规则（完整版在 dbs_scan.py / config/business_signals.yaml）
    signals_rules = [
        {"id": "diagnosis", "label": "商业模式诊断", "skill": "dbs-diagnosis",
         "keywords": ["赚钱", "商业模式", "变现", "收入", "利润", "定价", "卖什么"]},
        {"id": "benchmark", "label": "对标分析", "skill": "dbs-benchmark",
         "keywords": ["对标", "模仿", "抄", "参考", "借鉴", "像.*一样"]},
        {"id": "content", "label": "内容创作诊断", "skill": "dbs-content",
         "keywords": ["小红书", "抖音", "视频", "标题", "封面", "文案", "公众号", "播放量"]},
        {"id": "action", "label": "执行力诊断", "skill": "dbs-action",
         "keywords": ["拖延", "做不动", "不想做", "懒", "逃避", "就是不做"]},
        {"id": "goal", "label": "目标清晰化", "skill": "dbs-goal",
         "keywords": ["我想做", "我想成为", "我的目标是", "个人IP", "财务自由"]},
    ]

    themes = {}
    for fpath in diary_files:
        content = read_file_content(fpath)
        if not content:
            continue
        date_str = fpath.stem[:10] if len(fpath.stem) >= 10 else fpath.stem

        for signal in signals_rules:
            matched = False
            snippets = []
            paragraphs = [p.strip() for p in content.split("\n") if p.strip()]

            for kw in signal["keywords"]:
                if kw in content:
                    matched = True
                    for para in paragraphs:
                        if kw in para and para not in snippets:
                            snippets.append(para[:150])

            if matched:
                sid = signal["id"]
                if sid not in themes:
                    themes[sid] = {
                        "id": sid,
                        "label": signal["label"],
                        "skill": signal["skill"],
                        "diary_dates": [],
                        "snippets": [],
                    }
                themes[sid]["diary_dates"].append(date_str)
                themes[sid]["snippets"].extend(snippets[:2])

    # 去重snippets
    for sid in themes:
        seen = set()
        unique = []
        for s in themes[sid]["snippets"]:
            if s[:50] not in seen:
                seen.add(s[:50])
                unique.append(s)
        themes[sid]["snippets"] = unique[:3]

    return sorted(themes.values(), key=lambda t: -len(t["diary_dates"]))


def read_facts_brief() -> str:
    """读取事实库摘要（前30行）"""
    facts_path = config.COGNITIVE_PROFILE_DIR / "事实库.md"
    if not facts_path.exists():
        return ""
    content = facts_path.read_text(encoding="utf-8")
    lines = content.split("\n")[:30]
    return "\n".join(lines)


def generate_daily_draft(
    target_date: str,
    diary_files: list[Path],
    signals: dict,
    business_themes: list[dict],
    facts_brief: str,
) -> str:
    """生成每日0.1版草稿"""

    today = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines = [
        "---",
        f'title: "0.1版待处理 {target_date}"',
        "tags: [0.1版, 待处理, 自动生成, daily-draft]",
        f"created: {target_date}",
        "type: fleeting",
        "status: v0.1",
        f'summary: "{target_date} 日记自动扫描产出，待人工筛选→1.0深度打磨"',
        "---",
        f"# 0.1版待处理 — {target_date}",
        "",
        f"> 自动生成于 {today}",
        f"> 日记篇数: {len(diary_files)}",
        f"> 状态: v0.1 — 人工筛选后进入1.0深度打磨",
        "",
        "---",
        "",
        "## 一、今日标签信号",
        "",
    ]

    # 标签分布
    if signals["tags"]:
        lines.append("| 类型 | 标签 | 次数 |")
        lines.append("|------|------|------|")
        for tag, count in sorted(signals["tags"].items(), key=lambda x: -x[1]):
            lines.append(f"| 标签 | {tag} | {count} |")
        lines.append("")
    else:
        lines.append("今日日记无标签或未找到日记。")
        lines.append("")

    # 情绪
    if signals["emotions"]:
        emo_str = ", ".join(f"{k}({v})" for k, v in signals["emotions"].items())
        lines.append(f"**情绪信号**: {emo_str}")
        lines.append("")

    # 状态
    if signals["states"]:
        state_str = ", ".join(f"{k}({v})" for k, v in signals["states"].items())
        lines.append(f"**状态信号**: {state_str}")
        lines.append("")

    # 赛道活跃度
    if signals["tracks"]:
        lines.append("**赛道活跃**: " + ", ".join(f"{k}({v})" for k, v in signals["tracks"].items()))
        lines.append("")

    # 二、关键内容提取
    lines.append("---")
    lines.append("")
    lines.append("## 二、今日关键内容（0.1版，未打磨）")
    lines.append("")

    if signals["decisions"]:
        lines.append("### 决策/决定")
        for d in signals["decisions"][:3]:
            lines.append(f"- {d}")
        lines.append("")

    if signals["goals"]:
        lines.append("### 目标/计划")
        for g in signals["goals"][:3]:
            lines.append(f"- {g}")
        lines.append("")

    if signals["breakthroughs"]:
        lines.append("### 突破/顿悟")
        for b in signals["breakthroughs"][:3]:
            lines.append(f"- {b}")
        lines.append("")

    if signals["concerns"]:
        lines.append("### 担忧/困扰")
        for c in signals["concerns"][:3]:
            lines.append(f"- {c}")
        lines.append("")

    # 三、商业主题信号
    lines.append("---")
    lines.append("")
    lines.append("## 三、商业主题信号（0.1版，待/dbskill诊断）")
    lines.append("")

    if business_themes:
        lines.append(f"检测到 {len(business_themes)} 个商业主题:")
        lines.append("")
        for t in business_themes:
            lines.append(f"- **{t['label']}** → `/{t['skill']}` (出现{len(t['diary_dates'])}天)")
            if t.get("snippets"):
                lines.append(f"  > {t['snippets'][0][:120]}")
        lines.append("")
        lines.append("> 人工筛选：哪个值得进入1.0深度诊断？对哪个说\"诊断\"即可触发dbskill。")
    else:
        lines.append("今日日记中未检测到明确商业主题。")
    lines.append("")

    # 四、事实库对照
    lines.append("---")
    lines.append("")
    lines.append("## 四、事实库对照（0.1版参考）")
    lines.append("")
    if facts_brief:
        lines.append("当前事实库前30行摘要:")
        lines.append("```")
        lines.append(facts_brief)
        lines.append("```")
    else:
        lines.append("事实库不存在或为空。")
    lines.append("")

    # 五、AI自动建议（0.1版）
    lines.append("---")
    lines.append("")
    lines.append("## 五、AI自动建议（0.1版，未审核）")
    lines.append("")

    suggestions = []
    if signals["states"].get("突破", 0) >= 1:
        suggestions.append("今日有突破信号，值得在下次访谈中深入探讨")
    if signals["states"].get("低谷", 0) >= 1:
        suggestions.append("今日有低谷信号，关注是否有规律性低谷周期")
    if signals["emotions"].get("焦虑", 0) >= 2:
        suggestions.append("焦虑情绪较频，关注压力来源")
    if signals["tracks"].get("财务CPA", 0) == 0 and signals["tracks"].get("区块链技术", 0) == 0:
        suggestions.append("今日ACCA和编程赛道均无提及，检查是否偏离主线")
    if not diary_files:
        suggestions.append("今日无日记，记录频率下降")
    if signals["decisions"]:
        suggestions.append(f"今日有{len(signals['decisions'])}个决定，值得记录到事实库")
    if business_themes:
        suggestions.append(f"今日检测到{len(business_themes)}个商业主题，可用/dbs-vault诊断")

    if suggestions:
        for s in suggestions:
            lines.append(f"- {s}")
    else:
        lines.append("- 今日信号正常，无明显需关注项")
    lines.append("")

    # 六、筛选标记区
    lines.append("---")
    lines.append("")
    lines.append("## 六、人工筛选区")
    lines.append("")
    lines.append("<!-- 人工填写：哪些进入1.0深度打磨？ -->")
    lines.append("")
    lines.append("- [ ] 值得深入：______")
    lines.append("- [ ] 沉淀到事实库：______")
    lines.append("- [ ] 触发dbskill诊断：______")
    lines.append("- [ ] 丢弃（噪音）：______")
    lines.append("")
    lines.append(f"> 筛选完成后，在周度观察日统一汇总")
    lines.append("")

    lines.append("---")
    lines.append(f"*0.1版自动生成于 {today} | daily_draft.py*")

    return "\n".join(lines)


def update_draft_index(date: str, diary_count: int, theme_count: int, dry_run: bool = False):
    """更新待处理池索引"""
    DRAFT_POOL_DIR.mkdir(parents=True, exist_ok=True)
    index_path = DRAFT_POOL_DIR / "INDEX.md"

    if index_path.exists():
        existing = index_path.read_text(encoding="utf-8")
    else:
        existing = (
            "---\n"
            'title: "0.1版待处理池索引"\n'
            "tags: [0.1版, 索引, 待处理]\n"
            f'created: {datetime.now().strftime("%Y-%m-%d")}\n'
            "type: index\n"
            'summary: "每日0.1版自动产出汇总，人工筛选后进入1.0"\n'
            "---\n"
            "# 0.1版待处理池索引\n\n"
            "> 每日22:00自动生成 | 周日pipeline汇总筛选\n\n"
            "| 日期 | 日记数 | 商业主题 | 状态 | 筛选进入1.0 |\n"
            "|------|--------|---------|------|-------------|\n"
        )

    if date not in existing:
        new_line = f"| {date} | {diary_count} | {theme_count} | 待筛选 | |\n"
        lines = existing.strip().split("\n")
        lines.append(new_line)
        updated = "\n".join(lines) + "\n"
    else:
        updated = existing

    if not dry_run:
        index_path.write_text(updated, encoding="utf-8")
        print(f"  待处理池索引已更新: {index_path}")


def run(target_date: str = None, dry_run: bool = False) -> dict:
    """主入口：生成每日0.1版草稿

    Args:
        target_date: 目标日期 YYYY-MM-DD，默认今天
        dry_run: 预览模式

    Returns:
        dict: 产出信息
    """
    if target_date is None:
        target_date = datetime.now().strftime("%Y-%m-%d")

    print("=" * 50)
    print(f"每日0.1版草稿生成 — {target_date}")
    print("=" * 50)

    # Step 1: 收集当天日记
    print(f"\n[1/4] 收集 {target_date} 日记...")
    diary_files = find_today_diary(target_date)
    print(f"  找到 {len(diary_files)} 篇日记")
    for df in diary_files:
        print(f"    - {df.name}")

    if not diary_files:
        print("  提示: 今日无日记，仍生成空草稿供记录")

    # Step 2: 提取信号
    print(f"\n[2/4] 提取日记信号...")
    signals = extract_daily_signals(diary_files)
    print(f"  标签: {dict(signals['tags'])}")
    print(f"  决策: {len(signals['decisions'])} 条")
    print(f"  目标: {len(signals['goals'])} 条")
    print(f"  突破: {len(signals['breakthroughs'])} 条")
    print(f"  担忧: {len(signals['concerns'])} 条")

    # Step 3: 商业主题检测
    print(f"\n[3/4] 检测商业主题...")
    business_themes = detect_daily_business_signals(diary_files)
    print(f"  检测到 {len(business_themes)} 个商业主题")

    # Step 4: 读取事实库摘要
    facts_brief = read_facts_brief()

    # 生成草稿
    print(f"\n[4/4] 生成0.1版草稿...")
    markdown = generate_daily_draft(
        target_date, diary_files, signals, business_themes, facts_brief
    )

    # 写入文件
    DRAFT_POOL_DIR.mkdir(parents=True, exist_ok=True)
    filepath = DRAFT_POOL_DIR / f"{target_date}.md"

    if dry_run:
        print(f"\n  [DRY-RUN] 将写入: {filepath}")
        print(f"\n  --- 预览(前500字) ---")
        print(markdown[:500])
    else:
        filepath.write_text(markdown, encoding="utf-8")
        print(f"\n  0.1版草稿已生成: {filepath}")

    # 更新索引
    update_draft_index(target_date, len(diary_files), len(business_themes), dry_run)

    return {
        "date": target_date,
        "filepath": filepath,
        "diary_count": len(diary_files),
        "theme_count": len(business_themes),
        "markdown": markdown,
    }


if __name__ == "__main__":
    target_date = None
    dry_run = "--dry-run" in sys.argv

    for i, arg in enumerate(sys.argv):
        if arg == "--date" and i + 1 < len(sys.argv):
            target_date = sys.argv[i + 1]

    run(target_date=target_date, dry_run=dry_run)
