# scripts/build_home_view.py
import json
from pathlib import Path
from datetime import datetime
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
QUERY = '"RN to BSN" OR RN-BSN OR RNBSN OR "RN BSN" OR "BSN RN"'

def latest_run_dir(base: Path) -> Path:
    runs = [p for p in base.iterdir() if p.is_dir()]
    if not runs:
        raise SystemExit(f"No runs under {base}")
    try:
        runs.sort(key=lambda p: datetime.strptime(p.name, "%Y-%m-%d"), reverse=True)
    except Exception:
        runs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return runs[0]

def latest_posts_csv(posts_dir: Path) -> Path:
    csvs = sorted(posts_dir.glob("posts_*.csv"))
    if not csvs:
        raise SystemExit(f"No posts_*.csv under {posts_dir}")
    return csvs[-1]

def load_per_post_json(per_post_dir: Path):
    data = {}
    for fp in per_post_dir.glob("*.json"):
        try:
            obj = json.loads(fp.read_text())
            pid = obj.get("post", {}).get("post_id", fp.stem)
            data[pid] = obj
        except Exception:
            pass
    return data

def humanize_date(iso_str: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        # Use %-d for Unix, %#d for Windows; fall back to %d
        try:
            return dt.strftime("%b %-d, %Y")
        except ValueError:
            try:
                return dt.strftime("%b %#d, %Y")
            except ValueError:
                return dt.strftime("%b %d, %Y")
    except Exception:
        return iso_str

def comment_link(subreddit: str, post_id: str, comment_id: str, permalink: str) -> str:
    if comment_id == "post":
        return f"[link]({permalink})"
    return f"[link](https://reddit.com/r/{subreddit}/comments/{post_id}/_/{comment_id}/)"

def truncate_text(text: str, limit: int = 240) -> str:
    if not isinstance(text, str) or not text.strip():
        return ""
    t = " ".join(text.split())
    if len(t) <= limit:
        return t
    return t[:limit].rsplit(" ", 1)[0] + "…"

def render_markdown(run_dir: Path, posts_df: pd.DataFrame, per_post: dict) -> str:
    lines = []
    # Header
    lines.append("# Reddit post analysis for WGU-RN-BSN degree\n")
    lines.append(f"QUERY = {QUERY}  ")
    lines.append(f"Run date: {run_dir.name}  ")
    lines.append(f"Source posts CSV: `{posts_df.attrs.get('source_csv','')}`  ")
    lines.append("Sorted by number of comments (desc).\n")

    # Stub sections
    lines.append("## Introduction to the posts\n")
    lines.append("_Short overview of what the collected posts cover. Replace this stub with a brief narrative once you review the data._\n")
    lines.append("## Post analysis\n")
    lines.append("_Key patterns in post topics, timing, and authorship. Replace this stub with bullet points or a paragraph summary._\n")
    lines.append("## Comment analysis\n")
    lines.append("_Themes and sentiments from comments. Replace this stub with highlights and notable disagreements._\n")

    # Per-post list (no table)
    for _, r in posts_df.sort_values("num_comments", ascending=False).iterrows():
        pid = r.post_id
        j = per_post.get(pid, {})
        reasons = j.get("reasons_to_choose", []) or []
        comments = j.get("comments", []) or []
        highlights = j.get("verbatim_highlights", []) or []
        summary = j.get("conversation_summary", "") or ""

        # Slightly smaller title
        lines.append(f"### {r.title}")
        lines.append(
            f"post_id: `{pid}`  |  comments: {r.num_comments}  |  "
            f"created: {humanize_date(r.created_iso)}  |  subreddit: {r.subreddit_name}"
        )
        lines.append(f"Links: [reddit]({r.permalink})")
        # Truncated selftext excerpt
        excerpt = truncate_text(getattr(r, "selftext", ""))
        if excerpt:
            lines.append(f"\n> {excerpt}\n")

        # Single compact dropdown
        lines.append("<details><summary>Expand details</summary>\n")

        if reasons:
            lines.append("**Reasons to choose**")
            for item in reasons:
                lines.append(f"- {item.get('summary','')}")
                for ev in item.get("evidence", []):
                    cid = ev.get("comment_id", "")
                    lines.append(f"  Evidence: {comment_link(r.subreddit_name, pid, cid, r.permalink)}")
            lines.append("")

        if comments:
            lines.append("**Other notable points**")
            for c in comments[:6]:
                lines.append(f"- {c.get('summary','')}")
            if len(comments) > 6:
                lines.append(f"- …and {len(comments)-6} more")
            lines.append("")

        lines.append("**Verbatim highlights**")
        if highlights:
            for h in highlights[:6]:
                cid = h.get("comment_id", "")
                link = comment_link(r.subreddit_name, pid, cid, r.permalink)
                lines.append(f"- {h.get('text','')}  \n  {link}")
            if len(highlights) > 6:
                lines.append(f"- …and {len(highlights)-6} more")
        else:
            lines.append("_None_")
        lines.append("")

        lines.append("**Conversation summary**")
        lines.append(summary if summary else "_No summary_")
        lines.append("\n</details>\n")

    return "\n".join(lines)

def main():
    outputs_base = PROJECT_ROOT / "output" / "reddit"
    run_dir = latest_run_dir(outputs_base)
    per_post_dir = run_dir / "per_post"

    posts_csv_dir = PROJECT_ROOT / "data" / "reddit" / "posts"
    posts_csv = latest_posts_csv(posts_csv_dir)
    df = pd.read_csv(posts_csv, dtype={"post_id": str})
    df.attrs["source_csv"] = posts_csv.as_posix()

    # ensure selftext column exists
    if "selftext" not in df.columns:
        df["selftext"] = ""

    per_post = load_per_post_json(per_post_dir)
    md = render_markdown(run_dir, df, per_post)
    out_md = run_dir / "rn-bsn-analysis.md"
    out_md.write_text(md, encoding="utf-8")
    print(f"Wrote {out_md}")

if __name__ == "__main__":
    main()