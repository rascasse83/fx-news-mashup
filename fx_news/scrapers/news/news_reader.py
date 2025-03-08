import os
import re
import glob
import pandas as pd
from datetime import datetime

def get_local_news_articles(base_dir="fx_news/scrapers/news", currency_pairs=None, days_limit=7, debug=True):
    """
    Reads news articles from local text files in the specified directory structure.
    
    Args:
        base_dir (str): Base directory containing news folders
        currency_pairs (list): List of currency pairs to filter for (e.g. [('EUR', 'USD'), ('GBP', 'USD')])
        days_limit (int): Number of days to look back for articles
        debug (bool): Whether to print debug information
        
    Returns:
        pd.DataFrame: DataFrame containing news articles with metadata
    """
    articles = []
    
    if debug:
        print(f"Searching for news in: {base_dir}")
        print(f"Looking for currency pairs: {currency_pairs}")
    
    # Create a regex pattern to match currency pairs if provided
    pair_pattern = None
    if currency_pairs:
        # Convert currency pairs list to lowercase patterns
        pair_strings = []
        for base, quote in currency_pairs:
            # Match both lowercase and uppercase versions
            base_lc, quote_lc = base.lower(), quote.lower()
            pair_strings.append(f"{base_lc}_{quote_lc}")
            pair_strings.append(f"{base.upper()}_{quote.upper()}")
        
        if debug:
            print(f"Pair patterns to match: {pair_strings}")
        
        pair_pattern = re.compile(r'(' + '|'.join(pair_strings) + r')\.txt$', re.IGNORECASE)
    
    # Calculate cutoff date for filtering by date
    today = datetime.now()
    cutoff_date = today - pd.Timedelta(days=days_limit)
    
    # Check if base_dir is a directory or a file
    if os.path.isfile(base_dir):
        if debug:
            print(f"Input path is a file: {base_dir}")
        # Process a single file
        file_path = base_dir
        process_single_file(file_path, pair_pattern, cutoff_date, articles, debug)
    elif os.path.isdir(base_dir):
        # Process directory
        # Check if this is a source directory with txt files or a parent directory
        txt_files = glob.glob(os.path.join(base_dir, "*.txt"))
        
        if txt_files:
            # This is a source directory itself
            if debug:
                print(f"Found {len(txt_files)} txt files in {base_dir}")
            
            source = os.path.basename(base_dir)
            for file_path in txt_files:
                process_single_file(file_path, pair_pattern, cutoff_date, articles, debug, source)
        else:
            # This is a parent directory, check subdirectories
            source_dirs = [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]
            
            if debug:
                print(f"Found subdirectories: {source_dirs}")
            
            for source in source_dirs:
                source_path = os.path.join(base_dir, source)
                files = glob.glob(os.path.join(source_path, "*.txt"))
                
                if debug:
                    print(f"Found {len(files)} txt files in {source_path}")
                
                for file_path in files:
                    process_single_file(file_path, pair_pattern, cutoff_date, articles, debug, source)
    else:
        if debug:
            print(f"Path does not exist: {base_dir}")
    
    # Convert to DataFrame and sort by date (newest first)
    if articles:
        df = pd.DataFrame(articles)
        df = df.sort_values('date', ascending=False)
        if debug:
            print(f"Returning DataFrame with {len(df)} articles")
        return df
    else:
        if debug:
            print("No articles found, returning empty DataFrame")
        # Return empty DataFrame with expected columns
        return pd.DataFrame(columns=['title', 'text', 'date', 'timestamp', 'source', 'currency', 'currency_pairs', 'file_path', 'filename'])

def process_single_file(file_path, pair_pattern, cutoff_date, articles, debug=False, source=None):
    """Helper function to process a single news file"""
    filename = os.path.basename(file_path)
    
    if debug:
        print(f"Processing file: {filename}")
    
    # Check if file matches currency pair filter
    if pair_pattern:
        match = pair_pattern.search(filename)
        if not match:
            if debug:
                print(f"  Skipping {filename} - doesn't match any requested currency pair")
            return
        if debug:
            print(f"  Matched pattern: {match.group(0)}")
    
    # Extract date from filename if it follows the pattern article_YYYYMMDD_HHMMSS_currency_pair.txt
    date_match = re.search(r'article_(\d{8})_(\d{6})_', filename)
    if date_match:
        date_str = date_match.group(1)
        time_str = date_match.group(2)
        try:
            article_date = datetime.strptime(f"{date_str}_{time_str}", "%Y%m%d_%H%M%S")
            
            # Skip if article is older than the cutoff date
            if article_date < cutoff_date:
                if debug:
                    print(f"  Skipping {filename} - older than cutoff date")
                return
        except ValueError as e:
            if debug:
                print(f"  Warning: Couldn't parse date from {filename}: {str(e)}")
            # Use file modification date as fallback
            article_date = datetime.fromtimestamp(os.path.getmtime(file_path))
    else:
        if debug:
            print(f"  No date pattern found in {filename}, using file modification date")
        # Use file modification date if filename doesn't contain date
        article_date = datetime.fromtimestamp(os.path.getmtime(file_path))
    
    # Extract currency pair from filename - try multiple patterns to be flexible
    # First try standard pattern with lowercase
    pair_match = re.search(r'_([a-z]{3})_([a-z]{3})\.txt$', filename.lower())
    if not pair_match:
        # Try with uppercase
        pair_match = re.search(r'_([A-Z]{3})_([A-Z]{3})\.txt$', filename)
    
    if pair_match:
        base_currency = pair_match.group(1).upper()
        quote_currency = pair_match.group(2).upper()
        currency_pair = f"{base_currency}/{quote_currency}"
        if debug:
            print(f"  Found currency pair: {currency_pair}")
    else:
        if debug:
            print(f"  Warning: Couldn't extract currency pair from {filename}")
        # Try to extract from filename using simple split
        parts = filename.split('_')
        if len(parts) >= 4:
            try:
                base_currency = parts[-2].upper()
                quote_currency = parts[-1].split('.')[0].upper()
                if len(base_currency) == 3 and len(quote_currency) == 3:
                    currency_pair = f"{base_currency}/{quote_currency}"
                    if debug:
                        print(f"  Extracted pair from parts: {currency_pair}")
                else:
                    currency_pair = "Unknown"
            except:
                currency_pair = "Unknown"
        else:
            currency_pair = "Unknown"
    
    # Read file content
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract title and text
        # Assuming first line is title, rest is content
        lines = content.split('\n')
        title = lines[0].strip() if lines else "Untitled"
        text = '\n'.join(lines[1:]).strip() if len(lines) > 1 else content
        
        if debug:
            print(f"  Title: '{title[:30]}...' ({len(title)} chars)")
            print(f"  Content: {len(text)} chars")
        
        # If source wasn't provided, extract from directory structure
        if source is None:
            source = os.path.basename(os.path.dirname(file_path))
        
        # Add to articles list
        articles.append({
            'title': title,
            'text': text,
            'date': article_date,
            'timestamp': article_date,
            'source': source,
            'currency': currency_pair,
            'currency_pairs': {currency_pair},
            'file_path': file_path,
            'filename': filename
        })
        
        if debug:
            print(f"  Added article: {filename} ({currency_pair}, {article_date})")
    
    except Exception as e:
        if debug:
            print(f"  Error reading file {file_path}: {str(e)}")

def get_news_for_currency_pair(base, quote, base_dir="fx_news/scrapers/news", days_limit=7, debug=True):
    """
    Get news articles specific to a currency pair.
    
    Args:
        base (str): Base currency (e.g., 'EUR')
        quote (str): Quote currency (e.g., 'USD')
        base_dir (str): Base directory for news articles
        days_limit (int): Number of days to look back
        debug (bool): Whether to print debug information
        
    Returns:
        list: List of news article dictionaries
    """
    if debug:
        print(f"Getting news for {base}/{quote} from {base_dir}")
    
    currency_pairs = [(base, quote)]
    df = get_local_news_articles(base_dir, currency_pairs, days_limit, debug)
    
    if df.empty:
        if debug:
            print("No articles found in DataFrame")
        return []
    
    # Convert DataFrame rows to dictionaries
    news_list = df.to_dict('records')
    
    if debug:
        print(f"Found {len(news_list)} articles")
    
    # Add sentiment analysis (placeholder - you'd integrate your actual sentiment model here)
    for item in news_list:
        # Simple placeholder sentiment analysis
        # Replace with your actual sentiment analysis logic
        if 'positive' in item['text'].lower() or 'rise' in item['text'].lower() or 'gain' in item['text'].lower():
            item['sentiment'] = 'positive'
            item['score'] = 0.75
        elif 'negative' in item['text'].lower() or 'fall' in item['text'].lower() or 'drop' in item['text'].lower():
            item['sentiment'] = 'negative'
            item['score'] = -0.75
        else:
            item['sentiment'] = 'neutral'
            item['score'] = 0.0
    
    return news_list


# For testing
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 3:
        base = sys.argv[1]
        quote = sys.argv[2]
        directory = sys.argv[3]
    else:
        base = 'USD'
        quote = 'CAD'
        directory = './fx_news/scrapers/news/yahoo'
    
    print(f"Testing with {base}/{quote} in directory {directory}")
    result = get_news_for_currency_pair(base, quote, directory)
    
    print(f"Found {len(result)} articles:")
    for i, item in enumerate(result):
        print(f"\nArticle {i+1}:")
        print(f"  Title: {item.get('title', 'No title')[:50]}...")
        print(f"  Source: {item.get('source', 'Unknown')}")
        print(f"  Date: {item.get('date', 'Unknown date')}")
        print(f"  Currency: {item.get('currency', 'Unknown')}")
        print(f"  Sentiment: {item.get('sentiment', 'Unknown')} ({item.get('score', 'Unknown')})")
        print(f"  Text length: {len(item.get('text', ''))}")
        print(f"  File: {item.get('filename', 'Unknown')}")