"""
袁裕杰每日习惯清单提醒
每天早上6点自动输出今日清单
用法: python daily_reminder.py [--silent]
  --silent  只写入文件，不弹出窗口
"""
import datetime
import os
import sys
import tempfile

tempfile.gettempdir()

# ====== 考试日期配置 ======
EXAMS = [
    {"name": "ACCA PM考试", "date": datetime.date(2026, 9, 9)},
    {"name": "ACCA FR考试", "date": datetime.date(2026, 9, 10)},
    {"name": "计算机二级考试", "date": datetime.date(2026, 9, 19)},
]

FINAL_EXAM_DATE = datetime.date(2026, 7, 10)

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "日记")


def get_weekly_tasks(today):
    weekday = today.weekday()  # 0=周一, 6=周日
    tasks = []
    if weekday == 6:  # 周日
        tasks.append("- 公众号文章（本周未发则提醒）")
        tasks.append("- 英语真题一套")
    return tasks


def get_special_reminder(today):
    if today < datetime.date(2026, 7, 10):
        days_left = (FINAL_EXAM_DATE - today).days
        return f"期末考试还有{days_left}天，先专注期末"
    elif today < datetime.date(2026, 7, 27):
        return "期末考完了！全力复习FR，建议每天ACCA学习3-4小时"
    elif today < datetime.date(2026, 8, 4):
        return "ACCA常规报名已截止！确认是否已报名。FR和PM冲刺阶段"
    elif today < datetime.date(2026, 9, 9):
        return "ACCA考试临近！最后冲刺。考完ACCA后立即转计算机二级备考"
    elif today < datetime.date(2026, 9, 12):
        return "ACCA考试周！放松心态，正常发挥"
    else:
        return "ACCA考完了！全力转计算机二级备考"


def get_github_project(today):
    """读取下周清单，返回今日GitHub项目"""
    vault_dir = os.path.dirname(os.path.abspath(__file__))
    weekly_file = os.path.join(
        vault_dir, "raw", "2-领域", "GitHub开源学习", "下周清单.md"
    )
    if not os.path.exists(weekly_file):
        return None

    try:
        with open(weekly_file, "r", encoding="utf-8") as f:
            content = f.read()

        # 根据星期几提取对应行
        weekday = today.weekday()  # 0=周一, 6=周日
        weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        target_day = weekdays[weekday]

        for line in content.split("\n"):
            if line.startswith(f"| {target_day}"):
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 6:
                    return {
                        "project": parts[2].strip("* "),
                        "question": parts[4],
                        "prep": parts[5],
                    }
    except Exception:
        pass
    return None


def generate_text():
    today = datetime.date.today()
    weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    date_str = f"{today.year}年{today.month}月{today.day}日 {weekday_names[today.weekday()]}"

    lines = []
    lines.append("=" * 40)
    lines.append(f"早安！今日清单  |  {date_str}")
    lines.append("=" * 40)
    lines.append("")
    lines.append("每日必做：")
    lines.append("- 跑步4公里 或 跳绳3500下")
    lines.append("- Reader阅读一篇读三遍（5000词英文阅读）")
    lines.append("- 朗读背诵英语一篇")
    lines.append("- 每天工作/学习8小时，先完成最重要的事")
    lines.append("- 早中晚餐后养成习惯")
    lines.append("")

    weekly_tasks = get_weekly_tasks(today)
    if weekly_tasks:
        lines.append("每周任务：")
        lines.extend(weekly_tasks)
        lines.append("")

    lines.append("考试倒计时：")
    for exam in sorted(EXAMS, key=lambda x: x["date"]):
        days_left = (exam["date"] - today).days
        if days_left > 0:
            lines.append(f"- {exam['name']}：{exam['date'].month}月{exam['date'].day}日（剩余 {days_left} 天）")
        elif days_left == 0:
            lines.append(f"- {exam['name']}：{exam['date'].month}月{exam['date'].day}日（就在今天！）")
        else:
            lines.append(f"- {exam['name']}：{exam['date'].month}月{exam['date'].day}日（已过）")
    lines.append("")

    # GitHub开源学习提醒
    github = get_github_project(today)
    if github and today.weekday() < 6:  # 周一到周六提醒
        lines.append("GitHub今日学习：")
        lines.append(f"- 项目：{github['project']}")
        lines.append(f"- 核心问题：{github['question']}")
        lines.append(f"- 准备：{github['prep']}")
        lines.append("- 限时45分钟，跑不通也记")
        lines.append("")

    special = get_special_reminder(today)
    lines.append("特别提醒：")
    lines.append(f"- {special}")
    lines.append("")
    lines.append("=" * 40)

    return "\n".join(lines)


def save_to_file(content):
    today = datetime.date.today()
    filename = f"每日清单_{today.strftime('%Y-%m-%d')}.md"

    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return filepath


def show_notification(title, message):
    """Windows 桌面通知"""
    try:
        from win10toast import ToastNotifier
        toaster = ToastNotifier()
        toaster.show_toast(title, message, duration=30)
    except ImportError:
        # 降级方案：用 ctypes 弹窗
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, message, title, 0x40)


def main():
    silent = "--silent" in sys.argv

    content = generate_text()

    # 写入文件
    filepath = save_to_file(content)

    # 控制台输出
    print(content)
    print(f"\n[已保存到: {filepath}]")

    # 桌面通知/弹窗
    if not silent:
        today = datetime.date.today()
        weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        date_str = f"{today.month}月{today.day}日 {weekday_names[today.weekday()]}"

        # 取特别提醒作为通知摘要
        special = get_special_reminder(today)
        show_notification(f"早安！{date_str}", special)


if __name__ == "__main__":
    main()
