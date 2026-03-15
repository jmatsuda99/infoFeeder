from db import init_db
from fetcher import fetch_active_feeds, load_feeds

def main():
    init_db()
    feeds = [f for f in load_feeds() if f.get("is_active", True)]
    print(f"Active feeds: {len(feeds)}")
    count = fetch_active_feeds()
    print(f"Inserted {count} new items")

if __name__ == "__main__":
    main()
