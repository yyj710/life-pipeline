"""
数字永生计划 - 共享工具模块
抽取各模块重复的 frontmatter 解析、日记文件发现、文件读取等函数
"""
import re
import yaml
from datetime import datetime, timedelta
from pathlib import Path

import config


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """解析 YAML frontmatter，返回 (frontmatter_dict, body_text)
    统一处理 BOM 头
    """
    text = text.lstrip("\ufeff")  # 去除 BOM
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    try:
        fm = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        fm = {}
    return fm, parts[2].strip()


def build_frontmatter(fm: dict) -> str:
    """构建 YAML frontmatter 字符串
    按优先级排列常用字段，其余追加在后
    """
    lines = ["---"]
    priority = ["title", "tags", "created", "date", "type", "status", "summary"]
    for key in priority:
        if key in fm:
            val = fm[key]
            if isinstance(val, list):
                lines.append(f"{key}: [{', '.join(str(v) for v in val)}]")
            else:
                lines.append(f"{key}: {val}")
    for key, val in fm.items():
        if key not in priority:
            if isinstance(val, list):
                lines.append(f"{key}: [{', '.join(str(v) for v in val)}]")
            else:
                lines.append(f"{key}: {val}")
    lines.append("---")
    return "\n".join(lines)


def find_diary_files(days: int = 7, diary_dir: Path = None) -> list[Path]:
    """找到最近 N 天的日记文件（按日期升序排列）"""
    if diary_dir is None:
        diary_dir = config.DIARY_DIR
    if not diary_dir.exists():
        return []

    since = datetime.now() - timedelta(days=days)
    found = []
    for f in sorted(diary_dir.glob("*.md")):
        if f.stem == "index":
            continue
        match = re.match(r"(\d{4}-\d{2}-\d{2})", f.stem)
        if match:
            try:
                date = datetime.strptime(match.group(1), "%Y-%m-%d")
                if date >= since:
                    found.append(f)
            except ValueError:
                pass
    return sorted(found)


def read_file_content(filepath: Path) -> str:
    """读取文件内容（去除 BOM + frontmatter）"""
    text = filepath.read_text(encoding="utf-8").lstrip("\ufeff")
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            return parts[2].strip()
    return text.strip()
