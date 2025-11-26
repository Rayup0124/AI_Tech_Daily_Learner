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

## 3. 技术栈要求
- **编程语言**: Python 3.
- **依赖库**:
  - `requests`: 用于 API 调用和网页请求。
  - `beautifulsoup4`: 用于网页 HTML 解析和文本清洗。
  - `google-generativeai`: 用于调用 Google Gemini API。
  - `apscheduler` (可选，如果脚本内需要重试机制) 或直接用简单的循环。
- **安全性**: 所有敏感 Key (`GEMINI_API_KEY`, `NOTION_TOKEN`, `NOTION_DATABASE_ID`) 必须通过 `os.environ` 读取，严禁硬编码在代码中。

## 4. 输出文件清单 (Deliverables)
请生成以下所有文件，并保持目录结构整洁：

1. **`main.py`**: 
   - 包含主程序逻辑。
   - 包含简单的重试机制（如果爬虫失败，跳过该文章）。
   - 包含清晰的注释（解释每一段在做什么）。
2. **`requirements.txt`**: 
   - 列出所有需要的 Python 库。
3. **`.github/workflows/daily_run.yml`**: 
   - GitHub Actions 的配置文件。
4. **`README.md`**: 
   - **非常重要**：请写一份详细的“傻瓜式”指南。
   - 教我如何在 Notion 创建 Database（列名需要和代码里对应）。
   - 教我如何获取 Google Gemini API Key。
   - 教我如何在 GitHub 仓库设置 Secrets。

## 5. 特别指令
- 请确保代码足够健壮，如果某篇文章内容太长超过 Token 限制，或者无法抓取，代码应该 catch 异常并继续处理下一篇，而不是直接崩溃。
- Notion 的内容排版要美观一点（例如使用 Emoji）。