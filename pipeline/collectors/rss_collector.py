import json
import feedparser
from datetime import datetime, timedelta
from anthropic import Anthropic
from config import LOOKBACK_DAYS, OUTPUT_DIR, ANTHROPIC_API_KEY, CLAUDE_MODEL
import os

RSS_FEEDS = [
    {
        "url": "https://www.dezeen.com/feed/",
        "source": "Dezeen",
        "verticals": ["architect", "interior"]
    },
    {
        "url": "https://www.architecturaldigest.com/feed/rss",
        "source": "Architectural Digest",
        "verticals": ["interior", "architect"]
    },
    {
        "url": "https://www.houzz.com/rss/ideabooks",
        "source": "Houzz",
        "verticals": ["interior", "builder"]
    },
    {
        "url": "https://www.wallpaper.com/rss",
        "source": "Wallpaper*",
        "verticals": ["interior", "architect"]
    },
    {
        "url": "https://www.asla.org/rss",
        "source": "ASLA",
        "verticals": ["landscape"]
    },
    {
        "url": "https://www.builderonline.com/feed",
        "source": "Builder Magazine",
        "verticals": ["builder"]
    },
    {
        "url": "https://www.probuilder.com/rss",
        "source": "Pro Builder",
        "verticals": ["builder"]
    },
    {
        "url": "https://landscapearchitecturemagazine.org/feed",
        "source": "Landscape Architecture Magazine",
        "verticals": ["landscape"]
    },
]


def collect_rss_articles():
    """Fetch articles from RSS feeds and filter by Claude relevance."""
    print("[RSS] Starting feed collection...")

    cutoff_date = datetime.utcnow() - timedelta(days=LOOKBACK_DAYS)
    all_articles = []
    feeds_failed = []

    for feed_config in RSS_FEEDS:
        try:
            print(f"  Fetching {feed_config['source']}...", end=" ")
            feed = feedparser.parse(feed_config["url"])

            if feed.bozo:
                print(f"(warning: {feed.bozo_exception})")
            else:
                print(f"({len(feed.entries)} entries)")

            for entry in feed.entries:
                published_parsed = entry.get("published_parsed")
                if not published_parsed:
                    continue

                published_date = datetime(*published_parsed[:6])
                if published_date < cutoff_date:
                    continue

                article = {
                    "title": entry.get("title", ""),
                    "summary": entry.get("summary", "")[:500],
                    "link": entry.get("link", ""),
                    "published_date": published_date.isoformat(),
                    "source": feed_config["source"],
                    "verticals": feed_config["verticals"],
                }
                all_articles.append(article)

        except Exception as e:
            print(f"ERROR: {str(e)}")
            feeds_failed.append({
                "url": feed_config["url"],
                "error": str(e)
            })

    print(f"[RSS] Collected {len(all_articles)} raw articles")

    if not all_articles:
        print("[RSS] No articles to filter, returning empty")
        return {
            "collected_at": datetime.utcnow().isoformat(),
            "source_count": len(RSS_FEEDS),
            "article_count": 0,
            "articles": []
        }

    print(f"[RSS] Filtering {len(all_articles)} articles with Claude...")
    filtered_articles = filter_articles_with_claude(all_articles)

    output = {
        "collected_at": datetime.utcnow().isoformat(),
        "source_count": len(RSS_FEEDS),
        "article_count": len(filtered_articles),
        "articles": filtered_articles
    }

    with open(os.path.join(OUTPUT_DIR, "rss_articles.json"), "w") as f:
        json.dump(output, f, indent=2)
    # TODO: write to Supabase instead of JSON

    print(f"[RSS] Complete: {len(filtered_articles)} articles passed filter")
    return output


def filter_articles_with_claude(articles):
    """Send articles to Claude for relevance filtering."""
    client = Anthropic()

    article_list = "\n".join([
        f"{i+1}. Title: {a['title']}\n   Summary: {a['summary']}"
        for i, a in enumerate(articles)
    ])

    system_prompt = """You are filtering RSS articles for relevance to a content research
pipeline serving luxury interior designers, residential architects,
landscape architects, and custom home builders.

Score each article 1-10:
10 = directly about design trends, materials, style, architecture,
     landscape, building, or luxury living
5  = adjacent signal (art, fashion, hospitality, sustainability)
     useful for trend context
1  = irrelevant (tech news, politics, sports, general lifestyle)

Return ONLY a JSON array, one object per article, in input order.
Each object:
{
  "title": "exact title from input",
  "score": 8,
  "trend_tags": ["material", "color", "texture"],
  "verticals": ["interior", "architect"]
}

No preamble. No markdown. No explanation. JSON array only."""

    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=4000,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": article_list
                }
            ]
        )

        response_text = response.content[0].text.strip()
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
            response_text = response_text.strip()
        if response_text.endswith("```"):
            response_text = response_text[:-3].strip()

        scores = json.loads(response_text)
    except Exception as e:
        print(f"[RSS] Claude filtering failed: {str(e)}, keeping all articles")
        return articles

    filtered = []
    for i, article in enumerate(articles):
        if i < len(scores):
            score_obj = scores[i]
            if score_obj.get("score", 0) >= 7:
                article["relevance_score"] = score_obj.get("score", 0)
                article["trend_tags"] = score_obj.get("trend_tags", [])
                filtered.append(article)

    return filtered
