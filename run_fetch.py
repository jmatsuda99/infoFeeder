
from db import init_db
from fetcher import fetch_active_feeds
def main():
    init_db()
    c=fetch_active_feeds()
    print(f"Inserted {c} new items")
if __name__=="__main__":
    main()
