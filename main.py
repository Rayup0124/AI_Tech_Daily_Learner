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

# Reddit-based sources were removed to avoid API friction.
# We now use local "seed" prompts to generate Cursor tips and Indie ideas
# directly with Gemini (no external APIs).
CURSOR_SUBREDDITS = ["cursor", "vscode", "programming"]  # kept for backward compat (unused)
IDEA_SUBREDDITS = ["AppIdeas", "SideProject"]  # kept for backward compat (unused)

# Cursor tips seed themes (one tip per seed, cycled by date)
CURSOR_TIP_SEEDS = [
    {
        "slug": "daily-learning-workflow",
        "title": "为自己设计 Cursor 每日学习流程",
        "prompt": "Design a daily learning workflow using Cursor: review yesterday's code, ask AI to comment on weak spots, generate 1-2 micro tasks, and summarize new knowledge.",
    },
    {
        "slug": "ai-edit-refactor",
        "title": "用 AI Edit 快速重构函数",
        "prompt": "Use Cursor's AI Edit to refactor a long Python function into smaller testable units, including how to write safe refactor prompts and verify changes with tests.",
    },
    {
        "slug": "prompt-library",
        "title": "建立自己的 Prompt Library",
        "prompt": "Build a small prompt library inside Cursor or snippets so that common refactor / debug / explain prompts can be reused quickly every day.",
    },
    {
        "slug": "debug-workflow",
        "title": "将 Cursor 融入调试流程",
        "prompt": "Combine traditional debugging tools with Cursor chat: letting AI explain stack traces, suggest hypotheses, and generate focused logging or assertions.",
    },
    {
        "slug": "reading-source-code",
        "title": "用 Cursor 阅读源码不迷路",
        "prompt": "Use Cursor to navigate and understand unfamiliar open-source code bases, generating file overviews, call graphs, and learning checklists.",
    },
]

# Indie / side‑project idea seeds
IDEA_SEEDS = [
    {
        "slug": "dev-learning-coach",
        "title": "程序员学习教练小助手",
        "prompt": "A personal learning coach for developers that tracks what you learned each day, suggests spaced‑repetition reviews, and creates tiny weekend projects.",
    },
    {
        "slug": "micro-saas-tracker",
        "title": "Micro‑SaaS 收入追踪面板",
        "prompt": "A dashboard for indie hackers to track revenue, churn and experiments across multiple tiny SaaS products, with AI suggesting next actions.",
    },
    {
        "slug": "idea-validator",
        "title": "应用想法快速验证工具",
        "prompt": "A tool where you paste a new app idea and receive a quick validation: who needs it, minimum MVP scope, and 3 cheapest channels to find first users.",
    },
    {
        "slug": "dev-log-to-newsletter",
        "title": "把开发日志自动变成 Newsletter",
        "prompt": "A service that turns a developer's daily changelog into a weekly email newsletter to followers, summarizing progress in human‑friendly language.",
    },
]

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
    category: str  # Tech, Stock, Cursor, Idea, Language
    sentiment: Optional[str] = None  # Bullish 🟢, Bearish 🔴, Neutral ⚪ (only for Stock)


@dataclass
class TrilingualMatrixPayload:
    """Payload for Trilingual Matrix (Language Learning) content."""
    title: str
    date: str
    scenes: List[Dict[str, Any]]  # Each scene has name, register, and trilingual content
    category: str = "Language"


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

def _select_daily_seeds(seeds: List[Dict[str, str]], count: int) -> List[Dict[str, str]]:
    """Select a small number of seeds based on today's date so that content rotates."""
    if not seeds or count <= 0:
        return []
    base = dt.datetime.utcnow().date().toordinal()
    selected: List[Dict[str, str]] = []
    max_count = min(count, len(seeds))
    for i in range(max_count):
        idx = (base + i) % len(seeds)
        selected.append(seeds[idx])
    return selected


def generate_cursor_tip_from_seed(
    model: genai.GenerativeModel,
    seed: Dict[str, str],
) -> ArticlePayload:
    """Use Gemini directly to generate a Cursor tip from a local seed theme (no Reddit)."""
    prompt = (
        "You are a senior developer and heavy Cursor user.\n"
        "Based on the following theme, generate practical tips and shortcuts for using Cursor in daily work.\n"
        "Return ONLY valid JSON with this schema:\n"
        "{\n"
        '  "summary_points": ["3 concise Chinese bullet points with practical tips"],\n'
        '  "keywords": [{"term_en": "English term", "term_zh": "Chinese explanation"}],\n'
        '  "one_liner": "English one sentence summary of why this tip is useful",\n'
        '  "score": 1-5 integer (usefulness level)\n'
        "}\n"
        "Do not add markdown fences."
    )

    try:
        response = model.generate_content(
            [prompt, f"Theme: {seed['prompt']}"],
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
        score = int(json_payload.get("score", 4))

        if not summary_points:
            raise ValueError("AI response missing summary_points")

        return ArticlePayload(
            title=seed["title"],
            url=f"cursor://{seed['slug']}",
            summary_points=summary_points[:3],
            keywords=keywords[:2],
            one_liner=one_liner,
            score=max(1, min(score, 5)),
            category="Cursor",
        )
    except Exception as err:
        logging.warning("Gemini cursor tip generation failed for '%s': %s", seed.get("slug"), err)
        # Fallback: simple local tip
        summary_points = [
            f"围绕主题【{seed['title']}】尝试在 Cursor 中实践：{seed['prompt']}",
            "先在小项目或练习仓库中试验新的工作流，再逐步应用到正式项目。",
        ]
        keywords = [
            {"term_en": "fallback", "term_zh": "本条目由本地备用逻辑生成"},
        ]
        one_liner = "Local fallback tip about using Cursor more effectively in daily workflow."
        return ArticlePayload(
            title=seed["title"],
            url=f"cursor://{seed['slug']}",
            summary_points=summary_points,
            keywords=keywords,
            one_liner=one_liner,
            score=3,
            category="Cursor",
        )


def worker_cursor(notion_token: str, notion_db_id: str) -> int:
    """Worker 3: Generate Cursor tips from local seeds (no Reddit needed)."""
    try:
        api_key = get_gemini_key("Cursor")
        model = init_gemini(GEMINI_MODEL, api_key)
    except ConfigurationError:
        logging.warning("Skipping Cursor worker: No Gemini API key configured")
        return 0

    processed = 0
    seeds = _select_daily_seeds(CURSOR_TIP_SEEDS, 2)  # up to 2 tips per run

    for seed in seeds:
        try:
            payload = generate_cursor_tip_from_seed(model, seed)
            push_to_notion(notion_token, notion_db_id, payload)
            processed += 1
            logging.info("Successfully generated Cursor tip '%s'.", seed["title"])
        except Exception as err:
            logging.exception("Failed to generate Cursor tip from seed '%s': %s", seed.get("slug"), err)

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
    """Worker 4: Generate Indie ideas from local seeds (no Reddit needed)."""
    try:
        api_key = get_gemini_key("Idea")
        model = init_gemini(GEMINI_MODEL, api_key)
    except ConfigurationError:
        logging.warning("Skipping Idea worker: No Gemini API key configured")
        return 0

    processed = 0
    seeds = _select_daily_seeds(IDEA_SEEDS, 1)  # one idea per run

    for seed in seeds:
        try:
            # Reuse analyze_idea prompt, feeding our own seed content
            try:
                payload = analyze_idea(model, seed["title"], seed["prompt"])
            except Exception as err:
                logging.warning("Gemini idea generation failed for '%s': %s", seed.get("slug"), err)
                # Fallback: simple local idea
                summary_points = [
                    f"围绕主题【{seed['title']}】构思一个应用或服务：{seed['prompt']}",
                    "先用极小的 MVP 验证：只做一个简单的网页或自动化脚本找 3~5 个真实用户试用。",
                ]
                keywords = [
                    {"term_en": "fallback", "term_zh": "本条目由本地备用逻辑生成"},
                ]
                one_liner = "Local fallback description for an indie project idea."
                payload = ArticlePayload(
                    title=seed["title"],
                    url=f"idea://{seed['slug']}",
                    summary_points=summary_points,
                    keywords=keywords,
                    one_liner=one_liner,
                    score=3,
                    category="Idea",
                )

            # Ensure URL is a stable pseudo-link so we can de‑duplicate in Notion
            if not payload.url:
                payload.url = f"idea://{seed['slug']}"

            push_to_notion(notion_token, notion_db_id, payload)
            processed += 1
            logging.info("Successfully generated Idea '%s'.", seed["title"])
        except Exception as err:
            logging.exception("Failed to generate Idea from seed '%s': %s", seed.get("slug"), err)

    return processed


# ==================== Worker 5: Trilingual Matrix (Language Learning) ====================

def generate_trilingual_matrix(model: genai.GenerativeModel, date: str) -> TrilingualMatrixPayload:
    """Generate a daily Trilingual Matrix lesson covering Work, Life, Tech scenes."""
    prompt = (
        "You are a professional language teacher fluent in English, Chinese, and Bahasa Melayu.\n"
        "Task: Generate a 'Trilingual Matrix' lesson for {date} covering three scenes: Work, Life, Tech.\n"
        "\n"
        "Output must be valid JSON with this structure:\n"
        "{\n"
        '  "title": "Trilingual Matrix: {date}",\n'
        '  "scenes": [\n'
        '    {\n'
        '      "name": "Work",\n'
        '      "register": "Formal BM",\n'
        '      "english": {\n'
        '        "phrases": ["Professional phrase 1", "Professional phrase 2"],\n'
        '        "example_dialogue": ["Speaker A: Hello, how can I help you?", "Speaker B: I need assistance with the project."]\n'
        '      },\n'
        '      "chinese": {\n'
        '        "phrases": ["中文商务表达1", "中文商务表达2"],\n'
        '        "example_dialogue": ["A: 你好，我能帮你什么？", "B: 我需要项目帮助。"]\n'
        '      },\n'
        '      "malay": {\n'
        '        "register": "formal",\n'
        '        "phrases": ["Ungkapan formal 1", "Ungkapan formal 2"],\n'
        '        "example_dialogue": ["A: Selamat pagi, bagaimana saya boleh membantu?", "B: Saya perlukan bantuan dengan projek."]\n'
        '      },\n'
        '      "quiz": [\n'
        '        {"q": "How do you say \'project deadline\' in Malay?", "a": "Tarikh akhir projek"},\n'
        '        {"q": "Translate: \'会议推迟\' to English", "a": "Meeting postponed"}\n'
        '      ]\n'
        '    },\n'
        '    {\n'
        '      "name": "Life",\n'
        '      "register": "Casual BM",\n'
        '      ... (similar structure with casual Malay expressions)\n'
        '    },\n'
        '    {\n'
        '      "name": "Tech",\n'
        '      "register": "Formal BM",\n'
        '      ... (similar structure with tech-specific terms)\n'
        '    }\n'
        '  ]\n'
        "}\n"
        "\n"
        "Requirements:\n"
        "- Work scene: Malay must be Formal BM (Bahasa Baku).\n"
        "- Life scene: Malay must be Casual BM (include spoken particles like 'tak', 'nak', 'camne' where appropriate).\n"
        "- Each scene must include 3+ phrases and a short example dialogue.\n"
        "- Each scene must have 2+ quiz items for active recall.\n"
        "- The JSON should be parseable.\n"
        "- Content should be practical and immediately usable."
    ).format(date=date)

    try:
        response = model.generate_content(
            [prompt],
            generation_config=GenerationConfig(
                temperature=0.6,
                max_output_tokens=1024,
                response_mime_type="application/json",
            ),
        )
        raw_text = extract_response_text(response)
        # Log a truncated preview of the raw response to help debug model outputs
        logging.info("Language model raw response preview: %s", raw_text[:2000])
        try:
            json_payload = extract_json(raw_text)
        except Exception as parse_err:
            logging.warning("Failed to parse language JSON: %s\nRaw preview: %s", parse_err, raw_text[:2000])
            raise

        # Validate structure
        scenes = json_payload.get("scenes")
        if not isinstance(scenes, list) or len(scenes) != 3:
            raise ValueError("Invalid scenes structure")

        title = json_payload.get("title", f"Trilingual Matrix: {date}")

        return TrilingualMatrixPayload(
            title=title,
            date=date,
            scenes=scenes,
            category="Language"
        )

    except Exception as err:
        logging.warning("Gemini trilingual matrix generation failed, using fallback: %s", err)

        # Fallback content
        fallback_scenes = [
            {
                "name": "Work",
                "register": "Formal BM",
                "english": {
                    "phrases": ["I would like to schedule a meeting", "Please review the document"],
                    "example_dialogue": ["A: Can we meet tomorrow?", "B: Yes, what time works for you?"]
                },
                "chinese": {
                    "phrases": ["我想安排一个会议", "请审核这个文件"],
                    "example_dialogue": ["A: 我们明天可以见面吗？", "B: 可以，你什么时间方便？"]
                },
                "malay": {
                    "register": "formal",
                    "phrases": ["Saya ingin menjadualkan mesyuarat", "Sila semak dokumen ini"],
                    "example_dialogue": ["A: Bolehkah kita bertemu esok?", "B: Ya, pukul berapa sesuai untuk tuan?"]
                },
                "quiz": [
                    {"q": "How to say 'meeting' in Malay?", "a": "Mesyuarat"},
                    {"q": "Translate '请审核' to English", "a": "Please review"}
                ]
            },
            {
                "name": "Life",
                "register": "Casual BM",
                "english": {
                    "phrases": ["What's up?", "Wanna grab some food?"],
                    "example_dialogue": ["A: Hey, long time no see!", "B: Yeah, what's new?"]
                },
                "chinese": {
                    "phrases": ["最近怎么样？", "想吃东西吗？"],
                    "example_dialogue": ["A: 嘿，好久不见！", "B: 是啊，最近有什么新鲜事？"]
                },
                "malay": {
                    "register": "casual",
                    "phrases": ["Ada apa?", "Nak makan tak?"],
                    "example_dialogue": ["A: Eh, lama tak jumpa!", "B: Ya la, apa khabar?"]
                },
                "quiz": [
                    {"q": "How to say 'what's up' casually in Malay?", "a": "Ada apa?"},
                    {"q": "Translate '好久不见' to English", "a": "Long time no see"}
                ]
            },
            {
                "name": "Tech",
                "register": "Formal BM",
                "english": {
                    "phrases": ["This code needs refactoring", "Let's deploy the update"],
                    "example_dialogue": ["A: The API is down", "B: I'll check the logs"]
                },
                "chinese": {
                    "phrases": ["这段代码需要重构", "让我们部署更新"],
                    "example_dialogue": ["A: API 挂了", "B: 我检查一下日志"]
                },
                "malay": {
                    "register": "formal",
                    "phrases": ["Kod ini perlu direka bentuk semula", "Mari kita gunakan kemas kini"],
                    "example_dialogue": ["A: API tidak berfungsi", "B: Saya akan semak log"]
                },
                "quiz": [
                    {"q": "What does 'refactoring' mean in Chinese?", "a": "重构"},
                    {"q": "How to say 'API' in Malay?", "a": "API (same)"}
                ]
            }
        ]

        return TrilingualMatrixPayload(
            title=f"Trilingual Matrix: {date}",
            date=date,
            scenes=fallback_scenes,
            category="Language"
        )


def push_trilingual_matrix_to_notion(
    notion_token: str,
    database_id: str,
    payload: TrilingualMatrixPayload,
) -> None:
    """Push Trilingual Matrix content to Notion as rich blocks."""
    # Check if already exists (by title)
    if check_url_exists(notion_token, database_id, payload.title):
        logging.info("Skipping '%s' - already exists in database", payload.title)
        return

    headers = {
        "Authorization": f"Bearer {notion_token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }

    # Build rich content blocks
    children = []

    for scene in payload.scenes:
        # Scene heading
        register_note = " (Formal BM)" if scene["register"] == "Formal BM" else " (Casual BM)"
        children.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"text": {"content": f"{scene['name']} Scene{register_note}"}}]
            }
        })

        # English section
        children.append({
            "object": "block",
            "type": "heading_3",
            "heading_3": {
                "rich_text": [{"text": {"content": "🇺🇸 English"}}]
            }
        })

        # English phrases
        if scene["english"].get("phrases"):
            phrases_text = "\n".join(f"• {phrase}" for phrase in scene["english"]["phrases"])
            children.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"text": {"content": f"**Key Phrases:**\n{phrases_text}"}}]
                }
            })

        # English dialogue
        if scene["english"].get("example_dialogue"):
            dialogue_text = "\n".join(scene["english"]["example_dialogue"])
            children.append({
                "object": "block",
                "type": "quote",
                "quote": {
                    "rich_text": [{"text": {"content": f"**Example Dialogue:**\n{dialogue_text}"}}]
                }
            })

        # Chinese section
        children.append({
            "object": "block",
            "type": "heading_3",
            "heading_3": {
                "rich_text": [{"text": {"content": "🇨🇳 Chinese"}}]
            }
        })

        # Chinese phrases
        if scene["chinese"].get("phrases"):
            phrases_text = "\n".join(f"• {phrase}" for phrase in scene["chinese"]["phrases"])
            children.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"text": {"content": f"**Key Phrases:**\n{phrases_text}"}}]
                }
            })

        # Chinese dialogue
        if scene["chinese"].get("example_dialogue"):
            dialogue_text = "\n".join(scene["chinese"]["example_dialogue"])
            children.append({
                "object": "block",
                "type": "quote",
                "quote": {
                    "rich_text": [{"text": {"content": f"**Example Dialogue:**\n{dialogue_text}"}}]
                }
            })

        # Malay section
        children.append({
            "object": "block",
            "type": "heading_3",
            "heading_3": {
                "rich_text": [{"text": {"content": f"🇲🇾 Malay ({scene['register']})"}}]
            }
        })

        # Malay phrases
        if scene["malay"].get("phrases"):
            phrases_text = "\n".join(f"• {phrase}" for phrase in scene["malay"]["phrases"])
            children.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"text": {"content": f"**Key Phrases:**\n{phrases_text}"}}]
                }
            })

        # Malay dialogue
        if scene["malay"].get("example_dialogue"):
            dialogue_text = "\n".join(scene["malay"]["example_dialogue"])
            children.append({
                "object": "block",
                "type": "quote",
                "quote": {
                    "rich_text": [{"text": {"content": f"**Example Dialogue:**\n{dialogue_text}"}}]
                }
            })

        # Quiz section as toggle blocks
        if scene.get("quiz"):
            children.append({
                "object": "block",
                "type": "heading_3",
                "heading_3": {
                    "rich_text": [{"text": {"content": "📝 Quiz (Click to reveal answers)"}}]
                }
            })

            for quiz_item in scene["quiz"]:
                question = quiz_item.get("q", "")
                answer = quiz_item.get("a", "")
                children.append({
                    "object": "block",
                    "type": "toggle",
                    "toggle": {
                        "rich_text": [{"text": {"content": f"Q: {question}"}}],
                        "children": [
                            {
                                "object": "block",
                                "type": "paragraph",
                                "paragraph": {
                                    "rich_text": [{"text": {"content": f"A: {answer}"}}]
                                }
                            }
                        ]
                    }
                })

    # Create page with rich content
    data = {
        "parent": {"database_id": database_id},
        "properties": {
            "Title": {
                "title": [{"text": {"content": payload.title}}],
            },
            "URL": {
                "url": f"trilingual://{payload.date.replace('-', '')}",
            },
            "Date": {
                "date": {"start": payload.date},
            },
            "Category": {
                "select": {"name": "Language"},
            },
            "Score": {
                "number": 5,  # Language content always gets high score
            },
        },
        "children": children,
    }

    response = requests.post("https://api.notion.com/v1/pages", headers=headers, json=data, timeout=15)
    if response.status_code >= 300:
        raise RuntimeError(f"Failed to send Trilingual Matrix to Notion: {response.text}")


def worker_lang(notion_token: str, notion_db_id: str) -> int:
    """Worker 5: Generate daily Trilingual Matrix for language learning."""
    try:
        # Use separate key for language generation if available
        lang_key = os.getenv("LANG_GEMINI_KEY") or os.getenv("GEMINI_API_KEY")
        if not lang_key:
            logging.warning("Skipping Language worker: No Gemini API key configured")
            return 0

        model = init_gemini(GEMINI_MODEL, lang_key)
    except ConfigurationError:
        logging.warning("Skipping Language worker: No Gemini API key configured")
        return 0

    processed = 0
    today = dt.datetime.utcnow().date().isoformat()

    try:
        payload = generate_trilingual_matrix(model, today)
        push_trilingual_matrix_to_notion(notion_token, notion_db_id, payload)
        processed += 1
        logging.info("Successfully generated Trilingual Matrix for '%s'.", today)
    except Exception as err:
        logging.exception("Failed to generate Trilingual Matrix: %s", err)

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

    # Worker 5: Language (Trilingual Matrix)
    logging.info("=== Starting Language Worker ===")
    try:
        count = worker_lang(notion_token, notion_db_id)
        total_processed += count
        logging.info("Language Worker completed: %s matrices", count)
    except Exception as err:
        logging.exception("Language Worker failed: %s", err)

    logging.info("=== All Workers Completed ===")
    logging.info("Total items processed: %s", total_processed)


if __name__ == "__main__":
    try:
        run()
    except ConfigurationError as config_err:
        logging.error("Configuration error: %s", config_err)
