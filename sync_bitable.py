"""
从飞书多维表格同步时间记录到 Obsidian vault
"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

from feishu_client import FeishuClient
import config


def ensure_dirs():
    """确保目标目录存在"""
    config.TIME_RECORDS_DIR.mkdir(parents=True, exist_ok=True)
    config.DATA_ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    config.INTERVIEW_PREP_DIR.mkdir(parents=True, exist_ok=True)


def discover_time_table(client: FeishuClient) -> dict | None:
    """发现时间记录表和字段结构，返回 {table_id, table_name, fields, date_field}，无权或失败时返回 None"""
    tables = client.list_base_tables(config.BITABLE_APP_TOKEN)
    if not tables:
        print("⚠️ 未找到数据表。请确认：")
        print("  1. 飞书应用已开通 bitable:app 权限")
        print("  2. BITABLE_APP_TOKEN 正确")
        print("  3. 应用已被添加到多维表格的协作者中")
        print("  跳过时间数据同步，继续后续步骤…")
        return None

    print(f"发现 {len(tables)} 个数据表:")
    for t in tables:
        print(f"  - {t['name']} (id={t['table_id']})")

    # 默认用第一个表（通常时间记录就一个表）
    target = tables[0]
    table_id = target["table_id"]
    table_name = target["name"]

    fields = client.list_table_fields(config.BITABLE_APP_TOKEN, table_id)
    print(f"\n表 '{table_name}' 有 {len(fields)} 个字段:")
    for f in fields:
        print(f"  - {f['field_name']} (type={f['type']}, id={f['field_id']})")

    # 智能识别日期字段: 优先 DateTime 类型(type=5)，其次"日期/时间"关键词
    date_field = None
    for f in fields:
        if f["type"] == 5:  # DateTime
            date_field = f["field_name"]
            break
    if not date_field:
        date_keywords = ["日期", "时间", "date"]
        for f in fields:
            fn = f["field_name"].lower()
            if any(kw in fn for kw in date_keywords):
                date_field = f["field_name"]
                break

    print(f"\n识别日期字段: {date_field} (type=5 DateTime)")
    print(f"识别活动名称字段: 时间花销")
    return {
        "table_id": table_id,
        "table_name": table_name,
        "fields": fields,
        "date_field": date_field,
    }


def parse_record_date(record: dict, date_field: str) -> str | None:
    """从记录中提取日期，返回 YYYY-MM-DD 格式"""
    value = record.get("fields", {}).get(date_field)
    if not value:
        return None
    # Feishu DateTime 字段返回 Unix timestamp 毫秒 (int)
    if isinstance(value, (int, float)):
        try:
            ts = value / 1000 if value > 1e10 else value
            return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
        except (OSError, ValueError):
            pass
    if isinstance(value, str):
        for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%Y年%m月%d日"]:
            try:
                return datetime.strptime(value.strip(), fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        if len(value) >= 10:
            return value[:10]
    return str(value)[:10]


def fetch_time_records(client: FeishuClient, table_info: dict, days: int = 7) -> list[dict]:
    """拉取最近 N 天的时间记录"""
    table_id = table_info["table_id"]

    # 尝试用筛选条件拉取
    since_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    print(f"\n拉取 {since_date} 至今的记录...")

    # 先尝试直接拉取全部记录（飞书 Bitable 通常数据量不大）
    records = client.list_records(
        config.BITABLE_APP_TOKEN,
        table_id,
        page_size=200,
    )
    print(f"总共拉取 {len(records)} 条记录")
    return records


def normalize_record(record: dict, table_info: dict) -> dict | None:
    """将飞书记录标准化为统一格式"""
    fields = record.get("fields", {})
    if not fields:
        return None

    date_field = table_info["date_field"]
    date_str = parse_record_date({"fields": fields}, date_field) if date_field else None
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")

    # 识别分类字段（包含"分类"/"类别"/"赛道"等关键词）
    category = ""
    subcategory = ""
    duration = 0
    notes = ""

    for key, value in fields.items():
        kl = key.lower()
        if any(kw in kl for kw in ["分类", "类别", "category"]):
            category = str(value) if value else ""
        elif any(kw in kl for kw in ["子类", "subcategory", "项目", "事项"]):
            subcategory = str(value) if value else ""
        elif any(kw in kl for kw in ["时长", "duration", "分钟", "小时", "时间(min)", "时间（min）"]):
            try:
                duration = int(value) if value else 0
            except (ValueError, TypeError):
                pass
        elif any(kw in kl for kw in ["备注", "note", "说明", "描述"]):
            notes = str(value) if value else ""

    return {
        "date": date_str,
        "category": category,
        "subcategory": subcategory,
        "duration": duration,
        "notes": notes,
        "raw_fields": fields,
    }


def group_by_date(records: list[dict]) -> dict[str, list[dict]]:
    """按日期分组"""
    groups = defaultdict(list)
    for r in records:
        groups[r["date"]].append(r)
    return dict(sorted(groups.items(), reverse=True))


def write_weekly_report(all_records: list[dict]):
    """生成周度时间分析报告（唯一输出文件）"""
    if not all_records:
        return

    cat_totals = defaultdict(int)
    cat_items = defaultdict(list)  # 每个分类下的具体项目
    for r in all_records:
        cat_totals[r["category"]] += r["duration"]
        sub = r["subcategory"] or r["category"]
        if sub not in cat_items[r["category"]]:
            cat_items[r["category"]].append(sub)

    total_minutes = sum(r["duration"] for r in all_records)
    total_hours = total_minutes / 60
    days = len(set(r["date"] for r in all_records))
    avg_per_day = total_hours / days if days > 0 else 0
    today = datetime.now().strftime("%Y-%m-%d")

    lines = [
        "---",
        "title: \"时间周报\"",
        "tags: [数据分析, 时间记录, 自动化]",
        f"date: {today}",
        "type: permanent",
        f"summary: \"近{days}天时间分析: {total_hours:.0f}h, 日均{avg_per_day:.1f}h, 共{len(all_records)}条\"",
        "---",
        f"# 时间周报",
        "",
        f"| 指标 | 值 |",
        f"|------|----|",
        f"| 统计天数 | {days} |",
        f"| 总时长 | {total_hours:.0f}h |",
        f"| 日均 | {avg_per_day:.1f}h |",
        f"| 记录数 | {len(all_records)} |",
        "",
        "## 分类分布",
        "",
        "| 分类 | 时长 | 占比 | 涉及项目 |",
        "|------|------|------|----------|",
    ]

    for cat, mins in sorted(cat_totals.items(), key=lambda x: x[1], reverse=True):
        pct = (mins / total_minutes * 100) if total_minutes > 0 else 0
        items_str = "、".join(cat_items[cat][:3])
        if len(cat_items[cat]) > 3:
            items_str += f" 等{len(cat_items[cat])}项"
        lines.append(f"| {cat} | {mins/60:.1f}h | {pct:.0f}% | {items_str} |")

    # 每日趋势（紧凑表格）
    lines.extend([
        "",
        "## 每日趋势",
        "",
        "| 日期 | 时长 | 条数 |",
        "|------|------|------|",
    ])

    date_groups = group_by_date(all_records)
    for date_str, recs in date_groups.items():
        day_total = sum(r["duration"] for r in recs)
        lines.append(f"| {date_str} | {day_total/60:.1f}h | {len(recs)} |")

    lines.append("")
    lines.append(f"*{today} 自动同步*")

    filepath = config.DATA_ANALYSIS_DIR / "时间周报.md"
    if config.DRY_RUN:
        print(f"  [DRY-RUN] 将写入: {filepath}")
        return
    filepath.write_text("\n".join(lines), encoding="utf-8")
    print(f"  已写入: {filepath}")


def sync(client: FeishuClient = None, days: int = None):
    """执行时间数据同步 -> 生成一份周报"""
    if days is None:
        days = config.SYNC_DAYS
    if client is None:
        client = FeishuClient()

    print("=" * 50)
    print(f"时间记录同步 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)

    ensure_dirs()

    table_info = discover_time_table(client)
    if table_info is None:
        print("同步跳过：无法访问多维表格\n")
        return []

    raw_records = fetch_time_records(client, table_info, days)

    normalized = []
    for r in raw_records:
        nr = normalize_record(r, table_info)
        if nr:
            normalized.append(nr)

    # 客户端兜底过滤：只保留最近 N 天的记录
    since_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    normalized = [r for r in normalized if r["date"] >= since_date]

    print(f"有效记录: {len(normalized)} 条")

    write_weekly_report(normalized)

    date_groups = group_by_date(normalized)
    print(f"同步完成 → {config.DATA_ANALYSIS_DIR / '时间周报.md'}")
    return normalized


if __name__ == "__main__":
    sync()
