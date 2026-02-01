import feedparser
import random

RSS_SOURCES = [
    "http://feeds.bbci.co.uk/news/world/rss.xml",
    "https://www.sciencedaily.com/rss/top/science.xml",
    "https://www.wired.com/feed/category/science/latest/rss",
    "https://futurism.com/feed",
    "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
]

def fetch_all_news(limit=100):
    all_headlines = []
    for url in RSS_SOURCES:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                all_headlines.append(entry.title.strip())
        except Exception as e:
            print(f"RSS Error ({url}): {e}")
            continue
    
    if not all_headlines:
        return []

    random.shuffle(all_headlines)
    return all_headlines[:limit]

def get_top_3_separate_news():
    """
    Returns 3 distinct news headlines for the video generation.
    Does NOT use LLM to select locally (for speed/simplicity), 
    just picks 3 random distinct ones from reputable sources is often enough, 
    but we can add simple heuristic filtering.
    """
    headlines = fetch_all_news(limit=50)
    if len(headlines) < 3:
        return headlines # Return whatever we have
    
    # Simple selection: Just take top 3 distinct ones (already shuffled)
    # We could add LLM selection here if needed, but 'fetch_all_news' returns random shuffle.
    return headlines[:3]
