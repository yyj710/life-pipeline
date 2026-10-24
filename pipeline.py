#!/usr/bin/env python
"""
数字永生计划 × 飞书集成 — 统一调度入口

用法:
  python pipeline.py sync        同步飞书时间数据 → 时间周报
  python pipeline.py tag         扫描日记 → 打标签 + 加双链
  python pipeline.py wiki        维护 wiki 概念/实体/主题页
  python pipeline.py cognition   检测认知变化 → 更新认知画像
  python pipeline.py analyze     生成周度观察初稿
  python pipeline.py dbs-scan    扫描日记中的商业主题 → 待诊断清单
  python pipeline.py interview   生成访谈问题
  python pipeline.py weekly      完整七步流水线（建议每周日跑）
  python pipeline.py weekly --dry-run   预览不写入

流水线顺序: sync → tag → wiki → cognition → analyze → dbs-scan → interview
"""
import sys
import os
import time
from datetime import datetime

from feishu_client import FeishuClient
from sync_bitable import sync
from tag_diary import scan_and_tag
from update_wiki import maintain_wiki
from update_cognition import detect_and_update
from analyze_diary import analyze
from dbs_scan import scan as dbs_scan
from interview_engine import prepare_interview
from select_github_projects import select_weekly_projects
from pipeline_log import init_run, log_step, finish_run
from cleanup import run_cleanup
import config
import traceback


def _run_step(step_num: int, total: int, name: str, func, *args, **kwargs):
    """执行流水线单步，失败时打印错误并继续"""
    print(f"\n>>> [{step_num}/{total}] {name}")
    try:
        result = func(*args, **kwargs)
        return result
    except Exception as e:
        print(f"  ❌ 步骤 [{step_num}/{total}] {name} 失败: {e}")
        traceback.print_exc()
        return None


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return

    command = args[0]
    dry_run = "--dry-run" in args
    target_date = None

    for i, arg in enumerate(args):
        if arg == "--date" and i + 1 < len(args):
            target_date = args[i + 1]

    if dry_run:
        os.environ["DRY_RUN"] = "1"
        config.DRY_RUN = True
        print("[DRY-RUN 模式] 只预览不写入文件\n")

    client = FeishuClient()

    # ---- 单步命令 ----

    if command == "sync":
        print("执行: sync — 同步时间数据\n")
        sync(client)

    elif command == "tag":
        print("执行: tag — 扫描日记打标签加双链\n")
        scan_and_tag(days=7)

    elif command == "wiki":
        print("执行: wiki — 维护概念页\n")
        _, new_entities, existing_mentions = scan_and_tag(days=7, dry_run=dry_run)
        maintain_wiki(new_entities, existing_mentions=existing_mentions)

    elif command == "cognition":
        print("执行: cognition — 检测认知变化\n")
        detect_and_update()

    elif command == "analyze":
        print("执行: analyze — 生成周度观察\n")
        analyze(client)

    elif command == "interview":
        print("执行: interview — 生成访谈问题\n")
        prepare_interview(client, target_date)

    elif command == "dbs-scan":
        print("执行: dbs-scan — 扫描日记中的商业主题\n")
        dbs_scan(target_date=target_date, dry_run=dry_run)

    # ---- 组合命令 ----

    elif command == "weekly":
        init_run()
        start_time = time.time()

        print("=" * 50)
        print(f"每周自动流水线 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print("=" * 50)

        tag_results = []
        new_entities = {}
        existing_mentions = {}
        scan_result = {}

        _run_step(1, 7, "sync: 同步飞书时间数据", sync, client)
        log_step("sync", "ok")

        tag_data = _run_step(2, 7, "tag: 扫描日记打标签加双链",
                             scan_and_tag, days=7, dry_run=dry_run)
        if tag_data:
            tag_results, new_entities, existing_mentions = tag_data
        log_step("tag", "ok" if tag_data else "error", tag_count=len(tag_results))

        wiki_result = _run_step(3, 7, "wiki: 维护概念/实体/主题页",
                  maintain_wiki, new_entities, dry_run=dry_run, existing_mentions=existing_mentions)
        log_step("wiki", "ok" if wiki_result is not None else "error", new_entities=len(new_entities))

        cognition_result = _run_step(4, 7, "cognition: 检测认知变化",
                  detect_and_update, dry_run=dry_run, tag_results=tag_results)
        log_step("cognition", "ok" if cognition_result is not None else "error")

        analyze_result = _run_step(5, 7, "analyze: 生成周度观察",
                  analyze, client, skip_sync=True, tag_results=tag_results)
        log_step("analyze", "ok" if analyze_result is not None else "error")

        scan_result = _run_step(6, 7, "dbs_scan: 扫描本周商业主题",
                                dbs_scan, target_date=target_date, tag_results=tag_results, dry_run=dry_run) or {}
        log_step("dbs_scan", "ok", theme_count=len(scan_result.get("business_themes_for_interview", [])))

        interview_result = _run_step(7, 8, "interview: 生成访谈问题",
                  prepare_interview, client, target_date,
                  skip_sync=True, tag_results=tag_results,
                  business_themes=scan_result.get("business_themes_for_interview", []))
        log_step("interview", "ok" if interview_result is not None else "error")

        github_result = _run_step(8, 8, "github: 预选下周开源项目",
                  select_weekly_projects, dry_run=dry_run)
        log_step("github", "ok" if github_result is not None else "error")

        # 清理检测（只报告，不删除）
        cleanup_report = _run_step(9, 9, "cleanup: 检测过期stub/休眠事实/孤立标签",
                                  run_cleanup, dry_run=dry_run)

        log_step("cleanup", "ok" if cleanup_report else "skip")
        finish_run(time.time() - start_time)

        print("\n" + "=" * 50)
        print("每周流水线完成")
        print(f"  - 日记处理: {len(tag_results)} 篇")

    elif command == "full":
        # 兼容旧版 full 命令
        init_run()
        start_time = time.time()

        print("=" * 50)
        print(f"全量执行 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print("=" * 50)

        tag_results = []
        new_entities = {}
        existing_mentions = {}
        scan_result = {}

        _run_step(1, 8, "sync: 同步飞书时间数据", sync, client)
        log_step("sync", "ok")

        tag_data = _run_step(2, 8, "tag: 扫描日记打标签加双链",
                             scan_and_tag, days=7, dry_run=dry_run)
        if tag_data:
            tag_results, new_entities, existing_mentions = tag_data
        log_step("tag", "ok" if tag_data else "error", tag_count=len(tag_results))

        wiki_result = _run_step(3, 8, "wiki: 维护概念页",
                  maintain_wiki, new_entities, dry_run=dry_run, existing_mentions=existing_mentions)
        log_step("wiki", "ok" if wiki_result is not None else "error", new_entities=len(new_entities))

        cognition_result = _run_step(4, 8, "cognition: 检测认知变化",
                  detect_and_update, dry_run=dry_run, tag_results=tag_results)
        log_step("cognition", "ok" if cognition_result is not None else "error")

        analyze_result = _run_step(5, 8, "analyze: 生成周度观察",
                  analyze, client, skip_sync=True, tag_results=tag_results)
        log_step("analyze", "ok" if analyze_result is not None else "error")

        scan_result = _run_step(6, 8, "dbs_scan: 扫描本周商业主题",
                                dbs_scan, target_date=target_date, tag_results=tag_results, dry_run=dry_run) or {}
        log_step("dbs_scan", "ok", theme_count=len(scan_result.get("business_themes_for_interview", [])))

        interview_result = _run_step(7, 8, "interview: 生成访谈问题",
                  prepare_interview, client, target_date,
                  skip_sync=True, tag_results=tag_results,
                  business_themes=scan_result.get("business_themes_for_interview", []))
        log_step("interview", "ok" if interview_result is not None else "error")

        github_result = _run_step(8, 8, "github: 预选下周开源项目",
                  select_weekly_projects, dry_run=dry_run)
        log_step("github", "ok" if github_result is not None else "error")

        # 清理检测（只报告，不删除）
        cleanup_report = _run_step(9, 9, "cleanup: 检测过期stub/休眠事实/孤立标签",
                                  run_cleanup, dry_run=dry_run)

        log_step("cleanup", "ok" if cleanup_report else "skip")
        finish_run(time.time() - start_time)

        print("\n" + "=" * 50)
        print("全量执行完成")

    else:
        print(f"未知命令: {command}")
        print("可用: sync | tag | wiki | cognition | analyze | dbs-scan | interview | weekly | full")
        sys.exit(1)


if __name__ == "__main__":
    main()
