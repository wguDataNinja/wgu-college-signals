# filename: scripts/reddit_fetch_rnbsn_posts.py
# Purpose: search RN-BSN terms across WGU-related subs; handle closed/private subs; text-only CSV.

import os, csv, re, time
from pathlib import Path
from datetime import datetime, timezone
import praw
import prawcore

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH  = ROOT / ".env"
SUBS_PATH = ROOT / "data" / "wgu_subreddits.csv"
OUT_DIR   = ROOT / "data" / "reddit" / "posts"
OUT_FILE  = OUT_DIR / f"posts_{datetime.now().strftime('%Y%m%d')}.csv"

QUERY = '"RN to BSN" OR RN-BSN OR RNBSN OR "RN BSN" OR "BSN RN"'
LIMIT = 100
SLEEP_SECONDS = 0.5


POSTS_HEADER = [
    "post_id","num_comments","title","selftext","created_iso","subreddit_name","permalink"
]

def load_env_file(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()

def reddit_client():
    return praw.Reddit(
        client_id=os.getenv("REDDIT_CLIENT_ID"),
        client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
        user_agent=os.getenv("REDDIT_USER_AGENT"),
        username=os.getenv("REDDIT_USERNAME"),
        password=os.getenv("REDDIT_PASSWORD"),
    )

def iso(ts):
    return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat().replace("+00:00","Z")

def clean(s):
    if s is None: return ""
    s = s.replace("\r\n","\n").replace("\r","\n")
    s = re.sub(r"\s+", " ", s).strip()
    return s

def load_subs(csv_path):
    subs = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.reader(f):
            if row and row[0].strip():
                subs.append(row[0].strip())
    return subs

def write_rows(path, rows, header):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)

def search_subreddit_safe(reddit, sub_name, query, limit):
    """Generator: yields submissions or returns empty on 404/403/quarantine."""
    try:
        sr = reddit.subreddit(sub_name)
        try:
            sr.quaran.opt_in()
        except Exception:
            pass
        for p in sr.search(query, sort="new", time_filter="year", limit=limit):
            yield p
    except (prawcore.exceptions.NotFound,
            prawcore.exceptions.Forbidden,
            prawcore.exceptions.Redirect) as e:
        print(f"[skip] r/{sub_name} {e.__class__.__name__}")
        return
    except prawcore.exceptions.TooManyRequests as e:
        wait = getattr(e, "sleep_time", 5)
        print(f"[rate] r/{sub_name} sleeping {wait}s")
        time.sleep(wait)
        try:
            for p in reddit.subreddit(sub_name).search(query, sort="new", time_filter="year", limit=limit):
                yield p
        except Exception as e2:
            print(f"[skip] r/{sub_name} after rate limit: {e2.__class__.__name__}")
            return
    except Exception as e:
        print(f"[skip] r/{sub_name} unexpected: {e.__class__.__name__}")
        return

def main():
    if not ENV_PATH.exists():
        raise FileNotFoundError(f".env not found at {ENV_PATH}")
    load_env_file(ENV_PATH)
    reddit = reddit_client()

    subs = load_subs(SUBS_PATH)
    dedup = {}
    total_rows = 0

    for sub in subs:
        sub_rows = 0
        for p in search_subreddit_safe(reddit, sub, QUERY, LIMIT):
            row = [
                p.id,
                int(p.num_comments),
                clean(p.title),
                clean(p.selftext),
                iso(p.created_utc),
                sub,
                p.permalink,
            ]
            dedup[p.id] = row
            sub_rows += 1
        total_rows += sub_rows
        print(f"[{sub}] {sub_rows}")
        time.sleep(SLEEP_SECONDS)

    # sort by num_comments desc
    final_rows = sorted(dedup.values(), key=lambda r: r[1], reverse=True)
    write_rows(OUT_FILE, final_rows, POSTS_HEADER)
    print(f"[done] wrote {len(final_rows)} unique rows → {OUT_FILE} (raw seen {total_rows})")

if __name__ == "__main__":
    main()