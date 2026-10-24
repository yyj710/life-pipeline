"""
为每周日 19:00 访谈生成上下文感知的访谈问题
可独立运行，也可从 pipeline 接收预计算数据避免重复处理
"""
import re
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

from feishu_client import FeishuClient
from sync_bitable import sync
from analyze_diary import (
    find_diary_files,
    read_file_content,
    find_previous_observation,
    build_insights_from_tags,
    extract_keywords_from_text,
)
import config
from config_loader import load_data_gaps


def _build_interview_schedule() -> dict:
    """根据 config.INTERVIEW_START_DATE + INTERVIEW_TOPICS 动态生成访谈日程"""
    from datetime import datetime, timedelta
    start = datetime.strptime(config.INTERVIEW_START_DATE, "%Y-%m-%d")
    schedule = {}
    for i, topic in enumerate(config.INTERVIEW_TOPICS):
        date = start + timedelta(weeks=i)
        date_str = date.strftime("%Y-%m-%d")
        schedule[date_str] = {"week": i + 1, "topic": topic}
    return schedule

INTERVIEW_SCHEDULE = _build_interview_schedule()

# 数据质量缺口（来自认知画像）
DATA_GAPS = {
    "情感模式": {"rating": 1, "focus": True, "description": "几乎没有数据，访谈重点方向"},
    "失败经验": {"rating": 2, "focus": True, "description": "对挫折的具体应对策略"},
    "家庭背景": {"rating": 2, "focus": True, "description": "资金紧迫感的根源"},
    "长期恐惧": {"rating": 1, "focus": True, "description": "10年后最怕什么"},
    "思维模式": {"rating": 4, "focus": False, "description": "5周观察充分覆盖"},
    "价值观": {"rating": 4, "focus": False, "description": "系统化沉淀完成"},
    "执行风格": {"rating": 4, "focus": False, "description": "多维度确认"},
    "经历完整性": {"rating": 3, "focus": False, "description": "当前状态清晰，历史待补充"},
}


def _apply_external_config():
    """尝试从 YAML 加载数据缺口配置"""
    global DATA_GAPS
    ext = load_data_gaps()
    if ext and isinstance(ext, dict):
        DATA_GAPS = ext
        print(f"  已从 config/data_gaps.yaml 加载 {len(ext)} 个数据缺口")


def find_interview_for_date(target_date: str = None) -> dict | None:
    """找到目标日期对应的访谈主题"""
    if target_date is None:
        target_date = datetime.now().strftime("%Y-%m-%d")
    return INTERVIEW_SCHEDULE.get(target_date)


def find_next_interview() -> tuple[str, dict]:
    """找到下一个访谈日期和主题
    
    如果当前日期超出预设日程，自动循环生成下一个主题
    """
    today = datetime.now().strftime("%Y-%m-%d")
    for date_str in sorted(INTERVIEW_SCHEDULE.keys()):
        if date_str >= today:
            return date_str, INTERVIEW_SCHEDULE[date_str]
    # 所有预设访谈已过期，自动生成下一周
    if INTERVIEW_SCHEDULE:
        last_date = max(INTERVIEW_SCHEDULE.keys())
        last_info = INTERVIEW_SCHEDULE[last_date]
        next_date_dt = datetime.strptime(last_date, "%Y-%m-%d") + timedelta(weeks=1)
        next_date = next_date_dt.strftime("%Y-%m-%d")
        next_week = last_info["week"] + 1
        # 循环使用主题列表
        topic_idx = (next_week - 1) % len(config.INTERVIEW_TOPICS)
        topic = config.INTERVIEW_TOPICS[topic_idx]
        return next_date, {"week": next_week, "topic": topic}
    return None, None


def read_cognitive_profile() -> str:
    """加载最新认知画像（自动找最新日期的文件）"""
    profile_dir = config.COGNITIVE_PROFILE_DIR
    if not profile_dir.exists():
        return ""
    latest = None
    latest_date = ""
    for f in profile_dir.glob("认知画像-*.md"):
        m = re.search(r"(\d{4}-\d{2}-\d{2})", f.name)
        if m and m.group(1) > latest_date:
            latest_date = m.group(1)
            latest = f
    if latest:
        return read_file_content(latest)
    return ""


def read_weekly_observation(target_date: str) -> tuple[Path | None, str]:
    """读取目标日期对应的周度观察（找最近的）"""
    target = datetime.strptime(target_date, "%Y-%m-%d")
    obs_dir = config.DIGITAL_IMMORTALITY_DIR

    best_path = None
    best_diff = timedelta.max

    for f in obs_dir.glob("周度观察-*.md"):
        match = re.match(r"周度观察-(\d{4}-\d{2}-\d{2})\.md", f.name)
        if not match:
            continue
        try:
            obs_date = datetime.strptime(match.group(1), "%Y-%m-%d")
            diff = target - obs_date
            if timedelta(0) <= diff < best_diff:
                best_diff = diff
                best_path = f
        except ValueError:
            pass

    if best_path:
        return best_path, read_file_content(best_path)
    return None, ""


def reconcile_diary_with_gaps(
    diary_insights: list[dict],
    interview_topic: str,
    tag_based: bool = False,
) -> dict:
    """对比日记内容和数据缺口，找出可以深入的方向"""
    if tag_based:
        # 新版：从标签数据提取
        all_emotional = []
        all_tracks = set()
        all_entities = []
        all_states = []
        for insight in diary_insights:
            all_emotional.extend(insight.get("emotion_tags", []))
            all_tracks.update(insight.get("track_tags", []))
            all_entities.extend(insight.get("entities", []))
            all_states.extend(insight.get("state_tags", []))
        return {
            "emotional_count": len(all_emotional),
            "emotional_samples": list(dict.fromkeys(all_emotional)),
            "concept_count": len(all_tracks),
            "concept_samples": list(all_tracks),
            "decision_count": len(all_states),
            "decision_samples": all_states,
            "entities": list(dict.fromkeys(all_entities)),
            "topic": interview_topic,
        }
    else:
        all_emotional = []
        all_concepts = []
        all_decisions = []
        for insight in diary_insights:
            all_emotional.extend(insight.get("emotional_content", []))
            all_concepts.extend(insight.get("new_concepts", []))
            all_decisions.extend(insight.get("decisions", []))
        return {
            "emotional_count": len(all_emotional),
            "emotional_samples": all_emotional[:3],
            "concept_count": len(all_concepts),
            "concept_samples": all_concepts[:3],
            "decision_count": len(all_decisions),
            "decision_samples": all_decisions[:3],
            "entities": [],
            "topic": interview_topic,
        }


def generate_questions(
    interview_date: str,
    interview_info: dict,
    diary_files: list[Path],
    diary_insights: list[dict],
    obs_text: str,
    profile_text: str,
    tag_based: bool = False,
    business_themes: list[dict] = None,
) -> str:
    """生成访谈问题

    Args:
        business_themes: dbs_scan.scan() 返回的 business_themes_for_interview，
                         包含本周日记中的商业主题，作为采访追问素材
    """
    topic = interview_info["topic"]
    week = interview_info["week"]
    recon = reconcile_diary_with_gaps(diary_insights, topic, tag_based)

    # 从本周日记中提取具体事件作为问题锚点
    diary_events = []
    for i, df in enumerate(diary_files):
        if i < len(diary_insights):
            insight = diary_insights[i]
            fname = df.stem[:10] if len(df.stem) >= 10 else df.stem

            if tag_based:
                tags = insight.get("all_tags", [])
                entities = insight.get("entities", [])
                if tags or entities:
                    diary_events.append({
                        "date": fname,
                        "tags": tags,
                        "entities": entities[:5],
                    })
            else:
                concepts = insight.get("new_concepts", [])
                decisions = insight.get("decisions", [])
                projects = insight.get("new_projects", [])
                if concepts or decisions or projects:
                    diary_events.append({
                        "date": fname,
                        "concepts": concepts[:2],
                        "decisions": decisions[:2],
                        "projects": projects[:2],
                    })

    today = datetime.now().strftime("%Y-%m-%d")

    lines = [
        "---",
        f"title: \"访谈准备 {interview_date}\"",
        "tags: [访谈, 数字永生, 自动生成]",
        f"created: {today}",
        "type: fleeting",
        f"summary: \"第{week}周访谈问题准备 — 主题: {topic}\"",
        "---",
        f"# 访谈准备 - 第{week}周",
        "",
        f"**日期**：{interview_date} (周日 19:00)",
        f"**时长**：约30分钟",
        f"**主题**：{topic}",
        f"**数据缺口**：",
    ]

    # 列出本主题对应的数据缺口
    relevant_gaps = []
    for gap_name, gap_info in DATA_GAPS.items():
        if gap_info["focus"]:
            relevant_gaps.append(f"- {gap_name} ⭐{'⭐'*gap_info['rating']} — {gap_info['description']}")

    lines.extend(relevant_gaps[:4])
    lines.append("")

    # 本周日记概览
    lines.append("## 本周日记概览")
    lines.append("")
    if diary_events:
        for event in diary_events:
            lines.append(f"### {event['date']}")
            if tag_based:
                if event.get("tags"):
                    lines.append(f"- 标签: {', '.join(event['tags'])}")
                if event.get("entities"):
                    lines.append(f"- 实体: {', '.join(event['entities'][:5])}")
            else:
                for c in event.get("concepts", []):
                    lines.append(f"- 💡 {c.strip(' -')}")
                for d in event.get("decisions", []):
                    lines.append(f"- 🎯 {d.strip(' -')}")
                for p in event.get("projects", []):
                    lines.append(f"- 🔧 {p.strip(' -')}")
            lines.append("")
    else:
        lines.append("本周日记中未检测到显著事件。")
        lines.append("")

    # 情感信号
    if recon["emotional_samples"]:
        lines.append("## 本周情感信号")
        lines.append("")
        for e in recon["emotional_samples"]:
            lines.append(f"- {e}")
        lines.append("")
    else:
        lines.append("## 本周情感信号")
        lines.append("")
        lines.append("⚠️ 本周日记中未检测到情感表述。情感模式维度仍然是最大的数据缺口。")
        lines.append("")

    # 核心：访谈问题
    lines.append("## 访谈问题")
    lines.append("")
    lines.append(f"以下是基于本周日记 + 数据缺口 + 「{topic}」主题生成的 {8} 个问题：")
    lines.append("")

    # 根据每周主题生成不同的问题模板
    if "成长经历" in topic or "价值观" in topic:
        questions = [
            {
                "q": "本周你做了[具体项目/行动]，这和你的成长经历有什么关系？你小时候有没有遇到过类似的挑战？",
                "why": "关联本周具体行动与成长经历，避免泛泛而谈",
                "gap": "经历完整性",
            },
            {
                "q": "你提到过资金紧迫感——这种感受从什么时候开始的？最早有钱不够用的记忆是什么？",
                "why": "挖掘家庭背景和财务观念的起源",
                "gap": "家庭背景",
            },
            {
                "q": "CZ 和李笑来的原则体系中，哪一条是你在本周真正用到了的？能举个具体例子吗？",
                "why": "连接价值观理论与实际行动，检验价值观的实践性",
                "gap": "价值观",
            },
            {
                "q": "你的「结果导向」思维方式是谁教给你的？还是自己悟出来的？",
                "why": "追溯核心思维模式的来源",
                "gap": "思维模式",
            },
            {
                "q": "如果让你用一个词总结你 18 岁之前的人生，会是什么？为什么？",
                "why": "获得自我认知的凝练表达",
                "gap": "经历完整性",
            },
            {
                "q": "你父母对你现在的状态了解多少？他们对你的四条赛道知道吗？",
                "why": "打开家庭背景维度",
                "gap": "家庭背景",
            },
            {
                "q": "你说过「靠谱比关系重要」——这个观念是怎么形成的？有没有被不靠谱的人坑过？",
                "why": "价值观形成背后的具体故事",
                "gap": "失败经验",
            },
            {
                "q": "如果让你给 15 岁的自己一个建议，你会说什么？",
                "why": "暴露成长中的遗憾和关键转折点",
                "gap": "经历完整性",
            },
        ]
    elif "人际关系" in topic or "情感" in topic:
        questions = [
            {
                "q": "本周你在日记/时间记录中提到了[人际关系事件]，当时你的感受是什么？后面有没有再想过这件事？",
                "why": "关联本周具体关系事件，挖掘情感反应",
                "gap": "情感模式",
            },
            {
                "q": "你把「短期关系」和「长期关系」分成两套系统——这种划分有没有过纠结？执行起来最困难的是什么？",
                "why": "检验恋爱框架的实际执行难度",
                "gap": "情感模式",
            },
            {
                "q": "你有没有过一段关系（友情或恋爱），让你至今想起来还会觉得复杂？",
                "why": "挖掘过去关系中的情感记忆",
                "gap": "情感模式",
            },
            {
                "q": "你说人脉是价值交换——那什么样的人你会愿意为他付出不求回报？",
                "why": "检验价值交换理论的边界",
                "gap": "价值观",
            },
            {
                "q": "你生气的时候是什么样子的？会怎么处理？",
                "why": "情绪管理策略，当前数据完全空白",
                "gap": "情感模式",
            },
            {
                "q": "你觉得自己好相处吗？别人一般怎么评价你？",
                "why": "获得外部视角的自我认知",
                "gap": "情感模式",
            },
            {
                "q": "本周有没有遇到让你觉得「这个人不行」的人？为什么这么判断？",
                "why": "关联本周社交事件 + 人际判断标准",
                "gap": "价值观",
            },
            {
                "q": "你想成为什么样的男朋友/丈夫？这个形象和你现在的差距在哪里？",
                "why": "连接恋爱框架与自我认知",
                "gap": "情感模式",
            },
        ]
    elif "失败" in topic or "应对" in topic:
        questions = [
            {
                "q": "本周有没有什么事情没做好？你是怎么应对的？",
                "why": "关联本周具体失败/挫折事件",
                "gap": "失败经验",
            },
            {
                "q": "你一生中最大的失败是什么？那件事对你的影响持续了多久？",
                "why": "重大失败经历的深度访谈",
                "gap": "失败经验",
            },
            {
                "q": "ACCA 考试你觉得能考到什么程度？万一考砸了怎么办？",
                "why": "检验是否有具体的失败预案",
                "gap": "失败经验",
            },
            {
                "q": "你在日记里经常自我纠偏（幻想→拉回现实）——这个机制是怎么建立起来的？",
                "why": "自我纠偏是执行特征的关键部分，追溯其形成",
                "gap": "执行风格",
            },
            {
                "q": "有没有一件事你尝试了很多次都失败了，但还在坚持的？",
                "why": "挖掘韧性和失败中的坚持",
                "gap": "失败经验",
            },
            {
                "q": "你最害怕失去什么？如果失去了会怎么样？",
                "why": "关联恐惧与失败经验",
                "gap": "长期恐惧",
            },
            {
                "q": "你见过别人失败后的样子吗？你害怕自己变成那样吗？",
                "why": "通过外部观察了解对失败的态度",
                "gap": "失败经验",
            },
            {
                "q": "如果三条赛道同时崩了，你会先救哪一个？为什么？",
                "why": "检验优先级框架在压力下的稳定性",
                "gap": "失败经验",
            },
        ]
    elif "愿景" in topic or "恐惧" in topic:
        questions = [
            {
                "q": "本周有没有什么事情让你想到「10年后」？",
                "why": "关联本周具体事件，切入长期视角",
                "gap": "长期恐惧",
            },
            {
                "q": "你的一五计划到 2030 年——如果到了 2030 年你发现走错路了，最可能错在哪一步？",
                "why": "检验规划的自我质疑能力",
                "gap": "长期恐惧",
            },
            {
                "q": "你最怕 30 岁的自己变成什么样？",
                "why": "直接探索长期恐惧",
                "gap": "长期恐惧",
            },
            {
                "q": "你说过「不买房不买车」——但如果你未来的另一半想要呢？你怎么处理这种冲突？",
                "why": "价值观与长期关系的张力",
                "gap": "情感模式",
            },
            {
                "q": "你羡慕谁的生活状态？你觉得你能达到吗？",
                "why": "通过偶像/对标反推自我期望",
                "gap": "长期恐惧",
            },
            {
                "q": "数字永生计划如果能成功，你最希望谁来使用它？",
                "why": "连接数字永生目标与情感需求",
                "gap": "情感模式",
            },
            {
                "q": "如果健康出了问题，不能再跑4公里了，你会怎么调整？",
                "why": "检验对不可控因素的适应能力",
                "gap": "长期恐惧",
            },
            {
                "q": "你说要做数字游民环球旅行——这是一个人的旅行还是有人陪的？",
                "why": "长期愿景中的人际关系维度",
                "gap": "情感模式",
            },
        ]
    else:
        questions = [
            {
                "q": f"本周关于「{topic}」，你有没有什么特别想聊的？",
                "why": "开放式问题，探索未知领域",
                "gap": "通用",
            },
        ]

    # 用本周日记事件个性化替换问题中的变量
    for i, q_data in enumerate(questions):
        lines.append(f"### 问题 {i+1}: {q_data['q']}")
        lines.append(f"- **目标缺口**: {q_data['gap']}")
        lines.append(f"- **为什么问**: {q_data['why']}")
        lines.append("")
        lines.append("---")
        lines.append("")

    lines.append("## 采访提示")
    lines.append("")
    lines.append("- 先用 2 分钟回顾本周重要事件，建立上下文")
    lines.append("- 每个问题给对方足够的思考时间，不打断")
    lines.append("- 如果回答触及情感内容，追问「当时什么感受」")
    lines.append("- 如果回答是抽象的，追问「能举个具体例子吗」")
    lines.append("- 每次采访控制在 30 分钟左右，不必问完所有问题")
    lines.append("")

    # 商业主题注入（来自 dbs_scan）
    if business_themes:
        lines.append("---")
        lines.append("")
        lines.append("## 本周商业洞察（来自日记扫描）")
        lines.append("")
        lines.append(f"> 以下内容由 dbs_scan 自动生成。采访中如果聊到相关话题，可以自然带入。")
        lines.append("")
        for i, bt in enumerate(business_themes):
            days = len(bt.get("diary_dates", []))
            fire = "🔥 " if days >= 3 else ""
            lines.append(f"### {fire}{bt['theme']}")
            lines.append("")
            lines.append(f"- **建议技能**：`/{bt['skill']}`")
            lines.append(f"- **出现天数**：{days} 天")
            lines.append(f"- **追问方向**：{bt['key_question']}")
            if bt.get("context_snippets"):
                lines.append(f"- **日记原文参考**：")
                for snippet in bt["context_snippets"][:2]:
                    lines.append(f"  > {snippet[:150]}")
            lines.append("")
            lines.append("**采访中如果用户展开聊这个话题**：可以提议现场用 dbskill 诊断。")
            lines.append("")

    lines.append(f"*自动生成于 {datetime.now().strftime('%Y-%m-%d %H:%M')}*")

    return "\n".join(lines)


def prepare_interview(client: FeishuClient = None, target_date: str = None,
                      tag_results: list[dict] = None, skip_sync: bool = False,
                      business_themes: list[dict] = None):
    """执行访谈准备

    Args:
        client: 飞书客户端（独立运行时自动创建）
        target_date: 目标访谈日期
        tag_results: 来自 tag_diary.scan_and_tag() 的结果，提供后跳过关键词提取
        skip_sync: True 时跳过飞书同步（pipeline 已同步过）
        business_themes: 来自 dbs_scan.scan() 的 business_themes_for_interview，
                         注入到采访问题中作为商业追问素材
    """
    # 加载外部配置
    _apply_external_config()

    if client is None:
        client = FeishuClient()

    # 确定访谈日期
    if target_date:
        interview_info = find_interview_for_date(target_date)
    else:
        target_date, interview_info = find_next_interview()

    if not interview_info:
        print("未找到后续访谈安排")
        return None

    print("=" * 50)
    print(f"访谈准备 — 第{interview_info['week']}周 ({target_date})")
    print(f"主题: {interview_info['topic']}")
    print("=" * 50)

    # Step 1: 同步飞书时间数据（独立运行时需要）
    if skip_sync:
        print("\n[1/5] 跳过飞书同步（使用已同步数据）")
    else:
        print("\n[1/5] 同步飞书时间数据...")
        sync(client, config.SYNC_DAYS)

    # Step 2: 收集本周日记
    print(f"\n[2/5] 收集日记...")
    diary_files = find_diary_files(config.ANALYSIS_DAYS)
    print(f"  找到 {len(diary_files)} 篇日记")

    # Step 3: 分析日记 — 优先使用预计算的 tag_results
    tag_based = tag_results is not None and len(tag_results) > 0
    print(f"\n[3/5] 分析日记内容... (数据源: {'标签/实体数据' if tag_based else '关键词提取'})")

    if tag_based:
        diary_insights = build_insights_from_tags(tag_results)
    else:
        diary_insights = []
        for df in diary_files:
            content = read_file_content(df)
            insights = extract_keywords_from_text(content)
            diary_insights.append(insights)

    # Step 4: 加载参考资料
    print(f"\n[4/5] 加载参考资料...")
    profile_text = read_cognitive_profile()
    obs_path, obs_text = read_weekly_observation(target_date)
    print(f"  认知画像: {'已加载' if profile_text else '未找到'}")
    print(f"  周度观察: {obs_path.name if obs_path else '未找到'}")
    if business_themes:
        print(f"  商业主题注入: {len(business_themes)} 个（来自 dbs_scan）")
    else:
        print(f"  商业主题注入: 无（dbs_scan 未运行）")

    # Step 5: 生成问题
    print(f"\n[5/5] 生成访谈问题...")
    markdown = generate_questions(
        target_date, interview_info,
        diary_files, diary_insights,
        obs_text, profile_text,
        tag_based=tag_based,
        business_themes=business_themes,
    )

    filepath = config.INTERVIEW_PREP_DIR / f"{target_date}-问题.md"
    if config.DRY_RUN:
        print(f"\n  [DRY-RUN] 将写入: {filepath}")
    else:
        filepath.write_text(markdown, encoding="utf-8")
        print(f"\n  访谈问题已生成: {filepath}")

    print(f"\n  === 问题预览 ===")
    for match in re.finditer(r"### 问题 (\d+): (.+)", markdown):
        print(f"  {match.group(0)}")

    return markdown


if __name__ == "__main__":
    prepare_interview()
