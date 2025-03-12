import streamlit as st
import json
import os
import logging
from datetime import datetime, timedelta
import glob
from io import StringIO

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger("fx_pulsar_hub")

# Initialize log capture for display in the UI
log_capture = StringIO()
log_handler = logging.StreamHandler(log_capture)
log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log_handler.setFormatter(log_formatter)
logger.addHandler(log_handler)

# Configure page with minimal styling
st.set_page_config(
    page_title="FX Pulsar Hub",
    page_icon="https://images.seeklogo.com/logo-png/60/1/lmax-digital-icon-black-logo-png_seeklogo-609777.png",
    layout="wide",
    initial_sidebar_state="expanded"
)


# Check if debug mode is in session state, initialize if not
if 'debug_mode' not in st.session_state:
    st.session_state.debug_mode = False

# Set logger level based on debug mode
if st.session_state.debug_mode:
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.WARNING)

# Add Roboto font
st.markdown("""
    <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap" rel="stylesheet">
    <style>
        * {
            font-family: 'Roboto', sans-serif !important;
        }
    </style>
""", unsafe_allow_html=True)

def transform_json_structure(original_data):
    """
    Transform the original JSON structure to the expected format
    """
    if not original_data:
        logger.warning("No data to transform")
        return None
    
    logger.debug(f"Original data keys: {list(original_data.keys())}")
    
    # Check if this is already in the expected format
    if "trends" in original_data and "drivers" in original_data and "outlook" in original_data:
        logger.debug("Data already in expected format")
        return original_data
    
    # New structure to return
    transformed = {}
    
    # Extract from market_summary if it exists
    market_summary = original_data.get("market_summary", {})
    if market_summary:
        logger.debug("Processing market_summary section")
        
        # Date
        if "date" in market_summary:
            transformed["date"] = market_summary["date"].replace("-", "") if "-" in market_summary["date"] else market_summary["date"]
            logger.debug(f"Extracted date: {transformed['date']}")
        
        # Title and summary
        if "overview" in market_summary:
            overview = market_summary["overview"]
            # Instead of splitting by period, use the full overview text
            transformed["title"] = "Daily Market Report: " + overview
            transformed["summary"] = overview
            logger.debug(f"Extracted title and summary")
        
        # Create trends from major_indexes and notable_stocks
        trends = []
        
        # Add major indexes as trends
        major_indexes = market_summary.get("major_indexes", {})
        logger.debug(f"Processing {len(major_indexes)} major indexes")
        for index_name, details in major_indexes.items():
            # Determine direction based on keywords in performance
            performance = details.get("performance", "")
            direction = "down" if any(keyword in performance.lower() for keyword in ["fell", "drop", "shed", "plummet", "declin"]) else "up"
            
            # Combine performance and status
            description = f"{performance} {details.get('status', '')}"
            
            trends.append({
                "currency": index_name,
                "direction": direction,
                "description": description.strip()
            })
            logger.debug(f"Added trend for {index_name} with direction {direction}")
        
        # Add notable stocks as trends
        notable_stocks = market_summary.get("notable_stocks", {})
        logger.debug(f"Processing {len(notable_stocks)} notable stocks")
        for stock_name, details in notable_stocks.items():
            # Determine direction based on keywords in performance
            performance = details.get("performance", "")
            direction = "down" if any(keyword in performance.lower() for keyword in ["fell", "drop", "shed", "plummet", "declin", "slid"]) else "up"
            
            # Combine performance and details
            description = f"{performance} {details.get('details', '')}"
            
            trends.append({
                "currency": stock_name,
                "direction": direction,
                "description": description.strip()
            })
            logger.debug(f"Added trend for {stock_name} with direction {direction}")
            
        transformed["trends"] = trends
        logger.debug(f"Added {len(trends)} total trends")
        
        # Add economic indicators to drivers
        drivers = []
        economic_indicators = market_summary.get("economic_indicators", {})
        logger.debug(f"Processing {len(economic_indicators)} economic indicators")
        for indicator, details in economic_indicators.items():
            driver_text = f"{indicator}: {details.get('performance', '')} {details.get('details', '')}"
            drivers.append(driver_text.strip())
            logger.debug(f"Added driver for {indicator}")
        
        # Store these initial drivers
        transformed["drivers"] = drivers
    
    # Extract from market_tendencies_for_tomorrow if it exists
    tendencies = original_data.get("market_tendencies_for_tomorrow", {})
    if tendencies:
        logger.debug("Processing market_tendencies_for_tomorrow section")
        
        # Add overview to outlook
        if "overview" in tendencies:
            transformed["outlook"] = {
                "sentiment": "neutral",  # Default to neutral unless specified
                "description": tendencies["overview"]
            }
            logger.debug(f"Added outlook from tendencies overview")
        
        # Add more drivers from expectations
        if "drivers" not in transformed:
            transformed["drivers"] = []
            
        # Add expectations to drivers
        expectations = tendencies.get("expectations", {})
        logger.debug(f"Processing {len(expectations)} expectations")
        for expectation, details in expectations.items():
            driver_text = f"{expectation}: {details.get('details', '')}"
            transformed["drivers"].append(driver_text.strip())
            logger.debug(f"Added driver for expectation {expectation}")
        
        # Add sectors to watch to drivers
        sectors = tendencies.get("sectors_to_watch", {})
        logger.debug(f"Processing {len(sectors)} sectors to watch")
        for sector, details in sectors.items():
            driver_text = f"{sector} sector: {details.get('details', '')}"
            transformed["drivers"].append(driver_text.strip())
            logger.debug(f"Added driver for sector {sector}")
    
    logger.debug(f"Transformation complete. New keys: {list(transformed.keys())}")
    return transformed

def get_latest_report():
    """Get the latest market report from the FX news directory."""
    # Check both possible directory paths - with and without underscore
    possible_paths = ["fx_news/reports", "fxnews/reports"]
    report_data = None
    
    for reports_dir in possible_paths:
        if os.path.exists(reports_dir):
            logger.info(f"Found directory: {reports_dir}")
            
            # Get all JSON files in the directory
            report_files = glob.glob(os.path.join(reports_dir, "*.json"))
            
            if report_files:
                logger.info(f"Found {len(report_files)} report files in {reports_dir}")
                # Sort files by name in descending order (newest first)
                report_files.sort(reverse=True)
                
                # Try each file until we find a valid one
                for report_file in report_files:
                    try:
                        # Skip empty files
                        if os.path.getsize(report_file) == 0:
                            logger.warning(f"Skipping empty file: {os.path.basename(report_file)}")
                            continue
                            
                        logger.info(f"Trying to load: {os.path.basename(report_file)}")
                        with open(report_file, "r") as f:
                            file_content = f.read()
                            try:
                                original_data = json.loads(file_content)
                                logger.info(f"Successfully loaded report from {os.path.basename(report_file)}")
                                
                                # Transform the data structure to match expected format
                                transformed_data = transform_json_structure(original_data)
                                if transformed_data:
                                    return transformed_data
                                else:
                                    logger.error("Could not transform report data")
                                    
                            except json.JSONDecodeError as e:
                                logger.error(f"JSON decode error in file: {os.path.basename(report_file)}: {str(e)}")
                                continue
                    except Exception as e:
                        logger.error(f"Error with file {os.path.basename(report_file)}: {str(e)}")
                        continue
    
    # If we reach here, no valid report was found
    logger.warning("No valid report files found in any directory")
    return None

def display_market_report(report_data):
    """Display market report using native Streamlit components with enhanced styling."""
    if not report_data:
        st.warning("No market report available.")
        return
    
    # Extract report date and format it
    report_date = report_data.get("date", "")
    try:
        date_obj = datetime.strptime(report_date, "%Y%m%d")
        formatted_date = date_obj.strftime("%A, %B %d, %Y")
    except:
        # Try alternate format
        try:
            date_obj = datetime.strptime(report_date, "%Y-%m-%d")
            formatted_date = date_obj.strftime("%A, %B %d, %Y")
        except:
            formatted_date = report_date
    
    logger.debug(f"Displaying report for date: {formatted_date}")
    
    # Use native Streamlit components
    st.subheader(f"Market Report for {formatted_date}")
    st.title(report_data.get('title', 'Daily Market Report'))
    
    # Summary with more visible styling
    summary = report_data.get("summary", "")
    if summary:
        st.markdown(f"**{summary}**")
        logger.debug("Displayed summary")
    
    # Key trends with spacing
    st.header("Key Market Trends")
    trends = report_data.get("trends", [])
    if trends:
        logger.debug(f"Displaying {len(trends)} trends")
        for i, trend in enumerate(trends):
            direction = trend.get("direction", "neutral")
            
            # Using direct HTML with inline color styles instead of Streamlit's markdown color syntax
            if direction == "up":
                arrow_html = '<span style="color: #28a745; font-weight: bold;">▲</span>'  # Green arrow
                st.markdown(f"<div style='font-size: 18px; margin-bottom: 12px;'>{arrow_html} <strong>{trend.get('currency', '')}</strong>: {trend.get('description', '')}</div>", unsafe_allow_html=True)
            elif direction == "down":
                arrow_html = '<span style="color: #dc3545; font-weight: bold;">▼</span>'  # Red arrow
                st.markdown(f"<div style='font-size: 18px; margin-bottom: 12px;'>{arrow_html} <strong>{trend.get('currency', '')}</strong>: {trend.get('description', '')}</div>", unsafe_allow_html=True)
            else:
                arrow_html = '<span style="color: #fd7e14; font-weight: bold;">◆</span>'  # Orange diamond
                st.markdown(f"<div style='font-size: 18px; margin-bottom: 12px;'>{arrow_html} <strong>{trend.get('currency', '')}</strong>: {trend.get('description', '')}</div>", unsafe_allow_html=True)
            logger.debug(f"Displayed trend {i+1}: {trend.get('currency', '')} ({direction})")
    else:
        st.write("No trend data available")
        logger.warning("No trend data to display")
    
    # Market drivers with spacing
    st.header("Market Drivers")
    drivers = report_data.get("drivers", [])
    if drivers:
        logger.debug(f"Displaying {len(drivers)} drivers")
        for i, driver in enumerate(drivers):
            # Using larger font size and more spacing between items with a bullet point
            st.markdown(f"<div style='font-size: 18px; margin-bottom: 12px;'>• {driver}</div>", unsafe_allow_html=True)
            logger.debug(f"Displayed driver {i+1}")
    else:
        st.write("No driver data available")
        logger.warning("No driver data to display")

    # Market outlook with spacing
    st.header("Market Outlook")
    outlook = report_data.get("outlook", {})
    if outlook:
        sentiment = outlook.get("sentiment", "neutral")
        logger.debug(f"Displaying outlook with sentiment: {sentiment}")
        
        # Add color to outlook based on sentiment, but use direct HTML with larger font
        description = outlook.get('description', '')
        if description:
            if sentiment == "positive":
                # Green background for positive outlook
                st.markdown(f"""
                <div style="background-color: rgba(40, 167, 69, 0.1); border-left: 4px solid #28a745; 
                        padding: 16px; margin: 12px 0; border-radius: 4px;">
                    <p style="font-size: 18px; color: #333333; margin: 0;">{description}</p>
                </div>
                """, unsafe_allow_html=True)
            elif sentiment == "negative":
                # Red background for negative outlook
                st.markdown(f"""
                <div style="background-color: rgba(220, 53, 69, 0.1); border-left: 4px solid #dc3545; 
                        padding: 16px; margin: 12px 0; border-radius: 4px;">
                    <p style="font-size: 18px; color: #333333; margin: 0;">{description}</p>
                </div>
                """, unsafe_allow_html=True)
            else:
                # Blue background for neutral outlook
                st.markdown(f"""
                <div style="background-color: rgba(23, 162, 184, 0.1); border-left: 4px solid #17a2b8; 
                        padding: 16px; margin: 12px 0; border-radius: 4px;">
                    <p style="font-size: 18px; color: #333333; margin: 0;">{description}</p>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.write("No outlook data available")
        logger.warning("No outlook data to display")

# Sidebar with debug toggle
with st.sidebar:
    # Add debug mode toggle at the bottom of the sidebar
    st.markdown("### Developer Options")
    debug_toggle = st.checkbox("Enable Debug Mode", value=st.session_state.debug_mode)
    
    # Update debug mode if changed
    if debug_toggle != st.session_state.debug_mode:
        st.session_state.debug_mode = debug_toggle
        if debug_toggle:
            logger.setLevel(logging.DEBUG)
            st.success("Debug mode enabled")
            logger.debug("Debug logging enabled")
        else:
            logger.setLevel(logging.WARNING)
            st.info("Debug mode disabled")
        st.rerun()

# Main content - using a two-column layout
# First get the market report data
logger.info("Fetching latest market report")
report_data = get_latest_report()

# If no valid report, generate a sample
if not report_data:
    logger.warning("No valid report found, using sample data")
    # Sample report data 
    sample_json = {
        "market_summary": {
            "date": "2025-03-12",
            "overview": "Stocks plunged to a six-month low amid ongoing uncertainty about the impact of policies from the Trump White House and concerns about the U.S. economy.",
            "major_indexes": {
                "Dow Jones Industrial Average": {
                    "performance": "Fell 2.1%, equivalent to a near-900 point decline.",
                    "status": "Closed at its lowest level since last September."
                },
                "S&P 500": {
                    "performance": "Shed 2.7%.",
                    "status": "Closed at its lowest level since last September."
                },
                "Nasdaq Composite": {
                    "performance": "Dropped 4%.",
                    "status": "Biggest one-day loss since September 2022."
                }
            },
            "notable_stocks": {
                "Tesla (TSLA)": {
                    "performance": "Plummeted 15.4%.",
                    "details": "Facing weak deliveries, tariffs, and declining sales in China and Europe."
                },
                "Apple (AAPL)": {
                    "performance": "Slid nearly 6%.",
                    "details": "Delay in AI-driven Siri features could impact iPhone sales."
                },
                "Palantir (PLTR)": {
                    "performance": "Dropped 11%.",
                    "details": "Concerns about economic uncertainty and potential defense spending cuts."
                }
            },
            "economic_indicators": {
                "10-year Treasury yield": {
                    "performance": "Fell to 4.22% from 4.32%.",
                    "details": "Reflects growing concerns about the economy."
                },
                "Inflation rate": {
                    "performance": "Rose to 3.00% in January.",
                    "details": "Core inflation stayed roughly the same at 3.26%."
                }
            }
        },
        "market_tendencies_for_tomorrow": {
            "overview": "Investors are concerned about President Trump's plans for widespread tariffs and the retaliatory measures announced by other countries.",
            "expectations": {
                "Federal Reserve meeting": {
                    "details": "The Fed will conclude its meeting and announce the new level of the federal funds rate. It is expected to keep the rate unchanged, but may announce a 0.25% cut.",
                    "impact": "Could influence market sentiment and economic projections."
                },
                "Consumer sentiment": {
                    "details": "Consumer spending has supported the economy's recovery, but worries about cost increases may erode optimism.",
                    "impact": "Potential slowdown in consumer spending could affect economic growth."
                }
            },
            "sectors_to_watch": {
                "Consumer staples": {
                    "details": "Investors may continue to turn to consumer staples as a defense against volatility.",
                    "impact": "Sector could outperform if market uncertainty persists."
                },
                "Technology": {
                    "details": "High-flying tech stocks have been hit hard by fears of a possible recession.",
                    "impact": "Continued volatility expected in the tech sector."
                }
            }
        }
    }
    
    # Transform the sample data
    logger.info("Transforming sample data")
    report_data = transform_json_structure(sample_json)

# Create two columns
col_report, col_features = st.columns([5, 4])

# Left column: Market Report
with col_report:
    logger.info("Displaying market report")
    display_market_report(report_data)
    
    # Show log viewer if in debug mode
    if st.session_state.debug_mode:
        with st.expander("Debug Logs", expanded=True):
            st.text(log_capture.getvalue())

# Right column: Feature Cards
with col_features:
    # App heading
    st.title("🌐 FX Pulsar Hub")
    st.write("Comprehensive Foreign Exchange and Crypto Market Analysis Tools")
    
    # Use containers with borders for feature cards
    with st.container():
        st.subheader("💱 FX Market Monitor")
        st.write("Real-time monitoring of foreign exchange and cryptocurrency markets with market sentiment analysis, volatility tracking, and economic calendar integration.")
        col1, col2 = st.columns(2)
        with col1:
            st.write("• Live currency pair tracking")
            st.write("• Interactive heatmaps and visualizations")
        with col2:
            st.write("• Real-time market volatility indicators")
            st.write("• Economic calendar integration")
        
        monitor_btn = st.button("Go to FX Monitor", use_container_width=True)
        if monitor_btn:
            logger.info("Navigating to FX Monitor")
            st.switch_page("pages/1_FX_Monitor.py")
    
    st.markdown("---")
    
    with st.container():
        st.subheader("📰 FX News Summarizer")
        st.write("AI-powered summaries of the latest FX and crypto news, helping you stay informed about market-moving events and trends without information overload.")
        col1, col2 = st.columns(2)
        with col1:
            st.write("• AI-generated market summaries")
            st.write("• Customizable currency pair tracking")
        with col2:
            st.write("• Sentiment analysis integration")
            st.write("• Downloadable reports")
        
        news_btn = st.button("Go to News Summarizer", use_container_width=True)
        if news_btn:
            logger.info("Navigating to News Summarizer")
            st.switch_page("pages/2_News_Summarizer.py")

    st.markdown("---")

    with st.container():
        st.subheader("👥 Trader Sentiment Dashboard")
        st.write("Real-time trader positioning and sentiment analysis to help you identify potential market reversals and gauge overall market bias.")
        col1, col2 = st.columns(2)
        with col1:
            st.write("• Detailed sentiment heatmaps")
            st.write("• Position analysis by currency pair")
        with col2:
            st.write("• Contrarian trading signals")
            st.write("• Historical sentiment tracking")
        
        sentiment_btn = st.button("Go to Trader Sentiment", use_container_width=True)
        if sentiment_btn:
            logger.info("Navigating to Trader Sentiment")
            st.switch_page("pages/3_Trader_Sentiment.py")

# Footer
st.markdown("---")
st.write("FX Pulsar Hub | Comprehensive Market Analysis Platform")
st.caption("Disclaimer: This app is for informational purposes only and should not be considered financial advice.")