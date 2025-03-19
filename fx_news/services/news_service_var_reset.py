import streamlit as st
import os
import glob
import re
from datetime import datetime, timedelta
import json

def force_news_reset_and_load(base_folder="fx_news/scrapers/news/yahoo", max_days=30):
    """
    Force-reset all news-related session state and manually load news files.
    This bypasses the regular loading mechanism to diagnose issues.
    
    Args:
        base_folder: Path to news files folder
        max_days: Maximum age of news to load in days
        
    Returns:
        Dictionary with results
    """
    results = {
        "timestamp": datetime.now().isoformat(),
        "reset_keys": [],
        "files_loaded": [],
        "total_found": 0,
        "total_loaded": 0,
        "market_type": st.session_state.get("market_type", "Unknown"),
        "error": None
    }
    
    try:
        # Step 1: Reset all news-related session state
        news_keys = [
            'fx_news', 'crypto_news', 'indices_news', 'cached_news',
            'last_fx_news_fetch', 'last_crypto_news_fetch', 'last_indices_news_fetch', 
            'last_news_fetch', 'next_fx_news_refresh_time', 'next_crypto_news_refresh_time',
            'next_indices_news_refresh_time', 'disk_news_loaded'
        ]
        
        for key in news_keys:
            if key in st.session_state:
                # Record the original value for lists
                if isinstance(st.session_state[key], list):
                    results[f"original_{key}_count"] = len(st.session_state[key])
                
                # Reset the key
                if key.startswith('last_') or key.startswith('next_'):
                    st.session_state[key] = None
                elif key.endswith('_news'):
                    st.session_state[key] = []
                elif key == 'disk_news_loaded':
                    st.session_state[key] = False
                    
                results["reset_keys"].append(key)
        
        # Step 2: Force reset the SESSION_PROCESSED_TIMESTAMPS and SESSION_PROCESSED_URLS
        # Note: This is a global variable in the article_downloader.py file
        # We can't directly modify it, so we note that manual intervention might be needed
        results["note"] = "SESSION_PROCESSED_TIMESTAMPS and SESSION_PROCESSED_URLS need manual reset"
        
        # Step 3: Manually load news files from disk
        if not os.path.exists(base_folder):
            results["folder_exists"] = False
            results["error"] = f"Folder not found: {base_folder}"
            return results
            
        results["folder_exists"] = True
        
        # Calculate cutoff date
        cutoff_date = datetime.now() - timedelta(days=max_days)
        cutoff_timestamp = int(cutoff_date.timestamp())
        results["cutoff_date"] = cutoff_date.isoformat()
        
        # Find all news files
        all_files = glob.glob(os.path.join(base_folder, "*.txt"))
        results["total_found"] = len(all_files)
        
        # Load each file
        loaded_news = []
        for file_path in all_files:
            try:
                filename = os.path.basename(file_path)
                
                # Extract timestamp from filename
                timestamp_match = re.search(r'article_(\d{10})_', filename)
                if not timestamp_match:
                    continue
                    
                file_timestamp = int(timestamp_match.group(1))
                
                # Skip if too old
                if file_timestamp < cutoff_timestamp:
                    continue
                
                # Read file content
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Extract title
                title_match = re.search(r'^# (.+)$', content, re.MULTILINE)
                title = title_match.group(1).strip() if title_match else filename
                
                # Extract source URL
                source_match = re.search(r'^Source: (.+)$', content, re.MULTILINE)
                url = source_match.group(1).strip() if source_match else ""
                
                # Default source based on URL
                source = "Yahoo Finance"  # Default
                if "bloomberg" in url.lower():
                    source = "Bloomberg"
                elif "reuters" in url.lower():
                    source = "Reuters"
                elif "cnbc" in url.lower():
                    source = "CNBC"
                
                # Extract summary
                summary_match = re.search(r'SUMMARY:\s(.*?)(?:\n\n|\Z)', content, re.DOTALL)
                summary = summary_match.group(1).strip() if summary_match else ""
                
                # Extract sentiment if available
                sentiment = "neutral"  # Default
                sentiment_match = re.search(r'SENTIMENT:\s(.*?)$', content, re.MULTILINE)
                if sentiment_match:
                    sentiment = sentiment_match.group(1).strip()
                
                # Extract score if available
                score = 0.0  # Default
                score_match = re.search(r'SCORE:\s([-\d\.]+)$', content, re.MULTILINE)
                if score_match:
                    try:
                        score = float(score_match.group(1).strip())
                    except:
                        pass
                
                # Extract currency pair from filename
                currency_pair_match = re.search(r'article_\d+_([a-zA-Z0-9_]+).txt$', filename.lower())
                if currency_pair_match:
                    symbol = currency_pair_match.group(1)
                    
                    # Special handling for different market types
                    market_type = st.session_state.get("market_type", "FX")
                    
                    # For indices
                    if market_type == "Indices" and (symbol.startswith('^') or 
                                                     symbol in ["dji", "gspc", "ixic", "ftse", "gdaxi", "fchi", "n225"]):
                        indices_map = {
                            'dji': 'Dow Jones',
                            'gspc': 'S&P 500',
                            'ixic': 'NASDAQ',
                            'ftse': 'FTSE 100',
                            'gdaxi': 'DAX',
                            'fchi': 'CAC 40',
                            'n225': 'Nikkei 225'
                        }
                        currency = indices_map.get(symbol.lower(), symbol.upper())
                        currency_pairs = {currency}
                        is_indices = True
                        is_fx = False
                        is_crypto = False
                        is_market = False
                    
                    # For crypto
                    elif market_type == "Crypto" and any(c in symbol.upper() for c in 
                                                        ["BTC", "ETH", "XRP", "SOL", "BNB", "ADA", "DOGE", "DOT"]):
                        parts = symbol.split('_')
                        base = parts[0].upper()
                        quote = parts[1].upper() if len(parts) > 1 else "USD"
                        currency = f"{base}/{quote}"
                        currency_pairs = {currency}
                        is_indices = False
                        is_fx = False
                        is_crypto = True
                        is_market = False
                    
                    # For FX
                    elif market_type == "FX":
                        parts = symbol.split('_')
                        base = parts[0].upper()
                        quote = parts[1].upper() if len(parts) > 1 else ""
                        
                        if quote:
                            currency = f"{base}/{quote}"
                            currency_pairs = {currency}
                        else:
                            currency = base
                            currency_pairs = {currency}
                            
                        is_indices = False
                        is_fx = True
                        is_crypto = False
                        is_market = False
                    
                    # General market news
                    else:
                        currency = "Market"
                        currency_pairs = {"Market"}
                        is_indices = False
                        is_fx = False
                        is_crypto = False
                        is_market = True
                else:
                    # If can't determine from filename, use generic
                    currency = "Market"
                    currency_pairs = {"Market"}
                    is_indices = False
                    is_fx = False
                    is_crypto = False
                    is_market = True
                
                # Create news item
                news_item = {
                    "title": title,
                    "summary": summary,
                    "url": url,
                    "source": source,
                    "timestamp": datetime.fromtimestamp(file_timestamp),
                    "unix_timestamp": file_timestamp,
                    "currency": currency,
                    "currency_pairs": currency_pairs,
                    "sentiment": sentiment,
                    "score": score,
                    "file_path": file_path,
                    "is_indices": is_indices,
                    "is_fx": is_fx, 
                    "is_crypto": is_crypto,
                    "is_market": is_market
                }
                
                loaded_news.append(news_item)
                results["files_loaded"].append({
                    "filename": filename,
                    "currency": currency,
                    "sentiment": sentiment,
                    "date": datetime.fromtimestamp(file_timestamp).isoformat()
                })
                
            except Exception as e:
                results.setdefault("errors", []).append({
                    "file": os.path.basename(file_path),
                    "error": str(e)
                })
        
        # Step 4: Update session state with loaded news
        # Sort by timestamp (newest first)
        loaded_news.sort(key=lambda x: x.get("timestamp", datetime.now()), reverse=True)
        results["total_loaded"] = len(loaded_news)
        
        # Categorize by market type
        fx_news = [n for n in loaded_news if n.get("is_fx", False) or n.get("is_market", False)]
        crypto_news = [n for n in loaded_news if n.get("is_crypto", False) or n.get("is_market", False)]
        indices_news = [n for n in loaded_news if n.get("is_indices", False) or n.get("is_market", False)]
        
        # Update session state
        st.session_state.fx_news = fx_news
        st.session_state.crypto_news = crypto_news
        st.session_state.indices_news = indices_news
        
        # Also update current market-specific cache
        if st.session_state.get("market_type") == "FX":
            st.session_state.cached_news = fx_news
        elif st.session_state.get("market_type") == "Crypto":
            st.session_state.cached_news = crypto_news
        else:  # Indices
            st.session_state.cached_news = indices_news
            
        # Update timestamps
        current_time = datetime.now()
        st.session_state.last_fx_news_fetch = current_time
        st.session_state.last_crypto_news_fetch = current_time
        st.session_state.last_indices_news_fetch = current_time
        st.session_state.last_news_fetch = current_time
        
        # Set disk_news_loaded flag
        st.session_state.disk_news_loaded = True
        
        # Set next refresh times to 5 minutes from now
        next_refresh = current_time + timedelta(minutes=5)
        st.session_state.next_fx_news_refresh_time = next_refresh
        st.session_state.next_crypto_news_refresh_time = next_refresh
        st.session_state.next_indices_news_refresh_time = next_refresh
        
        results["news_counts"] = {
            "fx_news": len(fx_news),
            "crypto_news": len(crypto_news),
            "indices_news": len(indices_news),
            "current_market": len(st.session_state.cached_news)
        }
            
    except Exception as e:
        results["error"] = str(e)
    
    return results

# Use in Streamlit
st.title("News Reset and Force Load Utility")
st.warning("This utility forcibly resets all news-related session state and manually loads news files. Use with caution!")

col1, col2 = st.columns(2)
with col1:
    folder = st.text_input("News folder path", value="fx_news/scrapers/news/yahoo")
    
with col2:
    max_days = st.slider("Max days old", min_value=1, max_value=90, value=30)
    
reset_button = st.button("Reset and Force Load News")

if reset_button or 'reset_results' in st.session_state:
    with st.spinner("Resetting news state and loading files..."):
        results = force_news_reset_and_load(folder, max_days)
        st.session_state.reset_results = results
    
    # Display results
    st.header("Reset Results")
    
    if results.get("error"):
        st.error(f"Error: {results['error']}")
        st.stop()
    
    # Success message
    st.success(f"Successfully reset news state and loaded {results['total_loaded']} news files.")
    
    # Show statistics
    st.subheader("Statistics")
    st.write(f"Reset keys: {', '.join(results['reset_keys'])}")
    st.write(f"Total files found: {results['total_found']}")
    st.write(f"Total files loaded: {results['total_loaded']}")
    
    if "news_counts" in results:
        st.write("News counts by market type:")
        for market, count in results["news_counts"].items():
            st.write(f"- {market}: {count} items")
    
    # Show loaded files
    if results.get("files_loaded"):
        with st.expander(f"Loaded files ({len(results['files_loaded'])})"):
            for file in results["files_loaded"]:
                st.markdown(f"**{file['filename']}**")
                st.write(f"Currency: {file['currency']}")
                st.write(f"Sentiment: {file['sentiment']}")
                st.write(f"Date: {file['date']}")
                st.write("---")
    
    # Show errors if any
    if "errors" in results and results["errors"]:
        with st.expander(f"Errors ({len(results['errors'])})"):
            for error in results["errors"]:
                st.write(f"**{error['file']}**: {error['error']}")
    
    # Instructions for next steps
    st.subheader("Next Steps")
    st.write("1. Go back to your main app page")
    st.write("2. The news should now be loaded from files")
    st.write("3. If still not working, check market type filters or timestamp processing")
    
    # Refresh button
    if st.button("Refresh App"):
        st.rerun()