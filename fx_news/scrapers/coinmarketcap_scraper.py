import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import random
import time
import json
from typing import List, Dict, Any, Optional
import traceback

def get_random_headers():
    """Generate random headers to avoid detection"""
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0'
    ]
    return {
        'User-Agent': random.choice(user_agents),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'max-age=0'
    }

def scrape_coinmarketcap_events(days: int = 7, debug_log: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """
    Scrape cryptocurrency events from CoinMarketCap
    
    Args:
        days: Number of days to look ahead (though actual implementation gets what's on the page)
        debug_log: Optional list to append debug information
    
    Returns:
        List of event dictionaries
    """
    if debug_log is None:
        debug_log = []
    
    events = []
    url = "https://coinmarketcap.com/events/"
    
    print(f"Fetching crypto events from {url}")
    debug_log.append(f"Fetching crypto events from {url}")
    
    try:
        # Send request to the events page
        headers = get_random_headers()
        response = requests.get(url, headers=headers, timeout=15)
        
        print(f"Response status code: {response.status_code}")
        
        if response.status_code != 200:
            debug_log.append(f"Failed to fetch events page, status code: {response.status_code}")
            print(f"Failed to fetch events page, status code: {response.status_code}")
            return events
        
        # Save the response HTML for debugging
        with open("coinmarketcap_response.html", "w", encoding="utf-8") as f:
            f.write(response.text)
        print("Saved response HTML to coinmarketcap_response.html")
        
        soup = BeautifulSoup(response.text, 'html.parser')
        print("Successfully created BeautifulSoup object")
        debug_log.append("Successfully fetched events page")
        
        # Process today's events
        today_events = process_day_events(soup, "Today", debug_log)
        events.extend(today_events)
        print(f"Added {len(today_events)} events for today")
        
        # Process tomorrow's events
        tomorrow_events = process_day_events(soup, "Tomorrow", debug_log)
        events.extend(tomorrow_events)
        print(f"Added {len(tomorrow_events)} events for tomorrow")
        
        # Also get trending and significant events
        trending_events = process_special_events(soup, "Trending Events", debug_log)
        events.extend(trending_events)
        print(f"Added {len(trending_events)} trending events")
        
        significant_events = process_special_events(soup, "Significant Events", debug_log)
        events.extend(significant_events)
        print(f"Added {len(significant_events)} significant events")
        
        debug_log.append(f"Successfully extracted {len(events)} events")
        print(f"Successfully extracted {len(events)} events")
        return events
    
    except Exception as e:
        debug_log.append(f"Error scraping CoinMarketCap events: {str(e)}")
        print(f"Error scraping CoinMarketCap events: {str(e)}")
        print(traceback.format_exc())
        return []

def process_day_events(soup, day_label, debug_log):
    """Process events for a specific day (Today or Tomorrow)"""
    events = []
    
    print(f"Looking for '{day_label}' section...")
    day_section = None
    event_date = datetime.now() if day_label == "Today" else datetime.now() + timedelta(days=1)
    formatted_date = event_date.strftime("%Y-%m-%d")
    
    # Find the section with the day label
    event_list_headers = soup.find_all("p", {"class": "sc-71024e3e-0", "font-weight": "bold", "color": "text", "font-size": "1"})
    print(f"Found {len(event_list_headers)} event list headers")
    
    for header in event_list_headers:
        if header.text.strip() == day_label:
            print(f"Found '{day_label}' section!")
            # The structure is typically a div with class "event-list-header" containing the day label,
            # followed by a div with class "event-list-body"
            header_parent = header.parent
            if header_parent and header_parent.get("class") and "event-list-header" in header_parent.get("class"):
                day_section = header_parent.find_next_sibling("div", {"class": "event-list-body"})
                break
    
    if not day_section:
        debug_log.append(f"Could not find {day_label.lower()}'s events section")
        print(f"Could not find {day_label.lower()}'s events section")
        return events
    
    # Extract individual event blocks (class "sc-928a8bf1-0")
    event_blocks = day_section.find_all("div", {"class": "sc-928a8bf1-0"})
    print(f"Found {len(event_blocks)} event blocks for {day_label}")
    debug_log.append(f"Found {len(event_blocks)} event blocks for {day_label}")
    
    for i, block in enumerate(event_blocks):
        try:
            print(f"Processing {day_label} event block {i+1}...")
            event = extract_event_data(block, formatted_date, debug_log)
            if event:
                events.append(event)
                print(f"Successfully added {day_label} event: {event['title']}")
        except Exception as e:
            debug_log.append(f"Error processing event block: {str(e)}")
            print(f"Error processing event block: {str(e)}")
            print(traceback.format_exc())
    
    return events

def process_special_events(soup, section_title, debug_log):
    """Process trending or significant events sections"""
    events = []
    
    print(f"Looking for '{section_title}' section...")
    section_header = None
    
    # Find the section with the given title
    event_list_headers = soup.find_all("p", {"class": "sc-71024e3e-0", "font-weight": "bold", "color": "text", "font-size": "1"})
    print(f"Found {len(event_list_headers)} event list headers")
    
    for header in event_list_headers:
        if section_title in header.text:
            print(f"Found '{section_title}' section!")
            header_parent = header.parent
            if header_parent and header_parent.get("class") and "event-list-header" in header_parent.get("class"):
                special_section = header_parent.find_next_sibling("div", {"class": "event-list-body"})
                break
    
    if not special_section:
        debug_log.append(f"Could not find {section_title} section")
        print(f"Could not find {section_title} section")
        return events
    
    # Extract individual event blocks (class "sc-e05ea6c3-0")
    event_blocks = special_section.find_all("div", {"class": "sc-e05ea6c3-0"})
    print(f"Found {len(event_blocks)} event blocks for {section_title}")
    debug_log.append(f"Found {len(event_blocks)} event blocks for {section_title}")
    
    today_date = datetime.now().strftime("%Y-%m-%d")
    
    for i, block in enumerate(event_blocks):
        try:
            print(f"Processing {section_title} event block {i+1}...")
            # Extract event data from special section format
            event = extract_special_event_data(block, today_date, section_title, debug_log)
            if event:
                events.append(event)
                print(f"Successfully added {section_title} event: {event['title']}")
        except Exception as e:
            debug_log.append(f"Error processing {section_title} event: {str(e)}")
            print(f"Error processing {section_title} event: {str(e)}")
            print(traceback.format_exc())
    
    return events

def extract_event_data(block, event_date, debug_log):
    """Extract event data from a standard event block"""
    try:
        # Extract coin info
        event_header = block.find("div", {"class": "event-header"})
        if not event_header:
            print("No event header found")
            return None
        
        coin_link = event_header.find("a", {"class": "cmc-link"})
        if not coin_link:
            print("No coin link found")
            return None
        
        coin_img = coin_link.find("img")
        coin_name_elem = coin_link.find("span")
        coin_name = coin_name_elem.text.strip() if coin_name_elem else "Unknown"
        coin_image_url = coin_img["src"] if coin_img and "src" in coin_img.attrs else ""
        print(f"Coin: {coin_name}")
        
        # Extract event body
        event_body = block.find("div", {"class": "event-body"})
        if not event_body:
            print("No event body found")
            return None
        
        # Extract event content
        event_content = event_body.find("div", {"class": "event-body-content"})
        if not event_content:
            print("No event content found")
            return None
            
        # Get event link and details
        event_link = event_content.find("a", {"class": "cmc-link"})
        if not event_link:
            print("No event link found")
            return None
            
        event_url = event_link.get("href", "")
        
        # Extract title
        event_title_elem = event_link.find("div", {"class": "event-body-title"})
        if not event_title_elem:
            print("No event title element found")
            return None
            
        title_p = event_title_elem.find("p")
        if not title_p:
            print("No title paragraph found")
            return None
            
        title_span = title_p.find("span")
        event_title = title_span.text.strip() if title_span else "Unknown Event"
        print(f"Event title: {event_title}")
        
        # Extract description
        event_texts = event_link.find("div", {"class": "event-body-texts"})
        event_desc = ""
        if event_texts:
            desc_div = event_texts.find("div")
            if desc_div:
                event_desc = desc_div.text.strip()
        
        # Extract tags
        event_tags = []
        tags_div = event_body.find("div", {"class": "event-body-tags"})
        if tags_div:
            tag_buttons = tags_div.find_all("button")
            for button in tag_buttons:
                tag_text = button.text.strip()
                if tag_text:
                    event_tags.append(tag_text)
        
        # Create event object
        event = {
            "coin": coin_name,
            "coin_image_url": coin_image_url,
            "title": event_title,
            "description": event_desc,
            "date": event_date,
            "url": event_url,
            "type": event_tags[0] if event_tags else "Other",
            "tags": event_tags
        }
        
        return event
        
    except Exception as e:
        debug_log.append(f"Error extracting event data: {str(e)}")
        print(f"Error extracting event data: {str(e)}")
        print(traceback.format_exc())
        return None

def extract_special_event_data(block, event_date, section_type, debug_log):
    """Extract event data from trending or significant event blocks"""
    try:
        # Extract coin info
        event_header = block.find("div", {"class": "event-header"})
        if not event_header:
            print("No event header found")
            return None
        
        coin_link = event_header.find("a", {"class": "cmc-link"})
        if not coin_link:
            print("No coin link found")
            return None
        
        coin_img = coin_link.find("img")
        coin_image_url = coin_img["src"] if coin_img and "src" in coin_img.attrs else ""
        
        # Extract event body
        event_body = block.find("div", {"class": "event-body"})
        if not event_body:
            print("No event body found")
            return None
        
        # Extract event content
        event_content = event_body.find("div", {"class": "event-body-content"})
        if not event_content:
            print("No event content found")
            return None
            
        # Get event link
        event_link = event_content.find("a", {"class": "cmc-link"})
        if not event_link:
            print("No event link found")
            return None
            
        event_url = event_link.get("href", "")
        
        # Extract title
        event_title_elem = event_link.find("div", {"class": "event-body-title"})
        if not event_title_elem:
            print("No event title element found")
            return None
            
        title_p = event_title_elem.find("p")
        if not title_p:
            print("No title paragraph found")
            return None
            
        event_title = title_p.text.strip()
        print(f"Event title: {event_title}")
        
        # Extract description
        event_texts = event_link.find("div", {"class": "event-body-texts"})
        event_desc = ""
        if event_texts:
            desc_p = event_texts.find("p")
            if desc_p:
                event_desc = desc_p.text.strip()
        
        # Extract coin name and tags
        event_tags = []
        coin_name = "Unknown"
        
        tags_div = event_body.find("div", {"class": "event-body-tags"})
        if tags_div:
            tag_buttons_div = tags_div.find("div")
            if tag_buttons_div:
                tag_buttons = tag_buttons_div.find_all("button")
                
                # First button usually contains the coin name
                if tag_buttons and len(tag_buttons) > 0:
                    first_button = tag_buttons[0]
                    img = first_button.find("img")
                    if img:  # If there's an image, this is a coin button
                        coin_name = first_button.text.strip()
                        # Skip the first button as it's the coin name
                        tag_buttons = tag_buttons[1:]
                
                # Rest are real tags
                for button in tag_buttons:
                    tag_text = button.text.strip()
                    if tag_text:
                        event_tags.append(tag_text)
        
        # Create event object
        event = {
            "coin": coin_name,
            "coin_image_url": coin_image_url,
            "title": event_title,
            "description": event_desc,
            "date": event_date,
            "url": event_url,
            "type": event_tags[0] if event_tags else "Other",
            "tags": event_tags,
            "category": section_type  # Mark as trending or significant
        }
        
        # Check if the event has likes
        event_like = block.find("div", {"class": "event-like"})
        if event_like:
            like_number = event_like.find("span", {"class": "event-like-number"})
            if like_number and like_number.text.strip():
                try:
                    event["likes"] = int(like_number.text.strip())
                except ValueError:
                    event["likes"] = 0
        
        return event
        
    except Exception as e:
        debug_log.append(f"Error extracting special event data: {str(e)}")
        print(f"Error extracting special event data: {str(e)}")
        print(traceback.format_exc())
        return None

def create_mock_crypto_events(count: int = 10) -> List[Dict[str, Any]]:
    """
    Create mock crypto event data for testing
    
    Args:
        count: Number of mock events to create
    
    Returns:
        List of mock event dictionaries
    """
    print(f"Creating {count} mock crypto events")
    today = datetime.now()
    tomorrow = today + timedelta(days=1)
    
    coins = [
        {"name": "Bitcoin", "symbol": "BTC", "image": "https://s2.coinmarketcap.com/static/img/coins/64x64/1.png"},
        {"name": "Ethereum", "symbol": "ETH", "image": "https://s2.coinmarketcap.com/static/img/coins/64x64/1027.png"},
        {"name": "Solana", "symbol": "SOL", "image": "https://s2.coinmarketcap.com/static/img/coins/64x64/5426.png"},
        {"name": "Binance Coin", "symbol": "BNB", "image": "https://s2.coinmarketcap.com/static/img/coins/64x64/1839.png"},
        {"name": "Cardano", "symbol": "ADA", "image": "https://s2.coinmarketcap.com/static/img/coins/64x64/2010.png"},
        {"name": "XRP", "symbol": "XRP", "image": "https://s2.coinmarketcap.com/static/img/coins/64x64/52.png"},
        {"name": "Polkadot", "symbol": "DOT", "image": "https://s2.coinmarketcap.com/static/img/coins/64x64/6636.png"},
        {"name": "Polygon", "symbol": "MATIC", "image": "https://s2.coinmarketcap.com/static/img/coins/64x64/3890.png"},
        {"name": "Chainlink", "symbol": "LINK", "image": "https://s2.coinmarketcap.com/static/img/coins/64x64/1975.png"},
        {"name": "Avalanche", "symbol": "AVAX", "image": "https://s2.coinmarketcap.com/static/img/coins/64x64/5805.png"}
    ]
    
    event_types = [
        "Release", "AMA", "Airdrop", "Tokenomics", "Fork/Swap", 
        "Partnership", "Team Update", "Community", "Integration"
    ]
    
    events = []
    
    for i in range(count):
        # Pick a random coin
        coin = random.choice(coins)
        
        # Assign to today or tomorrow randomly
        event_date = (today if random.random() > 0.5 else tomorrow).strftime("%Y-%m-%d")
        
        # Create random event
        event_type = random.choice(event_types)
        
        # Generate a title based on the event type
        title = ""
        description = ""
        
        if event_type == "Release":
            product = random.choice(["Mainnet", "Testnet", "v2.0", "Mobile App", "New Platform", "DEX", "Wallet"])
            title = f"{coin['symbol']} {product} Release"
            description = f"The {coin['name']} team is launching their {product.lower()} with new features and improved security."
            
        elif event_type == "AMA":
            platform = random.choice(["Discord", "Telegram", "Twitter Spaces", "Reddit", "YouTube"])
            title = f"{coin['symbol']} {platform} AMA"
            description = f"Join the {coin['name']} team for a live AMA session on {platform} to discuss recent developments."
            
        elif event_type == "Airdrop":
            title = f"{coin['symbol']} Community Airdrop"
            description = f"{coin['name']} is launching an airdrop for early adopters and community members."
            
        elif event_type == "Tokenomics":
            action = random.choice(["Token Burn", "Staking Rewards", "Vesting Update", "Supply Adjustment"])
            title = f"{coin['symbol']} {action}"
            description = f"Important update to {coin['name']}'s tokenomics with a new {action.lower()} mechanism."
            
        elif event_type == "Fork/Swap":
            title = f"{coin['symbol']} Token Swap"
            description = f"{coin['name']} is implementing a token swap to a new contract for improved functionality."
            
        elif event_type == "Partnership":
            partner = random.choice(["Microsoft", "Amazon", "Google", "Chainlink", "Binance", "Coinbase", "PayPal"])
            title = f"{coin['symbol']} x {partner} Partnership"
            description = f"{coin['name']} announces strategic partnership with {partner} to enhance adoption."
            
        elif event_type == "Team Update":
            update = random.choice(["Roadmap Update", "New CTO", "Development Update", "Q1 Recap", "Monthly Review"])
            title = f"{coin['symbol']} {update}"
            description = f"The {coin['name']} team shares important updates on project development and future plans."
            
        elif event_type == "Community":
            activity = random.choice(["Hackathon", "Conference", "Meetup", "Twitter Space", "Governance Vote"])
            title = f"{coin['symbol']} Community {activity}"
            description = f"{coin['name']} is hosting a community {activity.lower()} to engage with developers and users."
            
        else:  # Integration
            platform = random.choice(["Polygon", "Solana", "Ethereum", "Arbitrum", "BSC", "Optimism"])
            title = f"{coin['symbol']} {platform} Integration"
            description = f"{coin['name']} is expanding to {platform} to improve scalability and reach new users."
        
        # Add some tags
        tags = [event_type]
        if random.random() > 0.5:
            second_tag = random.choice([t for t in event_types if t != event_type])
            tags.append(second_tag)
        
        # Categorize some events as trending or significant
        category = None
        if random.random() > 0.7:
            category = random.choice(["Trending Events", "Significant Events"])
        
        # Create the event object
        event = {
            "coin": coin["name"],
            "symbol": coin["symbol"],
            "coin_image_url": coin["image"],
            "title": title,
            "description": description,
            "date": event_date,
            "url": f"https://example.com/{coin['symbol'].lower()}/{event_type.lower().replace('/', '-')}",
            "type": event_type,
            "tags": tags,
            "likes": random.randint(0, 10) if random.random() > 0.7 else 0
        }
        
        if category:
            event["category"] = category
        
        events.append(event)
    
    print(f"Created {len(events)} mock events")
    return events

def fetch_crypto_events(days: int = 7, use_mock_fallback: bool = True, debug_log: Optional[List[str]] = None) -> str:
    """
    Fetch cryptocurrency events with error handling and fallback to mock data

    Args:
        days: Number of days to look ahead
        use_mock_fallback: Whether to use mock data as fallback
        debug_log: Optional list to append debug information

    Returns:
        JSON string of events (real or mock)
    """
    if debug_log is None:
        debug_log = []

    # Try to get real data
    events = scrape_coinmarketcap_events(days=days, debug_log=debug_log)

    # Check if we have valid data
    if events and len(events) > 0:
        debug_log.append(f"Successfully fetched {len(events)} real crypto events")
    else:
        # Fall back to mock data if needed and allowed
        if use_mock_fallback:
            debug_log.append("No real events found or error occurred, using mock data")
            events = create_mock_crypto_events(count=15)
        else:
            # Return empty list if no fallback
            debug_log.append("No events found and mock fallback not enabled")
            return json.dumps([])

    # Format events to match the desired JSON structure
    formatted_events = []
    for event in events:
        formatted_event = {
            "title": event["title"],
            "description": event["description"].replace('"', ''),  # Sanitize the description here
            "type": event["type"],
            "coin": event.get("symbol", "Unknown"),  # Use symbol if available, otherwise use coin name
            "coin_name": event["coin"],
            "date": event["date"],
            "url": event["url"],
            "tags": event.get("tags", []),
            "category": event.get("category", "")
        }
        formatted_events.append(formatted_event)

    # Return the formatted events as a JSON string
    return json.dumps(formatted_events, indent=2)

# Example usage
if __name__ == "__main__":
    debug_log = []
    events_json = fetch_crypto_events(debug_log=debug_log)

    # Print debug log
    for log in debug_log:
        print(log)

    # Print events JSON
    print("\nFetched events JSON:")
    print(events_json)