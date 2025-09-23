# filename: scripts/fetch_comments_rn-bsn.py
# Purpose: Fetch raw Reddit comments for RN-BSN posts listed in a posts CSV.
# Output: one JSONL per post with minimal, LLM-friendly fields (no author/timestamps).

import os
import csv
import json
import time
from pathlib import Path
import praw
import prawcore

# --------- Config ---------
ROOT = Path(__file__).resolve().parents[1]

# Inputs
ENV_PATH   = ROOT / ".env"
POSTS_CSV  = ROOT / "data" / "reddit" / "posts" / "posts_rn-bsn_20250922.csv"  # update date as needed

# Outputs
RAW_DIR    = ROOT / "data" / "reddit" / "comments" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

# Behavior
REPLACE_MORE_LIMIT = None   # None = expand all MoreComments;
SLEEP_BETWEEN_POSTS = 0.3
SKIP_IF_EXISTS = True
# -------------------------


def load_env_file(path: Path) -> None:
    """Load simple KEY=VALUE lines from .env into os.environ."""
    if not path.exists():
        raise FileNotFoundError(f".env not found at {path}")
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ[k.strip()] = v.strip()


def reddit_client() -> praw.Reddit:
    """Instantiate PRAW client from environment variables."""
    return praw.Reddit(
        client_id=os.getenv("REDDIT_CLIENT_ID"),
        client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
        user_agent=os.getenv("REDDIT_USER_AGENT"),
        username=os.getenv("REDDIT_USERNAME"),
        password=os.getenv("REDDIT_PASSWORD"),
        ratelimit_seconds=5,
    )


def iter_posts(csv_path: Path):
    """Yield (post_id, permalink) from the posts CSV."""
    with open(csv_path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        # expected header:
        # post_id,num_comments,title,selftext,created_iso,subreddit_name,permalink
        for row in r:
            pid = row.get("post_id", "").strip()
            permalink = row.get("permalink", "").strip()
            if not pid:
                continue
            yield pid, permalink


def fetch_comments_for_post(reddit: praw.Reddit, post_id: str):
    """
    Yield minimal, LLM-friendly comment records for a single submission.
    Fields: post_id, comment_id, parent_id, depth, body, permalink
    """
    subm = reddit.submission(id=post_id)
    subm.comment_sort = "top"
    subm.comment_limit = None
    # expand "MoreComments"
    subm.comments.replace_more(limit=REPLACE_MORE_LIMIT)

    # BFS traversal to preserve conversational flow
    queue = [(c, 0) for c in subm.comments]  # (comment, depth)

    while queue:
        c, depth = queue.pop(0)

        # body may be "[deleted]" or "[removed]"—keep as-is for transparency
        body = (c.body or "").strip()

        yield {
            "post_id": post_id,
            "comment_id": c.id,
            "parent_id": c.parent_id,  # t3_<post> or t1_<comment>
            "depth": int(depth),
            "body": body,
            "permalink": f"https://reddit.com{c.permalink}",
        }

        #  replies ordered by creation time
        try:
            replies = list(c.replies)
            # Some replies may lack created_utc (very rare); fallback to stable order
            try:
                replies.sort(key=lambda x: getattr(x, "created_utc", 0))
            except Exception:
                pass
            for rc in replies:
                queue.append((rc, depth + 1))
        except Exception:
            # If replies are unavailable for this comment, skip gracefully
            continue


def main():
    load_env_file(ENV_PATH)
    reddit = reddit_client()

    for post_id, permalink in iter_posts(POSTS_CSV):
        out_path = RAW_DIR / f"{post_id}.jsonl"
        if SKIP_IF_EXISTS and out_path.exists():
            print(f"[skip] {post_id} raw exists")
            continue

        try:
            with open(out_path, "w", encoding="utf-8") as out:
                wrote = 0
                for rec in fetch_comments_for_post(reddit, post_id):
                    out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    wrote += 1
            print(f"[ok] {post_id} ({wrote} comments) → {out_path}")
            time.sleep(SLEEP_BETWEEN_POSTS)
        except prawcore.exceptions.TooManyRequests as e:
            wait = getattr(e, "sleep_time", 5)
            print(f"[rate] {post_id} sleeping {wait}s")
            time.sleep(wait)
        except (prawcore.exceptions.Forbidden,
                prawcore.exceptions.NotFound,
                prawcore.exceptions.Redirect) as e:
            print(f"[skip] {post_id} {e.__class__.__name__}")
        except Exception as e:
            print(f"[err]  {post_id} {e.__class__.__name__}: {e}")


if __name__ == "__main__":
    main()