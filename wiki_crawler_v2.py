#!/usr/bin/env python3
#
# Usage: ./wiki_crawler_v2.py --force-reload
#        ./wiki_crawler_v2.py --limit 50 --force-reload
#
# Author: Gemini 2.5Pro
# Human: Jim Dunphy - Aug 11, 2025
#
# wiki_crawler_v2.py
# This script crawls a MediaWiki site, extracts text from pages,
# chunks the text, creates embeddings, and stores it all in a LanceDB database.

import os
import sys
import argparse
import requests
from bs4 import BeautifulSoup
import lancedb
from lancedb.pydantic import LanceModel, Vector
from lancedb.embeddings import get_registry
from dotenv import load_dotenv

# --- Configuration ---
load_dotenv()
WIKI_BASE_URL = os.getenv("WIKI_BASE")
WIKI_USER = os.getenv("WIKI_USER")
WIKI_BOT_PASSWORD = os.getenv("WIKI_BOT_PASSWORD")

if not os.getenv("OPENAI_API_KEY"):
    raise ValueError("OPENAI_API_KEY environment variable not set.")

# --- THE FIX ---
# Explicitly define the embedding model to ensure consistency with the app.
openai = get_registry().get("openai").create(name="text-embedding-3-small")

# --- Pydantic Schema for LanceDB ---
class WikiChunk(LanceModel):
    text: str = openai.SourceField()
    vector: Vector(openai.ndims()) = openai.VectorField()
    source: str
    title: str

# --- MediaWiki API Functions ---
S = requests.Session()

def login_to_wiki(base_url: str):
    if not (WIKI_USER and WIKI_BOT_PASSWORD):
        print("INFO: No wiki credentials provided, proceeding with anonymous access.")
        return
    try:
        r1 = S.get(
            f"{base_url}/api.php",
            params={"action": "query", "meta": "tokens", "type": "login", "format": "json"},
            timeout=30
        )
        r1.raise_for_status()
        token = r1.json()["query"]["tokens"]["logintoken"]
    except Exception as e:
        print(f"ERROR: Could not get login token. Please check WIKI_BASE_URL. Details: {e}", file=sys.stderr)
        sys.exit(1)
    r2 = S.post(
        f"{base_url}/api.php",
        data={"action": "login", "lgname": WIKI_USER, "lgpassword": WIKI_BOT_PASSWORD, "lgtoken": token, "format": "json"},
        timeout=30
    )
    r2.raise_for_status()
    result = r2.json().get("login", {}).get("result")
    if result == "Success":
        print("✅ Successfully logged into MediaWiki.")
    else:
        print(f"WARN: Login failed. Result: {r2.json()}", file=sys.stderr)


def get_all_page_ids(base_url: str, namespace: int, limit: int) -> list[int]:
    print(f"Fetching page list for namespace {namespace}...")
    page_ids = []
    params = {"action": "query", "list": "allpages", "apnamespace": namespace, "aplimit": "max", "format": "json"}
    while True:
        try:
            res = S.get(f"{base_url}/api.php", params=params, timeout=30)
            res.raise_for_status()
            data = res.json()
            pages = data.get("query", {}).get("allpages", [])
            if not pages: break
            for page in pages:
                page_ids.append(page["pageid"])
                if limit and len(page_ids) >= limit: return page_ids
            if "continue" in data:
                params["apcontinue"] = data["continue"]["apcontinue"]
            else:
                break
        except requests.RequestException as e:
            print(f"Error fetching page list: {e}", file=sys.stderr)
            break
    print(f"Found {len(page_ids)} pages.")
    return page_ids

def get_page_content(base_url: str, page_id: int) -> dict | None:
    params = {"action": "parse", "pageid": page_id, "prop": "text|title", "format": "json"}
    try:
        res = S.get(f"{base_url}/api.php", params=params, timeout=30)
        res.raise_for_status()
        data = res.json().get("parse", {})
        if "text" in data and "*" in data["text"]:
            return {"html": data["text"]["*"], "title": data.get("title", "Untitled"), "source": f"{base_url}/index.php?curid={page_id}"}
    except requests.RequestException as e:
        print(f"Error fetching page {page_id}: {e}", file=sys.stderr)
    return None

# --- Text Processing ---
def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
    if not text: return []
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunks.append(" ".join(words[i:i + chunk_size]))
    return chunks

# --- Main Ingestion Logic ---
def main(args):
    db_path, table_name = args.db_path, args.table_name
    login_to_wiki(WIKI_BASE_URL)
    print(f"Connecting to LanceDB at: {db_path}")
    db = lancedb.connect(db_path)
    if args.force_reload:
        print(f"Dropping existing table '{table_name}'...")
        db.drop_table(table_name, ignore_missing=True)
    table = db.create_table(table_name, schema=WikiChunk, mode="overwrite")
    print(f"Table '{table_name}' created successfully.")
    page_ids = get_all_page_ids(WIKI_BASE_URL, args.namespace, args.limit)
    all_chunks_data = []
    for page_id in page_ids:
        content = get_page_content(WIKI_BASE_URL, page_id)
        if not content: continue
        soup = BeautifulSoup(content["html"], "html.parser")
        for element in soup.select(".mw-editsection, .toc, .mw-jump-link"):
            element.decompose()
        clean_text = soup.get_text(" ", strip=True)
        text_chunks = chunk_text(clean_text)
        for chunk in text_chunks:
            all_chunks_data.append({"text": chunk, "source": content["source"], "title": content["title"]})
        print(f"Processed '{content['title']}', created {len(text_chunks)} chunks.")
    if all_chunks_data:
        print(f"\nFound {len(all_chunks_data)} total chunks to ingest.")
        batch_size = 150
        for i in range(0, len(all_chunks_data), batch_size):
            batch = all_chunks_data[i:i + batch_size]
            try:
                print(f"Adding batch {i//batch_size + 1}... ({len(batch)} chunks)")
                table.add(batch)
            except Exception as e:
                print(f"ERROR: Failed to add batch {i//batch_size + 1}. Details: {e}", file=sys.stderr)
                sys.exit(1)
        print("✅ Ingestion complete.")
    else:
        print("No content found to ingest.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Crawl a MediaWiki site and ingest content into LanceDB.")
    parser.add_argument("--db-path", type=str, default="data/wiki.lancedb", help="Path to the LanceDB database directory.")
    parser.add_argument("--table-name", type=str, default="wiki_content", help="Name of the table to store content.")
    parser.add_argument("--namespace", type=int, default=0, help="The MediaWiki namespace ID to crawl (0 is for main articles).")
    parser.add_argument("--limit", type=int, default=None, help="Limit the number of pages to crawl (for testing).")
    parser.add_argument("--force-reload", action="store_true", help="If set, deletes and recreates the table.")
    args = parser.parse_args()
    main(args)
