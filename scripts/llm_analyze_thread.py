# scripts/llm_analyze_thread.py
import os
import json
import time
import logging
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from dotenv import load_dotenv
from openai import OpenAI

# -----------------------
# Simple config
# -----------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
THREADS_DIR = PROJECT_ROOT / "data/reddit/comments/threads"  # change if needed

# Limit how many thread JSON files to process. None = all, or set an int like 1, 5, etc.
LIMIT: Optional[int] = None

# Optional: process a single specific JSON file. Set to Path(...) or leave as None.
SINGLE_THREAD_FILE: Optional[Path] = None

# Model and retries
MODEL_NAME = "gpt-5-mini"
MAX_RETRIES = 3
RETRY_SLEEP_SECONDS = 2.0

# Pretruncate content sent to the LLM (storage still keeps full selftext)
PRETRUNCATE = True
PRETRUNCATE_LIMIT = 200

# -----------------------
# Paths
# -----------------------
RUN_ID = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
OUT_BASE = PROJECT_ROOT / "output" / "reddit" / RUN_ID
OUT_PER_POST = OUT_BASE / "per_post"
OUT_TABLES = OUT_BASE / "tables"
OUT_AGG = OUT_BASE / "aggregate"
OUT_META = OUT_BASE / "meta"

# -----------------------
# Prompt
# -----------------------
PROMPT = """You are a WGU institutional stakeholder focused on the RN-BSN program’s reputation and decision drivers.
Read ONE Reddit thread (post + all comments) and output a concise, valid JSON object for leadership.

INPUT
- thread_json: {
    "post": {"post_id": "...", "title": "...", "selftext": "...", "permalink": "...", "created_iso": "...", "subreddit": "..."},
    "comments": [{"comment_id": "...", "body": "...", "replies": [...]}, ...]
  }

OUTPUT
Return ONLY a single JSON object with this exact schema:
{
  "post": {
    "post_id": "...",
    "title": "...",
    "permalink": "...",
    "created_iso": "...",
    "subreddit": "...",
    "num_comments": <int>
  },
  "reasons_to_choose": [
    {
      "summary": "<specific example reason WGU was valued in THIS thread>",
      "evidence": [ { "text": "<<text>>", "comment_id": "<post or t1_xxxxx>" } ]
    }
  ],
  "comments": [
    {
      "summary": "<other notable point (risks, context, oddities, side topics)>",
      "evidence": [ { "text": "<<text>>", "comment_id": "<post or t1_xxxxx>" } ]
    }
  ],
  "verbatim_highlights": [
    { "text": "<<short notable quote>>", "comment_id": "<post or t1_xxxxx>" }
  ],
  "conversation_summary": "<5–8 sentence plain-English synthesis of the full thread>"
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
"""

# -----------------------
# Helpers
# -----------------------
def truncate_text(s: Optional[str], n: int = PRETRUNCATE_LIMIT) -> str:
    if not s:
        return ""
    return s if len(s) <= n else s[:n]

def pretruncate_thread(thread: Dict[str, Any], limit: int = PRETRUNCATE_LIMIT) -> Dict[str, Any]:
    out = {
        "post": dict(thread.get("post", {})),
        "comments": []
    }
    # keep title and metadata; truncate selftext only for the LLM input
    if "selftext" in out["post"]:
        out["post"]["selftext"] = truncate_text(out["post"]["selftext"], limit)

    def walk(comments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        acc = []
        for c in comments or []:
            c_new = {
                "comment_id": c.get("comment_id"),
                "body": truncate_text(c.get("body", ""), limit),
                "replies": walk(c.get("replies", []))
            }
            acc.append(c_new)
        return acc

    out["comments"] = walk(thread.get("comments", []))
    return out

def count_comments(thread: Dict[str, Any]) -> int:
    n = 0
    def walk(lst):
        nonlocal n
        for c in lst or []:
            n += 1
            walk(c.get("replies", []))
    walk(thread.get("comments", []))
    return n

def ensure_dirs():
    for p in [OUT_PER_POST, OUT_TABLES, OUT_AGG, OUT_META]:
        p.mkdir(parents=True, exist_ok=True)

def write_json(path: Path, data: Any):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))

# -----------------------
# OpenAI setup
# -----------------------
def setup_openai() -> OpenAI:
    load_dotenv(override=True)  # just to load OPENAI_API_KEY from .env
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not found in environment")
    logging.info(f"Using model={MODEL_NAME}")
    return OpenAI(api_key=api_key)

def build_messages(thread_for_llm: Dict[str, Any]) -> List[Dict[str, str]]:
    sys_msg = {
        "role": "system",
        "content": "You are a WGU institutional stakeholder analyzing RN-BSN reputation. Return valid JSON only."
    }
    user_msg = {
        "role": "user",
        "content": PROMPT.replace("{{thread_json}}", json.dumps(thread_for_llm, ensure_ascii=False))
    }
    return [sys_msg, user_msg]

def call_llm(client: OpenAI, messages: List[Dict[str, str]]) -> str:
    try:
        resp = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            response_format={"type": "json_object"},
        )
        return resp.choices[0].message.content
    except Exception as e:
        logging.warning(f"Strict JSON failed, retrying: {e}")
        resp = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
        )
        return resp.choices[0].message.content

def robust_llm_call(client: OpenAI, messages: List[Dict[str, str]]) -> Optional[Dict[str, Any]]:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            raw = call_llm(client, messages)
            return json.loads(raw)
        except Exception as e:
            logging.error(f"Attempt {attempt} failed: {type(e).__name__}: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_SLEEP_SECONDS)
    return None

# -----------------------
# Main
# -----------------------
def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ensure_dirs()
    client = setup_openai()

    # choose inputs
    if SINGLE_THREAD_FILE:
        thread_files = [Path(SINGLE_THREAD_FILE)]
    else:
        files = sorted(THREADS_DIR.glob("*.json"))
        thread_files = files[:LIMIT] if LIMIT is not None else files

    if not thread_files:
        logging.error(f"No thread files found in {THREADS_DIR.resolve()}")
        return

    meta_inputs = []
    processed = 0

    for fp in thread_files:
        try:
            raw_thread = json.loads(Path(fp).read_text())
            raw_thread_post = raw_thread.get("post", {}) or {}
            raw_thread_post.setdefault("num_comments", count_comments(raw_thread))
            raw_thread["post"] = raw_thread_post

            thread_for_llm = pretruncate_thread(raw_thread) if PRETRUNCATE else raw_thread
            messages = build_messages(thread_for_llm)
            result = robust_llm_call(client, messages)

            post_id = raw_thread["post"].get("post_id", Path(fp).stem)
            out_path = OUT_PER_POST / f"{post_id}.json"

            if result is None:
                write_json(out_path.with_suffix(".error.json"), {
                    "error": "LLM failed after retries",
                    "post_id": post_id
                })
                logging.error(f"LLM failed for post_id={post_id}")
                continue

            # attach full, original selftext to saved output
            full_selftext = (raw_thread.get("post", {}) or {}).get("selftext") or ""
            if full_selftext:
                result.setdefault("post", {})["selftext"] = full_selftext
                result["post"]["selftext_truncated_for_llm"] = PRETRUNCATE

            write_json(out_path, result)
            logging.info(f"Wrote {out_path}")
            processed += 1
            meta_inputs.append({"post_id": post_id, "thread_path": str(fp)})

        except Exception as e:
            logging.error(f"Failed on file {fp}: {type(e).__name__}: {e}")

    write_json(OUT_META / "inputs_manifest.json", {
        "run_id": RUN_ID,
        "threads_dir": str(THREADS_DIR.resolve()),
        "processed_count": processed,
        "inputs": meta_inputs
    })

if __name__ == "__main__":
    main()