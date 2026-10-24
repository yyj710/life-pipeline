"""
读取本周日记 + 时间记录 + 标签/实体数据，生成周度观察初稿
可独立运行，也可从 pipeline 接收预计算数据避免重复处理
"""
import re
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

from feishu_client import FeishuClient
from sync_bitable import sync
import config
from utils import find_diary_files, read_file_content



def build_insights_from_tags(tag_results: list[dict]) -> list[dict]:
    """从 tag_diary 的结果构建洞察数据，避免重复提取关键词"""
    insights = []
    for r in tag_results:
        all_tags = r.get("all_tags", [])
        new_tags = r.get("new_tags", [])
        entities = r.get("entities_found", [])

        # 按标签类型分类
        dimension_tags = [t for t in all_tags if t in
                          ["思维模式", "价值观", "情感", "决策", "执行"]]
        emotion_tags = [t for t in all_tags if t in
                        ["兴奋", "焦虑", "愤怒", "失落", "恐惧"]]
        state_tags = [t for t in all_tags if t in
                      ["幻想", "纠偏", "突破", "低谷"]]
        track_tags = [t for t in all_tags if t in
                      ["生产输出", "英语", "财务CPA", "区块链技术"]]
        relation_tags = [t for t in all_tags if t in
                         ["家人", "朋友", "恋人", "导师", "同学", "人际关系"]]

        insights.append({
            "file": r["filepath"].name,
            "all_tags": all_tags,
            "new_tags": new_tags,
            "dimension_tags": dimension_tags,
            "emotion_tags": emotion_tags,
            "state_tags": state_tags,
            "track_tags": track_tags,
            "relation_tags": relation_tags,
            "entities": entities,
            "entities_detail": r.get("entities_detail", []),
        })
    return insights


def read_time_summary() -> dict:
    """从时间周报读取摘要"""
    result = {"total_hours": 0, "avg_per_day": 0, "days": 0, "categories": {}}
    report_path = config.DATA_ANALYSIS_DIR / "时间周报.md"
    if not report_path.exists():
        return result

    content = report_path.read_text(encoding="utf-8")
    # 提取总时长
    m = re.search(r"总时长\s*\|\s*([\d.]+)h", content)
    if m:
        result["total_hours"] = float(m.group(1))
    m = re.search(r"日均\s*\|\s*([\d.]+)h", content)
    if m:
        result["avg_per_day"] = float(m.group(1))
    m = re.search(r"统计天数\s*\|\s*(\d+)", content)
    if m:
        result["days"] = int(m.group(1))
    # 提取分类占比
    for m in re.finditer(r"\|\s*(\S+)\s*\|\s*([\d.]+)h\s*\|\s*(\d+)%\s*\|", content):
        result["categories"][m.group(1)] = {"hours": float(m.group(2)), "pct": int(m.group(3))}

    return result


def find_previous_observation() -> tuple[Path | None, str]:
    """找到上一份周度观察"""
    obs_dir = config.DIGITAL_IMMORTALITY_DIR
    pattern = re.compile(r"周度观察-(\d{4}-\d{2}-\d{2})\.md")
    latest = None
    latest_date = ""

    for f in obs_dir.glob("周度观察-*.md"):
        match = pattern.match(f.name)
        if match:
            date_str = match.group(1)
            if date_str > latest_date:
                latest_date = date_str
                latest = f

    if latest:
        return latest, read_file_content(latest)
    return None, ""


def collect_weekly_drafts() -> list[dict]:
    """收集本周0.1版待处理池中的草稿，用于汇总到周度观察"""
    draft_dir = config.DIGITAL_IMMORTALITY_DIR / "0.1版待处理池"
    if not draft_dir.exists():
        return []

    since = datetime.now() - timedelta(days=7)
    drafts = []

    for f in sorted(draft_dir.glob("*.md")):
        if f.name == "INDEX.md":
            continue
        match = re.match(r"(\d{4}-\d{2}-\d{2})", f.stem)
        if match:
            try:
                date = datetime.strptime(match.group(1), "%Y-%m-%d")
                if date >= since:
                    content = read_file_content(f)
                    # 提取筛选标记
                    selected = []
                    for line in content.split("\n"):
                        if "[x]" in line.lower() or "[X]" in line:
                            selected.append(line.strip())
                    drafts.append({
                        "date": match.group(1),
                        "filepath": f,
                        "selected_items": selected,
                        "has_content": len(content) > 200,
                    })
            except ValueError:
                pass

    return drafts


def read_facts_for_review() -> str:
    """读取事实库摘要用于周度对照"""
    facts_path = config.COGNITIVE_PROFILE_DIR / "事实库.md"
    if not facts_path.exists():
        return ""
    return read_file_content(facts_path)[:2000]


def calculate_execution_score(
    diary_files: list[Path],
    time_summary: dict,
    tag_results: list[dict] = None,
) -> dict:
    """计算本周执行力评分（0-10）

    评分维度：
    - 日记完整率（有日记的天数/7）权重30%
    - 时间记录（日均时长是否达标）权重30%
    - 赛道活跃（四条赛道提及天数）权重20%
    - 状态信号（突破vs低谷）权重20%
    """
    score = 0
    details = []

    # 1. 日记完整率（30%）
    diary_days = len(diary_files)
    diary_ratio = min(diary_days / 7, 1.0)
    diary_score = diary_ratio * 3.0
    score += diary_score
    if diary_days >= 5:
        details.append(f"日记{diary_days}篇，完整率{diary_ratio:.0%}（+{diary_score:.1f}）")
    else:
        details.append(f"日记仅{diary_days}篇，完整率{diary_ratio:.0%}（+{diary_score:.1f}，低于5篇目标）")

    # 2. 时间记录（30%）
    avg_hours = time_summary.get("avg_per_day", 0)
    if avg_hours >= 8:
        time_score = 3.0
        details.append(f"日均{avg_hours:.1f}h，达标（+3.0）")
    elif avg_hours >= 5:
        time_score = (avg_hours / 8) * 3.0
        details.append(f"日均{avg_hours:.1f}h，未达8h目标（+{time_score:.1f}）")
    else:
        time_score = avg_hours / 8 * 1.5
        details.append(f"日均仅{avg_hours:.1f}h，严重不足（+{time_score:.1f}）")
    score += time_score

    # 3. 赛道活跃（20%）
    track_tags = ["生产输出", "英语", "财务CPA", "区块链技术"]
    active_tracks = 0
    if tag_results:
        for tag in track_tags:
            for r in tag_results:
                if tag in r.get("all_tags", []):
                    active_tracks += 1
                    break
    track_score = (active_tracks / 4) * 2.0
    score += track_score
    details.append(f"四条赛道活跃{active_tracks}/4（+{track_score:.1f}）")

    # 4. 状态信号（20%）
    breakthroughs = 0
    lows = 0
    if tag_results:
        for r in tag_results:
            states = [t for t in r.get("all_tags", []) if t in ["突破", "低谷"]]
            if "突破" in states:
                breakthroughs += 1
            if "低谷" in states:
                lows += 1
    state_score = min(breakthroughs * 0.5, 2.0) - min(lows * 0.3, 1.0)
    state_score = max(state_score, 0)
    score += state_score
    if breakthroughs > 0:
        details.append(f"突破{breakthroughs}次，低谷{lows}次（+{state_score:.1f}）")
    elif lows > 0:
        details.append(f"无突破，低谷{lows}次（+{state_score:.1f}）")
    else:
        details.append(f"无突破无低谷信号（+{state_score:.1f}）")

    return {
        "score": round(min(score, 10), 1),
        "details": details,
        "diary_days": diary_days,
        "avg_hours": avg_hours,
        "active_tracks": active_tracks,
        "breakthroughs": breakthroughs,
        "lows": lows,
    }


def generate_brutal_feedback(exec_score: dict, time_summary: dict, tag_results: list[dict] = None) -> str:
    """生成不留情面反馈（基于王振宇录音29:28的风格）"""
    score = exec_score["score"]
    parts = []

    if score < 4:
        parts.append(f"本周执行力评分{score}/10。")
        parts.append(f"根据本周数据，日记{exec_score['diary_days']}篇、日均{exec_score['avg_hours']:.1f}h、"
                     f"活跃赛道{exec_score['active_tracks']}/4。")
        if exec_score["diary_days"] < 5:
            parts.append(f"日记只有{exec_score['diary_days']}篇，连记录都坚持不了，谈什么ACCA大陆第一？")
        if exec_score["avg_hours"] < 6:
            parts.append(f"日均{exec_score['avg_hours']:.1f}小时，这种状态持续下去，暑假结束FR/PM过不了是必然结果。")
        if exec_score["active_tracks"] < 3:
            parts.append(f"四条赛道只活跃{exec_score['active_tracks']}条，主线在偏离而不自知。")
        parts.append("这种状态如果不改变，开学后会被甩开更远。")
    elif score < 7:
        parts.append(f"本周执行力评分{score}/10，及格但不够。")
        parts.append(f"日记{exec_score['diary_days']}篇、日均{exec_score['avg_hours']:.1f}h。")
        if exec_score["breakthroughs"] == 0:
            parts.append("本周没有突破信号，是在原地踏步还是有进展没记录？")
        if exec_score["avg_hours"] < 8:
            parts.append(f"日均{exec_score['avg_hours']:.1f}h离8h目标还差{8-exec_score['avg_hours']:.1f}h，差在哪了？")
    else:
        parts.append(f"本周执行力评分{score}/10，状态不错。")
        parts.append(f"日记{exec_score['diary_days']}篇、日均{exec_score['avg_hours']:.1f}h、"
                     f"突破{exec_score['breakthroughs']}次。")
        if exec_score["breakthroughs"] > 0:
            parts.append("有突破信号，下次访谈值得深入探讨是什么突破。")
        parts.append("保持这个节奏，但问自己：这是极限还是还有提升空间？")

    return " ".join(parts)


def generate_next_week_suggestions(
    exec_score: dict,
    time_summary: dict,
    tag_results: list[dict] = None,
    weekly_drafts: list[dict] = None,
) -> list[str]:
    """生成下周重点建议（≤3条）"""
    suggestions = []

    # 基于执行力短板
    if exec_score["diary_days"] < 5:
        suggestions.append(f"日记记录频率下降（本周仅{exec_score['diary_days']}篇），下周目标每天必写，哪怕只写3行")
    if exec_score["avg_hours"] < 8:
        suggestions.append(f"日均学习时长{exec_score['avg_hours']:.1f}h未达标，分析时间花在哪了，下周提升到8h")
    if exec_score["active_tracks"] < 3:
        suggestions.append(f"四条赛道仅活跃{exec_score['active_tracks']}条，检查是否在主线之外浪费了时间")

    # 基于状态信号
    if exec_score["lows"] >= 2:
        suggestions.append(f"本周低谷{exec_score['lows']}次，找出低谷触发因素，下周提前预防")
    if exec_score["breakthroughs"] == 0 and exec_score["score"] < 7:
        suggestions.append("本周无突破信号，下周设定一个可检验的小目标（如完成FR一个chapter）")

    # 基于0.1版草稿筛选
    if weekly_drafts:
        unselected = [d for d in weekly_drafts if not d["selected_items"] and d["has_content"]]
        if len(unselected) >= 3:
            suggestions.append(f"0.1版待处理池有{len(unselected)}天未筛选，周日晚统一处理")

    # 基于时间分布
    if time_summary.get("categories"):
        cats = time_summary["categories"]
        max_cat = max(cats.items(), key=lambda x: x[1]["pct"])
        if max_cat[1]["pct"] > 60:
            suggestions.append(f"时间集中在{max_cat[0]}({max_cat[1]['pct']}%)，注意其他赛道是否被挤压")

    # 最多3条
    return suggestions[:3] if suggestions else ["本周数据正常，保持节奏"]


def generate_observation(
    diary_files: list[Path],
    diary_insights: list[dict],
    time_summary: dict,
    prev_obs_text: str,
    tag_based: bool = False,
    exec_score: dict = None,
    brutal_feedback: str = "",
    next_week_suggestions: list[str] = None,
    weekly_drafts: list[dict] = None,
) -> str:
    """生成周度观察初稿

    diary_insights 可以来自 extract_keywords()（旧版）或 build_insights_from_tags()（新版）。
    当 tag_based=True 时，insights 结构来自 tag_diary 的结果。

    新增参数（1.0版增强）:
    - exec_score: calculate_execution_score() 的返回值
    - brutal_feedback: generate_brutal_feedback() 的返回值
    - next_week_suggestions: generate_next_week_suggestions() 的返回值
    - weekly_drafts: collect_weekly_drafts() 的返回值
    """
    today = datetime.now().strftime("%Y-%m-%d")
    week_start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    # 汇总洞察 — 兼容新旧两种格式
    if tag_based:
        # 新版：来自 tag_diary 的标签数据
        tag_counts = defaultdict(int)
        emotion_counts = defaultdict(int)
        track_counts = defaultdict(int)
        state_counts = defaultdict(int)
        all_entities = []
        fantasy_correction_pairs = 0

        for insight in diary_insights:
            for tag in insight.get("all_tags", []):
                tag_counts[tag] += 1
            for tag in insight.get("emotion_tags", []):
                emotion_counts[tag] += 1
            for tag in insight.get("track_tags", []):
                track_counts[tag] += 1
            for tag in insight.get("state_tags", []):
                state_counts[tag] += 1
            all_entities.extend(insight.get("entities", []))

            # 检测 幻想→纠偏 成对出现
            states = insight.get("state_tags", [])
            if "幻想" in states and "纠偏" in states:
                fantasy_correction_pairs += 1

        all_entities = list(dict.fromkeys(all_entities))
    else:
        # 旧版：来自 extract_keywords 的文本行
        all_new_concepts = []
        all_emotional = []
        all_decisions = []
        all_new_projects = []
        all_goals = []
        track_counts = defaultdict(int)

        for insight in diary_insights:
            all_new_concepts.extend(insight.get("new_concepts", []))
            all_emotional.extend(insight.get("emotional_content", []))
            all_decisions.extend(insight.get("decisions", []))
            all_new_projects.extend(insight.get("new_projects", []))
            all_goals.extend(insight.get("goals_mentioned", []))
            for track, count in insight.get("four_tracks", {}).items():
                track_counts[track] += count

        all_new_concepts = list(dict.fromkeys(all_new_concepts))
        all_emotional = list(dict.fromkeys(all_emotional))
        all_decisions = list(dict.fromkeys(all_decisions))
        all_new_projects = list(dict.fromkeys(all_new_projects))

    lines = [
        "---",
        f"title: \"周度观察 {today}\"",
        "tags: [周度观察, 复盘, 自我分析, 自动化]",
        f"created: {today}",
        "type: permanent",
        "status: draft",
        f"summary: \"基于 {len(diary_files)} 篇日记 + 标签/实体数据 + 时间记录自动生成，待审核\"",
        "---",
        f"# 周度观察 - {today}",
        "",
        f"> 生成区间: {week_start} ~ {today}",
        f"> 日记篇数: {len(diary_files)}",
        f"> 本文件由 pipeline 自动生成，标记为 draft，请审核后发布",
        "",
    ]

    # ---- 执行力评分（1.0版增强）----
    if exec_score:
        lines.append("## 执行力评分")
        lines.append("")
        lines.append(f"**本周得分: {exec_score['score']}/10**")
        lines.append("")
        lines.append("| 维度 | 明细 |")
        lines.append("|------|------|")
        for d in exec_score["details"]:
            lines.append(f"| - | {d} |")
        lines.append("")

    # ---- 不留情面反馈（1.0版增强）----
    if brutal_feedback:
        lines.append("## 不留情面反馈")
        lines.append("")
        lines.append(f"> {brutal_feedback}")
        lines.append("")

    # ---- 标签分布概览 (新版) ----
    if tag_based:
        lines.append("## 本周标签分布")
        lines.append("")
        lines.append("| 类型 | 标签 | 出现天数 |")
        lines.append("|------|------|---------|")
        # 维度标签
        for tag in ["思维模式", "价值观", "情感", "决策", "执行"]:
            if tag_counts.get(tag):
                lines.append(f"| 维度 | {tag} | {tag_counts[tag]} |")
        # 情绪标签
        for tag in ["兴奋", "焦虑", "愤怒", "失落", "恐惧"]:
            if emotion_counts.get(tag):
                lines.append(f"| 情绪 | {tag} | {emotion_counts[tag]} |")
        # 状态标签
        for tag in ["幻想", "纠偏", "突破", "低谷"]:
            if state_counts.get(tag):
                lines.append(f"| 状态 | {tag} | {state_counts[tag]} |")
        # 赛道标签
        for tag in ["生产输出", "英语", "财务CPA", "区块链技术"]:
            if track_counts.get(tag):
                lines.append(f"| 赛道 | {tag} | {track_counts[tag]} |")
        lines.append("")

        # 本周发现的新实体
        if all_entities:
            lines.append("## 本周关联实体")
            lines.append("")
            lines.append(", ".join(f"[[{e}]]" for e in all_entities[:15]))
            lines.append("")
            lines.append("")

    # ---- 本周新增认知 ----
    if not tag_based:
        lines.append("## 本周新增认知")
        lines.append("")
        if all_new_concepts:
            for i, concept in enumerate(all_new_concepts[:8], 1):
                lines.append(f"### {i}. {concept.strip(' -')}")
                lines.append("")
        else:
            lines.append("本周日记中未检测到显著的新认知表述。")
            lines.append("")

    lines.append("## 本周的核心变化")
    lines.append("")

    # 时间使用总结
    if time_summary["total_hours"] > 0:
        lines.append(f"### 时间使用")
        lines.append(f"本周 {time_summary['days']} 天有记录，共 {time_summary['total_hours']:.0f}h，日均 {time_summary['avg_per_day']:.1f}h。")
        if time_summary["categories"]:
            cats = ", ".join(f"{k}({v['pct']}%)" for k, v in time_summary["categories"].items())
            lines.append(f"分布: {cats}")
        lines.append("")
    else:
        lines.append("本周暂无时间记录数据。")
        lines.append("")

    # 四条赛道活跃度
    total_track_mentions = sum(track_counts.values())
    if total_track_mentions > 0:
        lines.append(f"### 四条赛道活跃度")
        lines.append(f"| 赛道 | 提及天数 |")
        lines.append(f"|------|---------|")
        for track in ["生产输出", "英语", "财务CPA", "区块链技术"]:
            count = track_counts.get(track, 0)
            if count > 0:
                lines.append(f"| {track} | {count} |")
        lines.append("")

    # 状态模式检测
    if tag_based:
        if state_counts.get("突破", 0) >= 2:
            lines.append(f"### ⚡ 突破信号")
            lines.append(f"本周 {state_counts['突破']} 篇日记出现「突破」标签，可能有重要进展值得关注。")
            lines.append("")

        if state_counts.get("低谷", 0) >= 2:
            lines.append(f"### ⚠️ 低谷信号")
            lines.append(f"本周 {state_counts['低谷']} 篇日记出现「低谷」标签，关注是否有持续下滑趋势。")
            lines.append("")

        if fantasy_correction_pairs >= 2:
            lines.append(f"### 🧠 自我纠偏模式")
            lines.append(f"本周 {fantasy_correction_pairs} 次出现「幻想→纠偏」成对标签，自我监控机制活跃。")
            lines.append("")

        # 情感概览
        total_emotional = sum(emotion_counts.values())
        if total_emotional >= 3:
            top_emotions = sorted(emotion_counts.items(), key=lambda x: x[1], reverse=True)
            emo_str = ", ".join(f"{k}({v})" for k, v in top_emotions[:3])
            lines.append(f"### 情感概览")
            lines.append(f"本周检测到 {total_emotional} 条情感标签: {emo_str}")
            lines.append("")
    else:
        # 旧版情感信号
        if all_emotional:
            lines.append("### 本周情感信号")
            lines.append(f"检测到 {len(all_emotional)} 条情绪相关表述：")
            for e in all_emotional[:5]:
                lines.append(f"- {e.strip(' -')}")
            lines.append("")

        if all_decisions:
            lines.append("### 决策变化")
            for d in all_decisions[:5]:
                lines.append(f"- {d.strip(' -')}")
            lines.append("")

        if all_new_projects:
            lines.append(f"### 新项目/行动")
            for proj in all_new_projects[:5]:
                lines.append(f"- {proj.strip(' -')}")
            lines.append("")

    lines.append("## 可持续观察点")
    lines.append("")
    lines.append("（以下为 AI 建议的观察点，请根据实际情况增删）")
    lines.append("")

    # 自动建议观察点
    if tag_based:
        if state_counts.get("突破", 0):
            lines.append(f"- 本周有突破信号，访谈时可深入了解具体是什么突破")
        if state_counts.get("低谷", 0):
            lines.append(f"- 本周有低谷信号，关注是否有规律性低谷周期")
        if emotion_counts.get("焦虑", 0) >= 2:
            lines.append(f"- 焦虑情绪出现较多，关注压力来源")
        if not emotion_counts:
            lines.append("- 本周情感标签较少，情感模式维度数据仍需积累")
    else:
        if all_new_projects:
            lines.append(f"- 新项目是否持续推进，还是一次性尝试")

    if len(diary_files) < 5:
        lines.append(f"- 本周日记篇数较少（{len(diary_files)} 篇），记录频率是否下降")
    if time_summary["days"] == 0:
        lines.append("- 本周暂无时间记录，是否未在飞书记录时间")
    if track_counts:
        min_track = min(track_counts.items(), key=lambda x: x[1])
        if total_track_mentions > 0 and min_track[1] < total_track_mentions * 0.1:
            lines.append(f"- 「{min_track[0]}」赛道本周提及较少，是否需要关注")

    lines.append("")

    # ---- 0.1版草稿筛选汇总（1.0版增强）----
    if weekly_drafts:
        lines.append("## 0.1版草稿筛选汇总")
        lines.append("")
        total_drafts = len(weekly_drafts)
        selected_count = sum(1 for d in weekly_drafts if d["selected_items"])
        unselected = [d for d in weekly_drafts if not d["selected_items"] and d["has_content"]]
        lines.append(f"本周生成 {total_drafts} 份0.1版草稿，已筛选 {selected_count} 份，"
                     f"待处理 {len(unselected)} 份。")
        lines.append("")
        if unselected:
            lines.append("| 日期 | 状态 |")
            lines.append("|------|------|")
            for d in unselected:
                lines.append(f"| {d['date']} | 未筛选 |")
            lines.append("")
            lines.append("> 周日晚统一筛选，挑出值得1.0版深度打磨的条目。")
            lines.append("")

    # ---- 下周重点（1.0版增强）----
    if next_week_suggestions:
        lines.append("## 下周重点")
        lines.append("")
        lines.append("> 基于本周数据自动生成，≤3条，按优先级排列")
        lines.append("")
        for i, s in enumerate(next_week_suggestions, 1):
            lines.append(f"{i}. {s}")
        lines.append("")

    lines.append(f"*自动生成于 {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
    lines.append(f"*状态: draft — 请人工审核后去除 frontmatter 中的 status: draft*")

    return "\n".join(lines)


def analyze(client: FeishuClient = None, days: int = None,
            tag_results: list[dict] = None, skip_sync: bool = False):
    """执行周度观察分析

    Args:
        client: 飞书客户端（独立运行时自动创建）
        days: 分析天数
        tag_results: 来自 tag_diary.scan_and_tag() 的结果，提供后跳过关键词提取
        skip_sync: True 时跳过飞书同步（pipeline 已同步过）
    """
    if days is None:
        days = config.ANALYSIS_DAYS
    if client is None:
        client = FeishuClient()

    print("=" * 50)
    print(f"周度观察生成 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)

    # Step 1: 同步最新时间数据（独立运行时需要）
    if skip_sync:
        print("\n[1/5] 跳过飞书同步（使用已同步数据）")
    else:
        print("\n[1/5] 同步飞书时间数据...")
        sync(client, days)

    # Step 2: 收集日记
    print(f"\n[2/5] 收集最近 {days} 天日记...")
    diary_files = find_diary_files(days)
    print(f"  找到 {len(diary_files)} 篇日记")
    for df in diary_files:
        print(f"    - {df.name}")

    if not diary_files:
        print("  警告: 未找到日记文件，将生成空初稿")

    # Step 3: 分析日记 — 优先使用预计算的 tag_results
    tag_based = tag_results is not None and len(tag_results) > 0
    print(f"\n[3/5] 分析日记内容... (数据源: {'标签/实体数据' if tag_based else '关键词提取'})")

    if tag_based:
        diary_insights = build_insights_from_tags(tag_results)
        for insight in diary_insights:
            print(f"  {insight['file']}: 标签 {insight['all_tags']} | "
                  f"实体 {len(insight['entities'])}")
    else:
        diary_insights = []
        for df in diary_files:
            content = read_file_content(df)
            insights = extract_keywords_from_text(content)
            diary_insights.append(insights)
            print(f"  {df.name}: 新概念 {len(insights['new_concepts'])} | "
                  f"情感 {len(insights['emotional_content'])} | "
                  f"决策 {len(insights['decisions'])} | "
                  f"赛道 {dict(insights['four_tracks'])}")

    # Step 4: 读取参考资料并生成
    print("\n[4/5] 生成周度观察初稿...")
    prev_obs, prev_text = find_previous_observation()
    print(f"  上一份周度观察: {prev_obs.name if prev_obs else '无'}")

    time_summary = read_time_summary()

    # 1.0版增强：计算执行力评分
    print("\n[5/5] 计算执行力评分 + 生成反馈...")
    exec_score = calculate_execution_score(diary_files, time_summary, tag_results)
    print(f"  执行力评分: {exec_score['score']}/10")
    for d in exec_score["details"]:
        print(f"    - {d}")

    # 收集0.1版草稿
    weekly_drafts = collect_weekly_drafts()
    print(f"  0.1版草稿: {len(weekly_drafts)} 份")

    # 生成不留情面反馈
    brutal_feedback = generate_brutal_feedback(exec_score, time_summary, tag_results)

    # 生成下周建议
    next_week_suggestions = generate_next_week_suggestions(
        exec_score, time_summary, tag_results, weekly_drafts
    )
    for i, s in enumerate(next_week_suggestions, 1):
        print(f"  下周建议{i}: {s}")

    markdown = generate_observation(
        diary_files, diary_insights, time_summary, prev_text,
        tag_based=tag_based,
        exec_score=exec_score,
        brutal_feedback=brutal_feedback,
        next_week_suggestions=next_week_suggestions,
        weekly_drafts=weekly_drafts,
    )

    today = datetime.now().strftime("%Y-%m-%d")
    filepath = config.DIGITAL_IMMORTALITY_DIR / f"周度观察-{today}.md"

    if config.DRY_RUN:
        print(f"\n  [DRY-RUN] 将写入: {filepath}")
        print(f"\n  --- 预览 ---")
        print(markdown[:2000])
    else:
        filepath.write_text(markdown, encoding="utf-8")
        print(f"\n  周度观察已生成: {filepath}")
        print(f"  状态: draft (待审核)")

    return markdown


def extract_keywords_from_text(text: str) -> dict:
    """从日记文本中提取关键信息（独立运行时的备用方案）"""
    result = {
        "new_projects": [],
        "new_concepts": [],
        "emotional_content": [],
        "four_tracks": defaultdict(int),
        "decisions": [],
        "goals_mentioned": [],
    }

    track_keywords = {
        "生产输出": ["公众号", "自媒体", "写作", "文章", "日更", "输出", "内容"],
        "英语": ["英语", "雅思", "听力", "口语", "英文", "单词"],
        "财务CPA": ["ACCA", "CPA", "会计", "审计", "四大", "财务", "财会", "考试", "绩点", "期末"],
        "区块链技术": ["编程", "代码", "部署", "开发", "web3", "区块链", "AI", "Claude", "技术", "前后端"],
    }

    lines = text.split("\n")
    for line in lines:
        line_lower = line.lower()
        if any(kw in line for kw in ["意识到", "原来", "才发现", "突然明白", "懂了", "想通了"]):
            if len(line) > 10:
                result["new_concepts"].append(line.strip())
        if any(kw in line for kw in ["开心", "难过", "焦虑", "害怕", "喜欢", "感动", "愤怒", "烦躁",
                                       "失望", "兴奋", "紧张", "担忧", "恐惧", "孤独", "累", "烦"]):
            if len(line) > 5:
                result["emotional_content"].append(line.strip())
        if any(kw in line for kw in ["决定", "以后", "从现在开始", "不再", "改成", "优先级"]):
            if len(line) > 10:
                result["decisions"].append(line.strip())
        for track, keywords in track_keywords.items():
            if any(kw in line for kw in keywords):
                result["four_tracks"][track] += 1
        if any(kw in line_lower for kw in ["部署", "配置", "搭建", "注册", "申请", "开始用"]):
            if len(line) > 8:
                result["new_projects"].append(line.strip())
        if any(kw in line for kw in ["目标", "计划", "要做", "准备", "打算"]):
            if len(line) > 8:
                result["goals_mentioned"].append(line.strip())

    return result


if __name__ == "__main__":
    analyze()
