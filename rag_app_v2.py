#!/usr/bin/env python3
#
# Usage: streamlit run rag_app_v2.py
#
# Author: Gemini 2.5Pro
# Human: Jim Dunphy - Aug 11, 2025
#
# rag_app_v2.py
# This script runs a Streamlit web application that provides a user interface
# for a Retrieval-Augmented Generation (RAG) system.

import os
import streamlit as st
import lancedb
import openai
from dotenv import load_dotenv

# --- Configuration ---
load_dotenv()
DB_PATH = os.getenv("DB_PATH", "data/wiki.lancedb")
TABLE_NAME = os.getenv("TABLE_NAME", "wiki_content")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    st.error("OPENAI_API_KEY environment variable not set.")
    st.stop()
    
client = openai.OpenAI(api_key=OPENAI_API_KEY)

# --- Page Setup ---
st.set_page_config(page_title="Wiki RAG Assistant v2", page_icon="✅", layout="wide")
st.title("✅ Wiki RAG Assistant v2")
st.markdown("A stable RAG application built with standard Python libraries.")

# --- Sidebar ---
with st.sidebar:
    st.header("⚙️ Parameters")
    st.info(f"**Database:** `{DB_PATH}`\n**Table:** `{TABLE_NAME}`")
    search_limit = st.slider("Search Results (k)", min_value=1, max_value=10, value=3, help="Number of chunks to retrieve as context.")

# --- Core Functions ---
@st.cache_resource
def get_db_table():
    if not os.path.exists(DB_PATH):
        st.error(f"Database not found at '{DB_PATH}'. Please run `wiki_crawler_v2.py` first.")
        st.stop()
    db = lancedb.connect(DB_PATH)
    try:
        table = db.open_table(TABLE_NAME)
        return table
    except Exception:
        st.error(f"Table '{TABLE_NAME}' not found. Please run `wiki_crawler_v2.py` first.")
        st.stop()

def get_embedding(text: str, model: str = "text-embedding-3-small"):
    return client.embeddings.create(input=[text], model=model).data[0].embedding

table = get_db_table()

# --- UI Tabs ---
ai_tab, search_tab = st.tabs(["🤖 AI Assistant (RAG)", "🔎 Direct Database Search"])

# --- AI Assistant Tab ---
with ai_tab:
    st.header("Ask the AI a Question")
    query = st.text_area("Your question:", key="ai_query", value="how do you run an ansible playbook")

    if st.button("🚀 Get AI Answer", type="primary"):
        if not query:
            st.error("Please enter a question.")
        else:
            with st.spinner("Embedding query..."):
                query_vector = get_embedding(query)
            with st.spinner("Searching for relevant documents..."):
                search_results = table.search(query_vector).limit(search_limit).to_list()
            
            if not search_results:
                st.error("Could not find any relevant documents.")
            else:
                context_str = "\n\n---\n\n".join([result['text'] for result in search_results])
                sources = {f"[{result['title']}]({result['source']})" for result in search_results}

                # --- THE FIX ---
                # Changed the variable name from {context} to {context_str} to match the variable defined above.
                system_prompt = f"""
                You are an expert assistant. Answer the user's question based *only* on the following context.
                If the context does not contain the answer, state that you cannot answer from the provided information.

                CONTEXT:
                {context_str}
                """
                
                st.markdown("### 💡 Answer")
                answer_placeholder = st.empty()
                with st.spinner("Generating answer..."):
                    stream = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": query},
                        ],
                        stream=True,
                    )
                    full_response = ""
                    for chunk in stream:
                        content = chunk.choices[0].delta.content or ""
                        full_response += content
                        answer_placeholder.markdown(full_response + "▌")
                answer_placeholder.markdown(full_response)
                
                st.markdown("---")
                st.subheader("📚 Sources")
                for source in sources:
                    st.markdown(f"- {source}")

                with st.expander("Show Retrieved Context"):
                    st.text(context_str)

# --- Direct Database Search Tab ---
with search_tab:
    st.header("Search the Raw Database")
    search_query = st.text_input("Search query:", key="db_query", value="ansible")

    if st.button("🔍 Search"):
        if not search_query:
            st.error("Please enter a query.")
        else:
            with st.spinner("Embedding query and searching..."):
                query_vector = get_embedding(search_query)
                results = table.search(query_vector).limit(search_limit).to_list()
            st.success(f"Found {len(results)} results.")
            for result in results:
                with st.expander(f"**{result['title']}**"):
                    st.markdown(f"**Source:** <{result['source']}>")
                    st.markdown("---")
                    st.write(result['text'])
