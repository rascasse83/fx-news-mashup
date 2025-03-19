import streamlit as st
from datetime import datetime
from datetime import datetime, timedelta
from fx_news.services.news_service import fetch_news, filter_news_by_market_type, reset_news_session_state, debug_news_file_loading
from fx_news.utils.notifications import add_notification

def force_load_news_files():
    """Force load news files from the disk, bypassing the usual loading mechanism."""
    import os
    import glob
    import re
    from datetime import datetime
    
    # Try multiple possible locations for the news files
    possible_folders = [
        "fx_news/scrapers/news/yahoo",
        "scrapers/news/yahoo",
        "news/yahoo",
        "yahoo"
    ]
    
    found_folder = None
    for folder in possible_folders:
        if os.path.exists(folder) and os.path.isdir(folder):
            files = glob.glob(os.path.join(folder, "*.txt"))
            if files:
                found_folder = folder
                st.success(f"Found {len(files)} news files in {folder}")
                break
    
    if not found_folder:
        st.error("Could not find any news files in the expected locations.")
        return
    
    # Load news files
    all_news = []
    
    files = glob.glob(os.path.join(found_folder, "*.txt"))
    for file_path in files:
        try:
            # Extract basic file info
            filename = os.path.basename(file_path)
            
            # Extract timestamp from filename
            timestamp_match = re.search(r'article_(\d{10})_', filename)
            if not timestamp_match:
                continue
                
            file_timestamp = int(timestamp_match.group(1))
            file_date = datetime.fromtimestamp(file_timestamp)
            
            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract title
            title_match = re.search(r'^# (.+)$', content, re.MULTILINE)
            title = title_match.group(1).strip() if title_match else "No title"
            
            # Extract source
            source = "Yahoo Finance"  # Default
            source_match = re.search(r'^Source: (.+)$', content, re.MULTILINE)
            if source_match:
                url = source_match.group(1).strip()
                if "bloomberg" in url.lower():
                    source = "Bloomberg"
                elif "reuters" in url.lower():
                    source = "Reuters"
            
            # Extract summary
            summary = ""
            summary_match = re.search(r'SUMMARY:\s(.*?)(?:\n\n|\Z)', content, re.DOTALL)
            if summary_match:
                summary = summary_match.group(1).strip()
            
            # Extract sentiment
            sentiment = "neutral"  # Default
            sentiment_match = re.search(r'SENTIMENT:\s(.*?)$', content, re.MULTILINE)
            if sentiment_match:
                sentiment = sentiment_match.group(1).strip()
            
            # Extract score
            score = 0.0  # Default
            score_match = re.search(r'SCORE:\s([-\d\.]+)$', content, re.MULTILINE)
            if score_match:
                try:
                    score = float(score_match.group(1).strip())
                except:
                    pass
            
            # Extract currency pair from filename
            currency = "Unknown"
            currency_pairs = set()
            
            # Try to extract currency from filename
            currency_match = re.search(r'_([a-zA-Z0-9_]+).txt$', filename)
            if currency_match:
                symbol = currency_match.group(1).lower()
                
                # Try to split into base/quote
                if '_' in symbol:
                    base, quote = symbol.split('_', 1)
                    currency = f"{base.upper()}/{quote.upper()}"
                    currency_pairs = {currency}
                else:
                    # Special cases
                    if symbol in ['dji', 'gspc', 'ixic', 'ftse', 'gdaxi', 'fchi', 'n225']:
                        indices_map = {
                            'dji': 'Dow Jones',
                            'gspc': 'S&P 500',
                            'ixic': 'NASDAQ',
                            'ftse': 'FTSE 100',
                            'gdaxi': 'DAX',
                            'fchi': 'CAC 40',
                            'n225': 'Nikkei 225'
                        }
                        currency = indices_map.get(symbol, symbol.upper())
                    else:
                        currency = symbol.upper()
                    
                    currency_pairs = {currency}
            
            # Create news item
            news_item = {
                "title": title,
                "summary": summary,
                "source": source,
                "timestamp": file_date,
                "unix_timestamp": file_timestamp,
                "currency": currency,
                "currency_pairs": currency_pairs,
                "sentiment": sentiment,
                "score": score,
                "file_path": file_path,
                # Add market type flags
                "is_fx": True,  # Default to all types for now to ensure display
                "is_crypto": True,
                "is_indices": True,
                "is_market": True
            }
            
            all_news.append(news_item)
        except Exception as e:
            st.error(f"Error processing {filename}: {str(e)}")
    
    # Sort by timestamp (newest first)
    all_news.sort(key=lambda x: x["timestamp"], reverse=True)
    
    # Update session state
    st.session_state.fx_news = all_news.copy()
    st.session_state.crypto_news = all_news.copy()
    st.session_state.indices_news = all_news.copy()
    st.session_state.cached_news = all_news.copy()
    
    # Set timestamps
    current_time = datetime.now()
    st.session_state.last_fx_news_fetch = current_time
    st.session_state.last_crypto_news_fetch = current_time
    st.session_state.last_indices_news_fetch = current_time
    st.session_state.last_news_fetch = current_time
    
    st.success(f"Successfully loaded {len(all_news)} news items")
    return all_news


def display_news_sidebar():

    # Reset all news-related state to force a fresh load
    # reset_news_session_state()

    """Display the news sidebar with filter controls and news items"""
    # Dynamic header based on market type
    if st.session_state.market_type == 'FX':
        st.header("Currency News")
    elif st.session_state.market_type == 'Crypto':
        st.header("Crypto Market News")
    else:  # Indices
        st.header("Market News")
        
    # Filter controls
    sentiment_filter = st.selectbox(
        "Filter by sentiment using Finbert-Tone AI Model",
        options=["All News", "Positive", "Negative", "Neutral", "Important Only"]
    )

    # Get currencies from subscriptions
    subscription_currencies = list(set([sub["base"] for sub in st.session_state.subscriptions] +
                            [sub["quote"] for sub in st.session_state.subscriptions]))

    market_type = st.session_state.market_type  # Get the current market type
    
    # Initialize market-specific news cache keys if they don't exist
    if 'fx_news' not in st.session_state:
        st.session_state.fx_news = []
        
    if 'crypto_news' not in st.session_state:
        st.session_state.crypto_news = []
        
    if 'indices_news' not in st.session_state:
        st.session_state.indices_news = []
        
    if 'last_fx_news_fetch' not in st.session_state:
        st.session_state.last_fx_news_fetch = None
        
    if 'last_crypto_news_fetch' not in st.session_state:
        st.session_state.last_crypto_news_fetch = None
        
    if 'last_indices_news_fetch' not in st.session_state:
        st.session_state.last_indices_news_fetch = None

    current_time = datetime.now()
    should_refresh_news = False
    
    # Use market-specific cache keys
    if market_type == 'FX':
        news_cache_key = 'fx_news'
        last_fetch_key = 'last_fx_news_fetch'
        next_refresh_key = 'next_fx_news_refresh_time'
    elif market_type == 'Crypto':
        news_cache_key = 'crypto_news'
        last_fetch_key = 'last_crypto_news_fetch'
        next_refresh_key = 'next_crypto_news_refresh_time'
    else:  # Indices
        news_cache_key = 'indices_news'
        last_fetch_key = 'last_indices_news_fetch'
        next_refresh_key = 'next_indices_news_refresh_time'
    
    # Initialize the next refresh time if it doesn't exist
    if next_refresh_key not in st.session_state:
        st.session_state[next_refresh_key] = current_time
    
    # Only refresh news if we meet certain conditions
    if st.session_state[last_fetch_key] is None:
        should_refresh_news = True
        reason = f"Initial {market_type} fetch"
        # Set the next refresh time
        st.session_state[next_refresh_key] = current_time + timedelta(seconds=300)
    elif not st.session_state[news_cache_key]:
        should_refresh_news = True
        reason = f"No cached {market_type} news"
        # Set the next refresh time
        st.session_state[next_refresh_key] = current_time + timedelta(seconds=300)
    elif current_time >= st.session_state[next_refresh_key]:
        should_refresh_news = True
        reason = f"Scheduled 5-minute {market_type} refresh"
        # Schedule the next refresh
        st.session_state[next_refresh_key] = current_time + timedelta(seconds=300)
    elif st.session_state.refresh_news_clicked:
        should_refresh_news = True
        reason = f"Manual {market_type} refresh"
        # Schedule the next refresh
        st.session_state[next_refresh_key] = current_time + timedelta(seconds=300)
        # Reset the flag
        st.session_state.refresh_news_clicked = False
        
    # Fetch news if needed
    if should_refresh_news:
        # Add notification to make refresh visible
        add_notification(f"Refreshing {market_type} news: {reason}", "info")
        
        # Fetch new news
        news_items = fetch_news(subscription_currencies, force=(reason == f"Manual {market_type} refresh"))
    else:
        # Use the market-specific cached news
        news_items = st.session_state.get(news_cache_key, [])
        
    # Add a small caption showing when news was last updated
    if st.session_state[last_fetch_key]:
        time_diff = current_time - st.session_state[last_fetch_key]
        if time_diff.seconds < 60:
            update_text = "just now"
        elif time_diff.seconds < 3600:
            update_text = f"{time_diff.seconds // 60} minutes ago"
        else:
            update_text = f"{time_diff.seconds // 3600} hours ago"
        st.caption(f"{market_type} news last updated: {update_text}")

    st.write(f"Before filtering: {len(news_items)} news items")

    # Apply sentiment filter
    if sentiment_filter != "All News":
        if sentiment_filter == "Important Only":
            # Filter for news with strong sentiment (positive or negative)
            news_items = [item for item in news_items if abs(item.get("score", 0)) > 0.5]
        else:
            sentiment_map = {"Positive": "positive", "Negative": "negative", "Neutral": "neutral"}
            filter_sentiment = sentiment_map.get(sentiment_filter, "neutral")
            
            # Include items that match the filter OR items without sentiment if filter is "Neutral"
            if filter_sentiment == "neutral":
                news_items = [item for item in news_items if 
                            item.get("sentiment", "neutral") == filter_sentiment or
                            "sentiment" not in item or
                            not item.get("sentiment") or
                            item.get("score", 0) == 0]
            else:
                news_items = [item for item in news_items if item.get("sentiment", "neutral") == filter_sentiment]

    # Display news items
    if news_items:
        # Filter news to show only items relevant to current subscriptions
        subscription_pairs = set()
        for sub in st.session_state.subscriptions:
            pair = f"{sub['base']}/{sub['quote']}"
            subscription_pairs.add(pair)
            
            # For indices in Indices mode, add their proper names too
            if st.session_state.market_type == 'Indices' and sub['base'].startswith('^'):
                indices_names = {
                    '^DJI': 'Dow Jones',
                    '^GSPC': 'S&P 500',
                    '^IXIC': 'NASDAQ',
                    '^FTSE': 'FTSE 100',
                    '^GDAXI': 'DAX',
                    '^FCHI': 'CAC 40',
                    '^N225': 'Nikkei 225',
                }
                if sub['base'] in indices_names:
                    subscription_pairs.add(indices_names[sub['base']])
            # For FX mode, add individual currencies if not indices
            elif st.session_state.market_type == 'FX':
                if not sub['base'].startswith('^'):
                    subscription_pairs.add(sub['base'])
                    subscription_pairs.add(sub['quote'])

        # Include market news (general news)
        subscription_pairs.add("Market")

        # Filter news based on current market type and subscriptions
        filtered_news = filter_news_by_market_type(news_items, subscription_pairs, st.session_state.market_type)
        # filtered_news = news_items  # Temporarily skip filtering
        st.write(f"Bypassing market type filter, showing all {len(filtered_news)} news items")
            
        # Display the filtered news
        if filtered_news:
            display_news_items(filtered_news)
        else:
            st.info("No news items match your filters")
    else:
        st.info("No news items match your filters")

    if st.button("Force Load News"):
            force_load_news_files()
            st.rerun()  # Force a page refresh


    if st.button("Debug News System"):
        simple_news_debug()
    # debug_news_file_loading()
    


# Add this function to your existing app file (e.g., app.py or news.py)
# Then call it from somewhere in your UI

def simple_news_debug():
    """
    A simple function to debug news loading issues directly in your Streamlit app.
    Add this function to your app and call it from somewhere in your UI.
    """
    import streamlit as st
    import os
    import glob
    from datetime import datetime
    
    st.header("News System Debug")
    
    # Show session state info
    st.subheader("Session State Information")
    market_type = st.session_state.get("market_type", "Unknown")
    st.write(f"Current market type: {market_type}")
    
    news_keys = [
        'fx_news', 'crypto_news', 'indices_news', 'cached_news',
        'last_fx_news_fetch', 'last_crypto_news_fetch', 'last_indices_news_fetch'
    ]
    
    for key in news_keys:
        if key in st.session_state:
            if isinstance(st.session_state[key], list):
                st.write(f"{key}: {len(st.session_state[key])} items")
            else:
                st.write(f"{key}: {st.session_state[key]}")
        else:
            st.write(f"{key}: Not in session state")
    
    # Check folder paths
    st.subheader("News Folder Check")
    
    folders_to_check = [
        "fx_news/scrapers/news/yahoo",
        "scrapers/news/yahoo",
        "news/yahoo",
        "yahoo",
        "news"
    ]
    
    current_dir = os.getcwd()
    st.write(f"Current working directory: {current_dir}")
    
    for folder in folders_to_check:
        exists = os.path.exists(folder)
        st.write(f"Folder '{folder}': {'Exists' if exists else 'Not found'}")
        
        if exists:
            # Check for .txt files
            txt_files = glob.glob(os.path.join(folder, "*.txt"))
            st.write(f"  - Found {len(txt_files)} .txt files")
            
            # Show a few example files
            if txt_files:
                st.write("  - Example files:")
                for file in txt_files[:5]:  # Show up to 5 files
                    filename = os.path.basename(file)
                    file_size = os.path.getsize(file)
                    mod_time = datetime.fromtimestamp(os.path.getmtime(file))
                    st.write(f"    - {filename} ({file_size} bytes, modified {mod_time})")
    
    # Add manual reset button
    st.subheader("Manual News Reset")
    if st.button("Reset News Cache"):
        # Reset news-related session state
        for key in news_keys:
            if key in st.session_state:
                if key.startswith("last_"):
                    st.session_state[key] = None
                elif isinstance(st.session_state[key], list):
                    st.session_state[key] = []
        
        # Force refresh flag
        if 'refresh_news_clicked' in st.session_state:
            st.session_state.refresh_news_clicked = True
        
        st.success("News cache reset. Please return to the main page.")
        
        # Optional: Force rerun
        st.rerun()



def display_news_items(news_items):
    """
    Display news items with better debugging information and market-specific styling.
    
    Args:
        news_items: List of news item dictionaries to display
    """
    # Check if we have any news to display
    if not news_items:
        st.info("No news items available to display.")
        
        # Add debug info when in Crypto mode but no news
        if st.session_state.market_type == 'Crypto':
            # Check if we have any news in the crypto_news cache
            if 'crypto_news' in st.session_state and st.session_state.crypto_news:
                st.warning(f"Found {len(st.session_state.crypto_news)} items in crypto_news cache, but none passed filtering.")
                
                # Show a sample of what's in the cache for debugging
                with st.expander("Debug: Sample from crypto_news cache"):
                    for i, item in enumerate(st.session_state.crypto_news[:3]):
                        st.markdown(f"**Item {i+1}:** {item.get('title', 'No title')}")
                        st.markdown(f"Currency: {item.get('currency', 'None')}")
                        pairs = item.get('currency_pairs', set())
                        st.markdown(f"Currency pairs: {', '.join(str(p) for p in pairs) if pairs else 'None'}")
                        # Show market type flags
                        flags = []
                        if item.get('is_fx', False):
                            flags.append("FX")
                        if item.get('is_crypto', False):
                            flags.append("Crypto")
                        if item.get('is_indices', False):
                            flags.append("Indices")
                        if item.get('is_market', False):
                            flags.append("Market")
                        st.markdown(f"Market types: {', '.join(flags) if flags else 'None'}")
        return
    
    # Group items by day for better organization
    grouped_news = {}
    for item in news_items:
        # Extract the date (just the day)
        if 'timestamp' in item:
            day_key = item['timestamp'].strftime('%Y-%m-%d')
        else:
            day_key = "Unknown Date"
            
        if day_key not in grouped_news:
            grouped_news[day_key] = []
            
        grouped_news[day_key].append(item)
    
    # Order days with most recent first
    sorted_days = sorted(grouped_news.keys(), reverse=True)
    
    for day in sorted_days:
        # Only add date header if more than one day
        if len(sorted_days) > 1:
            # Format the date nicely
            try:
                display_date = datetime.strptime(day, '%Y-%m-%d').strftime('%A, %B %d, %Y')
                st.markdown(f"### {display_date}")
            except:
                st.markdown(f"### {day}")
        
        # Display each item for this day
        for item in sorted(grouped_news[day], key=lambda x: x.get('timestamp', datetime.now()), reverse=True):
            # Format timestamp
            time_diff = datetime.now() - item["timestamp"]
            if time_diff.days > 0:
                time_str = f"{time_diff.days}d ago"
            elif time_diff.seconds // 3600 > 0:
                time_str = f"{time_diff.seconds // 3600}h ago"
            elif time_diff.seconds // 60 > 0:
                time_str = f"{time_diff.seconds // 60}m ago"
            else:
                time_str = "just now"

            # Create color based on sentiment
            if 'sentiment' in item and item['sentiment'] == 'positive':
                border_color = "green"
                bg_color = "#d4edda"
                text_color = "#28a745"
            elif 'sentiment' in item and item['sentiment'] == 'negative':
                border_color = "red"
                bg_color = "#f8d7da"
                text_color = "#dc3545"
            else:  # neutral
                border_color = "gray"
                bg_color = "#f8f9fa"
                text_color = "#6c757d"

            # Customize the badge color based on market type
            currency_badge = item.get('currency', 'Unknown')
            
            # Set badge color based on market type
            badge_bg = "#e0e8ff"  # Default blue
            badge_text = "black"
            
            # Check if the item has market type flags
            if item.get('is_crypto', False) or st.session_state.market_type == 'Crypto':
                badge_bg = "#9C27B0"  # Purple for crypto
                badge_text = "white"
            elif item.get('is_indices', False) or st.session_state.market_type == 'Indices':
                badge_bg = "#FF9800"  # Orange for indices
                badge_text = "white"
            elif item.get('is_fx', False) or st.session_state.market_type == 'FX':
                badge_bg = "#1E88E5"  # Blue for FX
                badge_text = "white"
            elif currency_badge == "Market":
                badge_bg = "#607D8B"  # Gray-blue for general market
                badge_text = "white"

            # Display the news item
            with st.container():
                # Title with link if available
                title_html = f"""<div style="padding:12px; margin-bottom:12px; border-left:4px solid {border_color}; border-radius:4px; background-color:#ffffff;">"""
                
                if 'url' in item and item['url']:
                    title_html += f"""<div style="font-weight:bold; margin-bottom:8px;">
                        <a href="{item['url']}" target="_blank" style="text-decoration:none; color:#1e88e5;">
                            {item['title']} <span style="font-size:0.8em;">🔗</span>
                        </a>
                    </div>"""
                else:
                    title_html += f"""<div style="font-weight:bold; margin-bottom:8px;">{item['title']}</div>"""
                
                # Add a brief summary if available (truncated)
                if 'summary' in item and item['summary']:
                    summary = item['summary']
                    if len(summary) > 150:
                        summary = summary[:147] + "..."
                    title_html += f"""<div style="font-size:0.9em; color:#333; margin-bottom:8px;">{summary}</div>"""
                
                # Add the currency badge and metadata
                title_html += f"""
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div>
                            <span style="background-color:{badge_bg}; color:{badge_text}; padding:2px 6px; border-radius:3px; margin-right:5px; font-size:0.8em;">
                                {currency_badge}
                            </span>
                            <span style="color:#6c757d; font-size:0.8em;">{item['source']}</span>
                        </div>
                        <div>
                            <span style="color:#6c757d; font-size:0.8em; margin-right:5px;">{time_str}</span>
                            <span style="background-color:{bg_color}; color:{text_color}; padding:2px 6px; border-radius:10px; font-size:0.8em;">
                                {item.get('sentiment', 'neutral')} ({'+' if item.get('score', 0) > 0 else ''}{item.get('score', 0)})
                            </span>
                        </div>
                    </div>
                </div>"""
                
                st.markdown(title_html, unsafe_allow_html=True)