"""V3 All-in-One Dashboard: Multi-dimensional data aggregation platform."""
import datetime as dt
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import google.generativeai as genai
from google.generativeai.types import GenerationConfig
import requests
from bs4 import BeautifulSoup
import yfinance as yf
import praw
import feedparser

# Hacker News API
HN_TOP_STORIES_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
# 为了节省 Gemini 免费额度，测试阶段只处理较少的文章数量
MAX_ARTICLES = 2  # 原本是 5，需要时你可以再调大
MAX_ARTICLE_CHARS = 2000

# Notion API
NOTION_API_URL = "https://api.notion.com/v1/pages"
NOTION_QUERY_URL = "https://api.notion.com/v1/databases/{database_id}/query"
NOTION_VERSION = "2022-06-28"

# Gemini Model
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

# Stock codes (default Malaysia stocks)
# 为了避免一次性触发太多 Gemini 调用，默认只分析一只股票；
# 你可以在环境变量 STOCK_CODES 或这里自行增加。
DEFAULT_STOCK_CODES = ["1155.KL"]

# Reddit subreddits
CURSOR_SUBREDDITS = ["cursor", "vscode", "programming"]
IDEA_SUBREDDITS = ["AppIdeas", "SideProject"]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)


@dataclass
class ArticlePayload:
    title: str
    url: str
    summary_points: List[str]
    keywords: List[Dict[str, str]]
    one_liner: str
    score: int
    category: str  # Tech, Stock, Cursor, Idea
    sentiment: Optional[str] = None  # Bullish 🟢, Bearish 🔴, Neutral ⚪ (only for Stock)


class ConfigurationError(ValueError):
    """Raised when required environment variables are missing."""


def require_env_var(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ConfigurationError(f"Environment variable '{name}' is required.")
    return value


def get_gemini_key(category: str) -> str:
    """Get the appropriate Gemini API key for the category."""
    if category == "Stock":
        key = os.getenv("STOCK_GEMINI_KEY") or os.getenv("GEMINI_API_KEY")
    elif category in ("Cursor", "Idea"):
        key = os.getenv("CURSOR_GEMINI_KEY") or os.getenv("GEMINI_API_KEY")
    else:  # Tech (default)
        key = os.getenv("GEMINI_API_KEY")
    
    if not key:
        raise ConfigurationError(f"No Gemini API key found for category '{category}'")
    return key


def init_gemini(model_name: str, api_key: str) -> genai.GenerativeModel:
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(model_name)


def extract_response_text(response: Any) -> str:
    """Extract text from Gemini response, handling various response formats."""
    text_attr: Optional[str] = None
    try:
        text_attr = getattr(response, "text", None)
    except ValueError:
        text_attr = None
    if isinstance(text_attr, str) and text_attr.strip():
        return text_attr.strip()

    collected: List[str] = []
    candidates = getattr(response, "candidates", []) or []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        if not content:
            continue
        for part in getattr(content, "parts", []) or []:
            part_text = getattr(part, "text", None)
            if isinstance(part_text, str) and part_text.strip():
                collected.append(part_text.strip())

    if collected:
        return "\n".join(collected)

    finish_reasons = {
        str(getattr(candidate, "finish_reason"))
        for candidate in candidates
        if getattr(candidate, "finish_reason", None) is not None
    }
    reasons_msg = ", ".join(sorted(finish_reasons)) or "unknown"
    raise RuntimeError(f"Gemini returned no textual parts (finish_reason={reasons_msg}).")


def extract_json(raw_text: str) -> Dict[str, Any]:
    """Extract JSON from raw text, handling markdown fences."""
    raw_text = raw_text.strip()
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        start = raw_text.find("{")
        end = raw_text.rfind("}")
        if start != -1 and end != -1:
            return json.loads(raw_text[start : end + 1])
        raise


def check_url_exists(notion_token: str, database_id: str, url: str) -> bool:
    """Check if an article with the same URL already exists in Notion."""
    headers = {
        "Authorization": f"Bearer {notion_token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }

    data = {
        "filter": {
            "property": "URL",
            "url": {
                "equals": url,
            },
        },
        "page_size": 1,
    }

    try:
        response = requests.post(
            NOTION_QUERY_URL.format(database_id=database_id),
            headers=headers,
            json=data,
            timeout=10,
        )
        if response.status_code == 200:
            results = response.json().get("results", [])
            return len(results) > 0
    except Exception as err:
        logging.warning("Failed to check URL existence: %s", err)
    return False


def push_to_notion(
    notion_token: str,
    database_id: str,
    payload: ArticlePayload,
) -> None:
    """Push article payload to Notion database."""
    if check_url_exists(notion_token, database_id, payload.url):
        logging.info("Skipping '%s' - URL already exists in database", payload.title)
        return

    headers = {
        "Authorization": f"Bearer {notion_token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }

    summary_block = build_summary_block(payload.summary_points, payload.one_liner)
    keywords_select = []
    for keyword in payload.keywords:
        keyword_name = build_keyword_name(keyword)
        if keyword_name:
            keywords_select.append({"name": keyword_name})

    properties = {
        "Title": {
            "title": [{"text": {"content": payload.title}}],
        },
        "URL": {
            "url": payload.url,
        },
        "Summary": {
            "rich_text": [{"text": {"content": summary_block}}],
        },
        "Keywords": {
            "multi_select": keywords_select,
        },
        "Date": {
            "date": {"start": dt.datetime.utcnow().date().isoformat()},
        },
        "Score": {
            "number": payload.score,
        },
        "Category": {
            "select": {"name": payload.category},
        },
    }

    # Add Sentiment only for Stock category
    if payload.sentiment:
        properties["Sentiment"] = {
            "select": {"name": payload.sentiment},
        }

    data = {
        "parent": {"database_id": database_id},
        "properties": properties,
    }

    response = requests.post(NOTION_API_URL, headers=headers, json=data, timeout=15)
    if response.status_code >= 300:
        raise RuntimeError(f"Failed to send data to Notion: {response.text}")


def build_summary_block(summary_points: List[str], one_liner: str) -> str:
    """Build formatted summary block for Notion."""
    bullet_list = "\n".join(f"• {point}" for point in summary_points)
    if one_liner:
        return f"📝 核心要点:\n{bullet_list}\n\n💡 EN One-liner:\n{one_liner}"
    return bullet_list


def build_keyword_name(keyword_item: Dict[str, str]) -> str:
    """Build keyword name from dict (term_en · term_zh)."""
    term_en = keyword_item.get("term_en")
    term_zh = keyword_item.get("term_zh")
    if term_en and term_zh:
        return f"{term_en} · {term_zh}"
    return term_en or term_zh or ""


# ==================== Worker 1: Tech News ====================

def fetch_top_story_ids(limit: int = MAX_ARTICLES) -> List[int]:
    """Fetch top story IDs from Hacker News."""
    logging.info("Fetching top stories from Hacker News...")
    response = requests.get(HN_TOP_STORIES_URL, timeout=10)
    response.raise_for_status()
    story_ids = response.json()
    return story_ids[:limit]


def fetch_story_metadata(story_id: int) -> Optional[Dict[str, Any]]:
    """Fetch story metadata from Hacker News."""
    response = requests.get(HN_ITEM_URL.format(story_id=story_id), timeout=10)
    if response.status_code != 200:
        logging.warning("Failed to fetch story %s (status %s)", story_id, response.status_code)
        return None
    return response.json()


def fetch_article_content(url: str, retries: int = 2, delay_seconds: int = 3) -> Optional[str]:
    """Fetch and extract article content from URL."""
    for attempt in range(retries + 1):
        try:
            logging.info("Fetching article body (%s)...", url)
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            return extract_clean_text(response.text)
        except Exception as err:
            logging.warning("Attempt %s to fetch article failed: %s", attempt + 1, err)
            time.sleep(delay_seconds)
    return None


def extract_clean_text(html: str) -> str:
    """Extract clean text from HTML."""
    soup = BeautifulSoup(html, "html.parser")

    for element in soup(["script", "style", "noscript", "header", "footer", "nav", "form"]):
        element.decompose()

    text = soup.get_text(separator="\n")
    cleaned_lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]
    combined = "\n".join(cleaned_lines)
    return combined[:MAX_ARTICLE_CHARS]


def summarize_tech_article(
    model: genai.GenerativeModel,
    title: str,
    article_text: str,
) -> ArticlePayload:
    """Summarize tech article using Gemini, with local fallback when AI fails."""
    prompt = (
        "You are an assistant who summarizes technical articles for bilingual learners.\n"
        "Return ONLY valid JSON with the following schema:\n"
        "{\n"
        '  "summary_points": ["3 concise Chinese bullet points"],\n'
        '  "keywords": [{"term_en": "English term", "term_zh": "Chinese explanation"}],\n'
        '  "one_liner": "English one sentence summary",\n'
        '  "score": 1-5 integer\n'
        "}\n"
        "Do not add markdown fences. Keep wording beginner-friendly."
    )

    try:
        response = model.generate_content(
            [
                prompt,
                f"Article title: {title}",
                "Article body:",
                article_text,
            ],
            generation_config=GenerationConfig(
                temperature=0.4,
                max_output_tokens=256,
                response_mime_type="application/json",
            ),
        )
        json_payload = extract_json(extract_response_text(response))
        summary_points = json_payload.get("summary_points", [])
        keywords = json_payload.get("keywords", [])
        one_liner = json_payload.get("one_liner", "")
        score = int(json_payload.get("score", 3))

        if not summary_points:
            raise ValueError("AI response missing summary_points")

        return ArticlePayload(
            title=title,
            url="",
            summary_points=summary_points[:3],
            keywords=keywords[:2],
            one_liner=one_liner,
            score=max(1, min(score, 5)),
            category="Tech",
        )
    except Exception as err:
        # Fallback: if Gemini refuses to answer or JSON is invalid, create a simple local summary
        logging.warning("Gemini summarization failed for '%s', using fallback: %s", title, err)
        preview = (article_text or "").strip()
        if preview:
            preview = preview[:180] + ("..." if len(preview) > 180 else "")
        else:
            preview = "原文内容获取失败，请直接点击链接阅读。"

        return ArticlePayload(
            title=title,
            url="",
            summary_points=[f"AI 总结失败，以下为原文前几句摘录：{preview}"],
            keywords=[{"term_en": "fallback", "term_zh": "本条目由本地备用逻辑生成"}],
            one_liner="AI summarization failed, showing a simple preview from the original article.",
            score=3,
            category="Tech",
        )


def worker_tech(notion_token: str, notion_db_id: str) -> int:
    """Worker 1: Process Tech articles from Hacker News."""
    try:
        api_key = get_gemini_key("Tech")
        model = init_gemini(GEMINI_MODEL, api_key)
    except ConfigurationError:
        logging.warning("Skipping Tech worker: No Gemini API key configured")
        return 0

    processed = 0
    for story_id in fetch_top_story_ids():
        try:
            story = fetch_story_metadata(story_id)
            if not story:
                continue
            title = story.get("title")
            url = story.get("url")
            if not title or not url:
                logging.info("Skipping story %s due to missing title or URL.", story_id)
                continue

            article_body = fetch_article_content(url)
            if not article_body:
                logging.info("Skipping %s due to empty article body.", title)
                continue

            summary_payload = summarize_tech_article(model, title, article_body)
            summary_payload.url = url

            push_to_notion(notion_token, notion_db_id, summary_payload)
            processed += 1
            logging.info("Successfully processed Tech article '%s'.", title)
        except Exception as err:
            # 对单篇文章的错误只做简短提示，避免在终端刷大量 Traceback
            logging.warning("Failed to process story %s: %s", story_id, err)

    return processed


# ==================== Worker 2: Stock Analysis ====================

def fetch_stock_data(stock_code: str) -> Optional[Dict[str, Any]]:
    """Fetch stock data using yfinance."""
    try:
        ticker = yf.Ticker(stock_code)
        info = ticker.info
        hist = ticker.history(period="5d")
        
        if hist.empty:
            return None

        current_price = hist["Close"].iloc[-1]
        prev_close = hist["Close"].iloc[-2] if len(hist) > 1 else current_price
        change_pct = ((current_price - prev_close) / prev_close * 100) if prev_close > 0 else 0

        return {
            "symbol": stock_code,
            "name": info.get("longName", stock_code),
            "current_price": float(current_price),
            "change_pct": float(change_pct),
            "pe_ratio": info.get("trailingPE"),
            "market_cap": info.get("marketCap"),
            "volume": int(hist["Volume"].iloc[-1]) if "Volume" in hist.columns else None,
        }
    except Exception as err:
        logging.warning("Failed to fetch stock data for %s: %s", stock_code, err)
        return None


def analyze_stock(
    model: genai.GenerativeModel,
    stock_data: Dict[str, Any],
) -> ArticlePayload:
    """Analyze stock using Gemini as financial analyst, with local fallback."""
    prompt = (
        "You are a financial analyst. Analyze the following stock data and market sentiment.\n"
        "Return ONLY valid JSON with the following schema:\n"
        "{\n"
        '  "summary_points": ["3 concise Chinese bullet points about market analysis"],\n'
        '  "keywords": [{"term_en": "English financial term", "term_zh": "Chinese explanation"}],\n'
        '  "one_liner": "Bullish (看涨)" or "Bearish (看跌)" with brief reason in English,\n'
        '  "score": 1-5 integer (recommendation level),\n'
        '  "sentiment": "Bullish 🟢" or "Bearish 🔴" or "Neutral ⚪"\n'
        "}\n"
        "Do not add markdown fences."
    )

    stock_text = (
        f"Stock: {stock_data['name']} ({stock_data['symbol']})\n"
        f"Current Price: {stock_data['current_price']:.2f}\n"
        f"Change: {stock_data['change_pct']:.2f}%\n"
    )
    if stock_data.get("pe_ratio"):
        stock_text += f"P/E Ratio: {stock_data['pe_ratio']:.2f}\n"
    if stock_data.get("volume"):
        stock_text += f"Volume: {stock_data['volume']:,}\n"

    title = f"{stock_data['name']} ({stock_data['symbol']}) - {stock_data['change_pct']:+.2f}%"
    url = f"https://finance.yahoo.com/quote/{stock_data['symbol']}"

    try:
        response = model.generate_content(
            [prompt, stock_text],
            generation_config=GenerationConfig(
                temperature=0.3,
                max_output_tokens=256,
                response_mime_type="application/json",
            ),
        )
        json_payload = extract_json(extract_response_text(response))
        summary_points = json_payload.get("summary_points", [])
        keywords = json_payload.get("keywords", [])
        one_liner = json_payload.get("one_liner", "")
        score = int(json_payload.get("score", 3))
        sentiment = json_payload.get("sentiment", "Neutral ⚪")

        if not summary_points:
            raise ValueError("AI response missing summary_points")

        return ArticlePayload(
            title=title,
            url=url,
            summary_points=summary_points[:3],
            keywords=keywords[:2],
            one_liner=one_liner,
            score=max(1, min(score, 5)),
            category="Stock",
            sentiment=sentiment,
        )
    except Exception as err:
        logging.warning("Gemini stock analysis failed for '%s', using fallback: %s", title, err)
        change_desc = (
            "小涨" if stock_data["change_pct"] > 0.5 else
            "小跌" if stock_data["change_pct"] < -0.5 else
            "基本持平"
        )
        summary_points = [
            f"{stock_data['name']} 今日涨跌幅 {stock_data['change_pct']:.2f}%（{change_desc}）。",
            "由于 AI 分析失败，本条内容为本地根据价格变动生成的简要说明。",
        ]
        keywords = [
            {"term_en": "fallback", "term_zh": "本条目由本地备用逻辑生成"},
        ]
        one_liner = "Local fallback summary based on recent price change."
        sentiment = "Neutral ⚪"

        return ArticlePayload(
            title=title,
            url=url,
            summary_points=summary_points,
            keywords=keywords,
            one_liner=one_liner,
            score=3,
            category="Stock",
            sentiment=sentiment,
        )


def worker_stock(notion_token: str, notion_db_id: str) -> int:
    """Worker 2: Process Stock analysis."""
    stock_codes = os.getenv("STOCK_CODES", ",".join(DEFAULT_STOCK_CODES)).split(",")
    stock_codes = [code.strip() for code in stock_codes if code.strip()]

    try:
        api_key = get_gemini_key("Stock")
        model = init_gemini(GEMINI_MODEL, api_key)
    except ConfigurationError:
        logging.warning("Skipping Stock worker: No Gemini API key configured")
        return 0

    processed = 0
    for stock_code in stock_codes:
        try:
            stock_data = fetch_stock_data(stock_code)
            if not stock_data:
                logging.info("Skipping %s due to missing data.", stock_code)
                continue

            payload = analyze_stock(model, stock_data)
            push_to_notion(notion_token, notion_db_id, payload)
            processed += 1
            logging.info("Successfully processed Stock analysis for '%s'.", stock_data['name'])
        except Exception as err:
            # 对单只股票分析的错误只做简短提示，避免在终端刷大量 Traceback
            logging.warning("Failed to process stock %s: %s", stock_code, err)

    return processed


# ==================== Worker 3: Cursor Tips ====================

def fetch_reddit_posts(subreddits: List[str], keywords: List[str], min_upvotes: int = 10) -> List[Dict[str, Any]]:
    """Fetch Reddit posts matching criteria."""
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    user_agent = os.getenv("REDDIT_USER_AGENT", "AI_Tech_Daily_Learner/1.0")

    if not client_id or not client_secret:
        logging.warning("Reddit credentials not configured, skipping Reddit fetch")
        return []

    try:
        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent,
        )

        posts = []
        cutoff_time = time.time() - 24 * 3600  # 24 hours ago

        for subreddit_name in subreddits:
            try:
                subreddit = reddit.subreddit(subreddit_name)
                for submission in subreddit.new(limit=50):
                    if submission.created_utc < cutoff_time:
                        continue
                    if submission.score < min_upvotes:
                        continue
                    title_lower = submission.title.lower()
                    if any(kw.lower() in title_lower for kw in keywords):
                        posts.append({
                            "title": submission.title,
                            "url": f"https://reddit.com{submission.permalink}",
                            "content": submission.selftext[:MAX_ARTICLE_CHARS] if submission.selftext else "",
                            "score": submission.score,
                        })
            except Exception as err:
                logging.warning("Failed to fetch from r/%s: %s", subreddit_name, err)

        return posts[:10]  # Limit to 10 posts
    except Exception as err:
        logging.warning("Failed to initialize Reddit client: %s", err)
        return []


def analyze_cursor_post(
    model: genai.GenerativeModel,
    title: str,
    content: str,
) -> Optional[ArticlePayload]:
    """Analyze Cursor-related Reddit post."""
    prompt = (
        "You are a senior developer. Extract practical tips, shortcuts, or prompts from this Reddit post.\n"
        "If the content has no valuable information, return null.\n"
        "Otherwise, return ONLY valid JSON:\n"
        "{\n"
        '  "summary_points": ["3 concise Chinese bullet points with practical tips"],\n'
        '  "keywords": [{"term_en": "English term", "term_zh": "Chinese explanation"}],\n'
        '  "one_liner": "English one sentence summary",\n'
        '  "score": 1-5 integer (usefulness level)\n'
        "}\n"
        "Do not add markdown fences."
    )

    response = model.generate_content(
        [prompt, f"Title: {title}", "Content:", content or title],
        generation_config=GenerationConfig(
            temperature=0.4,
            max_output_tokens=256,
            response_mime_type="application/json",
        ),
    )
    json_payload = extract_json(extract_response_text(response))

    # Check if AI returned null (no valuable content)
    if json_payload is None or json_payload.get("summary_points") is None:
        return None

    summary_points = json_payload.get("summary_points", [])
    keywords = json_payload.get("keywords", [])
    one_liner = json_payload.get("one_liner", "")
    score = int(json_payload.get("score", 3))

    if not summary_points:
        return None

    return ArticlePayload(
        title=title,
        url="",
        summary_points=summary_points[:3],
        keywords=keywords[:2],
        one_liner=one_liner,
        score=max(1, min(score, 5)),
        category="Cursor",
    )


def worker_cursor(notion_token: str, notion_db_id: str) -> int:
    """Worker 3: Process Cursor tips from Reddit."""
    try:
        api_key = get_gemini_key("Cursor")
        model = init_gemini(GEMINI_MODEL, api_key)
    except ConfigurationError:
        logging.warning("Skipping Cursor worker: No Gemini API key configured")
        return 0

    posts = fetch_reddit_posts(CURSOR_SUBREDDITS, ["cursor", "ai", "prompt", "shortcut", "tip"])
    processed = 0

    for post in posts:
        try:
            payload = analyze_cursor_post(model, post["title"], post["content"])
            if not payload:
                logging.info("Skipping '%s' - no valuable content.", post["title"])
                continue

            payload.url = post["url"]
            push_to_notion(notion_token, notion_db_id, payload)
            processed += 1
            logging.info("Successfully processed Cursor tip '%s'.", post["title"])
        except Exception as err:
            logging.exception("Failed to process Cursor post: %s", err)

    return processed


# ==================== Worker 4: Indie Ideas ====================

def analyze_idea(
    model: genai.GenerativeModel,
    title: str,
    content: str,
) -> ArticlePayload:
    """Analyze indie idea using Gemini as product manager."""
    prompt = (
        "You are a product manager. Evaluate this app/startup idea for feasibility.\n"
        "Return ONLY valid JSON:\n"
        "{\n"
        '  "summary_points": ["3 concise Chinese bullet points: core idea + potential pain points"],\n'
        '  "keywords": [{"term_en": "English term", "term_zh": "Chinese explanation"}],\n'
        '  "one_liner": "Recommended MVP tech stack (e.g., "Recommended Stack: Flutter + Firebase")",\n'
        '  "score": 1-5 integer (business potential)\n'
        "}\n"
        "Do not add markdown fences."
    )

    response = model.generate_content(
        [prompt, f"Title: {title}", "Content:", content or title],
        generation_config=GenerationConfig(
            temperature=0.5,
            max_output_tokens=256,
            response_mime_type="application/json",
        ),
    )
    json_payload = extract_json(extract_response_text(response))
    summary_points = json_payload.get("summary_points", [])
    keywords = json_payload.get("keywords", [])
    one_liner = json_payload.get("one_liner", "")
    score = int(json_payload.get("score", 3))

    if not summary_points:
        raise ValueError("AI response missing summary_points")

    return ArticlePayload(
        title=title,
        url="",
        summary_points=summary_points[:3],
        keywords=keywords[:2],
        one_liner=one_liner,
        score=max(1, min(score, 5)),
        category="Idea",
    )


def worker_idea(notion_token: str, notion_db_id: str) -> int:
    """Worker 4: Process Indie ideas from Reddit."""
    try:
        api_key = get_gemini_key("Idea")
        model = init_gemini(GEMINI_MODEL, api_key)
    except ConfigurationError:
        logging.warning("Skipping Idea worker: No Gemini API key configured")
        return 0

    posts = fetch_reddit_posts(IDEA_SUBREDDITS, [], min_upvotes=5)
    processed = 0

    for post in posts:
        try:
            payload = analyze_idea(model, post["title"], post["content"])
            payload.url = post["url"]
            push_to_notion(notion_token, notion_db_id, payload)
            processed += 1
            logging.info("Successfully processed Idea '%s'.", post["title"])
        except Exception as err:
            logging.exception("Failed to process Idea post: %s", err)

    return processed


# ==================== Main Runner ====================

def run() -> None:
    """Run all workers."""
    notion_token = require_env_var("NOTION_TOKEN")
    notion_db_id = require_env_var("NOTION_DATABASE_ID")

    total_processed = 0

    # Worker 1: Tech
    logging.info("=== Starting Tech Worker ===")
    try:
        count = worker_tech(notion_token, notion_db_id)
        total_processed += count
        logging.info("Tech Worker completed: %s articles", count)
    except Exception as err:
        logging.exception("Tech Worker failed: %s", err)

    # Worker 2: Stock
    logging.info("=== Starting Stock Worker ===")
    try:
        count = worker_stock(notion_token, notion_db_id)
        total_processed += count
        logging.info("Stock Worker completed: %s analyses", count)
    except Exception as err:
        logging.exception("Stock Worker failed: %s", err)

    # Worker 3: Cursor
    logging.info("=== Starting Cursor Worker ===")
    try:
        count = worker_cursor(notion_token, notion_db_id)
        total_processed += count
        logging.info("Cursor Worker completed: %s tips", count)
    except Exception as err:
        logging.exception("Cursor Worker failed: %s", err)

    # Worker 4: Idea
    logging.info("=== Starting Idea Worker ===")
    try:
        count = worker_idea(notion_token, notion_db_id)
        total_processed += count
        logging.info("Idea Worker completed: %s ideas", count)
    except Exception as err:
        logging.exception("Idea Worker failed: %s", err)

    logging.info("=== All Workers Completed ===")
    logging.info("Total items processed: %s", total_processed)


if __name__ == "__main__":
    try:
        run()
    except ConfigurationError as config_err:
        logging.error("Configuration error: %s", config_err)
