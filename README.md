# MediaWiki RAG Assistant

This project provides a set of tools to create a Retrieval-Augmented Generation (RAG) assistant for a private MediaWiki site. It consists of two main components:

1.  **`wiki_crawler_v2.py`**: A command-line tool that crawls a MediaWiki site, extracts page content, chunks it into manageable pieces, creates embeddings using the OpenAI API, and stores everything in a LanceDB vector database.
2.  **`rag_app_v2.py`**: A Streamlit web application that provides a user-friendly interface to ask questions. It retrieves relevant documents from the database and uses an OpenAI model to generate answers based on the retrieved context.

-----

## Setup

### 1\. Dependencies

First, install the required Python libraries. It's recommended to use a virtual environment.

```bash
pip install -U requests beautifulsoup4 lancedb openai python-dotenv streamlit
```

### 2\. Environment Variables

This project uses a `.env` file to manage secrets and configuration. Create a file named `.env` in the root of the project directory and add the following variables.

```env
# --- MediaWiki Configuration ---
# The base URL of your MediaWiki installation
WIKI_BASE="https://wiki.example.com:7443"

# Credentials for a bot user on your wiki (required for private wikis)
WIKI_USER="YourBotUsername"
WIKI_BOT_PASSWORD="YourBotPassword"


# --- OpenAI API Key ---
# Your secret key from platform.openai.com
OPENAI_API_KEY="sk-..."


# --- (Optional) Database Path for Streamlit App ---
# You can override the default paths for the app if needed.
# DB_PATH="data/wiki.lancedb"
# TABLE_NAME="wiki_content"
```

-----

## Usage

The process is two steps: first, run the crawler to build your knowledge base, and second, run the web app to ask questions.

### Step 1: Ingesting the Wiki Content (`wiki_crawler_v2.py`)

This script populates your LanceDB database. You only need to run it when you want to build the database for the first time or update it with new content from the wiki.

The scripts must be made executable first:

```bash
chmod +x wiki_crawler_v2.py
chmod +x rag_app_v2.py
```

#### **Command-Line Options**

  * `--db-path`: The folder where the database will be stored. (Default: `data/wiki.lancedb`)
  * `--table-name`: The name of the table inside the database. (Default: `wiki_content`)
  * `--namespace`: The MediaWiki namespace ID to crawl. (Default: `0` for main articles)
  * `--limit`: Limits the number of pages to crawl. Useful for quick tests. (Default: all pages)
  * `--force-reload`: Deletes the data table if it already exists, ensuring a fresh start. **Recommended for full re-ingestions.**

#### **Examples**

  * **Initial Full Ingestion (Recommended)**:
    This command will delete any old data and ingest the entire wiki.

    ```bash
    ./wiki_crawler_v2.py --force-reload
    ```

  * **Testing with a Small Number of Pages**:
    This is useful for quickly testing the crawler without waiting for the full site to be processed.

    ```bash
    ./wiki_crawler_v2.py --limit 50 --force-reload
    ```

  * **Using a Custom Database Path**:

    ```bash
    ./wiki_crawler_v2.py --db-path ./data/my_custom_db --table-name my_articles --force-reload
    ```

### Step 2: Running the Web Application (`rag_app_v2.py`)

This command starts the Streamlit web server, allowing you to access the AI assistant in your browser.

#### **How to Run**

```bash
streamlit run rag_app_v2.py
```

After running this command, your terminal will display a local URL (usually `http://localhost:8501`) that you can open in your web browser to use the application. The app will automatically connect to the database created by the crawler (as long as you use the default paths or set the `DB_PATH` and `TABLE_NAME` environment variables).

-----

## Maintenance: How to Reload the Data

Over time, your wiki will be updated with new or changed pages. To ensure the AI has the most current information, you should periodically reload the database.

The process is simple: just re-run the crawler with the `--force-reload` flag.

```bash
# This command deletes all the old data and re-crawls the entire wiki from scratch.
./wiki_crawler_v2.py --force-reload
```

This ensures that any deleted pages are removed from the database and all new or modified pages are chunked and embedded with the latest content. After the crawler finishes, you can restart the Streamlit application to use the updated knowledge base.
