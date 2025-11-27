"""Script to remove duplicate articles from Notion database (keeps the most recent one)."""
import os
from collections import defaultdict
from typing import Any, Dict, List

import requests

NOTION_API_URL = "https://api.notion.com/v1/databases/{database_id}/query"
NOTION_PAGE_URL = "https://api.notion.com/v1/pages/{page_id}"
NOTION_VERSION = "2022-06-28"


def require_env_var(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Environment variable '{name}' is required.")
    return value


def fetch_all_articles(notion_token: str, database_id: str) -> List[Dict[str, Any]]:
    """Fetch all articles from Notion database."""
    headers = {
        "Authorization": f"Bearer {notion_token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }

    all_pages = []
    query_url = NOTION_API_URL.format(database_id=database_id)
    start_cursor = None

    while True:
        data = {
            "sorts": [{"property": "Date", "direction": "descending"}],
            "page_size": 100,
        }
        if start_cursor:
            data["start_cursor"] = start_cursor

        try:
            response = requests.post(query_url, headers=headers, json=data, timeout=10)
            response.raise_for_status()
            result = response.json()
            all_pages.extend(result.get("results", []))

            if not result.get("has_more"):
                break
            start_cursor = result.get("next_cursor")
        except Exception as err:
            print(f"Error fetching articles: {err}")
            break

    return all_pages


def extract_url(page: Dict[str, Any]) -> str:
    """Extract URL from a Notion page."""
    props = page.get("properties", {})
    url_prop = props.get("URL", {})
    if url_prop.get("url"):
        return url_prop["url"]
    return ""


def delete_page(notion_token: str, page_id: str) -> bool:
    """Delete a Notion page."""
    headers = {
        "Authorization": f"Bearer {notion_token}",
        "Notion-Version": NOTION_VERSION,
    }

    try:
        response = requests.patch(
            NOTION_PAGE_URL.format(page_id=page_id),
            headers=headers,
            json={"archived": True},
            timeout=10,
        )
        return response.status_code == 200
    except Exception as err:
        print(f"Error deleting page {page_id}: {err}")
        return False


def main():
    notion_token = require_env_var("NOTION_TOKEN")
    database_id = require_env_var("NOTION_DATABASE_ID")

    print("Fetching all articles from Notion...")
    pages = fetch_all_articles(notion_token, database_id)
    print(f"Found {len(pages)} articles total.")

    # Group by URL
    url_to_pages = defaultdict(list)
    for page in pages:
        url = extract_url(page)
        if url:
            url_to_pages[url].append(page)

    # Find duplicates
    duplicates_to_delete = []
    for url, url_pages in url_to_pages.items():
        if len(url_pages) > 1:
            # Keep the first one (most recent due to sorting), delete the rest
            duplicates_to_delete.extend(url_pages[1:])

    if not duplicates_to_delete:
        print("No duplicates found! All articles are unique.")
        return

    print(f"\nFound {len(duplicates_to_delete)} duplicate articles to delete.")
    print("These will be archived (kept in Notion but hidden):")

    for page in duplicates_to_delete:
        page_id = page.get("id", "")
        props = page.get("properties", {})
        title_prop = props.get("Title", {})
        title = ""
        if title_prop.get("title"):
            title = "".join([t.get("plain_text", "") for t in title_prop["title"]])
        url = extract_url(page)
        print(f"  - {title[:50]}... ({url[:50]}...)")

    # Ask for confirmation
    response = input("\nProceed with deletion? (yes/no): ")
    if response.lower() != "yes":
        print("Cancelled.")
        return

    # Delete duplicates
    deleted_count = 0
    for page in duplicates_to_delete:
        page_id = page.get("id", "")
        if delete_page(notion_token, page_id):
            deleted_count += 1
            print(f"✓ Deleted page {page_id}")
        else:
            print(f"✗ Failed to delete page {page_id}")

    print(f"\nCompleted! Deleted {deleted_count} duplicate articles.")


if __name__ == "__main__":
    try:
        main()
    except ValueError as err:
        print(f"Error: {err}")
    except Exception as err:
        print(f"Unexpected error: {err}")

