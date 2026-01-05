#!/usr/bin/env python3
"""
Add 'Language' select option to Notion database 'Category' property if missing.

Usage:
  Set environment variables NOTION_TOKEN and NOTION_DATABASE_ID, then run:
    python scripts/add_language_option.py

This script will:
  - GET the database schema
  - Check the 'Category' property for a select option named 'Language'
  - If missing, PATCH the database to add the option
"""
import os
import sys
import requests

NOTION_VERSION = "2022-06-28"
NOTION_GET_DB = "https://api.notion.com/v1/databases/{database_id}"


def require_env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        print(f"Environment variable {name} is required.")
        sys.exit(1)
    return v


def main():
    token = require_env("NOTION_TOKEN")
    db_id = require_env("NOTION_DATABASE_ID")

    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }

    # Fetch current database schema
    r = requests.get(NOTION_GET_DB.format(database_id=db_id), headers=headers, timeout=10)
    if r.status_code != 200:
        print("Failed to fetch database:", r.status_code, r.text)
        sys.exit(1)

    db = r.json()
    properties = db.get("properties", {})
    cat_prop = properties.get("Category")
    if not cat_prop:
        print("No 'Category' property found in database. Please create a 'Category' Select property first.")
        sys.exit(1)

    if cat_prop.get("type") != "select":
        print("Property 'Category' is not a Select type. Please change it to Select and try again.")
        sys.exit(1)

    options = cat_prop.get("select", {}).get("options", [])
    names = [opt.get("name") for opt in options]
    if "Language" in names:
        print("Category option 'Language' already exists. Nothing to do.")
        return

    # Append new option and PATCH database
    new_options = options + [{"name": "Language", "color": "blue"}]

    patch_body = {
        "properties": {
            "Category": {
                "select": {
                    "options": new_options
                }
            }
        }
    }

    patch_url = NOTION_GET_DB.format(database_id=db_id)
    pr = requests.patch(patch_url, headers=headers, json=patch_body, timeout=10)
    if pr.status_code >= 300:
        print("Failed to update database:", pr.status_code, pr.text)
        sys.exit(1)

    print("Successfully added 'Language' option to Category property.")


if __name__ == "__main__":
    main()


