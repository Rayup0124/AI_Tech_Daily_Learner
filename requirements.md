# Project: AI Tech Daily Learner (全自动技术学习日报)

## 1. 项目概述
我需要创建一个基于 Python 的自动化工具，用于辅助我进行 IT 技能的自学。
该工具需要每天自动运行，抓取热门技术文章，通过 AI 进行“总结+筛选+翻译”，最后生成一份双语学习简报并推送到我的 Notion 数据库。

## 2. 核心功能需求

### 2.1 数据源 (Data Source)
- **目标网站**: Hacker News (使用官方 API 或者爬取 `https://news.ycombinator.com/`)。
- **筛选逻辑**: 获取 "Top Stories" 中的前 5 篇文章。
- **内容获取**: 对于每一篇文章，访问其 URL，并提取正文内容（需去除广告、导航栏等干扰信息）。

### 2.2 AI 处理 (AI Processing) - 核心部分
- **AI 模型**: 使用 Google Gemini API (推荐模型 `gemini-1.5-flash`，因为免费且速度快)。
- **Prompt 逻辑**:
  对于每篇文章的内容，请 AI 执行以下任务并返回 JSON 格式：
  1. **Summary (中文)**: 用通俗易懂的中文总结文章的 3 个核心技术知识点。
  2. **Keywords (双语)**: 提取 2 个核心 IT 术语/概念，格式为 "英文术语: 中文解释"。
  3. **One-liner (英文)**: 生成一句话的英文总结，用于练习英语阅读。
  4. **Score**: 给文章的技术含金量打分 (1-5分)，便于我决定是否阅读原文。

### 2.3 数据存储 (Storage)
- **平台**: Notion。
- **操作**: 通过 Notion API 将处理后的数据插入到一个 Database 中。
- **Notion Database 字段设计 (请在代码中匹配这些字段)**:
  - `Title` (Title类型): 文章标题
  - `URL` (URL类型): 原文链接
  - `Summary` (Rich Text类型): AI 生成的中文总结 + 英文金句
  - `Keywords` (Multi-select 或 Text类型): 提取的术语
  - `Date` (Date类型): 运行日期
  - `Score` (Number类型): 推荐分数

### 2.4 自动化部署 (Automation)
- **平台**: GitHub Actions。
- **频率**: 每天 UTC 时间 00:00 (北京时间早上 08:00) 自动触发。
- **环境**: Ubuntu Latest, Python 3.9+。

## 5. Implementation Notes & Robustness
- 在 `main.py` 中实现 `worker_tech()` 与 `worker_lang()` 并且保证相互独立（异常捕获、单次失败不影响其他 worker）。
- 对 Gemini 返回做严格校验：若 JSON 无法解析或模型返回空文本，使用安全 fallback（简短本地模板文本）并记录警告日志。
- 对生成的 Language JSON 做 schema 校验，确保 `scenes` 长度为 3 且每个 `scene` 含 `quiz`。
- Notion 写入：使用 block-level API（如果可用）或按文本把 Quiz 放入 Toggle 文本字段（尽量还原 Heading/Toggle 结构）。
- 环境变量（必须通过 os.environ 读取）：
  - `GEMINI_API_KEY`, `NOTION_TOKEN`, `NOTION_DATABASE_ID`, `GEMINI_MODEL`（可选）
- 建议将 Tech 与 Language 的模型 key /配额分离（`GEMINI_API_KEY`, `LANG_GEMINI_KEY`）以避免配额冲突。

## 6. 技术栈要求
- **编程语言**: Python 3.9+
- **核心依赖库**:
  - `requests`: 用于 API 调用和网页请求
  - `beautifulsoup4`: 用于网页 HTML 解析和文本清洗
  - `google-generativeai`: 用于调用 Google Gemini API
  - `yfinance`: 用于股票数据获取（可选）
- **部署**: GitHub Actions, Notion API, Vercel（可选）
- **安全性**: 所有敏感信息通过环境变量获取，严禁硬编码

## 7. 输出文件清单 (Deliverables)

### 核心文件
1. **`main.py`**:
   - 包含 5 个独立 worker 函数
   - 包含完整的异常处理和重试机制
   - 清晰的注释和日志记录

2. **`app.py`** (可选):
   - Flask Web Dashboard 用于展示内容
   - 支持按 Category 过滤显示

3. **`requirements.txt`**:
   - 基础依赖（Flask, requests）
   - Vercel 部署专用（<250MB 限制）

4. **`worker-requirements.txt`**:
   - 完整依赖（包含 Gemini, yfinance 等）
   - GitHub Actions 运行专用

### 配置和文档
5. **`.github/workflows/daily_run.yml`**:
   - GitHub Actions 自动化配置
   - 每日 UTC 00:00 自动触发

6. **`README.md`**:
   - V5 Ultimate Edition 完整指南
   - 傻瓜式 Notion 数据库设置教程
   - Gemini API Key 获取步骤
   - GitHub Secrets 配置说明

7. **`DEVELOPMENT.md`**:
   - 开发者完整文档
   - 故障排查指南
   - 架构设计说明

## 8. 特别指令
- **健壮性**: 每个 worker 独立运行，单个失败不影响其他 worker
- **Token 管理**: 智能截断长文本，fallback 到本地摘要
- **多语平衡**: Language worker 确保三语内容量均衡
- **Notion 美化**: 使用 Rich Blocks、Emoji 和 Toggle Blocks
- **配额管理**: 支持多 Key 分离，避免单点故障