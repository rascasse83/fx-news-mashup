import requests
import pandas as pd
from datetime import datetime, timedelta
import random
import time
from bs4 import BeautifulSoup
import re
import json

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
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0'
    }

def scrape_investing_economic_calendar(countries=None, importance=None, days=7, debug_log=None):
    """
    Scrape economic calendar from Investing.com
    
    Args:
        countries: List of country names to filter events
        importance: List of importance levels (1-3) to filter events
        days: Number of days to look ahead
        debug_log: Optional list to append debug information
    
    Returns:
        List of economic events
    """
    if debug_log is None:
        debug_log = []
    
    debug_log.append(f"Fetching economic calendar for the next {days} days")
    
    # Format date range for the URL
    today = datetime.now()
    end_date = today + timedelta(days=days)
    
    date_from = today.strftime('%Y-%m-%d')
    date_to = end_date.strftime('%Y-%m-%d')
    
    try:
        # Use the direct calendar HTML page instead of the AJAX service
        url = f"https://www.investing.com/economic-calendar/"
        
        headers = get_random_headers()
        headers["Referer"] = "https://www.investing.com/economic-calendar/"
        
        debug_log.append(f"Sending request to {url}")
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            debug_log.append("Request successful, parsing data")
            
            # The response is HTML content
            html_content = response.text
            
            # Try to find embedded JSON data first (more reliable)
            events = extract_events_from_json(html_content, debug_log)
            
            # If no JSON data found, fall back to HTML parsing
            if not events:
                debug_log.append("No JSON data found, falling back to HTML parsing")
                events = extract_events_from_html(html_content, debug_log)
            
            debug_log.append(f"Extracted {len(events)} events before filtering")
            
            # Output the first few events for debugging before filtering
            if events and len(events) > 0:
                debug_log.append(f"Sample event before filtering: {events[0]}")
            
            # Apply filters if needed
            filtered_events = filter_events(events, countries, importance, debug_log)
            
            debug_log.append(f"Successfully extracted {len(filtered_events)} events after filtering")
            
            # If no events after filtering, return the unfiltered events with a warning
            if len(filtered_events) == 0 and len(events) > 0:
                debug_log.append("WARNING: All events were filtered out. Returning unfiltered events.")
                return events
                
            return filtered_events if filtered_events else []
        else:
            debug_log.append(f"Request failed with status code: {response.status_code}")
            return []
    
    except Exception as e:
        debug_log.append(f"Error fetching economic calendar: {str(e)}")
        return []

def extract_events_from_json(html_content, debug_log=None):
    """
    Extract economic events from embedded JSON in the HTML content
    """
    if debug_log is None:
        debug_log = []
    
    events = []
    
    try:
        # Look for embedded JSON data in script tags
        soup = BeautifulSoup(html_content, 'html.parser')
        scripts = soup.find_all('script')
        
        for script in scripts:
            script_text = script.string
            if script_text and "window.econCalendarData" in script_text:
                debug_log.append("Found economic calendar data in script tag")
                
                # Extract the JSON data using regex
                match = re.search(r'window\.econCalendarData\s*=\s*({.*?});', script_text, re.DOTALL)
                if match:
                    json_str = match.group(1)
                    try:
                        data = json.loads(json_str)
                        if 'events' in data:
                            raw_events = data['events']
                            debug_log.append(f"Found {len(raw_events)} events in JSON data")
                            
                            for event in raw_events:
                                event_data = {}
                                
                                # Extract basic information
                                event_data["date"] = event.get('date', '')
                                event_data["time"] = event.get('time', '')
                                event_data["country"] = event.get('country', '')
                                event_data["event"] = event.get('name', '')
                                event_data["impact_currency"] = event.get('currency', '')
                                
                                # Convert importance (usually "1", "2", "3") to integer
                                importance_str = event.get('importance', '0')
                                try:
                                    event_data["importance"] = int(importance_str)
                                except (ValueError, TypeError):
                                    event_data["importance"] = 0
                                
                                # Add other available fields
                                event_data["actual"] = event.get('actual', '')
                                event_data["forecast"] = event.get('forecast', '')
                                event_data["previous"] = event.get('previous', '')
                                
                                events.append(event_data)
                            
                            return events
                    except json.JSONDecodeError as e:
                        debug_log.append(f"Failed to parse JSON data: {str(e)}")
    
    except Exception as e:
        debug_log.append(f"Error extracting events from JSON: {str(e)}")
    
    return events

def extract_events_from_html(html_content, debug_log=None):
    """
    Extract economic events from the HTML content
    """
    if debug_log is None:
        debug_log = []
        
    events = []
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Try different table selectors (site structure may change)
    event_table = None
    possible_selectors = [
        {'id': 'economicCalendarData'},
        {'class': 'js-event-item'},
        {'class': 'calendar-table'},
        {'class': 'economic-calendar'}
    ]
    
    for selector in possible_selectors:
        event_table = soup.find('table', selector)
        if event_table:
            debug_log.append(f"Found event table with selector: {selector}")
            break
    
    if not event_table:
        debug_log.append("Event table not found in HTML")
        return events
        
    # Try to find event rows with different selectors
    event_rows = []
    possible_row_selectors = [
        {'id': lambda x: x and x.startswith('eventRowId_')},
        {'class': 'js-event-item'},
        {'class': 'event-item'},
        {'class': 'calendar-event'}
    ]
    
    for selector in possible_row_selectors:
        rows = event_table.find_all('tr', selector)
        if rows:
            event_rows = rows
            debug_log.append(f"Found {len(rows)} event rows with selector: {selector}")
            break
    
    if not event_rows:
        debug_log.append("No event rows found in the table")
        return events
    
    for row in event_rows:
        try:
            event_data = {}
            
            # Extract date
            date_row = row.find_previous('tr', {'class': lambda x: x and ('theDay' in x or 'table-header' in x)})
            if date_row:
                # Try different date extraction methods
                date_id = date_row.get('id', '')
                if date_id and date_id.startswith('theDay'):
                    try:
                        timestamp = int(date_id.replace('theDay', ''))
                        event_data["date"] = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')
                    except ValueError:
                        pass
                
                # If no date found yet, try to extract from text
                if "date" not in event_data:
                    date_text = date_row.get_text().strip()
                    # Try to parse date from text
                    try:
                        # Various date formats
                        for date_format in ['%b %d, %Y', '%Y-%m-%d', '%d %b %Y']:
                            try:
                                parsed_date = datetime.strptime(date_text, date_format)
                                event_data["date"] = parsed_date.strftime('%Y-%m-%d')
                                break
                            except ValueError:
                                continue
                    except Exception:
                        pass
            
            # If still no date, use current date
            if "date" not in event_data:
                event_data["date"] = datetime.now().strftime('%Y-%m-%d')
            
            # Extract time - multiple possible class names
            time_cell = row.find('td', {'class': lambda x: x and any(c in x for c in ['time', 'event-time', 'calendar-time'])})
            if time_cell:
                event_data["time"] = time_cell.text.strip()
            
            # Extract country and currency
            flag_cell = row.find('td', {'class': lambda x: x and any(c in x for c in ['flagCur', 'country', 'flag'])})
            if flag_cell:
                # Try to extract country from flag span
                flag_span = flag_cell.find('span', {'class': lambda x: x and any(c in x for c in ['ceFlags', 'flag', 'country-flag'])})
                if flag_span:
                    country_class = flag_span.get('class', [])
                    if len(country_class) > 1:
                        country_name = [c for c in country_class if c not in ['ceFlags', 'flag', 'country-flag']]
                        if country_name:
                            event_data["country"] = country_name[0].replace('_', ' ').title()
                
                # If no country found, try to extract from text
                if "country" not in event_data and flag_cell.text:
                    # Extract first word as potential country name
                    country_text = flag_cell.text.strip().split()[0] if flag_cell.text.strip() else ""
                    if country_text:
                        event_data["country"] = country_text
                
                # Extract currency
                currency_text = flag_cell.text.strip()
                if currency_text:
                    # Try to extract currency code (usually 3 uppercase letters)
                    currency_match = re.search(r'\b[A-Z]{3}\b', currency_text)
                    if currency_match:
                        event_data["impact_currency"] = currency_match.group(0)
                    else:
                        # Use the whole text if no currency code found
                        event_data["impact_currency"] = currency_text
            
            # Extract importance - multiple possible selectors
            importance_cell = row.find('td', {'class': lambda x: x and any(c in x for c in ['sentiment', 'importance', 'bull-icon'])})
            if importance_cell:
                # Try to count bull icons
                bull_icons = importance_cell.find_all('i', {'class': lambda x: x and any(c in x for c in ['grayFullBullishIcon', 'bull-icon', 'importance-icon'])})
                
                if bull_icons:
                    event_data["importance"] = len(bull_icons)
                else:
                    # Alternative: look for a data attribute
                    importance_attr = importance_cell.get('data-importance', '')
                    if importance_attr:
                        try:
                            event_data["importance"] = int(importance_attr)
                        except ValueError:
                            event_data["importance"] = 0
                    else:
                        # Last resort: try to extract from text
                        importance_text = importance_cell.text.strip()
                        if importance_text:
                            if 'high' in importance_text.lower():
                                event_data["importance"] = 3
                            elif 'medium' in importance_text.lower() or 'moderate' in importance_text.lower():
                                event_data["importance"] = 2
                            elif 'low' in importance_text.lower():
                                event_data["importance"] = 1
                            else:
                                event_data["importance"] = 0
            
            # Extract event name - multiple possible selectors
            event_cell = row.find('td', {'class': lambda x: x and any(c in x for c in ['event', 'event-name', 'calendar-event'])})
            if event_cell:
                event_link = event_cell.find('a')
                if event_link:
                    event_data["event"] = event_link.text.strip()
                    event_data["event_url"] = event_link.get('href', '')
                else:
                    event_data["event"] = event_cell.text.strip()
            
            # Extract actual, forecast, and previous values - multiple possible selectors
            for field, class_names in [
                ('actual', ['act', 'actual', 'actual-value']),
                ('forecast', ['fore', 'forecast', 'forecast-value']),
                ('previous', ['prev', 'previous', 'previous-value'])
            ]:
                cell = row.find('td', {'class': lambda x: x and any(c in x for c in class_names)})
                if cell:
                    event_data[field] = cell.text.strip()
            
            # Add event ID if available
            event_attr = row.get('event_attr_id', row.get('data-event-id', ''))
            if event_attr:
                event_data["event_id"] = event_attr
                
            # Check if the row has enough data to be considered valid
            if ("event" in event_data) and ("country" in event_data or "impact_currency" in event_data):
                events.append(event_data)
            else:
                debug_log.append(f"Skipping incomplete event data: {event_data}")
                
        except Exception as e:
            debug_log.append(f"Error parsing event row: {str(e)}")
    
    return events

def filter_events(events, countries=None, importance=None, debug_log=None):
    """
    Filter events based on countries and importance
    """
    if debug_log is None:
        debug_log = []
        
    if not countries and not importance:
        debug_log.append("No filters specified, returning all events")
        return events
        
    filtered_events = []
    
    for event in events:
        include_event = True
        
        # Filter by country if specified
        if countries and "country" in event:
            country_match = False
            for country in countries:
                if country.lower() in event["country"].lower():
                    country_match = True
                    break
            
            if not country_match:
                debug_log.append(f"Country filter: Event for '{event.get('country', 'unknown')}' doesn't match criteria {countries}")
            
            include_event = include_event and country_match
        
        # Filter by importance if specified
        if importance and "importance" in event:
            importance_match = event["importance"] in importance
            
            if not importance_match:
                debug_log.append(f"Importance filter: Event with importance '{event.get('importance', 'unknown')}' doesn't match criteria {importance}")
            
            include_event = include_event and importance_match
        
        if include_event:
            filtered_events.append(event)
    
    debug_log.append(f"Filtered events from {len(events)} to {len(filtered_events)}")
    return filtered_events

def create_mock_economic_events(countries=None, days=7):
    """
    Create mock economic event data for testing
    
    Args:
        countries: List of country names to include
        days: Number of days to look ahead
    
    Returns:
        List of mock economic events
    """
    if not countries:
        countries = ["United States", "Eurozone", "Japan", "United Kingdom", "China"]
    
    event_types = [
        {"name": "Interest Rate Decision", "importance": 3},
        {"name": "GDP Growth Rate", "importance": 3},
        {"name": "Non-Farm Payrolls", "importance": 3},
        {"name": "Unemployment Rate", "importance": 2},
        {"name": "Consumer Price Index (CPI)", "importance": 2},
        {"name": "Producer Price Index (PPI)", "importance": 2},
        {"name": "Retail Sales", "importance": 2},
        {"name": "Manufacturing PMI", "importance": 2},
        {"name": "Services PMI", "importance": 1},
        {"name": "Building Permits", "importance": 1},
        {"name": "Consumer Confidence", "importance": 1},
        {"name": "Trade Balance", "importance": 1}
    ]
    
    # Map countries to currencies
    country_currency = {
        "United States": "USD",
        "Eurozone": "EUR",
        "Japan": "JPY",
        "United Kingdom": "GBP",
        "China": "CNY",
        "Australia": "AUD",
        "Canada": "CAD",
        "Switzerland": "CHF",
        "New Zealand": "NZD"
    }
    
    # Generate random events
    events = []
    today = datetime.now()
    
    for i in range(20):  # Generate 20 random events
        event_day = today + timedelta(days=random.randint(0, days-1))
        event_hour = random.randint(8, 20)
        event_minute = random.choice([0, 15, 30, 45])
        
        country = random.choice(countries)
        event_type = random.choice(event_types)
        
        # Generate some realistic looking values
        actual = None if random.random() < 0.7 else f"{random.uniform(-2.0, 5.0):.1f}%"
        forecast = f"{random.uniform(-1.0, 4.0):.1f}%" if random.random() > 0.1 else ""
        previous = f"{random.uniform(-2.0, 5.0):.1f}%"
        
        events.append({
            "date": event_day.strftime("%Y-%m-%d"),
            "time": f"{event_hour:02d}:{event_minute:02d}",
            "country": country,
            "event": event_type["name"],
            "importance": event_type["importance"],
            "actual": actual,
            "forecast": forecast,
            "previous": previous,
            "impact_currency": country_currency.get(country, "")
        })
    
    # Sort by date and time
    events.sort(key=lambda x: (x["date"], x["time"]))
    
    return events

def get_economic_events_for_currency(currency, all_events):
    """
    Filter economic events relevant to a specific currency
    
    Args:
        currency: Currency code to filter by (e.g., 'USD', 'EUR')
        all_events: List of all economic events
        
    Returns:
        List of events filtered for the specified currency
    """
    if not all_events:
        return []
        
    currency = currency.upper()  # Ensure currency code is uppercase
    currency_events = []
    
    for event in all_events:
        # Check if the event impacts this currency
        impact_currency = event.get("impact_currency", "")
        if impact_currency and currency in impact_currency.upper():
            currency_events.append(event)
        
        # Also check country-currency mapping as fallback
        country = event.get("country", "")
        if country:
            # Map countries to currencies
            country_currency_map = {
                "United States": "USD",
                "Eurozone": "EUR", 
                "Europe": "EUR",
                "Japan": "JPY",
                "United Kingdom": "GBP",
                "UK": "GBP",
                "China": "CNY",
                "Australia": "AUD",
                "Canada": "CAD",
                "Switzerland": "CHF",
                "New Zealand": "NZD"
            }
            
            if country in country_currency_map and country_currency_map[country] == currency:
                currency_events.append(event)
    
    return currency_events

def fetch_all_economic_events(force=False, debug_log=None):
    """
    Fetch all economic events with error handling and fallback to mock data
    
    Args:
        force: Force refresh regardless of cache
        debug_log: Optional list to append debug information
    
    Returns:
        List of economic events (real or mock)
    """
    if debug_log is None:
        debug_log = []
    
    try:
        # First try to get real data
        events = scrape_investing_economic_calendar(days=7, debug_log=debug_log)
        
        # Check if we have valid data
        if events and len(events) > 0:
            debug_log.append(f"Successfully fetched {len(events)} real economic events")
            return events
        else:
            debug_log.append("No real events found, using mock data")
            return create_mock_economic_events()
            
    except Exception as e:
        debug_log.append(f"Error in fetch_all_economic_events: {str(e)}")
        return create_mock_economic_events()

# Example usage
if __name__ == "__main__":
    # Test with real data
    debug_log = []
    # events = scrape_investing_economic_calendar(
    #     countries=["United States", "Eurozone"],
    #     importance=[2, 3],  # Medium and high importance
    #     days=7,
    #     debug_log=debug_log
    # )
    events = scrape_investing_economic_calendar(
    days=7,
    debug_log=debug_log
)
    
# Print debug log
    for log in debug_log:
        print(log)
    
    # If real data fails, use mock data
    if not events:
        print("Using mock data")
        events = create_mock_economic_events()
    
    # Print events
    for event in events[:5]:  # Show first 5 events
        print(f"{event.get('date', 'No date')} {event.get('time', 'No time')} - {event.get('country', 'No country')} - {event.get('event', 'No event')} (Importance: {event.get('importance', 'No importance')})")