#!/usr/bin/env python
"""
GitHub开源学习 — 下周项目预选

功能：
1. 读取已学项目列表，避免重复推荐
2. 基于固定项目池和日记标签，生成下周7个项目清单
3. 输出到 raw/2-领域/GitHub开源学习/下周清单.md

用法：
  python select_github_projects.py [--dry-run]
"""
import os
import re
from datetime import datetime, timedelta


def get_vault_path():
    """返回Vault根目录"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(script_dir)


def get_github_learn_dir():
    return os.path.join(get_vault_path(), "raw", "2-领域", "GitHub开源学习")


def parse_index_for_learned():
    """从 index.md 提取已学项目列表"""
    index_path = os.path.join(get_github_learn_dir(), "index.md")
    learned = set()
    if not os.path.exists(index_path):
        return learned

    with open(index_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 匹配已学项目表格中的项目名（格式：| 日期 | 项目 | ... |）
    for line in content.split("\n"):
        if line.startswith("|") and "github.com" not in line and "---" not in line:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 3 and parts[2]:
                # 提取项目名，去掉markdown加粗标记
                project = parts[2].strip("* ")
                if project and project != "项目":
                    learned.add(project.lower())
    return learned


# 备选项目池（可根据社区热点定期更新）
PROJECT_POOL = [
    {
        "project": "microsoft/markitdown",
        "name": "markitdown",
        "author": "微软",
        "question": "它怎么把PDF/Word/PPT变成Markdown的？怎么保留结构？",
        "prep": "`pip install markitdown`",
        "theme": "文档处理",
    },
    {
        "project": "karpathy/autoresearch",
        "name": "autoresearch",
        "author": "Andrej Karpathy",
        "question": "怎么用630行代码让AI自动做研究？核心逻辑是什么？",
        "prep": "Python环境",
        "theme": "AI Agent",
    },
    {
        "project": "cline/cline",
        "name": "cline",
        "author": "Cline团队",
        "question": "AI怎么读取代码上下文、规划修改、执行终端命令？",
        "prep": "VS Code + Node.js",
        "theme": "AI编程",
    },
    {
        "project": "browser-use/browser-use",
        "name": "browser-use",
        "author": "Browser Use团队",
        "question": "AI怎么理解网页结构、决策点击和输入？",
        "prep": "Python + Playwright",
        "theme": "AI Agent",
    },
    {
        "project": "huggingface/smolagents",
        "name": "smolagents",
        "author": "HuggingFace",
        "question": "Agent框架的核心抽象是什么？怎么设计一个好Agent？",
        "prep": "`pip install smolagents`",
        "theme": "AI Agent",
    },
    {
        "project": "mem0ai/mem0",
        "name": "mem0",
        "author": "Mem0团队",
        "question": "AI怎么记住用户偏好？记忆怎么存储和检索？",
        "prep": "`pip install mem0ai`",
        "theme": "AI记忆",
    },
    {
        "project": "continuedev/continue",
        "name": "continue",
        "author": "Continue团队",
        "question": "开源AI代码补全，与Cline对比有什么不同的设计思路？",
        "prep": "VS Code",
        "theme": "AI编程",
    },
    {
        "project": "aider-ai/aider",
        "name": "aider",
        "author": "Aider团队",
        "question": "终端里的AI结对编程，怎么实现多文件编辑和Git集成？",
        "prep": "`pip install aider-chat`",
        "theme": "AI编程",
    },
    {
        "project": "n8n-io/n8n",
        "name": "n8n",
        "author": "n8n团队",
        "question": "可视化工作流自动化，怎么设计节点和连接的抽象？",
        "prep": "Docker 或 `npx n8n`",
        "theme": "工作流自动化",
    },
    {
        "project": "pydantic/pydantic-ai",
        "name": "pydantic-ai",
        "author": "Pydantic团队",
        "question": "基于类型系统的AI Agent框架，类型安全怎么保障AI输出？",
        "prep": "`pip install pydantic-ai`",
        "theme": "AI Agent",
    },
    {
        "project": "langchain-ai/langgraph",
        "name": "langgraph",
        "author": "LangChain团队",
        "question": "有状态的多智能体工作流，怎么把AI任务建模成图结构？",
        "prep": "`pip install langgraph`",
        "theme": "AI Agent",
    },
]


def select_weekly_projects(dry_run=False):
    """选择下周7个项目，避免重复"""
    learned = parse_index_for_learned()

    # 过滤已学项目
    available = [p for p in PROJECT_POOL if p["name"].lower() not in learned]

    # 如果不够7个，从已学中补充（允许重复学习有价值的项目）
    selected = available[:7]
    if len(selected) < 7:
        # 补充尚未选择的项目
        for p in PROJECT_POOL:
            if len(selected) >= 7:
                break
            if p not in selected:
                selected.append(p)

    selected = selected[:7]

    # 生成下周清单文件
    today = datetime.now()
    week_num = today.isocalendar()[1]
    theme = selected[0]["theme"] if selected else "AI工具"

    lines = []
    lines.append("---")
    lines.append(f'title: "GitHub学习下周清单"')
    lines.append(f'week: "{today.year}-W{week_num}"')
    lines.append(f'generated: {today.strftime("%Y-%m-%d")}')
    lines.append(f'theme: "{theme}"')
    lines.append("---")
    lines.append("")
    lines.append(f"# 下周清单（{today.strftime('%m月%d日')} — {(today + timedelta(days=6)).strftime('%m月%d日')}）")
    lines.append("")
    lines.append("| 日期 | 项目 | 作者 | 核心问题 | 预计时间 | 前置准备 |")
    lines.append("|------|------|------|---------|---------|---------|")

    weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    for i, p in enumerate(selected):
        day_name = weekdays[i]
        lines.append(
            f"| {day_name} | **{p['project']}** | {p['author']} | {p['question']} | 45min | {p['prep']} |"
        )

    if len(selected) < 7:
        lines.append("| 周日 | **本周回顾** | - | 整合项目笔记，提取共性认知 | 30min | 阅读本周笔记 |")

    lines.append("")
    lines.append("## 选项目依据")
    lines.append("")
    lines.append(f"- 本周主题：{theme}")
    lines.append(f"- 已学项目数：{len(learned)}")
    lines.append(f"- 新项目数：{len([s for s in selected if s['name'].lower() not in learned])}")
    lines.append("- 筛选标准：能克隆跑通 + 实现原理值得学 + 与主线相关")
    lines.append("")

    output_path = os.path.join(get_github_learn_dir(), "下周清单.md")

    if dry_run:
        print(f"[DRY-RUN] 将写入: {output_path}")
        print("\n".join(lines))
        return

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"✅ 下周清单已生成: {output_path}")
    print(f"   选中 {len(selected)} 个项目（{len([s for s in selected if s['name'].lower() not in learned])} 个新项目）")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="预览不写入")
    args = parser.parse_args()
    select_weekly_projects(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
