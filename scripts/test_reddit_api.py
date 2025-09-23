import os
from pathlib import Path
from dotenv import load_dotenv
import praw


ENV_PATH = "/.env"

def main():
    if not Path(ENV_PATH).exists():
        raise FileNotFoundError(f".env not found at {ENV_PATH}")

    load_dotenv(ENV_PATH)

    reddit = praw.Reddit(
        client_id=os.getenv("REDDIT_CLIENT_ID"),
        client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
        user_agent=os.getenv("REDDIT_USER_AGENT"),
        username=os.getenv("REDDIT_USERNAME"),
        password=os.getenv("REDDIT_PASSWORD"),
    )

    # Test: fetch 3 newest posts from r/WGU
    print("Testing Reddit API...")
    for post in reddit.subreddit("WGU").new(limit=3):
        print(f"- {post.id} | {post.title[:80]}")

if __name__ == "__main__":
    main()