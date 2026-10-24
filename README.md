# life-pipeline · 日记自动化流水线

> 一句话：我每天在 Obsidian 写日记，这套 Python 流水线**自动**把日记变成标签、知识库页面、周报、认知画像和访谈问题——我一个字都不用改。

![Python](https://img.shields.io/badge/Python-3.x-3776ab)
![Feishu](https://img.shields.io/badge/飞书-Bitable%20API-00d6b9)
![Obsidian](https://img.shields.io/badge/Obsidian-vault-7c3aed)

## 30 秒懂这个项目

**痛点**：写日记容易，但日记写完就死了——没人回头看，经验不沉淀，想法不追踪。

**解法**：跑一条命令 `python pipeline.py weekly`，流水线自动做 7 件事：

```
你的日记（纯文本）
  │
  ├─ 1. 打标签      → 每篇日记自动加 2-6 个标签 + [[双向链接]]
  ├─ 2. 建 wiki     → 提到的人物/概念自动建知识库页面
  ├─ 3. 周度观察    → 生成"这周我在做什么/想什么"初稿
  ├─ 4. 每日草稿    → 扫描当天日记，产出 0.1 版洞察到待处理池
  ├─ 5. 认知画像    → 检测认知变化（新决策/新关注/转向），只追加不重写
  ├─ 6. 商业雷达    → 扫出日记里的商业想法，生成待诊断清单
  └─ 7. 飞书同步    → 时间记录同步到飞书多维表格，出周报
```

**结果**：跑了几个月的生产系统，不是玩具。日记从"写完就忘"变成"自动生长的个人数据库"。

## 对别人有什么用

你可以直接抄走的 4 个东西：

1. **`examples/` 文件夹 = 飞书 API 菜谱** — 发消息、日历、文档、审批 4 个可运行示例，比翻官方文档快
2. **规则优于模型的实践** — 打标签没用 NLP/大模型 API，纯词典+规则（`config/*.yaml`），零成本、可解释、可调试。大多数个人自动化场景规则就够了
3. **爆炸半径表**（见下）— 改代码前先查依赖影响面的工作方法，可直接套用到你的项目
4. **pipeline 设计模式** — 每步可独立跑、可 dry-run 预览、失败不炸全流程的流水线结构

## 文件导览（每个文件一句话）

### 入口
| 文件 | 干嘛的 |
|------|--------|
| `pipeline.py` | CLI 入口，串联七步，支持 `weekly` / `--dry-run` |

### 七步引擎
| 文件 | 干嘛的 |
|------|--------|
| `tag_diary.py` | 扫描本周日记 → 自动打标签 + 加双链 + 回写原文件 |
| `update_wiki.py` | 基于标签结果，创建/维护 wiki 概念页、实体页 |
| `analyze_diary.py` | 读本周日记+时间记录，生成周度观察初稿 |
| `daily_draft.py` | 扫描当天日记，自动产出 0.1 版洞察到待处理池 |
| `update_cognition.py` | 检测本周认知变化，自动更新认知画像 |
| `dbs_scan.py` | 扫出日记里的商业信号，输出待诊断清单 |
| `interview_engine.py` | 为每周日 19:00 深度访谈生成上下文感知的访谈问题 |

### 共享层（改它们要格外小心）
| 文件 | 干嘛的 |
|------|--------|
| `config.py` | 全局配置中心：路径、常量、访谈主题列表 |
| `utils.py` | 共享工具：frontmatter 解析/生成（6 个模块依赖它） |
| `feishu_client.py` | 飞书 API 封装：认证、多维表格读写 |
| `config_loader.py` | 加载 `config/*.yaml` 规则文件 |

### 运维与配套
| 文件 | 干嘛的 |
|------|--------|
| `sync_bitable.py` | 飞书多维表格 → Obsidian 时间记录同步 |
| `daily_reminder.py` | 每日习惯清单提醒 |
| `select_github_projects.py` | 筛选值得学习的 GitHub 项目 |
| `pipeline_log.py` | 流水线运行日志 |
| `cleanup.py` | 定期清理旧文件 |
| `test_basic.py` | 基础测试 |

### 规则与文档
| 文件 | 干嘛的 |
|------|--------|
| `config/*.yaml` | 标签词典、商业信号、实体词典——规则引擎的"数据库" |
| `pipeline_rules.md` | 指标驱动 + 失败处理规则 |
| `interview_rules.md` | 每周深度访谈流程 |
| `examples/*.py` | 飞书 API 可运行示例：消息/日历/文档/审批 |

## 模块爆炸半径表

改代码前必读——这套系统最值得借鉴的工程实践：

| 改这个文件 | 影响哪些文件 | 风险等级 |
|-----------|-------------|---------|
| `utils.py` | 6 个引擎模块 | **高** |
| `config.py` | 几乎所有模块 | **极高** |
| `feishu_client.py` | sync_bitable / pipeline | **高** |
| `config_loader.py` | tag_diary / analyze_diary | 中 |
| 其余模块 | 只被 pipeline 调用 | 低 |

规则：改标"高/极高"的文件，必须先跑一遍 `python pipeline.py weekly --dry-run` 验证。

## 快速开始

```bash
pip install -r requirements.txt
cp .env.example .env   # 填入飞书凭证和 vault 路径
python pipeline.py weekly --dry-run   # 干跑预览，不写文件
python pipeline.py weekly             # 正式跑七步
```

## 关键设计原则

- **如无必要勿增实体** — 能规则解决的不上模型
- **宁少勿滥** — 每篇日记 2-6 个标签，按优先级排序
- **只追加不重写** — 认知画像保留演化历史
- **dry-run 先行** — 任何写入操作都能先预览
