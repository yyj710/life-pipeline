"""
数字永生计划 × 飞书集成 — 集中配置
"""
import os
from pathlib import Path

# 飞书多维表格 token（从 Base URL 解析: xxx.feishu.cn/base/<token>，配置到 .env）
BITABLE_APP_TOKEN = os.getenv("BITABLE_APP_TOKEN", "")

# Obsidian vault 根路径（配置到 .env）
VAULT_ROOT = Path(os.getenv("VAULT_ROOT", str(Path.home() / "vault")))

# 数字永生计划子目录
DIGITAL_IMMORTALITY_DIR = VAULT_ROOT / "数字永生计划"
TIME_RECORDS_DIR = DIGITAL_IMMORTALITY_DIR / "时间记录"
DATA_ANALYSIS_DIR = DIGITAL_IMMORTALITY_DIR / "数据分析"
INTERVIEW_PREP_DIR = DIGITAL_IMMORTALITY_DIR / "访谈准备"
DIARY_DIR = VAULT_ROOT / "日记"

# 时间记录默认同步天数
SYNC_DAYS = 7

# 一周观察默认分析天数
ANALYSIS_DAYS = 7

# 访谈计划配置
INTERVIEW_START_DATE = "2026-06-07"  # 第一周访谈日期（周日）
INTERVIEW_TOPICS = [
    "成长经历与价值观形成",
    "人际关系与情感模式",
    "失败经验与应对策略",
    "长期愿景与恐惧",
    "思维模式与决策风格",
    "执行力与自我管理",
    "人生转折点与关键选择",
    "家庭背景与成长环境",
]

# 认知模型目录
COGNITIVE_PROFILE_DIR = DIGITAL_IMMORTALITY_DIR / "认知模型"

# 访谈记录目录
INTERVIEW_RECORDS_DIR = DIGITAL_IMMORTALITY_DIR / "访谈记录"

# Dry-run 模式（预览不写入文件）
DRY_RUN = os.getenv("DRY_RUN", "").lower() in ("1", "true", "yes")
