<!-- Language Switch -->
**English** | [中文](README.zh-CN.md)

# AI Tech Daily Learner - V3 All-in-One Dashboard

Python automation that aggregates multi-dimensional intelligence data (Tech articles, Stock analysis, Cursor tips, Indie ideas), processes them with Google Gemini AI, and sends results to a Notion database. A GitHub Actions workflow runs everything daily at 00:00 UTC (08:00 Beijing time).

## Features

### V3 Multi-Dimensional Data
- **💻 Tech Daily**: Pulls top 5 Hacker News stories, summarizes with bilingual learning nuggets
- **📈 Market Watch**: Analyzes Malaysian stocks (default: Maybank, Petronas Chem, CIMB) with AI-powered sentiment analysis
- **🖱️ Cursor Tips**: Generates daily Cursor productivity tips (no Reddit required)
- **💡 App Ideas**: Generates daily indie-dev inspiration + MVP suggestions (no Reddit required)

### AI Processing
- Uses Google Gemini (`gemini-1.5-flash` by default) to create Chinese summaries, bilingual keywords, English one-liners, and 1–5 scores
- **Multi-Key Support**: Use separate Gemini API keys for different categories to avoid quota conflicts
- Category-specific AI prompts (financial analyst for stocks, senior developer for Cursor, product manager for ideas)

### Data Storage
- Pushes all content into Notion with clean formatting and emoji accents
- Automatic deduplication by URL
- Category and Sentiment (for stocks) tagging

### Web Dashboard
- **👉 [Live Dashboard](https://ai-tech-daily-learner.vercel.app/)**
- Tab-based navigation with category-specific theme colors
- Mark articles as read/unread (saved per device in browser)
- Auto-refreshes every 5 minutes
- Responsive design for mobile and desktop

## 1. Prerequisites
- Python 3.9+
- Notion account with access to create a database
- Google Gemini API key(s) (can use multiple keys for different categories)
- GitHub account (optional for automation)

## 2. Local Setup (Step-by-step)

1. **Clone the repo**
   ```bash
   git clone <your-fork-url>
   cd AI_Tech_Daily_Learner
   ```

2. **Create & activate a virtual environment (optional but recommended)**
   **Windows PowerShell**
   ```powershell
   python -m venv .venv        # create once
   .\.venv\Scripts\Activate.ps1 # activate each session
   ```
   **macOS/Linux**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```
   To exit later, run `deactivate`.

3. **Install dependencies**
   ```bash
   # Worker (main.py) dependencies
   pip install -r worker-requirements.txt
   ```

4. **Set required environment variables**
   ```bash
   # Required
   GEMINI_API_KEY=<your_gemini_key>              # For Tech (default)
   NOTION_TOKEN=<secret_notion_integration_token>
   NOTION_DATABASE_ID=<target_database_id>

   # Optional (for multi-key setup - recommended)
   STOCK_GEMINI_KEY=<stock_gemini_key>           # For Stock analysis
   CURSOR_GEMINI_KEY=<cursor_gemini_key>          # For Cursor and Idea

   # Optional (for stock codes)
   STOCK_CODES=1155.KL,5183.KL,1023.KL           # Default: Maybank, Petronas Chem, CIMB

   # Optional (for Gemini model)
   GEMINI_MODEL=gemini-1.5-flash                 # Default model
   ```

   You can place them in your shell profile, a `.env` loader, or directly in GitHub Secrets (see below).

5. **Run manually**
   ```bash
   python main.py
   ```

## 3. Create the Notion Database (V3 Requirements)

1. Open Notion → create a new **Database** (table view works best).

2. Click the `...` menu → **Add connections** → search and add your integration (create one via [Notion Integrations](https://www.notion.so/my-integrations) if you haven't already). Copy the **Internal Integration Token**; this is `NOTION_TOKEN`.

3. Invite the integration to the database (Share → select the integration → give **Can edit** permission).

4. Adjust column names/types to match exactly:

| Property Name | Type        | Notes                                                   |
|---------------|-------------|---------------------------------------------------------|
| `Title`       | Title       | Default primary column                                  |
| `URL`         | URL         | Stores the article/stock link                           |
| `Summary`     | Rich Text   | Includes Chinese bullets + English one-liner with emoji |
| `Keywords`    | Multi-select| Two bilingual keywords per article                      |
| `Date`        | Date        | Automatically set to run day (UTC)                      |
| `Score`       | Number      | 1–5 value score                                         |
| `Category`    | Select      | **NEW**: Options: `Tech`, `Stock`, `Cursor`, `Idea`     |
| `Sentiment`   | Select      | **NEW**: Options: `Bullish 🟢`, `Bearish 🔴`, `Neutral ⚪` (only for Stock) |

5. Copy the database ID from the URL (the 32-character string after `/` in the page URL) and store it as `NOTION_DATABASE_ID`.

## 4. Get Google Gemini API Key(s)

1. Visit [Google AI Studio](https://aistudio.google.com/).
2. Sign in and open the **API Keys** tab.
3. Click **Create API key**, select a project (auto-created if you have none).
4. Copy the key and save it as `GEMINI_API_KEY`.

**For Multi-Key Setup (Recommended):**
- Create separate API keys for different categories to avoid quota conflicts
- Set `STOCK_GEMINI_KEY` for stock analysis
- Set `CURSOR_GEMINI_KEY` for Cursor and Idea workers
- If a category-specific key is not set, it will fall back to `GEMINI_API_KEY`

## 5. Get Reddit API Credentials (Optional)

**Note:** Reddit is no longer required. Cursor Tips and App Ideas are generated from local seed themes + Gemini.
You can ignore this section.

## 6. Configure GitHub Secrets

If you host this project on GitHub to leverage the daily workflow:

1. Go to your repo → **Settings** → **Secrets and variables** → **Actions**.
2. Add the following secrets (names must match):

   **Required:**
   - `GEMINI_API_KEY`
   - `NOTION_TOKEN`
   - `NOTION_DATABASE_ID`

   **Optional (for multi-key setup):**
   - `STOCK_GEMINI_KEY`
   - `CURSOR_GEMINI_KEY`

   **Optional (for customization):**
   - `GEMINI_MODEL` (defaults to `gemini-1.5-flash`)
   - `STOCK_CODES` (comma-separated, defaults to `1155.KL,5183.KL,1023.KL`)

## 7. GitHub Actions Workflow

- The workflow file lives at `.github/workflows/daily_run.yml`.
- Schedule: `0 0 * * *` (00:00 UTC daily).
- Runner: `ubuntu-latest`.
- Steps: checkout → set up Python → install deps (`worker-requirements.txt`) → run `python main.py`.
- The workflow automatically uses the secrets configured above.

## 8. Workers Overview

### Worker 1: Tech News
- **Source**: Hacker News Top Stories
- **Category**: `Tech`
- **Key**: `GEMINI_API_KEY`
- Processes top 5 stories daily

### Worker 2: Stock Analysis
- **Source**: Yahoo Finance (via `yfinance`)
- **Category**: `Stock`
- **Key**: `STOCK_GEMINI_KEY` (falls back to `GEMINI_API_KEY`)
- **Default Stocks**: `1155.KL` (Maybank), `5183.KL` (Petronas Chem), `1023.KL` (CIMB)
- **Output**: Includes `Sentiment` (Bullish 🟢 / Bearish 🔴 / Neutral ⚪)

### Worker 3: Cursor Tips
- **Source**: Local seed themes + Gemini (no external API)
- **Category**: `Cursor`
- **Key**: `CURSOR_GEMINI_KEY` (falls back to `GEMINI_API_KEY`)
- **Output**: 1–2 tips per run (rotates by date)

### Worker 4: Indie Ideas
- **Source**: Local seed themes + Gemini (no external API)
- **Category**: `Idea`
- **Key**: `CURSOR_GEMINI_KEY` (falls back to `GEMINI_API_KEY`)
- **Output**: Includes MVP tech stack recommendation in one-liner

## 9. Troubleshooting & Tips

- **Missing env vars**: Workers without required keys will be skipped with a warning.
- **Article scrape fails**: The script logs the error and moves to the next item.
- **Gemini JSON errors**: Ensure the model has access (some regions require a VPN) and retry; intermittent hiccups are common.
- **Notion rejects request**: Confirm the integration has edit access and the property names match exactly (especially `Category` and `Sentiment`).
- **Quota exceeded (429)**: Reduce the number of items per run or switch to a lighter model (e.g. `gemini-flash-latest`).
- **Stock data unavailable**: Some stocks may not have data available; the worker will skip them.
- **Local testing without automation**: Run `python main.py` anytime—the job is idempotent because it checks for duplicate URLs before pushing.

## 10. Web Dashboard Features

- **Tab Navigation**: Switch between Tech, Stock, Cursor, and Idea categories
- **Theme Colors**: Each category has its own color scheme
  - 💻 Tech: Blue/Purple gradient
  - 📈 Stock: Green gradient
  - 🖱️ Cursor: Purple/Pink gradient
  - 💡 Idea: Yellow/Orange gradient
- **Category-Specific Styling**:
  - Stock cards show sentiment badges (🟢/🔴/⚪)
  - Cursor cards use monospace font
  - Idea cards highlight MVP suggestions
- **Read/Unread Tracking**: Per-device storage in browser localStorage

Enjoy your daily multi-dimensional intelligence digest! 🚀
