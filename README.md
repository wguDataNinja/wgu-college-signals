# WGU College Choice Signals

This project transforms messy Reddit discussions into structured insights about **why students choose WGU programs**. It combines data collection, text processing, and LLM analysis in a reproducible pipeline.  

The current focus is on **RN-BSN (pre-licensure)** — a priority program for WGU’s School of Health.  

 **See the full analysis report here:** [Signals from Social Media: WGU’s RN-BSN (Pre-Licensure)](docs/index.md)

---

## Scope and intent

- Focus: **reasons to choose the RN-BSN program**
- Prototype: demonstrates how LLMs can extract decision drivers from social media  
- Extensible: pipeline can be run for other programs, degrees, or platforms

---

## Pipeline

All steps use the **official Reddit API**. You’ll need a Reddit account and API credentials in a `.env` file.  

1. **Fetch posts**  
   `scripts/reddit_fetch_rnbsn_posts.py`  
   → `data/reddit/posts/posts_YYYYMMDD.csv`

2. **Fetch comments**  
   `scripts/reddit_fetch_rnbsn_comments.py`  
   → `data/reddit/comments/raw/{post_id}.jsonl`

3. **Build nested threads**  
   `scripts/reddit_build_threads_rnbsn.py`  
   → `data/reddit/comments/threads/{post_id}.json`  
   → `data/reddit/comments/threads/{post_id}.md`

4. **Markdown index (optional)**  
   `scripts/build_markdown_index.py`  
   → browsable index of Markdown threads

5. **LLM analysis**  
   `scripts/llm_analyze_thread.py`  
   → `output/reddit/YYYY-MM-DD/per_post/{post_id}.json`  
   → `output/reddit/YYYY-MM-DD/meta/inputs_manifest.json`

**Optional utility**  
- `scripts/merge_reddit_threads.py` → merges per-post outputs into a single file  
- `scripts/test_reddit_api.py` → quick check of Reddit API access  

---

## Data

This repo includes sample data (all public via Reddit API):  

- `data/reddit/posts/posts_rn-bsn_20250922.csv` → keyword search results  
- `data/reddit/comments/raw/` → raw JSONL comment dumps  
- `data/reddit/comments/threads/` → threaded JSON + Markdown  
- `data/degrees_by_mention_count.csv` → aggregated mentions by degree  
- `data/wgu_subreddits.csv` → subreddits searched  

All data is public; usernames are excluded.  

---

## Models

- **gpt-5-mini** used for analysis (default temperature).  
- **gpt-5-nano** available for cheaper runs (~5× less cost).  
- Local models can replicate the method with simpler prompts.  

---

## Requirements

Minimal `requirements.txt`:  

```txt
praw
python-dotenv
openai