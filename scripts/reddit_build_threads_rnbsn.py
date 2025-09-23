# filename: scripts/build_threads_rn-bsn.py
# Purpose: Combine posts CSV + per-post raw comments into LLM-friendly nested threads.
# Inputs:
#   data/reddit/posts/posts_rn-bsn_YYYYMMDD.csv
#   data/reddit/comments/raw/{post_id}.jsonl
# Outputs:
#   data/reddit/comments/threads/{post_id}.json         # nested JSON (LLM-ready)
#   data/reddit/comments/threads/{post_id}.md

import csv, json
from pathlib import Path

# --- Paths (adjust the date) ---
ROOT          = Path(__file__).resolve().parents[1]
POSTS_CSV     = ROOT / "data" / "reddit" / "posts" / "posts_rn-bsn_20250923.csv"
RAW_DIR       = ROOT / "data" / "reddit" / "comments" / "raw"
THREADS_DIR   = ROOT / "data" / "reddit" / "comments" / "threads"
THREADS_DIR.mkdir(parents=True, exist_ok=True)

# Expected posts CSV header:
# post_id,num_comments,title,selftext,created_iso,subreddit_name,permalink

def load_posts(csv_path: Path):
    posts = {}
    with open(csv_path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            pid = row["post_id"].strip()
            posts[pid] = {
                "post_id": pid,
                "title": row.get("title",""),
                "selftext": row.get("selftext",""),
                "permalink": f"https://reddit.com{row.get('permalink','')}",
            }
    return posts

def load_raw_comments(jsonl_path: Path):
    """
    Returns comments in file order to preserve conversational flow from fetch step.
    Raw schema per line:
      {post_id, comment_id, parent_id, depth, body, permalink}
    """
    items = []
    with open(jsonl_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line: continue
            items.append(json.loads(line))
    return items

def build_tree(flat_comments):
    """
    Build nested comment tree without authors/timestamps.
    Keep sibling order as they appeared in the raw file.
    """
    id_to_node = {}
    roots = []

    # create nodes first
    for c in flat_comments:
        node = {
            "comment_id": c["comment_id"],
            "body": c.get("body",""),
            "permalink": c.get("permalink",""),
            "replies": []
        }
        id_to_node[c["comment_id"]] = node
        c["_node"] = node

    # link to parents
    for c in flat_comments:
        parent_id = c.get("parent_id","")
        if parent_id.startswith("t1_"):
            pid = parent_id.split("_", 1)[1]
            parent = id_to_node.get(pid)
            if parent:
                parent["replies"].append(c["_node"])
            else:
                roots.append(c["_node"])  # orphan fallback
        else:
            # parent is the post (t3_<post_id>)
            roots.append(c["_node"])

    return roots

def to_markdown(post_meta, comment_nodes):
    """
    Produce a compact, readable MD for quick manual review.
    Indent replies with bullet nesting.
    """
    lines = []
    lines.append(f"# {post_meta['title']}".strip())
    if post_meta.get("selftext"):
        lines.append("")
        lines.append(post_meta["selftext"])
    lines.append("")
    lines.append(f"Post: {post_meta['permalink']}")
    lines.append("")
    lines.append("## Comments")
    if not comment_nodes:
        lines.append("_No comments_")
        return "\n".join(lines)

    def emit(node, level=0):
        indent = "  " * level
        body = (node.get("body","") or "").replace("\r"," ").strip()
        lines.append(f"{indent}- {body}")
        if node.get("permalink"):
            lines.append(f"{indent}  [link]({node['permalink']})")
        for child in node.get("replies", []):
            emit(child, level+1)

    for n in comment_nodes:
        emit(n, 0)

    return "\n".join(lines)

def main():
    posts = load_posts(POSTS_CSV)

    for pid, meta in posts.items():
        raw_path = RAW_DIR / f"{pid}.jsonl"
        if not raw_path.exists():
            # No comments fetched for this post; still emit a minimal JSON thread file.
            thread = {"post": meta, "comments": []}
            out_json = THREADS_DIR / f"{pid}.json"
            with open(out_json, "w", encoding="utf-8") as f:
                json.dump(thread, f, ensure_ascii=False, indent=2)
            out_md = THREADS_DIR / f"{pid}.md"
            out_md.write_text(to_markdown(meta, []), encoding="utf-8")
            print(f"[warn] missing raw comments for {pid}; wrote empty thread")
            continue

        flat = load_raw_comments(raw_path)
        tree = build_tree(flat)

        # Write JSON
        out_json = THREADS_DIR / f"{pid}.json"
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump({"post": meta, "comments": tree}, f, ensure_ascii=False, indent=2)

        # Write Markdown (handy for quick scans)
        out_md = THREADS_DIR / f"{pid}.md"
        out_md.write_text(to_markdown(meta, tree), encoding="utf-8")

        print(f"[ok] {pid} → {out_json.name}, {out_md.name}")

if __name__ == "__main__":
    main()