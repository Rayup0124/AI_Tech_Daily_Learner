# AI Tech Daily Learner V3 - 开发与运行流程文档

## 📋 目录
1. [项目概述](#项目概述)
2. [V3 架构](#v3-架构)
3. [文件结构](#文件结构)
4. [环境变量配置](#环境变量配置)
5. [本地运行](#本地运行)
6. [GitHub Actions 自动运行](#github-actions-自动运行)
7. [Web Dashboard 部署](#web-dashboard-部署)
8. [故障排查](#故障排查)
9. [常见操作速查](#常见操作速查)

---

## 项目概述

这是一个 **V3 一体化学习面板**，每天自动聚合 4 类内容：

| 分类 | 说明 | 数据来源 |
|------|------|----------|
| 💻 Tech Daily | 技术文章双语学习小抄 | Hacker News |
| 📈 Market Watch | 股票分析 + 情绪判断 | Yahoo Finance |
| 🖱️ Cursor Tips | Cursor 生产力技巧 | 本地种子 + Gemini 生成 |
| 💡 App Ideas | 独立开发灵感 + MVP 建议 | 本地种子 + Gemini 生成 |

**核心流程：**
```
数据来源 → Gemini AI 处理 → Notion 存储 → Web Dashboard 展示
```

---

## V3 架构

### 多 Worker 设计

`main.py` 包含 4 个独立 worker，互不干扰：

```
main.py
├── worker_tech()    → 抓 Hacker News → Gemini 摘要 → Notion (Category=Tech)
├── worker_stock()   → 抓 Yahoo Finance → Gemini 分析 → Notion (Category=Stock)
├── worker_cursor()  → 本地种子 → Gemini 生成技巧 → Notion (Category=Cursor)
└── worker_idea()    → 本地种子 → Gemini 生成灵感 → Notion (Category=Idea)
```

### 多 Key 支持

可为不同分类配置不同 Gemini API Key，避免互相抢额度：

| 环境变量 | 用途 | 优先级 |
|----------|------|--------|
| `GEMINI_API_KEY` | 默认 Key（Tech 用） | 必填 |
| `STOCK_GEMINI_KEY` | 股票分析专用 | 可选，fallback 到默认 |
| `CURSOR_GEMINI_KEY` | Cursor/Idea 专用 | 可选，fallback 到默认 |

### Web Dashboard

Flask 后端 + 纯前端 Tab 切换：

```
app.py (Flask)
├── /              → 渲染 index.html
└── /api/articles  → 返回 JSON（支持 ?category=Tech 过滤）

templates/index.html
├── Tab 切换（Tech/Stock/Cursor/Idea）
├── 每个 Tab 不同主题色
├── 已读/未读标记（localStorage，设备独立）
└── 每 5 分钟自动刷新
```

---

## 文件结构

```
AI_Tech_Daily_Learner/
├── main.py                   # 主程序（4 个 worker）
├── app.py                    # Flask Web 后端
├── cleanup_duplicates.py     # 清理 Notion 重复记录
│
├── requirements.txt          # Web 依赖（轻量，给 Vercel 用）
├── worker-requirements.txt   # Worker 依赖（完整，给 GitHub Actions 用）
│
├── templates/
│   └── index.html            # Web Dashboard 前端
│
├── .github/
│   └── workflows/
│       └── daily_run.yml     # GitHub Actions 配置
│
├── vercel.json               # Vercel 部署配置
│
├── README.md                 # 英文 README
├── README.zh-CN.md           # 中文 README
└── DEVELOPMENT.md            # 本文档
```

### 依赖文件说明

| 文件 | 用途 | 包含内容 |
|------|------|----------|
| `requirements.txt` | Vercel 部署 | `flask`, `requests`（轻量，<250MB） |
| `worker-requirements.txt` | GitHub Actions | `google-generativeai`, `yfinance`, `beautifulsoup4` 等完整依赖 |

---

## 环境变量配置

### 必填

| 变量 | 说明 | 获取方式 |
|------|------|----------|
| `GEMINI_API_KEY` | Google Gemini API Key | [Google AI Studio](https://aistudio.google.com/apikey) |
| `NOTION_TOKEN` | Notion Integration Token | Notion Settings → Integrations |
| `NOTION_DATABASE_ID` | Notion 数据库 ID | 数据库 URL 中的 32 位字符串 |

### 可选（推荐）

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `STOCK_GEMINI_KEY` | 股票分析专用 Key | 使用 `GEMINI_API_KEY` |
| `CURSOR_GEMINI_KEY` | Cursor/Idea 专用 Key | 使用 `GEMINI_API_KEY` |
| `GEMINI_MODEL` | Gemini 模型名称 | `gemini-1.5-flash` |
| `STOCK_CODES` | 股票代码（逗号分隔） | `1155.KL,5183.KL,1295.KL` |

### Windows PowerShell 设置示例

```powershell
# 必填
$env:GEMINI_API_KEY = "AIza..."
$env:NOTION_TOKEN = "ntn_..."
$env:NOTION_DATABASE_ID = "abc123..."

# 可选
$env:STOCK_GEMINI_KEY = "AIza..."
$env:CURSOR_GEMINI_KEY = "AIza..."
$env:STOCK_CODES = "1155.KL,5183.KL"
$env:GEMINI_MODEL = "gemini-flash-latest"
```

---

## 本地运行

### 1. 运行主程序（抓取 + AI + Notion）

```bash
# 激活虚拟环境
.\.venv\Scripts\Activate.ps1  # Windows
# source .venv/bin/activate   # macOS/Linux

# 安装 worker 依赖
pip install -r worker-requirements.txt

# 设置环境变量（见上方）

# 运行
python main.py
```

**输出示例：**
```
2025-12-18 12:00:00 [INFO] ===== Worker: Tech =====
2025-12-18 12:00:02 [INFO] Fetching top stories from Hacker News...
2025-12-18 12:00:10 [INFO] Successfully processed 'Some Article Title'
2025-12-18 12:00:15 [INFO] ===== Worker: Stock =====
2025-12-18 12:00:20 [INFO] Analyzing stock 1155.KL...
2025-12-18 12:00:30 [INFO] ===== Worker: Cursor =====
2025-12-18 12:00:35 [INFO] ===== Worker: Idea =====
2025-12-18 12:00:40 [INFO] All workers completed.
```

### 2. 运行 Web Dashboard

```bash
# 安装 web 依赖
pip install -r requirements.txt

# 设置 Notion 环境变量
$env:NOTION_TOKEN = "ntn_..."
$env:NOTION_DATABASE_ID = "abc123..."

# 运行
python app.py

# 访问 http://localhost:5000
```

### 3. 清理重复记录

```bash
python cleanup_duplicates.py
# 按提示输入 yes 确认删除
```

---

## GitHub Actions 自动运行

### 配置 Secrets

在 GitHub 仓库：`Settings → Secrets and variables → Actions`

**必填 Secrets：**
- `GEMINI_API_KEY`
- `NOTION_TOKEN`
- `NOTION_DATABASE_ID`

**可选 Secrets：**
- `STOCK_GEMINI_KEY`
- `CURSOR_GEMINI_KEY`
- `STOCK_CODES`
- `GEMINI_MODEL`

### 运行时间

- **自动运行**：每天 00:00 UTC（马来西亚/北京 08:00）
- **手动运行**：Actions → Daily AI Tech Digest → Run workflow

### 查看日志

1. 进入仓库 → **Actions** 标签页
2. 点击最新的 workflow run
3. 展开 "Run daily script" 查看详细日志

---

## Web Dashboard 部署

### Vercel 部署步骤

1. 访问 https://vercel.com，用 GitHub 登录
2. 点击 "New Project"，选择 `AI_Tech_Daily_Learner` 仓库
3. 在 "Environment Variables" 添加：
   - `NOTION_TOKEN`
   - `NOTION_DATABASE_ID`
4. 点击 "Deploy"

### 部署后

- 访问 Vercel 提供的网址（如 `https://ai-tech-daily-learner.vercel.app`）
- 代码 push 到 GitHub 后，Vercel 会自动重新部署

### Web 功能

| 功能 | 说明 |
|------|------|
| Tab 切换 | Tech / Stock / Cursor / Idea |
| 主题色 | 每个分类不同颜色 |
| 已读/未读 | localStorage 保存，设备独立 |
| 自动刷新 | 每 5 分钟 |
| 去重 | 后端按 URL 去重 |

---

## 故障排查

### 1. Gemini 相关

**问题：`404 models/gemini-1.5-flash is not found`**
```bash
# 设置正确的模型名称
$env:GEMINI_MODEL = "gemini-flash-latest"
```

**问题：`429 Quota exceeded`**
- 配置多 Key 分流
- 减少 `MAX_ARTICLES`（在 `main.py` 中）
- 等待配额重置（通常 1 分钟）

**问题：`finish_reason=MAX_TOKENS`**
- 已内置截断逻辑，通常不需处理
- 如仍出现，减小 `MAX_ARTICLE_CHARS`

### 2. Notion 相关

**问题：`Summary is not a property that exists`**
- 检查 Notion 数据库字段名是否完全匹配：
  - `Title`, `URL`, `Summary`, `Keywords`, `Date`, `Score`, `Category`, `Sentiment`

**问题：文章没写入 Notion**
- 检查 URL 是否已存在（去重生效）
- 检查 Integration 是否有编辑权限

### 3. Web Dashboard 相关

**问题：显示"暂无文章"**
- 检查 Vercel 环境变量是否设置
- 确认 Notion 数据库有对应 Category 的文章
- 旧文章没有 Category 会被当作 Tech 显示

**问题：Vercel 部署失败 (250MB 限制)**
- 确保 `requirements.txt` 只有 `flask` 和 `requests`
- 完整依赖放在 `worker-requirements.txt`

### 4. GitHub Actions 相关

**问题：Workflow 失败**
- 检查 Secrets 拼写是否正确
- 查看 Actions 日志定位具体错误

**问题：所有文章被跳过**
- 正常行为，表示文章已存在（去重生效）

---

## 常见操作速查

### 本地完整测试

```powershell
# 1. 激活环境
.\.venv\Scripts\Activate.ps1

# 2. 设置环境变量
$env:GEMINI_API_KEY = "..."
$env:NOTION_TOKEN = "..."
$env:NOTION_DATABASE_ID = "..."

# 3. 运行 worker
python main.py

# 4. 运行 web（另一个终端）
python app.py
# 访问 http://localhost:5000
```

### 推送代码

```bash
git add .
git commit -m "描述更改"
git push
```

### 手动触发 GitHub Actions

1. 进入仓库 → Actions
2. 选择 "Daily AI Tech Digest"
3. 点击 "Run workflow"

### Notion 数据库字段

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `Title` | Title | 标题 |
| `URL` | URL | 链接 |
| `Summary` | Rich Text | 中文要点 + 英文一句话 |
| `Keywords` | Multi-select | 双语关键词 |
| `Date` | Date | 日期 |
| `Score` | Number | 1–5 |
| `Category` | Select | Tech/Stock/Cursor/Idea |
| `Sentiment` | Select | Bullish 🟢 / Bearish 🔴 / Neutral ⚪ |

---

## 维护建议

1. **每周检查** GitHub Actions 运行状态
2. **监控** Gemini API 配额使用
3. **定期** 运行 `cleanup_duplicates.py` 清理重复
4. **更新** 依赖版本（`pip install --upgrade`）

---

**最后更新：** 2025-12-18
