<!-- 语言切换 -->
[English](README.md) | **中文**

# AI Tech Daily Learner - V3 一体化学习面板

这是一个 Python 自动化工具：每天聚合多维度情报数据（技术文章、股票分析、Cursor 技巧、独立开发灵感），用 Google Gemini 生成学习要点，并写入 Notion 数据库；同时提供一个可部署到 Vercel 的 Web Dashboard 用来浏览内容。

默认 GitHub Actions 会在 **每天 00:00 UTC** 自动运行（马来西亚/北京约 **08:00**）。

## 功能一览

### V3（精简版）— 仅保留 Tech Daily
- **💻 Tech Daily**：抓取 Hacker News 热门文章并生成双语学习小抄（中文要点 + 英文一句话）。为简化项目，其他模块（Market Watch / Cursor Tips / App Ideas / Language Matrix）已移除。

### AI 处理
- 使用 Google Gemini 生成：中文要点、双语关键词、英文一句话、1–5 分评分（仅用于 Tech 文章）。
- 项目已简化：仅保留 Tech worker。你可以通过 `GEMINI_MODEL` 覆盖默认模型以调整生成效果。

### Notion 存储
- 写入 Notion 数据库（自动去重：按 URL 不重复写入）
- 请在数据库中保留 `Category` 字段并确保包含 `Tech` 选项。

### Web Dashboard
- Tab 切换（Tech/Stock/Cursor/Idea）+ 每个分类不同主题色
- 已读/未读标记（仅保存本机浏览器；每个设备独立）
- 每 5 分钟自动刷新

## 1. 环境需求

- Python 3.9+
- Notion 账号 + 一个数据库
- Google Gemini API Key（可选多 Key）
- GitHub（可选，用于每日自动运行）

## 2. 本地运行（一步一步）

1. **克隆仓库**

```bash
git clone <your-repo-url>
cd AI_Tech_Daily_Learner
```

2. **创建并激活虚拟环境（推荐）**

Windows PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

3. **安装依赖（运行 `main.py` 用）**

```bash
pip install -r worker-requirements.txt
```

4. **设置环境变量**

必填：
- `GEMINI_API_KEY`
- `NOTION_TOKEN`
- `NOTION_DATABASE_ID`

可选：
- `GEMINI_MODEL`：例如 `gemini-1.5-flash`（可覆盖为 `gemini-1.5-flash-latest`）

5. **运行**

```bash
python main.py
```

## 3. Notion 数据库字段（必须匹配）

请在 Notion 新建一个数据库（表格视图），并确保字段名/类型如下：

| 字段名 | 类型 | 说明 |
|---|---|---|
| `Title` | Title | 标题 |
| `URL` | URL | 原文链接 / 股票链接 / 伪链接（Cursor/Idea） |
| `Summary` | Rich Text | 中文要点 + 英文一句话 |
| `Keywords` | Multi-select | 双语关键词（最多 2 个） |
| `Date` | Date | 日期 |
| `Score` | Number | 1–5 |
| `Category` | Select | `Tech` / `Stock` / `Cursor` / `Idea` |
| `Sentiment` | Select | 仅股票：`Bullish 🟢` / `Bearish 🔴` / `Neutral ⚪` |

## 4. GitHub Actions 自动运行

1. 打开仓库：`Settings → Secrets and variables → Actions`
2. 添加 secrets（至少三项）：
   - `GEMINI_API_KEY`
   - `NOTION_TOKEN`
   - `NOTION_DATABASE_ID`
3. 可选：
   - `GEMINI_MODEL`

工作流文件：`.github/workflows/daily_run.yml`  
默认每天 UTC 00:00 执行；工作流会通过 `RUN_ONLY: "Tech"` 保证自动运行时只执行 Tech worker。

## 5. 部署 Web Dashboard（Vercel）

Web 端只需要轻量依赖（见 `requirements.txt`）。部署后主要用于浏览 `Tech Daily` 内容。

---


