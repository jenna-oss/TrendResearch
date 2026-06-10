import json
import os
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from config import OUTPUT_DIR


def collect_1stdibs_survey():
    """Scrape 1stDibs newsroom for Interior Designer Trends Survey."""
    print("[1stDibs] Starting survey collection...")

    output_file = os.path.join(OUTPUT_DIR, "1stdibs_survey.json")

    # Check if already collected for current year
    current_year = datetime.utcnow().year
    if os.path.exists(output_file):
        try:
            with open(output_file) as f:
                existing = json.load(f)
                if existing.get("year") == current_year and existing.get("found"):
                    print(f"[1stDibs] Survey already collected for {current_year} — skipping")
                    return existing
        except Exception:
            pass

    # Try to find and scrape the survey
    try:
        survey_data = _scrape_survey()

        output = {
            "collected_at": datetime.utcnow().isoformat(),
            "year": current_year,
            "found": survey_data["found"],
            "source_url": survey_data.get("source_url", ""),
            "title": survey_data.get("title", ""),
            "full_text": survey_data.get("full_text", ""),
            "key_findings": []
        }

        if "error" in survey_data:
            output["error"] = survey_data["error"]

        with open(output_file, "w") as f:
            json.dump(output, f, indent=2)
        # TODO: write to Supabase instead of JSON

        if output["found"]:
            word_count = len(output["full_text"].split())
            print(f"[1stDibs] Survey found — {word_count} words extracted")
        else:
            print(f"[1stDibs] Survey not found — using fallback")

        return output

    except Exception as e:
        print(f"[1stDibs] Error during collection: {str(e)}")
        output = {
            "collected_at": datetime.utcnow().isoformat(),
            "year": current_year,
            "found": False,
            "source_url": "",
            "title": "",
            "full_text": "",
            "key_findings": [],
            "error": str(e)
        }

        with open(output_file, "w") as f:
            json.dump(output, f, indent=2)
        # TODO: write to Supabase instead of JSON

        return output


def _scrape_survey():
    """Scrape 1stDibs pages for survey article."""
    pages_to_check = [
        "https://www.1stdibs.com/introspective-magazine/",
        "https://www.1stdibs.com/press/"
    ]

    for page_url in pages_to_check:
        try:
            response = requests.get(page_url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")

            # Look for article links
            articles = soup.find_all(["a", "h2", "h3", "article"])

            for article in articles:
                # Get text content
                text = article.get_text().lower()
                title = article.get("title", "") or article.get_text()

                # Check for matching patterns
                has_designer_trend = "designer" in text and "trend" in text
                has_interior_survey = "interior design" in text and "survey" in text
                has_2026_trend = "2026" in text and "trend" in text

                if has_designer_trend or has_interior_survey or has_2026_trend:
                    # Found a matching article, try to get its link
                    link = article.get("href")

                    if link:
                        # Make it absolute if needed
                        if link.startswith("/"):
                            link = "https://www.1stdibs.com" + link
                        elif not link.startswith("http"):
                            link = page_url.rstrip("/") + "/" + link

                        # Fetch the full article
                        try:
                            article_response = requests.get(link, timeout=10)
                            article_response.raise_for_status()
                            article_soup = BeautifulSoup(article_response.content, "html.parser")

                            # Extract all paragraph text
                            paragraphs = article_soup.find_all("p")
                            full_text = " ".join([p.get_text() for p in paragraphs])

                            if full_text:
                                return {
                                    "found": True,
                                    "source_url": link,
                                    "title": title.strip() if title else "1stDibs Designer Survey",
                                    "full_text": full_text
                                }
                        except Exception:
                            continue

        except Exception as e:
            continue

    # No article found
    return {
        "found": False,
        "source_url": "",
        "title": "",
        "full_text": ""
    }
