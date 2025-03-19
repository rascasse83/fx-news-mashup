import sys
import os

# Add the project root to the Python path to allow imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

try:
    from fx_news.scrapers.article_downloader import extract_article_id_from_url
    print("Successfully imported extract_article_id_from_url function")
except ImportError as e:
    print(f"Error importing extract_article_id_from_url: {e}")
    print("Make sure the function is properly defined in article_downloader.py")
    sys.exit(1)

def test_article_id_extraction():
    """Test the article ID extraction function with sample URLs"""
    test_urls = [
        "https://finance.yahoo.com/news/fed-signals-pending-interest-rate-cuts-20250318.html",
        "https://finance.yahoo.com/news/dollar-edges-higher-fed-meeting-015055115.html",
        "https://www.reuters.com/markets/currencies/dollar-gains-against-euro-yen-markets-focus-fed-meeting-09-18-2025/",
        "https://www.cnbc.com/2025/03/18/goldman-sachs-ceo-david-solomon-federal-reserve-interest-rate-cut.html",
        "https://finance.yahoo.com/video/market-volatility-20250318.html",
        "https://example.com/some-random-article",
        ""  # Test empty URL
    ]
    
    print("\nTesting Article ID Extraction:\n")
    print(f"{'URL':<80} | {'Extracted ID'}")
    print("-" * 100)
    
    for url in test_urls:
        try:
            article_id = extract_article_id_from_url(url)
            print(f"{url:<80} | {article_id}")
        except Exception as e:
            print(f"{url:<80} | Error: {str(e)}")
    
    print("\nTest completed.")

if __name__ == "__main__":
    test_article_id_extraction()