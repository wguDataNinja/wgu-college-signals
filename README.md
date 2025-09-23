# WGU College Choice Signals

This project transforms messy Reddit discussions into structured insights about **why students choose WGU programs**. It combines data collection, text processing, and LLM analysis in a reproducible pipeline.  

The current focus is on **RN-BSN (pre-licensure)**

 **See the full analysis report here:** [Signals from Social Media: WGU’s RN-BSN (Pre-Licensure)](docs/rn-bsn-analysis)

---

### Scope and intent

- Focus: **reasons to choose the RN-BSN program**
- Prototype: demonstrates how LLMs can extract decision drivers from social media  
- Extensible: pipeline can be run for other programs, degrees, or platforms

---

   ### Pipeline

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

   <details>
   <summary>Full prompt (click to expand)</summary>

   ```text
   You are a WGU institutional stakeholder focused on the RN-BSN program’s reputation and decision drivers.
   Read ONE Reddit thread (post + all comments) and output a concise, valid JSON object for leadership.

   INPUT
   - thread_json: {
       "post": {"post_id": "...", "title": "...", "selftext": "...", "permalink": "...", "created_iso": "...", "subreddit": "..."},
       "comments": [{"comment_id": "...", "body": "...", "replies": [...]}, ...]
     }

   OUTPUT
   Return ONLY a single JSON object with this exact schema:
   {
     "post": { ... },
     "reasons_to_choose": [ ... ],
     "comments": [ ... ],
     "verbatim_highlights": [ ... ],
     "conversation_summary": "..."
   }

   REQUIREMENTS
   1) Each item in "reasons_to_choose" is a standalone specific reason to choose WGU.
   2) Put all other relevant observations into "comments".
   3) Evidence: use comment_id only ("post" or "t1_xxxxx").
   4) Keep summaries concise and stakeholder-oriented.
   5) End with a conversation_summary that synthesizes the whole thread.
   6) Output JSON only. Do not wrap in Markdown or add extra text.

   NOW PROCESS THIS:
   {{thread_json}}
      </details>
   ```

---

## Data

This repo includes all raw and intermediary data (all public via Reddit API):  

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