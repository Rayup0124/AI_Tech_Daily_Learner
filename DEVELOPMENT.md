# AI Tech Daily Learner - 开发与运行流程文档

## 📋 目录
1. [项目概述](#项目概述)
2. [开发过程](#开发过程)
3. [运行流程](#运行流程)
4. [本地运行](#本地运行)
5. [GitHub Actions 自动运行](#github-actions-自动运行)
6. [Web 展示页面](#web-展示页面)
7. [故障排查](#故障排查)

---

## 项目概述

这是一个全自动化的技术学习日报系统，每天自动：
1. 从 Hacker News 抓取 Top 5 文章
2. 使用 Google Gemini AI 生成双语摘要
3. 推送到 Notion 数据库
4. 在网页上展示所有文章

---

## 开发过程

### 1. 项目初始化

```bash
# 克隆仓库
git clone https://github.com/Rayup0124/AI_Tech_Daily_Learner.git
cd AI_Tech_Daily_Learner

# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 核心文件说明

- **`main.py`**: 主程序，负责抓取、AI 处理、推送到 Notion
- **`app.py`**: Flask Web 应用，提供网页展示和 API
- **`templates/index.html`**: 前端展示页面
- **`.github/workflows/daily_run.yml`**: GitHub Actions 自动运行配置
- **`cleanup_duplicates.py`**: 清理 Notion 重复记录的脚本

### 3. 环境变量配置

需要配置以下环境变量：

```bash
# Windows PowerShell
$env:GEMINI_API_KEY = "你的Gemini API Key"
$env:NOTION_TOKEN = "你的Notion Integration Token"
$env:NOTION_DATABASE_ID = "你的Notion数据库ID"
$env:GEMINI_MODEL = "gemini-flash-latest"  # 可选，默认 gemini-1.5-flash

# macOS/Linux
export GEMINI_API_KEY="你的Gemini API Key"
export NOTION_TOKEN="你的Notion Integration Token"
export NOTION_DATABASE_ID="你的Notion数据库ID"
export GEMINI_MODEL="gemini-flash-latest"
```

---

## 运行流程

### 整体流程图

```
Hacker News API
    ↓
抓取 Top 5 文章
    ↓
提取文章正文（BeautifulSoup）
    ↓
Google Gemini AI 处理
    ├─ 生成中文摘要（3个要点）
    ├─ 提取双语关键词
    ├─ 生成英文 one-liner
    └─ 评分（1-5分）
    ↓
检查 URL 是否已存在（去重）
    ↓
推送到 Notion 数据库
    ↓
网页自动展示（Vercel）
```

---

## 本地运行

### 1. 运行主程序（抓取 + AI + 推送）

```bash
# 确保虚拟环境已激活
.\.venv\Scripts\Activate.ps1  # Windows
# source .venv/bin/activate   # macOS/Linux

# 设置环境变量
$env:GEMINI_API_KEY = "你的key"
$env:NOTION_TOKEN = "你的token"
$env:NOTION_DATABASE_ID = "你的数据库ID"

# 运行
python main.py
```

**输出示例：**
```
2025-11-26 12:00:00 [INFO] Fetching top stories from Hacker News...
2025-11-26 12:00:02 [INFO] Fetching article body (https://example.com/...)
2025-11-26 12:00:05 [INFO] Successfully processed 'Article Title'
2025-11-26 12:00:10 [INFO] Processing completed. Total articles pushed: 3
```

### 2. 运行 Web 展示页面

```bash
# 设置环境变量（只需要 Notion 相关的）
$env:NOTION_TOKEN = "你的token"
$env:NOTION_DATABASE_ID = "你的数据库ID"

# 运行 Flask 应用
python app.py
```

**访问：**
- 打开浏览器访问 `http://localhost:5000`
- API 端点：`http://localhost:5000/api/articles`

### 3. 清理重复记录（一次性操作）

```bash
# 设置环境变量
$env:NOTION_TOKEN = "你的token"
$env:NOTION_DATABASE_ID = "你的数据库ID"

# 运行清理脚本
python cleanup_duplicates.py
```

**交互流程：**
1. 脚本会列出所有重复的文章
2. 询问是否确认删除：`Proceed with deletion? (yes/no):`
3. 输入 `yes` 后自动删除重复项（保留最新的）

---

## GitHub Actions 自动运行

### 1. 配置 Secrets

在 GitHub 仓库中设置 Secrets：
- 进入仓库 → **Settings** → **Secrets and variables** → **Actions**
- 添加以下 Secrets：
  - `GEMINI_API_KEY`
  - `NOTION_TOKEN`
  - `NOTION_DATABASE_ID`
  - `GEMINI_MODEL`（可选）

### 2. 工作流配置

工作流文件：`.github/workflows/daily_run.yml`

**运行时间：**
- 每天 00:00 UTC（北京时间 08:00）
- 也可以手动触发：Actions → Daily AI Tech Digest → Run workflow

**执行步骤：**
1. Checkout 代码
2. 设置 Python 3.10
3. 安装依赖（`pip install -r requirements.txt`）
4. 运行 `python main.py`（自动使用 Secrets 中的环境变量）

### 3. 查看运行日志

- 进入仓库 → **Actions** 标签页
- 点击最新的 workflow run
- 展开 "Run daily script" 查看详细日志

---

## Web 展示页面

### 1. 部署到 Vercel

**方法 A：通过 Vercel 网站**
1. 访问 https://vercel.com，用 GitHub 登录
2. 点击 "New Project"，选择 `AI_Tech_Daily_Learner` 仓库
3. 在 "Environment Variables" 添加：
   - `NOTION_TOKEN`
   - `NOTION_DATABASE_ID`
4. 点击 "Deploy"

**方法 B：通过命令行**
```bash
npm install -g vercel
vercel login
vercel
# 按提示操作，设置环境变量
```

### 2. 访问网页

部署完成后，Vercel 会提供一个网址，例如：
- `https://ai-tech-daily-learner.vercel.app`

**功能：**
- 自动显示所有文章（按日期倒序）
- 自动去重（每个 URL 只显示最新一条）
- 已读/未读标记（保存在浏览器本地）
- 每 5 分钟自动刷新数据

### 3. 本地测试 Web 应用

```bash
# 设置环境变量
$env:NOTION_TOKEN = "你的token"
$env:NOTION_DATABASE_ID = "你的数据库ID"

# 运行
python app.py

# 访问 http://localhost:5000
```

---

## 故障排查

### 1. 主程序运行失败

**问题：`ModuleNotFoundError: No module named 'google'`**
```bash
# 解决：安装依赖
pip install -r requirements.txt
```

**问题：`API key not valid`**
- 检查 `GEMINI_API_KEY` 是否正确
- 确认 API Key 对应的项目已启用 Generative Language API
- 尝试重新生成新的 API Key

**问题：`finish_reason=MAX_TOKENS`**
- 文章太长，已自动截断到 2000 字符
- 如果仍出现，可以：
  - 进一步降低 `MAX_ARTICLE_CHARS`（在 `main.py` 中）
  - 更换模型为 `gemini-pro-latest`

**问题：`Failed to send data to Notion`**
- 检查 Notion 数据库列名是否匹配：`Title`, `URL`, `Summary`, `Keywords`, `Date`, `Score`
- 确认 Integration 有编辑权限
- 检查 `NOTION_TOKEN` 和 `NOTION_DATABASE_ID` 是否正确

### 2. Web 应用无法访问

**问题：网页显示"加载失败"**
- 检查 Vercel 环境变量是否设置正确
- 查看 Vercel 部署日志：Vercel Dashboard → Deployments → 查看日志

**问题：显示重复文章**
- 网页端已自动去重，刷新页面即可
- 如果仍有问题，检查 `app.py` 中的去重逻辑

### 3. GitHub Actions 失败

**问题：Workflow 运行失败**
- 检查 Secrets 是否设置正确
- 查看 Actions 日志，找到具体错误信息
- 常见问题：
  - Secrets 名称拼写错误
  - API Key 无效
  - Notion 权限问题

**问题：所有文章都被跳过**
- 可能是 URL 已存在（去重功能生效）
- 检查日志中的 "Skipping ... - URL already exists" 信息
- 这是正常行为，表示文章已存在

---

## 开发技巧

### 1. 调试模式

在 `main.py` 中添加更详细的日志：

```python
logging.basicConfig(
    level=logging.DEBUG,  # 改为 DEBUG 查看更详细日志
    format="%(asctime)s [%(levelname)s] %(message)s",
)
```

### 2. 测试单个文章

修改 `main.py` 中的 `MAX_ARTICLES`：

```python
MAX_ARTICLES = 1  # 只处理 1 篇文章，便于测试
```

### 3. 查看 Notion 数据

- 直接在 Notion 数据库页面查看
- 或通过 API：`python app.py` 然后访问 `http://localhost:5000/api/articles`

### 4. 清理测试数据

如果测试时产生了不需要的数据：
- 在 Notion 中手动删除
- 或运行 `cleanup_duplicates.py` 清理重复项

---

## 项目结构

```
AI_Tech_Daily_Learner/
├── main.py                 # 主程序（抓取 + AI + Notion）
├── app.py                  # Web 应用（Flask）
├── cleanup_duplicates.py   # 清理重复记录脚本
├── requirements.txt        # Python 依赖
├── README.md               # 项目说明
├── DEVELOPMENT.md          # 本文档
├── templates/
│   └── index.html         # 前端页面
├── .github/
│   └── workflows/
│       └── daily_run.yml   # GitHub Actions 配置
└── vercel.json            # Vercel 部署配置
```

---

## 常见操作速查

### 本地运行完整流程
```bash
# 1. 激活虚拟环境
.\.venv\Scripts\Activate.ps1

# 2. 设置环境变量
$env:GEMINI_API_KEY = "..."
$env:NOTION_TOKEN = "..."
$env:NOTION_DATABASE_ID = "..."

# 3. 运行主程序
python main.py

# 4. 运行 Web 应用（另一个终端）
python app.py
# 访问 http://localhost:5000
```

### 推送代码到 GitHub
```bash
git add .
git commit -m "描述你的更改"
git push
```

### 更新 Vercel 部署
代码推送到 GitHub 后，Vercel 会自动重新部署（通常 1-2 分钟）

---

## 维护建议

1. **定期检查**：
   - 每周查看一次 GitHub Actions 运行状态
   - 确认 Notion 数据库正常更新

2. **监控日志**：
   - 如果连续多天失败，检查 API Key 是否过期
   - 关注 Gemini API 配额使用情况

3. **清理数据**：
   - 如果 Notion 数据太多，可以定期运行 `cleanup_duplicates.py`
   - 或手动删除旧数据

---

## 技术支持

如果遇到问题：
1. 查看本文档的故障排查部分
2. 检查 GitHub Actions 日志
3. 查看 Vercel 部署日志
4. 检查环境变量配置

---

**最后更新：** 2025-11-27

