"""
扫描本周日记中的商业主题信号，输出待诊断清单 + 注入采访的结构化数据
可独立运行，也可从 pipeline 接收预计算 tag_results
用法:
  python dbs_scan.py             独立扫描最近 7 天日记
  python dbs_scan.py --dry-run   预览不写入
"""
import re
from datetime import datetime, timedelta
from pathlib import Path

from analyze_diary import (
    find_diary_files,
    read_file_content,
    build_insights_from_tags,
)
import config
from config_loader import load_business_signals


# 商业主题信号检测规则
BUSINESS_SIGNALS = [
    {
        "id": "diagnosis",
        "label": "商业模式诊断",
        "skill": "dbs-diagnosis",
        "keywords": [
            "赚钱", "商业模式", "怎么变现", "收入", "利润", "定价",
            "卖什么", "卖给谁", "怎么获客", "怎么交付", "产品是什么",
            "付款链接", "引流款", "利润款", "不赚钱", "变现",
        ],
        "patterns": [
            r"怎么(赚钱|变现|盈利)",
            r"(卖|定价|收费)\w{0,3}(多少|怎么|贵|便宜)",
            r"这个(生意|业务|模式)",
        ],
    },
    {
        "id": "benchmark",
        "label": "对标分析",
        "skill": "dbs-benchmark",
        "keywords": [
            "学谁", "对标", "模仿", "抄", "参考", "借鉴",
            "像.*一样", "朝钱", "老王", "云瀚", "李笑来", "CZ",
            "锐子", "模仿颗粒度", "像素级",
        ],
        "patterns": [
            r"(学|模仿|抄|对标)\w{0,2}(谁|一下|他)",
            r"(像|跟)\S{1,4}(一样|学|做)",
            r"(凭什么|为啥|为什么)\S{1,6}(能|可以)(赚钱|成功)",
        ],
    },
    {
        "id": "content",
        "label": "内容创作诊断",
        "skill": "dbs-content",
        "keywords": [
            "小红书", "抖音", "视频", "标题", "封面", "开头",
            "文案", "自媒体", "内容怎么做", "公开日记", "写作",
            "公众号", "起号", "播放量", "完播率", "流量",
        ],
        "patterns": [
            r"(小红书|抖音|视频号|公众号)(怎么|如何|起号|运营)",
            r"(拍|发|做|写)\w{0,2}(视频|内容|文案|文章)",
            r"播放量|完播率|涨粉|流量",
        ],
    },
    {
        "id": "action",
        "label": "执行力诊断",
        "skill": "dbs-action",
        "keywords": [
            "拖延", "做不动", "不想做", "知道该做但", "懒",
            "逃避", "害怕", "不敢", "再想想", "等准备好了",
            "就是不做", "一直在准备", "还没开始",
        ],
        "patterns": [
            r"知道\S{1,4}(但|就是)\S{1,4}(不做|没做|做不)",
            r"(总是|一直)\S{0,3}(拖延|逃避|害怕)",
            r"等\S{1,4}(好了|完了|准备好)",
        ],
    },
    {
        "id": "goal",
        "label": "目标清晰化",
        "skill": "dbs-goal",
        "keywords": [
            "我想做", "我想成为", "我想变", "我的目标是",
            "我想有", "未来我想", "个人 IP", "影响力",
            "财务自由", "变得更强", "想做有影响力",
        ],
        "patterns": [
            r"我想(做|成为|变|有)\S{1,10}",
            r"我的目标是",
            r"我要(做|成为|变)",
        ],
    },
    {
        "id": "decision",
        "label": "决策分析",
        "skill": "dbs-decision",
        "keywords": [
            "选 A 还是", "留学还是", "考研还是", "打工还是",
            "出国还是", "纠结", "不知道选哪个", "二选一",
            "要不要", "该不该",
        ],
        "patterns": [
            r"(还是|要么|或者)\S{1,6}(算了|吧|不)",
            r"(要不要|该不该)\S{1,10}",
            r"纠结\S{0,4}(要不要|该|选)",
        ],
    },
    {
        "id": "deconstruct",
        "label": "概念拆解",
        "skill": "dbs-deconstruct",
        "keywords": [
            "什么意思", "什么叫", "搞不清楚", "不懂什么是",
            "这个词", "这个概念",
        ],
        "patterns": [
            r"(什么|啥)(意思|叫|是)",
            r"搞不(清楚|懂|明白)",
        ],
    },
    {
        "id": "slowisfast",
        "label": "慢就是快",
        "skill": "dbs-slowisfast",
        "keywords": [
            "太快了", "有没有更慢", "捷径", "贪快",
            "想绕开", "省事的方法", "快速", "速成",
        ],
        "patterns": [
            r"(太快|太急|急着|赶着)",
            r"(捷径|速成|快速)\S{0,3}(方法|方式|路径)",
        ],
    },
    {
        "id": "good_question",
        "label": "好问题生成",
        "skill": "dbs-good-question",
        "keywords": [
            "问题到底是什么", "这个问题能不能自动化",
            "帮我把问题说清楚", "问题说明书",
        ],
        "patterns": [
            r"问题\S{0,2}(到底|究竟|本质)(是什么|在哪)",
            r"(能不能|可以不可以)(自动化|让 AI)",
        ],
    },
]


def _apply_external_config():
    """尝试从 YAML 加载商业信号规则"""
    global BUSINESS_SIGNALS
    ext = load_business_signals()
    if ext and isinstance(ext, list):
        BUSINESS_SIGNALS = ext
        print(f"  已从 config/business_signals.yaml 加载 {len(ext)} 条信号规则")


def detect_business_themes(diary_files: list[Path], tag_results: list[dict] = None) -> list[dict]:
    """扫描日记文件，检测商业主题信号

    Args:
        diary_files: 日记文件路径列表
        tag_results: tag_diary 的预计算结果（可选）

    Returns:
        list[dict]: 检测到的商业主题列表，按信号强度和出现天数排序
    """
    themes = {}  # key: signal_id -> accumulated data

    for i, fpath in enumerate(diary_files):
        content = read_file_content(fpath)
        if not content:
            continue

        date_str = fpath.stem[:10] if len(fpath.stem) >= 10 else fpath.stem
        content_lower = content.lower()

        # 分段落扫描，每个段落独立匹配
        paragraphs = [p.strip() for p in content.split("\n") if p.strip()]

        for signal in BUSINESS_SIGNALS:
            matched_snippets = []

            # 关键词匹配（中文不分大小写）
            for kw in signal["keywords"]:
                if kw.lower() in content_lower:
                    # 找到包含关键词的段落作为上下文
                    for para in paragraphs:
                        if kw in para and para not in matched_snippets:
                            matched_snippets.append(para[:200])

            # 正则匹配
            for pat in signal.get("patterns", []):
                matches = re.findall(pat, content)
                if matches:
                    for para in paragraphs:
                        if re.search(pat, para) and para not in matched_snippets:
                            matched_snippets.append(para[:200])

            if matched_snippets:
                sid = signal["id"]
                if sid not in themes:
                    themes[sid] = {
                        "id": sid,
                        "label": signal["label"],
                        "skill": signal["skill"],
                        "diary_dates": [],
                        "snippets": [],
                        "tag_entities": [],
                    }
                themes[sid]["diary_dates"].append(date_str)
                themes[sid]["snippets"].extend(matched_snippets[:3])

    # 合并标签信息
    if tag_results:
        for i, fpath in enumerate(diary_files):
            if i < len(tag_results):
                entities = tag_results[i].get("entities_found", [])
                if entities:
                    date_str = fpath.stem[:10]
                    for sid in themes:
                        if date_str in themes[sid]["diary_dates"]:
                            themes[sid]["tag_entities"].extend(entities)

    # 去重 tag_entities
    for sid in themes:
        themes[sid]["tag_entities"] = list(dict.fromkeys(themes[sid]["tag_entities"]))
        # 去重 snippets
        seen = set()
        unique_snippets = []
        for s in themes[sid]["snippets"]:
            if s[:50] not in seen:
                seen.add(s[:50])
                unique_snippets.append(s)
        themes[sid]["snippets"] = unique_snippets[:5]

    # 按出现天数排序（多天的排前面），同天数按 snippet 数量排
    result = sorted(themes.values(), key=lambda t: (-len(t["diary_dates"]), -len(t["snippets"])))
    return result


def generate_markdown(themes: list[dict], target_date: str = None) -> str:
    """生成待诊断 markdown 文件

    Args:
        themes: detect_business_themes 的输出
        target_date: 目标日期（用于文件名），默认今天
    """
    if target_date is None:
        target_date = datetime.now().strftime("%Y-%m-%d")

    today = datetime.now().strftime("%Y-%m-%d")
    lines = [
        "---",
        f"title: \"本周商业洞察待诊断\"",
        "tags: [商业洞察, dbskill, 自动生成]",
        f"created: {today}",
        "type: fleeting",
        f"summary: \"{target_date} 周日记中检测到的商业主题\"",
        "---",
        f"# 本周商业洞察待诊断",
        f"> 自动生成于 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
    ]

    if not themes:
        lines.append("本周日记中未检测到明确的商业主题。")
        lines.append("")
        return "\n".join(lines)

    lines.append(f"共检测到 {len(themes)} 个商业主题：")
    lines.append("")

    for i, theme in enumerate(themes):
        days = len(theme["diary_dates"])
        fire = "🔥 " if days >= 3 else ""
        lines.append(f"## {i + 1}. {fire}{theme['label']}")
        lines.append("")
        lines.append(f"- **技能**：`/{theme['skill']}`")
        lines.append(f"- **出现天数**：{days} 天（{', '.join(theme['diary_dates'])}）")
        lines.append(f"- **相关标签**：{', '.join(theme['tag_entities']) if theme['tag_entities'] else '（无）'}")
        lines.append("")
        lines.append("### 相关原文")
        lines.append("")
        for j, snippet in enumerate(theme["snippets"][:3]):
            lines.append(f"> {snippet}")
            lines.append("")
        lines.append(f"### 采访可追问")
        lines.append("")
        # 根据信号类型生成采访追问方向
        followup = _generate_followup_questions(theme)
        for fq in followup:
            lines.append(f"- {fq}")
        lines.append("")
        lines.append("---")
        lines.append("")

    lines.append(f"*下次采访前可用 `/dbs-vault` 逐项诊断*")
    return "\n".join(lines)


def _generate_followup_questions(theme: dict) -> list[str]:
    """根据主题类型生成采访追问建议"""
    mapping = {
        "diagnosis": [
            "你说的「这个怎么赚钱」，具体试过哪些方法？",
            "你现在的收入来源有几个？最稳定的是哪个？",
        ],
        "benchmark": [
            "XX 做的哪件事让你觉得最值得学？",
            "你模仿过他的什么？结果怎么样？",
        ],
        "content": [
            "你说的内容方向，你觉得你的独特优势在哪？",
            "有没有试过发一条看看数据反馈？",
        ],
        "action": [
            "具体是哪一件事你知道该做但一直没做？",
            "你觉得拖着的真正原因是什么？不用想太多，第一反应。",
        ],
        "goal": [
            "你说的这个目标，到什么程度算达到了？",
            "如果下周就能开始，第一步是什么？",
        ],
        "decision": [
            "这两个选项，各有什么是你确定知道的、什么是你在猜的？",
            "有没有问过走过这两条路的人？",
        ],
        "deconstruct": [
            "你说的这个词，能不能用自己的话重新定义一遍？",
            "你觉得别人用这个词的时候，和你想的是一个意思吗？",
        ],
        "slowisfast": [
            "你说的这件事，有没有哪个环节你觉得可以慢下来反而更好？",
            "你最近有没有在某个地方走了捷径结果反而更慢？",
        ],
        "good_question": [
            "你说的这个问题，能不能描述一个具体的场景？",
            "如果能拿到一个数据来判断这个问题的答案，你想要什么数据？",
        ],
    }
    return mapping.get(theme["id"], ["这个方向你觉得最值得深入的点是什么？"])


def scan(target_date: str = None, tag_results: list[dict] = None, dry_run: bool = False) -> dict:
    """主入口：扫描日记中的商业主题

    Args:
        target_date: 目标日期（用于文件名），默认今天
        tag_results: tag_diary 预计算结果
        dry_run: 预览模式

    Returns:
        dict: {
            "themes": list[dict],           # 检测到的商业主题
            "markdown": str,                 # 生成的 markdown 内容
            "filepath": Path,                # 输出文件路径
            "business_themes_for_interview": list[dict],  # 注入采访的结构化数据
        }
    """
    if target_date is None:
        target_date = datetime.now().strftime("%Y-%m-%d")

    print("=" * 50)
    print(f"商业主题扫描 — {target_date}")
    print("=" * 50)

    # 加载外部配置
    _apply_external_config()

    # 收集本周日记
    print(f"\n[1/3] 收集本周日记...")
    diary_files = find_diary_files(config.ANALYSIS_DAYS)
    print(f"  找到 {len(diary_files)} 篇日记")

    # 检测商业主题
    print(f"\n[2/3] 检测商业主题信号...")
    themes = detect_business_themes(diary_files, tag_results)
    print(f"  检测到 {len(themes)} 个商业主题")
    for t in themes:
        print(f"    - {t['label']} ({len(t['diary_dates'])} 天): /{t['skill']}")

    # 生成输出
    print(f"\n[3/3] 生成待诊断清单...")
    markdown = generate_markdown(themes, target_date)

    # 确保目录存在
    insight_dir = config.DIGITAL_IMMORTALITY_DIR / "商业洞察"
    if not dry_run:
        insight_dir.mkdir(parents=True, exist_ok=True)

    filepath = insight_dir / f"待诊断-{target_date}.md"

    if dry_run:
        print(f"\n  [DRY-RUN] 将写入: {filepath}")
    else:
        filepath.write_text(markdown, encoding="utf-8")
        print(f"\n  待诊断清单已生成: {filepath}")

    # 构建注入采访的结构化数据
    business_themes_for_interview = []
    for t in themes:
        business_themes_for_interview.append({
            "theme": t["label"],
            "skill": t["skill"],
            "diary_dates": t["diary_dates"],
            "key_question": _generate_followup_questions(t)[0] if _generate_followup_questions(t) else "",
            "context_snippets": t["snippets"][:3],
        })

    # 生成/更新 INDEX.md
    _update_index(insight_dir, target_date, len(themes), dry_run)

    return {
        "themes": themes,
        "markdown": markdown,
        "filepath": filepath,
        "business_themes_for_interview": business_themes_for_interview,
    }


def _update_index(insight_dir: Path, date: str, theme_count: int, dry_run: bool = False):
    """更新商业洞察索引"""
    index_path = insight_dir / "INDEX.md"
    today = datetime.now().strftime("%Y-%m-%d")

    if index_path.exists():
        existing = index_path.read_text(encoding="utf-8")
    else:
        existing = (
            "# 商业洞察索引\n\n"
            "| 日期 | 主题数 | 已诊断 | 备注 |\n"
            "|---|---:|---|---|\n"
        )

    # 追加新行
    new_line = f"| {date} | {theme_count} | 0 | 待处理 |\n"
    if date not in existing:
        lines = existing.strip().split("\n")
        # 在表格末尾插入
        lines.append(new_line)
        updated = "\n".join(lines) + "\n"
    else:
        updated = existing

    if not dry_run:
        index_path.write_text(updated, encoding="utf-8")


if __name__ == "__main__":
    import sys
    dry_run = "--dry-run" in sys.argv
    tag_results = None  # 独立运行时无预计算数据
    scan(dry_run=dry_run, tag_results=tag_results)
