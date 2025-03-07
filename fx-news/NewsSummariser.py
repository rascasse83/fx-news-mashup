import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

# Page configuration
st.set_page_config(
    page_title="FX News Summarizer",
    page_icon="💱",
    layout="wide"
)

# Initialize session state variables if they don't exist
if 'summaries' not in st.session_state:
    st.session_state.summaries = []
if 'last_run' not in st.session_state:
    st.session_state.last_run = None
if 'is_processing' not in st.session_state:
    st.session_state.is_processing = False
if 'raw_news' not in st.session_state:
    st.session_state.raw_news = pd.DataFrame()
if 'model_loaded' not in st.session_state:
    st.session_state.model_loaded = False
if 'tokenizer' not in st.session_state:
    st.session_state.tokenizer = None
if 'model' not in st.session_state:
    st.session_state.model = None

# App title and description
st.title("💱 FX News Summarizer")
st.markdown("""
This app searches for the latest Foreign Exchange (FX) news and generates concise summaries 
using the DistilBART CNN model locally. Select currency pairs of interest and customize your search parameters.
""")

# Function to load the model
@st.cache_resource
def load_model():
    """Load the DistilBART CNN model and tokenizer."""
    with st.spinner("Loading DistilBART CNN model for summarization... This may take a moment."):
        try:
            tokenizer = AutoTokenizer.from_pretrained("sshleifer/distilbart-cnn-12-6")
            model = AutoModelForSeq2SeqLM.from_pretrained("sshleifer/distilbart-cnn-12-6")
            return tokenizer, model, True
        except Exception as e:
            st.error(f"Error loading model: {str(e)}")
            return None, None, False

# Function to search and fetch news
def search_fx_news(pairs, sources, time_range):
    """
    Simulated function to search for FX news.
    In a real app, this would connect to news APIs or scrape websites.
    """
    st.info("Searching for FX news...", icon="🔍")
    progress_bar = st.progress(0)
    
    # Convert selected pairs and sources to lists
    selected_pairs = [pair for pair, selected in pairs.items() if selected]
    selected_sources = [source for source, selected in sources.items() if selected]
    
    # Map time range to days
    days_map = {
        "Last 24 hours": 1,
        "Last 3 days": 3,
        "Last week": 7
    }
    days = days_map[time_range]
    
    # Sample news data structure
    news_data = []
    
    # Example news sources URLs (for demonstration)
    source_urls = {
        "Reuters": "https://www.reuters.com/markets/currencies/",
        "Bloomberg": "https://www.bloomberg.com/markets/currencies",
        "Financial Times": "https://www.ft.com/currencies",
        "CNBC": "https://www.cnbc.com/currencies/",
        "ForexLive": "https://www.forexlive.com/"
    }
    
    # For each selected source, simulate fetching news
    for i, source in enumerate(selected_sources):
        progress_bar.progress((i / len(selected_sources)) * 0.5)
        time.sleep(0.5)  # Simulate API call delay
        
        # In a real app, you would use requests to get actual content
        for pair in selected_pairs:
            # Generate random date within the specified time range
            days_ago = pd.to_datetime('today') - timedelta(days=days*np.random.random())
            
            # Add some sample news items (in a real app, these would come from the API/scraping)
            news_data.append({
                "title": f"{pair} Analysis: Market trends and central bank impacts",
                "source": source,
                "url": source_urls.get(source, "#"),
                "date": days_ago.strftime("%Y-%m-%d %H:%M"),
                "snippet": f"Recent movements in {pair} have been influenced by central bank policies and economic data releases. Analysts expect continued volatility as markets digest the latest statements from central bankers. Economic indicators from major economies have shown mixed signals, leading to uncertain trading conditions. Traders are closely monitoring inflation data and employment figures for clues about future interest rate decisions.",
                "pair": pair
            })
            
            news_data.append({
                "title": f"Economic indicators affecting {pair} exchange rates",
                "source": source,
                "url": source_urls.get(source, "#"),
                "date": days_ago.strftime("%Y-%m-%d %H:%M"),
                "snippet": f"Key economic indicators released this week have caused volatility in {pair} trading. GDP figures from several countries have surprised analysts, leading to significant market movements. Manufacturing and services PMI data have also contributed to changing market sentiment. The upcoming central bank meeting is expected to provide further direction for this currency pair as policymakers weigh inflation concerns against growth targets.",
                "pair": pair
            })
    
    progress_bar.progress(0.5)
    time.sleep(1)  # Simulate processing delay
    
    # Convert to DataFrame for easier handling
    df = pd.DataFrame(news_data)
    
    # Sort by date (newest first)
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date', ascending=False)
    
    progress_bar.progress(1.0)
    time.sleep(0.5)
    progress_bar.empty()
    
    return df

# Function to generate summaries using DistilBART
def generate_summaries(news_df, summary_length, include_sentiment, tokenizer, model):
    """Generate summaries for the news articles using the DistilBART model."""
    if tokenizer is None or model is None:
        st.error("Model not loaded. Please check the model loading section.")
        return []

    st.info("Generating summaries with DistilBART...", icon="🤖")
    progress_bar = st.progress(0)
    
    summaries = []
    
    # Group news by currency pair
    grouped = news_df.groupby('pair')
    
    # Map summary length to max/min token counts
    length_map = {
        "Very Short": (30, 60),
        "Short": (60, 100),
        "Medium": (100, 150),
        "Detailed": (150, 250)
    }
    min_length, max_length = length_map[summary_length]
    
    # Prepare device
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)
    
    for i, (pair, group) in enumerate(grouped):
        progress_bar.progress((i / len(grouped)) * 0.9)
        
        try:
            # Prepare the news context
            news_context = "\n\n".join([
                f"Title: {row['title']}\nSource: {row['source']}\nDate: {row['date']}\nContent: {row['snippet']}"
                for _, row in group.iterrows()
            ])
            
            # Add sentiment analysis instruction if needed
            if include_sentiment:
                news_context += "\n\nPlease include market sentiment analysis and potential impact on trading in the summary."
            
            # Tokenize and generate summary
            inputs = tokenizer(news_context, max_length=1024, return_tensors="pt").to(device)
            
            # Generate summary
            summary_ids = model.generate(
                inputs["input_ids"],
                num_beams=4,
                min_length=min_length,
                max_length=max_length,
                early_stopping=True
            )
            
            # Decode the summary
            summary_text = tokenizer.decode(summary_ids[0], skip_special_tokens=True)
            
            # Format the summary with markdown
            formatted_summary = f"## {pair} Market Summary\n\n{summary_text}"
            
            # Add to summaries list
            summaries.append({
                "pair": pair,
                "summary": formatted_summary,
                "source_count": len(group),
                "date_range": f"{group['date'].min().strftime('%Y-%m-%d')} to {group['date'].max().strftime('%Y-%m-%d')}",
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            
        except Exception as e:
            error_msg = f"Error generating summary for {pair}: {str(e)}"
            st.error(error_msg)
            # Also add the error to summaries to ensure it doesn't disappear
            summaries.append({
                "pair": pair,
                "summary": f"**ERROR:** {error_msg}\n\nPlease check the model settings and try again.",
                "source_count": len(group),
                "date_range": f"{group['date'].min().strftime('%Y-%m-%d')} to {group['date'].max().strftime('%Y-%m-%d')}",
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "error": True
            })
            # Log the full error for debugging
            print(f"Full error details: {e}")
    
    progress_bar.progress(1.0)
    time.sleep(0.5)
    progress_bar.empty()
    
    return summaries

# Sidebar for configurations
with st.sidebar:
    st.header("Configuration")
    
    # Model loading section
    st.subheader("Model")
    if not st.session_state.model_loaded:
        if st.button("Load DistilBART Model"):
            tokenizer, model, success = load_model()
            if success:
                st.session_state.tokenizer = tokenizer
                st.session_state.model = model
                st.session_state.model_loaded = True
                st.success("Model loaded successfully!")
            else:
                st.error("Failed to load model. Please try again.")
    else:
        st.success("DistilBART Model loaded! ✅")
        if st.button("Reload Model"):
            tokenizer, model, success = load_model()
            if success:
                st.session_state.tokenizer = tokenizer
                st.session_state.model = model
                st.success("Model reloaded successfully!")
    
    # Currency pairs selection
    st.subheader("Currency Pairs")
    currency_pairs = {
        "EUR/USD": st.checkbox("EUR/USD", value=True),
        "GBP/USD": st.checkbox("GBP/USD", value=True),
        "USD/JPY": st.checkbox("USD/JPY"),
        "AUD/USD": st.checkbox("AUD/USD"),
        "USD/CAD": st.checkbox("USD/CAD"),
        "USD/CHF": st.checkbox("USD/CHF"),
        "NZD/USD": st.checkbox("NZD/USD"),
    }
    
    # News sources selection
    st.subheader("News Sources")
    news_sources = {
        "Reuters": st.checkbox("Reuters", value=True),
        "Bloomberg": st.checkbox("Bloomberg", value=True),
        "Financial Times": st.checkbox("Financial Times"),
        "CNBC": st.checkbox("CNBC", value=True),
        "ForexLive": st.checkbox("ForexLive", value=True),
    }
    
    # Time range selection
    st.subheader("Time Range")
    time_range = st.radio(
        "Select news from:",
        ["Last 24 hours", "Last 3 days", "Last week"]
    )
    
    # Summary length
    st.subheader("Summary Options")
    summary_length = st.select_slider(
        "Summary Length",
        options=["Very Short", "Short", "Medium", "Detailed"]
    )
    
    # Include market sentiment
    include_sentiment = st.checkbox("Include Market Sentiment Analysis", value=True)
    
    # Run button - disabled if model not loaded
    run_btn = st.button("Generate Summaries", type="primary", disabled=not st.session_state.model_loaded)

    # Debug section (toggle visibility)
    with st.expander("Debug Options", expanded=False):
        show_errors = st.checkbox("Show Error Details", value=True)
        log_level = st.selectbox("Log Level", ["INFO", "DEBUG", "WARNING", "ERROR"])
        if st.button("Clear Session State"):
            # Keep model loaded but clear results
            tokenizer = st.session_state.tokenizer
            model = st.session_state.model
            model_loaded = st.session_state.model_loaded
            st.session_state.clear()
            st.session_state.tokenizer = tokenizer
            st.session_state.model = model
            st.session_state.model_loaded = model_loaded
            st.experimental_rerun()

# Main content area with tabs
tab1, tab2, tab3 = st.tabs(["Summaries", "Raw News Data", "About"])

# Main app logic
if run_btn:
    if not st.session_state.model_loaded:
        st.sidebar.error("Please load the model first.")
    else:
        st.session_state.is_processing = True
        
        # Get selected pairs and sources
        selected_pairs = {k: v for k, v in currency_pairs.items() if v}
        selected_sources = {k: v for k, v in news_sources.items() if v}
        
        if not any(selected_pairs.values()):
            st.error("Please select at least one currency pair.")
        elif not any(selected_sources.values()):
            st.error("Please select at least one news source.")
        else:
            # Search for news
            news_df = search_fx_news(currency_pairs, news_sources, time_range)
            
            # Store raw news in session state for the Raw Data tab
            st.session_state.raw_news = news_df
            
            # Generate summaries
            summaries = generate_summaries(
                news_df, 
                summary_length, 
                include_sentiment, 
                st.session_state.tokenizer, 
                st.session_state.model
            )
            
            # Store the results
            st.session_state.summaries = summaries
            st.session_state.last_run = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        st.session_state.is_processing = False
        st.rerun()

# Display summaries in the first tab
with tab1:
    if st.session_state.is_processing:
        st.info("Processing your request...", icon="⏳")
    
    elif st.session_state.summaries:
        st.success(f"Last updated: {st.session_state.last_run}")
        
        # Create a container to display any errors that occurred
        error_container = st.container()
        any_errors = False
        
        # Display each summary in an expandable container
        for summary in st.session_state.summaries:
            # Check if this summary contains an error
            if summary.get('error', False):
                any_errors = True
                with error_container:
                    st.error(summary['summary'])
            
            with st.expander(f"📊 {summary['pair']} Summary", expanded=True):
                st.markdown(summary['summary'])
                st.caption(f"Based on {summary['source_count']} articles from {summary['date_range']}")
                
                # Add download button for this summary
                summary_text = f"# {summary['pair']} FX Market Summary\n\n"
                summary_text += f"Generated on: {summary['generated_at']}\n"
                summary_text += f"Date range: {summary['date_range']}\n"
                summary_text += f"Based on {summary['source_count']} news articles\n\n"
                summary_text += summary['summary']
                
                st.download_button(
                    label="Download Summary",
                    data=summary_text,
                    file_name=f"{summary['pair'].replace('/', '_')}_summary_{datetime.now().strftime('%Y%m%d')}.md",
                    mime="text/markdown",
                )
        
        # Add button to download all summaries
        all_summaries = "\n\n---\n\n".join([
            f"# {summary['pair']} FX Market Summary\n\n{summary['summary']}" 
            for summary in st.session_state.summaries
        ])
        
        st.download_button(
            label="Download All Summaries",
            data=all_summaries,
            file_name=f"fx_market_summaries_{datetime.now().strftime('%Y%m%d')}.md",
            mime="text/markdown",
        )
    
    else:
        if st.session_state.model_loaded:
            st.info("Configure your preferences in the sidebar and click 'Generate Summaries' to get started.", icon="👈")
        else:
            st.warning("Please load the DistilBART model in the sidebar first.", icon="⚠️")

# Display raw news data in the second tab
with tab2:
    if not st.session_state.raw_news.empty:
        st.subheader("Raw News Data")
        st.dataframe(st.session_state.raw_news, use_container_width=True)
        
        # Add CSV download button
        csv = st.session_state.raw_news.to_csv(index=False)
        st.download_button(
            label="Download CSV",
            data=csv,
            file_name=f"fx_news_data_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )
    else:
        st.info("Raw news data will appear here after you run the app.", icon="ℹ️")

# About tab
with tab3:
    st.subheader("About this App")
    st.markdown("""
    ### FX News Summarizer with DistilBART

    This Streamlit application helps forex traders and financial analysts stay informed about the 
    foreign exchange market by searching for relevant news and generating AI-powered summaries using
    the DistilBART CNN model running locally.

    #### Features:
    - Runs completely locally without requiring API keys
    - Search for news on multiple currency pairs
    - Customize news sources and time range
    - Generate concise summaries with optional sentiment analysis
    - Download summaries in Markdown format
    - Access raw news data for further analysis

    #### About the Model:
    DistilBART CNN is a distilled version of the BART model fine-tuned on CNN Daily Mail news articles 
    for summarization tasks. It generates abstractive summaries that capture the key points from input text
    while being significantly smaller and faster than the full BART model.

    #### Implementation Notes:
    - The app currently uses simulated news data for demonstration purposes
    - In a production environment, you would connect to real news APIs or perform web scraping
    - Summarization is performed locally using the DistilBART model from Hugging Face
    - First-time model loading may take a minute depending on your system

    #### Requirements:
    - Python 3.7+
    - Streamlit
    - PyTorch
    - Transformers (Hugging Face)
    - Pandas
    - NumPy
    """)

# Footer
st.markdown("---")
st.markdown("💱 **FX News Summarizer** | Built with Streamlit and DistilBART")
st.caption("Disclaimer: This app is for informational purposes only and should not be considered financial advice.")