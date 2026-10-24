"""
数字永生计划 - 流水线运行日志模块

每次 weekly 运行时记录每步状态到 TSV 文件，用于长期追踪流水线健康度。
TSV 字段：日期\t总耗时秒\tsync状态\ttag处理数\twiki新增实体\tcognition状态\tanalyze状态\tdbs_scan主题数\tinterview问题数\tcleanup状态\t备注
"""
from datetime import datetime
from pathlib import Path
import config

LOG_FILE = config.DIGITAL_IMMORTALITY_DIR / "pipeline_log.tsv"
HEADER = "日期\t总耗时秒\tsync\ttag处理数\twiki新增实体\tcognition\tanalyze\tdbs_scan\tinterview\tcleanup\t备注"

# 当前运行记录（内存中）
_current = None


def init_run():
    """在 weekly 开始时调用，初始化本次运行记录"""
    global _current
    _current = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "duration": 0,
        "sync": "skip",
        "tag_count": 0,
        "wiki_new": 0,
        "cognition": "skip",
        "analyze": "skip",
        "dbs_scan": "skip",
        "interview": "skip",
        "cleanup": "skip",
        "notes": "",
    }


def log_step(step_name: str, status: str, **kwargs):
    """记录单步状态。status: ok / skip / error"""
    if _current is None:
        return
    # 默认状态映射
    _current[step_name] = status
    # 额外数据
    if step_name == "tag" and "tag_count" in kwargs:
        _current["tag_count"] = kwargs["tag_count"]
    elif step_name == "wiki" and "new_entities" in kwargs:
        _current["wiki_new"] = kwargs["new_entities"]
    elif step_name == "dbs_scan" and "theme_count" in kwargs:
        _current["dbs_scan"] = f"ok({kwargs['theme_count']})"


def finish_run(duration: float, notes: str = ""):
    """在 weekly 结束时调用，写入 TSV 文件"""
    global _current
    if _current is None:
        return
    _current["duration"] = round(duration, 1)
    _current["notes"] = notes

    # 确保 log 文件和 header 存在
    log_path = Path(LOG_FILE)
    if not log_path.exists():
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(HEADER + "\n", encoding="utf-8")

    # 拼接行
    row = [
        _current["date"],
        str(_current["duration"]),
        _current["sync"],
        str(_current["tag_count"]),
        str(_current["wiki_new"]),
        _current["cognition"],
        _current["analyze"],
        _current["dbs_scan"],
        _current["interview"],
        _current["cleanup"],
        _current["notes"],
    ]
    line = "\t".join(row)

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(line + "\n")

    print(f"\n[日志] 流水线记录已追加到 {log_path.name}")
    _current = None
