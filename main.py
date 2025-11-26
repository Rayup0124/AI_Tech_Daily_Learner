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

HN_TOP_STORIES_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
MAX_ARTICLES = 5
MAX_ARTICLE_CHARS = 2000
NOTION_API_URL = "https://api.notion.com/v1/pages"
NOTION_VERSION = "2022-06-28"
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")


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


class ConfigurationError(ValueError):
    """Raised when required environment variables are missing."""


def require_env_var(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ConfigurationError(f"Environment variable '{name}' is required.")
    return value


def fetch_top_story_ids(limit: int = MAX_ARTICLES) -> List[int]:
    logging.info("Fetching top stories from Hacker News...")
    response = requests.get(HN_TOP_STORIES_URL, timeout=10)
    response.raise_for_status()
    story_ids = response.json()
    return story_ids[:limit]


def fetch_story_metadata(story_id: int) -> Optional[Dict[str, Any]]:
    response = requests.get(HN_ITEM_URL.format(story_id=story_id), timeout=10)
    if response.status_code != 200:
        logging.warning("Failed to fetch story %s (status %s)", story_id, response.status_code)
        return None
    return response.json()


def fetch_article_content(url: str, retries: int = 2, delay_seconds: int = 3) -> Optional[str]:
    for attempt in range(retries + 1):
        try:
            logging.info("Fetching article body (%s)...", url)
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            return extract_clean_text(response.text)
        except Exception as err:  # noqa: BLE001 - log and continue
            logging.warning("Attempt %s to fetch article failed: %s", attempt + 1, err)
            time.sleep(delay_seconds)
    return None


def extract_clean_text(html: str) -> str:
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


def init_gemini(model_name: str) -> genai.GenerativeModel:
    api_key = require_env_var("GEMINI_API_KEY")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(model_name)


def summarize_article(
    model: genai.GenerativeModel,
    title: str,
    article_text: str,
) -> ArticlePayload:
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
    )


def extract_json(raw_text: str) -> Dict[str, Any]:
    raw_text = raw_text.strip()
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        # Attempt to find JSON block if Gemini wraps it with extra text.
        start = raw_text.find("{")
        end = raw_text.rfind("}")
        if start != -1 and end != -1:
            return json.loads(raw_text[start : end + 1])
        raise


def extract_response_text(response: Any) -> str:
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


def push_to_notion(
    notion_token: str,
    database_id: str,
    payload: ArticlePayload,
) -> None:
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

    data = {
        "parent": {"database_id": database_id},
        "properties": {
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
        },
    }

    response = requests.post(NOTION_API_URL, headers=headers, json=data, timeout=15)
    if response.status_code >= 300:
        raise RuntimeError(f"Failed to send data to Notion: {response.text}")


def build_summary_block(summary_points: List[str], one_liner: str) -> str:
    bullet_list = "\n".join(f"• {point}" for point in summary_points)
    if one_liner:
        return f"📝 核心要点:\n{bullet_list}\n\n💡 EN One-liner:\n{one_liner}"
    return bullet_list


def build_keyword_name(keyword_item: Dict[str, str]) -> str:
    term_en = keyword_item.get("term_en")
    term_zh = keyword_item.get("term_zh")
    if term_en and term_zh:
        return f"{term_en} · {term_zh}"
    return term_en or term_zh or ""


def run() -> None:
    notion_token = require_env_var("NOTION_TOKEN")
    notion_db_id = require_env_var("NOTION_DATABASE_ID")
    model = init_gemini(GEMINI_MODEL)

    processed_articles = 0
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

            summary_payload = summarize_article(model, title, article_body)
            summary_payload.url = url

            push_to_notion(notion_token, notion_db_id, summary_payload)
            processed_articles += 1
            logging.info("Successfully processed '%s'.", title)
        except ConfigurationError as err:
            raise err
        except Exception as err:  # noqa: BLE001 - continue other stories
            logging.exception("Failed to process story %s: %s", story_id, err)

    logging.info("Processing completed. Total articles pushed: %s", processed_articles)


if __name__ == "__main__":
    try:
        run()
    except ConfigurationError as config_err:
        logging.error("Configuration error: %s", config_err)

