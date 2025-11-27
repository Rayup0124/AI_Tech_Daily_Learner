# AI Tech Daily Learner

Python automation that grabs the latest Hacker News highlights, asks Google Gemini to produce bilingual learning nuggets, and sends the result to a Notion database. A GitHub Actions workflow runs everything every day at 00:00 UTC (08:00 Beijing time).

## Features
- Pulls the top 5 Hacker News stories and scrapes each article body.
- Uses Gemini `gemini-1.5-flash` to create Chinese key points, bilingual keywords, an English one-liner, and a 1–5 tech score.
- Pushes the content into Notion with clean formatting and emoji accents.
- Resilient pipeline: skips items that fail to download, sanitize, summarize, or upload.
- **Web Dashboard**: View all articles in a beautiful web interface with read/unread tracking.

## 🌐 View Articles Online

Visit the live web dashboard to browse all articles:

**👉 [https://ai-tech-daily-learner.vercel.app/](https://ai-tech-daily-learner.vercel.app/)**

Features:
- Clean, responsive card-based layout
- Mark articles as read/unread (saved in browser)
- Auto-refreshes every 5 minutes
- Shows article summaries, keywords, scores, and dates

## 1. Prerequisites
- Python 3.9+
- Notion account with access to create a database.
- Google Gemini API key.
- GitHub account (optional for automation).

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
   pip install -r requirements.txt
   ```
4. **Set required environment variables**
   ```
   GEMINI_API_KEY=<your_gemini_key>
   NOTION_TOKEN=<secret_notion_integration_token>
   NOTION_DATABASE_ID=<target_database_id>
   ```
   You can place them in your shell profile, a `.env` loader, or directly in the GitHub Secrets (see below).
5. **Run manually**
   ```bash
   python main.py
   ```

## 3. Create the Notion Database (Foolproof Guide)
1. Open Notion → create a new **Database** (table view works best).
2. Click the `...` menu → **Add connections** → search and add your integration (create one via [Notion Integrations](https://www.notion.so/my-integrations) if you haven't already). Copy the **Internal Integration Token**; this is `NOTION_TOKEN`.
3. Invite the integration to the database (Share → select the integration → give **Can edit** permission).
4. Adjust column names/types to match exactly:

| Property Name | Type        | Notes                                                   |
|---------------|-------------|---------------------------------------------------------|
| `Title`       | Title       | Default primary column                                  |
| `URL`         | URL         | Stores the Hacker News article link                     |
| `Summary`     | Rich Text   | Includes Chinese bullets + English one-liner with emoji |
| `Keywords`    | Multi-select| Two bilingual keywords per article                      |
| `Date`        | Date        | Automatically set to run day (UTC)                      |
| `Score`       | Number      | 1–5 tech value score                                    |

5. Copy the database ID from the URL (the 32-character string after `/` in the page URL) and store it as `NOTION_DATABASE_ID`.

## 4. Get a Google Gemini API Key
1. Visit [Google AI Studio](https://aistudio.google.com/).
2. Sign in and open the **API Keys** tab.
3. Click **Create API key**, select a project (auto-created if you have none).
4. Copy the key and save it as `GEMINI_API_KEY`.

## 5. Configure GitHub Secrets
If you host this project on GitHub to leverage the daily workflow:
1. Go to your repo → **Settings** → **Secrets and variables** → **Actions**.
2. Add the following secrets (names must match):
   - `GEMINI_API_KEY`
   - `NOTION_TOKEN`
   - `NOTION_DATABASE_ID`
3. Optionally override the Gemini model by adding `GEMINI_MODEL` (defaults to `gemini-1.5-flash`).

## 6. GitHub Actions Workflow
- The workflow file lives at `.github/workflows/daily_run.yml`.
- Schedule: `0 0 * * *` (00:00 UTC daily).
- Runner: `ubuntu-latest`.
- Steps: checkout → set up Python → install deps → run `python main.py`.
- The workflow automatically uses the secrets configured above.

## 7. Troubleshooting & Tips
- **Missing env vars**: the script stops immediately with a clear log message.
- **Article scrape fails**: the script logs the error and moves to the next story.
- **Gemini JSON errors**: ensure the model has access (some regions require a VPN) and retry; intermittent hiccups are common.
- **Notion rejects request**: confirm the integration has edit access and the property names match exactly.
- **Local testing without automation**: run `python main.py` anytime—the job is idempotent because it simply appends a new row per run.

Enjoy your daily bilingual tech digest! 🚀

