"""Flask web app to display Notion database articles."""
import os
from datetime import datetime
from typing import Any, Dict, List

import requests
from flask import Flask, jsonify, render_template

app = Flask(__name__)

NOTION_API_URL = "https://api.notion.com/v1/databases/{database_id}/query"
NOTION_VERSION = "2022-06-28"


def fetch_notion_articles() -> List[Dict[str, Any]]:
    """Fetch articles from Notion database."""
    notion_token = os.getenv("NOTION_TOKEN")
    database_id = os.getenv("NOTION_DATABASE_ID")

    if not notion_token or not database_id:
        return []

    headers = {
        "Authorization": f"Bearer {notion_token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }

    data = {
        "sorts": [{"property": "Date", "direction": "descending"}],
        "page_size": 50,
    }

    try:
        response = requests.post(
            NOTION_API_URL.format(database_id=database_id),
            headers=headers,
            json=data,
            timeout=10,
        )
        response.raise_for_status()
        return response.json().get("results", [])
    except Exception as err:
        print(f"Error fetching from Notion: {err}")
        return []


def parse_notion_page(page: Dict[str, Any]) -> Dict[str, Any]:
    """Parse a Notion page into a simple dict."""
    props = page.get("properties", {})
    title = ""
    url = ""
    summary = ""
    keywords = []
    date_str = ""
    score = 0

    # Extract title
    title_prop = props.get("Title", {})
    if title_prop.get("title"):
        title = "".join([t.get("plain_text", "") for t in title_prop["title"]])

    # Extract URL
    url_prop = props.get("URL", {})
    if url_prop.get("url"):
        url = url_prop["url"]

    # Extract summary
    summary_prop = props.get("Summary", {})
    if summary_prop.get("rich_text"):
        summary = "".join([t.get("plain_text", "") for t in summary_prop["rich_text"]])

    # Extract keywords
    keywords_prop = props.get("Keywords", {})
    if keywords_prop.get("multi_select"):
        keywords = [kw.get("name", "") for kw in keywords_prop["multi_select"]]

    # Extract date
    date_prop = props.get("Date", {})
    if date_prop.get("date") and date_prop["date"].get("start"):
        date_str = date_prop["date"]["start"]

    # Extract score
    score_prop = props.get("Score", {})
    if score_prop.get("number") is not None:
        score = int(score_prop["number"])

    return {
        "title": title,
        "url": url,
        "summary": summary,
        "keywords": keywords,
        "date": date_str,
        "score": score,
    }


@app.route("/")
def index():
    """Render the main page."""
    return render_template("index.html")


@app.route("/api/articles")
def api_articles():
    """API endpoint to fetch articles."""
    pages = fetch_notion_articles()
    articles = [parse_notion_page(page) for page in pages]
    
    # Remove duplicates by URL, keeping the most recent one
    seen_urls = {}
    unique_articles = []
    for article in articles:
        url = article.get("url", "")
        if not url:
            continue
        # If we've seen this URL, skip (we're iterating from newest to oldest)
        if url in seen_urls:
            continue
        seen_urls[url] = True
        unique_articles.append(article)
    
    return jsonify(unique_articles)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

