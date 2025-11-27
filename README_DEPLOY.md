# 部署展示网页到 Vercel

## 方法 1: 使用 Vercel（推荐，最简单）

### 步骤：

1. **安装 Vercel CLI**（如果还没安装）：
   ```bash
   npm install -g vercel
   ```

2. **登录 Vercel**：
   ```bash
   vercel login
   ```

3. **在项目目录下部署**：
   ```bash
   cd D:\src\project\AI_Tech_Daily_Learner
   vercel
   ```

4. **设置环境变量**：
   - 在 Vercel 项目设置中添加：
     - `NOTION_TOKEN` = 你的 Notion Integration Token
     - `NOTION_DATABASE_ID` = 你的数据库 ID

5. **访问你的网站**：
   - 部署完成后，Vercel 会给你一个网址，例如：`https://ai-tech-daily-learner.vercel.app`
   - 每天打开这个网址就能看到最新文章！

---

## 方法 2: 使用 Netlify

1. 在 Netlify 创建新项目，连接你的 GitHub 仓库
2. 构建命令：留空（Netlify 会自动检测）
3. 发布目录：留空
4. 环境变量：
   - `NOTION_TOKEN`
   - `NOTION_DATABASE_ID`
5. 部署后访问 Netlify 提供的网址

---

## 方法 3: 本地运行（测试用）

```bash
# 设置环境变量
$env:NOTION_TOKEN = "你的token"
$env:NOTION_DATABASE_ID = "你的数据库ID"

# 运行
python app.py

# 打开浏览器访问 http://localhost:5000
```

---

## 注意事项

- 确保 `NOTION_TOKEN` 和 `NOTION_DATABASE_ID` 已正确设置
- 网页会自动每 5 分钟刷新一次数据
- 如果部署后看不到数据，检查 Vercel/Netlify 的环境变量设置

