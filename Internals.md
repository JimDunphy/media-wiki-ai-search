# MediaWiki RAG - Internals Guide

This document provides a technical deep-dive into the MediaWiki RAG Assistant project. It is intended for developers who will maintain and extend the system.

## 1. Background Concepts for Junior Developers

To understand this project, you need to be familiar with a few key concepts from the world of AI and Large Language Models (LLMs).

### What is RAG?

**RAG** stands for **Retrieval-Augmented Generation**. It's a technique for making LLMs "smarter" by giving them access to specific, up-to-date information. Instead of relying only on its pre-existing training data, a RAG system follows a two-step process:

1.  **Retrieve:** Before answering a question, the system first *retrieves* relevant documents from a knowledge base (in our case, our LanceDB database).
2.  **Augment & Generate:** The system then *augments* the user's original question by adding the retrieved documents as context. It sends this combined package to the LLM, which then *generates* an answer based on the provided information.

This process ensures that the AI's answers are grounded in our own data, making them more accurate and trustworthy.

### What are Embeddings and Vector Search?

Computers don't understand words; they understand numbers. **Embeddings** are the solution to this problem. An embedding is a numerical representation of a piece of text, often a long list of numbers called a **vector**.

* **Example:** The text "How to run a playbook" might be converted into a vector like `[0.01, -0.5, 0.88, ...]`.

The key idea is that semantically similar pieces of text will have mathematically similar vectors. This allows us to perform **Vector Search**.

When a user asks a question, we convert their question into a vector. Then, we search our database for the text chunks whose vectors are mathematically closest to the question's vector. This is how we find the most relevant documents to feed to the LLM, even if the user's question doesn't use the exact same keywords found in the source documents.

---

## 2. Program Deep Dive

The project consists of two core Python scripts.

### `wiki_crawler_v2.py` - The Ingestion Engine

The sole purpose of this script is to populate our knowledge base. It reads content from the MediaWiki site and prepares it for the AI.

**Workflow:**

1.  **Configuration:** It starts by loading environment variables from the `.env` file (`WIKI_BASE`, `WIKI_USER`, `OPENAI_API_KEY`, etc.).
2.  **Login:** It uses the `requests` library to perform a two-step login to the MediaWiki API, establishing an authenticated session to access private content.
3.  **Page Discovery:** Using the authenticated session, it queries the `allpages` API endpoint to get a list of all page IDs in the main namespace (`0`).
4.  **Content Extraction:** For each page ID, it calls the `parse` API endpoint to get the page's rendered HTML content and title.
5.  **Text Cleaning:** It uses the `BeautifulSoup` library to parse the HTML and remove unwanted elements like "Edit" links and tables of contents, leaving only the clean article text.
6.  **Chunking:** The clean text from each page is broken down into smaller, overlapping "chunks" of about 1000 words. This is critical because LLMs have a limited context window, and smaller chunks provide more focused context.
7.  **Database and Schema:** It connects to a local LanceDB database (a folder on the disk) and defines a table schema using `pydantic`. The schema specifies that each record will have `text`, a `vector`, a `source` URL, and a `title`.
8.  **Batch Ingestion:** It collects all the chunks from all the pages and adds them to the LanceDB table in small batches (e.g., 150 at a time). As it adds the data, the `lancedb` library automatically calls the OpenAI API to convert the `text` of each chunk into an embedding `vector` before saving it. This batching prevents API rate-limit errors.

### `rag_app_v2.py` - The User Interface

This script creates the interactive web application using Streamlit.

**Workflow:**

1.  **Configuration:** It loads the necessary environment variables (`OPENAI_API_KEY`, `DB_PATH`, etc.).
2.  **Database Connection:** It connects to the LanceDB database created by the crawler. The `@st.cache_resource` decorator ensures this connection is only made once and is reused for all user interactions, which is very efficient.
3.  **UI Layout:** It sets up the main page title and a sidebar with a slider to control the `search_limit` (how many documents to retrieve). It then creates two main tabs: "AI Assistant" and "Direct Database Search."
4.  **Direct Search Logic (🔎 Tab):**
    * When the user enters a query and clicks "Search," the app converts the query text into an embedding vector using the `get_embedding` function.
    * It then uses `table.search(query_vector)` to find the most similar chunks in the database.
    * Finally, it displays the raw text and metadata for each retrieved chunk. This tab is an essential debugging tool.
5.  **AI Assistant Logic (🤖 Tab):** This is the core RAG workflow.
    * It performs the same search as the direct search tab to retrieve the most relevant documents.
    * It then constructs a detailed **system prompt**. This is a set of instructions for the AI that includes the retrieved text chunks (the "context").
    * It sends the user's question and the system prompt to the OpenAI Chat API (`client.chat.completions.create`).
    * It **streams** the response back from the API, displaying the answer word-by-word for a better user experience.
    * After the answer is complete, it displays the source links from the documents that were used as context.

---

## 3. How to Extend the Programs

This project provides a solid foundation. Here are some ideas for how an entry-level developer could extend it.

* **Add More Metadata:** You could modify the crawler to extract more metadata from each page, such as the last modification date or the author.
    * **File to edit:** `wiki_crawler_v2.py`
    * **What to do:**
        1.  Update the `WikiChunk` schema to include a new field (e.g., `last_modified: str`).
        2.  Modify the `get_page_content` function to request this extra data from the MediaWiki API.
        3.  Add the new data to the dictionary in the `all_chunks_data.append()` call.

* **Support PDF Indexing:** You could add functionality to find links to PDFs in the wiki articles, download them, extract their text, and add that text to the database.
    * **File to edit:** `wiki_crawler_v2.py`
    * **What to do:**
        1.  In the main loop, after getting page content, use BeautifulSoup to find all `<a>` tags that link to `.pdf` files.
        2.  For each PDF link, use the `requests` library to download the file.
        3.  Use a library like `pypdf2` to open the downloaded PDF and extract its text content.
        4.  Chunk the PDF text and add it to `all_chunks_data` just like the wiki text, making sure to use the PDF's URL as the `source`.

* **Improve the UI:** You could add features to the Streamlit app.
    * **File to edit:** `rag_app_v2.py`
    * **What to do:**
        * Add a "Copy to Clipboard" button for the AI's answer.
        * Display a chat history of the current session. You could use `st.session_state` to store a list of questions and answers.
        * Add a button to clear the chat history.
