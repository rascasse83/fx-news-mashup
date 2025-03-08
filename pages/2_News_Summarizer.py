# Add this at the very top of your script, before any other imports
import sys

# Fix for PyTorch with Streamlit
# This prevents Streamlit's file watcher from trying to inspect PyTorch modules
class PathFinder:
    def __init__(self, path):
        self._path = path
    
    def __iter__(self):
        return iter(self._path)

# Apply the fix to torch._C module if needed
try:
    import torch
    if not hasattr(torch._C, "__path__"):
        torch._C.__path__ = PathFinder([])
except (ImportError, AttributeError):
    pass


import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import os
import re
import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from fx_news.scrapers.news.news_reader import get_local_news_articles, get_news_for_currency_pair
from transformers import BertTokenizer, BertForSequenceClassification
import torch

# Page configuration
st.set_page_config(
    page_title="FX Pulsar - News Summarizer",
    page_icon="https://images.seeklogo.com/logo-png/60/1/lmax-digital-icon-black-logo-png_seeklogo-609777.png",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for dark theme
st.markdown("""
<style>
    .main-header {
        font-size: 2rem !important;
        font-weight: 700 !important;
        margin-bottom: 1rem !important;
        color: white;
    }
    .block-container {
        padding-top: 1rem !important;
    }
    header {
        visibility: hidden;
    }
    #MainMenu {visibility: hidden;}
    .stDeployButton {display:none;}
</style>
""", unsafe_allow_html=True)

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

def check_news_file_structure(base_dir="fx_news/scrapers/news", show_report=True):
    """
    Check if the news file structure is correct and provide a report.
    
    Args:
        base_dir (str): Base directory for news files
        show_report (bool): Whether to display the report in Streamlit
        
    Returns:
        tuple: (is_valid, report_data)
    """
    report_data = {
        "total_files": 0,
        "valid_files": 0,
        "invalid_files": 0,
        "directories_found": [],
        "currency_pairs_found": set(),
        "date_ranges": {"oldest": None, "newest": None},
        "issues": [],
        "file_samples": []
    }
    
    if not os.path.exists(base_dir):
        report_data["issues"].append(f"Base directory {base_dir} does not exist")
        return False, report_data
    
    if not os.path.isdir(base_dir):
        report_data["issues"].append(f"{base_dir} is not a directory")
        return False, report_data
    
    # Check for source directories
    source_dirs = [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]
    report_data["directories_found"] = source_dirs
    
    if not source_dirs:
        report_data["issues"].append(f"No source directories found in {base_dir}")
        return False, report_data
    
    # Regular expression for expected filename format
    filename_pattern = re.compile(r'^article_\d{8}_\d{6}_([a-z]{3})_([a-z]{3})\.txt$', re.IGNORECASE)
    
    # Check each directory
    for source_dir in source_dirs:
        dir_path = os.path.join(base_dir, source_dir)
        files = [f for f in os.listdir(dir_path) if f.endswith('.txt')]
        
        report_data["total_files"] += len(files)
        
        # Check up to 10 files in each directory
        for file in files[:10]:
            file_path = os.path.join(dir_path, file)
            file_info = {
                "filename": file,
                "source": source_dir,
                "size": os.path.getsize(file_path),
                "valid": False,
                "issues": []
            }
            
            # Check filename format
            match = filename_pattern.match(file)
            if match:
                file_info["valid"] = True
                base_currency = match.group(1).upper()
                quote_currency = match.group(2).upper()
                currency_pair = f"{base_currency}/{quote_currency}"
                file_info["currency_pair"] = currency_pair
                report_data["currency_pairs_found"].add(currency_pair)
                
                # Extract date
                date_match = re.search(r'article_(\d{8})_(\d{6})_', file)
                if date_match:
                    date_str = date_match.group(1)
                    time_str = date_match.group(2)
                    try:
                        file_date = pd.to_datetime(f"{date_str}_{time_str}", format="%Y%m%d_%H%M%S")
                        file_info["date"] = file_date
                        
                        # Update date ranges
                        if report_data["date_ranges"]["oldest"] is None or file_date < report_data["date_ranges"]["oldest"]:
                            report_data["date_ranges"]["oldest"] = file_date
                        if report_data["date_ranges"]["newest"] is None or file_date > report_data["date_ranges"]["newest"]:
                            report_data["date_ranges"]["newest"] = file_date
                    except ValueError:
                        file_info["issues"].append("Invalid date format in filename")
                        file_info["valid"] = False
            else:
                file_info["issues"].append("Filename doesn't match expected pattern article_YYYYMMDD_HHMMSS_currency_pair.txt")
            
            # Check file content
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                if not content:
                    file_info["issues"].append("File is empty")
                    file_info["valid"] = False
                elif len(content.strip().splitlines()) < 2:
                    file_info["issues"].append("File should have at least a title and content")
                    file_info["valid"] = False
                
                file_info["content_sample"] = content[:100] + "..." if len(content) > 100 else content
                
            except Exception as e:
                file_info["issues"].append(f"Error reading file: {str(e)}")
                file_info["valid"] = False
            
            # Update valid file count
            if file_info["valid"]:
                report_data["valid_files"] += 1
            else:
                report_data["invalid_files"] += 1
            
            report_data["file_samples"].append(file_info)
    
    # Overall validation
    is_valid = report_data["total_files"] > 0 and report_data["valid_files"] > 0
    
    # Display report if requested
    if show_report and st:
        st.subheader("News Files Structure Check")
        
        # Summary metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Files", report_data["total_files"])
        with col2:
            st.metric("Valid Files", report_data["valid_files"])
        with col3:
            st.metric("Invalid Files", report_data["invalid_files"])
        
        # Source directories
        st.markdown("### Source Directories")
        if report_data["directories_found"]:
            st.write(", ".join(report_data["directories_found"]))
        else:
            st.error("No source directories found")
        
        # Currency pairs
        st.markdown("### Currency Pairs Found")
        if report_data["currency_pairs_found"]:
            st.write(", ".join(sorted(report_data["currency_pairs_found"])))
        else:
            st.warning("No currency pairs identified")
        
        # Date ranges
        st.markdown("### Date Range")
        if report_data["date_ranges"]["oldest"] and report_data["date_ranges"]["newest"]:
            st.write(f"Oldest: {report_data['date_ranges']['oldest'].strftime('%Y-%m-%d %H:%M:%S')}")
            st.write(f"Newest: {report_data['date_ranges']['newest'].strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            st.warning("Could not determine date range")
        
        # Issues
        if report_data["issues"]:
            st.markdown("### Issues Found")
            for issue in report_data["issues"]:
                st.error(issue)
        
        # File samples - THIS IS THE FIX: avoid nested expanders by using a different UI pattern
        st.markdown("### File Samples")
        if report_data["file_samples"]:
            # Create a selectbox to choose which file to view
            sample_options = [f"{sample['source']}/{sample['filename']} - {'✅ Valid' if sample['valid'] else '❌ Invalid'}" 
                             for sample in report_data["file_samples"][:5]]
            
            if sample_options:
                selected_sample = st.selectbox("Select a file to view details:", sample_options)
                
                # Find the selected sample
                selected_index = sample_options.index(selected_sample)
                sample = report_data["file_samples"][selected_index]
                
                # Display sample details
                st.markdown(f"**File:** {sample['filename']}")
                st.write(f"Source: {sample['source']}")
                
                if 'currency_pair' in sample:
                    st.write(f"Currency Pair: {sample.get('currency_pair', 'Unknown')}")
                
                if 'date' in sample:
                    st.write(f"Date: {sample['date'].strftime('%Y-%m-%d %H:%M:%S')}")
                
                st.write(f"Size: {sample['size']} bytes")
                
                if sample["issues"]:
                    st.error("Issues: " + ", ".join(sample["issues"]))
                
                st.text_area("Content Sample", sample["content_sample"], height=100)
    
    return is_valid, report_data

# Add this function to analyze sentiment with FinBERT
def analyze_sentiment_with_finbert(text, model=None, tokenizer=None):
    """
    Analyze financial sentiment of text using FinBERT.
    
    Args:
        text (str): Text to analyze
        model: Pre-loaded BertForSequenceClassification model (optional)
        tokenizer: Pre-loaded BertTokenizer (optional)
        
    Returns:
        dict: Dictionary with sentiment, score, and label color
    """
    # Load model and tokenizer if not provided
    if model is None or tokenizer is None:
        try:
            # You might need to adjust the model name/path based on your setup
            model_name = "yiyanghkust/finbert-tone"
            if 'finbert_model' not in st.session_state or 'finbert_tokenizer' not in st.session_state:
                with st.spinner("Loading FinBERT sentiment model..."):
                    tokenizer = BertTokenizer.from_pretrained(model_name)
                    model = BertForSequenceClassification.from_pretrained(model_name)
                    st.session_state.finbert_model = model
                    st.session_state.finbert_tokenizer = tokenizer
            else:
                model = st.session_state.finbert_model
                tokenizer = st.session_state.finbert_tokenizer
        except Exception as e:
            st.warning(f"Error loading FinBERT model: {str(e)}. Using basic sentiment analysis.")
            return basic_sentiment_analysis(text)
    
    try:
        # Prepare the text for the model (truncate if needed)
        # FinBERT typically handles 512 tokens max
        max_length = 512
        
        # Tokenize and get prediction
        inputs = tokenizer(text, return_tensors="pt", max_length=max_length, truncation=True, padding=True)
        with torch.no_grad():
            outputs = model(**inputs)
            predictions = torch.nn.functional.softmax(outputs.logits, dim=-1)
            
        # FinBERT-tone labels: 0=Negative, 1=Neutral, 2=Positive
        label_map = {0: "negative", 1: "neutral", 2: "positive"}
        color_map = {0: "#FF5252", 1: "#9E9E9E", 2: "#4CAF50"}  # Red, Grey, Green
        
        # Get the highest probability class
        predicted_class = torch.argmax(predictions, dim=1).item()
        confidence = predictions[0][predicted_class].item()
        
        # For calculating a numerical score (-1 to 1)
        if predicted_class == 0:  # Negative
            score = -confidence
        elif predicted_class == 2:  # Positive
            score = confidence
        else:  # Neutral
            score = 0
            
        return {
            "sentiment": label_map[predicted_class],
            "label": predicted_class,
            "confidence": confidence,
            "score": score,
            "color": color_map[predicted_class]
        }
        
    except Exception as e:
        st.warning(f"Error during FinBERT sentiment analysis: {str(e)}. Using basic analysis.")
        return basic_sentiment_analysis(text)

# Fallback sentiment analysis
def basic_sentiment_analysis(text):
    """Simple rule-based sentiment analysis as fallback"""
    text_lower = text.lower()
    
    # Simple keyword matching
    positive_words = ['positive', 'increase', 'rise', 'gain', 'growth', 'improve', 'bullish', 'uptrend', 'recovery']
    negative_words = ['negative', 'decrease', 'fall', 'drop', 'decline', 'worsen', 'bearish', 'downtrend', 'recession']
    
    positive_count = sum(1 for word in positive_words if word in text_lower)
    negative_count = sum(1 for word in negative_words if word in text_lower)
    
    # Determine sentiment
    if positive_count > negative_count:
        sentiment = "positive"
        score = min(0.7, (positive_count - negative_count) / 10)
        color = "#4CAF50"  # Green
    elif negative_count > positive_count:
        sentiment = "negative"
        score = max(-0.7, (negative_count - positive_count) / -10)
        color = "#FF5252"  # Red
    else:
        sentiment = "neutral"
        score = 0
        color = "#9E9E9E"  # Grey
        
    return {
        "sentiment": sentiment,
        "confidence": abs(score),
        "score": score,
        "color": color
    }




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

#---------------------------------------------------------------
# Function to search local news files
#---------------------------------------------------------------
def search_fx_news(pairs, sources, time_range, base_dir="fx_news/scrapers/news", debug=False):
    """
    Search for FX news using local text files.
    
    Args:
        pairs (dict): Dictionary of currency pairs with boolean selection
        sources (dict): Dictionary of news sources with boolean selection
        time_range (str): Time range selection (e.g., "Last 24 hours")
        base_dir (str): Base directory for news articles
    """
    st.info("Searching for FX news...", icon="🔍")
    progress_bar = st.progress(0)
    
    # Convert selected pairs to list of tuples
    selected_pairs = []
    for pair, selected in pairs.items():
        if selected:
            base, quote = pair.split('/')
            selected_pairs.append((base, quote))
    
    # Convert selected sources to list
    selected_sources = [source for source, selected in sources.items() if selected]
    
    # Map time range to days
    days_map = {
        "Last 24 hours": 1,
        "Last 3 days": 3,
        "Last week": 7
    }
    days = days_map[time_range]
    
    progress_bar.progress(0.2)
    
    # Get all news articles from the directories
    all_articles = []
    for base, quote in selected_pairs:
        # Get news specifically for this currency pair
        articles = get_news_for_currency_pair(base, quote, base_dir, days, debug)
        all_articles.extend(articles)
    
    progress_bar.progress(0.7)
    
    # Filter by selected sources
    if selected_sources:
        all_articles = [article for article in all_articles 
                      if article.get('source', '').lower() in [s.lower() for s in selected_sources]]
    
    # Convert to DataFrame for easier handling
    if all_articles:
        df = pd.DataFrame(all_articles)
        
        # Ensure date column is datetime
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'], errors='coerce')
            
        # Sort by date (newest first)
        df = df.sort_values('date', ascending=False)
    else:
        # Return empty DataFrame with expected columns
        df = pd.DataFrame(columns=['title', 'text', 'date', 'timestamp', 'source', 'currency', 'file_path'])
    
    progress_bar.progress(1.0)
    time.sleep(0.5)
    progress_bar.empty()
    
    return df

#---------------------------------------------------------------
# Function to create mock news when no local files available
#---------------------------------------------------------------
def create_mock_news(currencies=None):
    """Create mock news data for demo purposes when no local files are available"""
    mock_news = []
    
    # Get current date and time
    now = datetime.now()
    
    # Create some currency pairs from the currencies
    if currencies:
        pairs = []
        for i in range(min(len(currencies), 5)):
            for j in range(i+1, min(len(currencies), 5)):
                pairs.append((currencies[i], currencies[j]))
    else:
        # Default pairs
        pairs = [
            ('EUR', 'USD'), 
            ('GBP', 'USD'), 
            ('USD', 'JPY'), 
            ('AUD', 'USD'),
            ('USD', 'CAD')
        ]
    
    # Sentiment options
    sentiments = ['positive', 'negative', 'neutral']
    sources = ['Reuters', 'Bloomberg', 'Financial Times', 'CNBC', 'ForexLive']
    
    # Create mock news for each pair
    for base, quote in pairs:
        pair = f"{base}/{quote}"
        
        # Create 3-5 news items per pair
        for i in range(np.random.randint(3, 6)):
            # Random timestamp within the last week
            days_ago = np.random.randint(0, 7)
            hours_ago = np.random.randint(0, 24)
            timestamp = now - timedelta(days=days_ago, hours=hours_ago)
            
            # Random sentiment and score
            sentiment = np.random.choice(sentiments)
            if sentiment == 'positive':
                score = np.random.uniform(0.5, 1.0)
            elif sentiment == 'negative':
                score = np.random.uniform(-1.0, -0.5)
            else:
                score = np.random.uniform(-0.3, 0.3)
            
            # Create a mock title based on sentiment
            if sentiment == 'positive':
                title = f"{pair} rises as market confidence grows"
            elif sentiment == 'negative':
                title = f"{pair} falls amid economic uncertainty"
            else:
                title = f"{pair} stable despite market fluctuations"
            
            # Add some variety to titles
            title_variations = [
                f"Analysts predict {pair} will {sentiment == 'positive' and 'strengthen' or 'weaken'} further",
                f"Economic data impacts {pair} {sentiment == 'positive' and 'positively' or 'negatively'}",
                f"Central bank comments affect {pair} outlook",
                f"Trade tensions influence {pair} movement",
                f"Investors react to {pair} {sentiment == 'positive' and 'gains' or 'losses'}"
            ]
            
            if np.random.random() > 0.5:
                title = np.random.choice(title_variations)
            
            # Random source
            source = np.random.choice(sources)
            
            # Create mock URL
            url = f"https://www.example.com/news/{base.lower()}_{quote.lower()}_{timestamp.strftime('%Y%m%d')}"
            
            # Create mock article text
            text = f"""
            {title}. 
            
            Financial markets saw significant movement in {pair} trading today as investors reacted to 
            new economic data and geopolitical developments. Analysts from major financial institutions 
            provided varied perspectives on the currency pair's future direction.
            
            Market participants closely watched statements from central bank officials regarding monetary 
            policy, which could impact interest rate differentials between the {base} and {quote} currencies.
            Trading volume was {np.random.choice(['heavy', 'moderate', 'light'])} throughout the session.
            
            Technical indicators suggest the pair may experience {np.random.choice(['continued momentum', 'resistance', 'support', 'a reversal'])} 
            at current levels. The relative strength index (RSI) currently shows 
            {np.random.choice(['overbought', 'oversold', 'neutral'])} conditions.
            """
            
            # Add to mock news list
            mock_news.append({
                'title': title,
                'text': text,
                'date': timestamp,
                'timestamp': timestamp,
                'source': source,
                'url': url,
                'currency': pair,
                'currency_pairs': {pair},
                'sentiment': sentiment,
                'score': score
            })
    
    # Sort by timestamp (newest first)
    mock_news.sort(key=lambda x: x['timestamp'], reverse=True)
    
    return mock_news

#---------------------------------------------------------------
# Function to get available sources from directory
#---------------------------------------------------------------
def get_available_sources(base_dir="fx_news/scrapers/news"):
    """Get available news sources from folder structure"""
    if not os.path.exists(base_dir):
        return ["Yahoo", "Bloomberg", "FT", "CNBC", "ForexLive"]  # Default fallback
        
    sources = [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]
    if not sources:
        return ["Yahoo", "Bloomberg", "FT", "CNBC", "ForexLive"]  # Default fallback
    return sources

#---------------------------------------------------------------
# Function to generate summaries using DistilBART
#---------------------------------------------------------------
def generate_summaries(news_df, summary_length, include_sentiment, tokenizer, model, debug=False):
    """Generate summaries for the news articles using the DistilBART model."""
    if tokenizer is None or model is None:
        st.error("Model not loaded. Please check the model loading section.")
        return []

    st.info("Generating summaries with DistilBART...", icon="🤖")
    progress_bar = st.progress(0)
    
    summaries = []
    
    # Group news by currency pair
    # First ensure currency_pairs is a string column for groupby to work
    if 'currency' in news_df.columns:
        grouped = news_df.groupby('currency')
    else:
        st.error("News data missing currency information")
        return []
    
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
            # Prepare the news context by combining titles and text snippets
            news_articles_text = []
            for _, row in group.iterrows():
                # Get a snippet of the text (first 300 characters)
                text_snippet = row.get('text', '')[:300] + "..." if len(row.get('text', '')) > 300 else row.get('text', '')
                article_info = f"Title: {row.get('title', '')}\n"
                article_info += f"Source: {row.get('source', '')}\n"
                article_info += f"Date: {row.get('date', '').strftime('%Y-%m-%d %H:%M') if isinstance(row.get('date'), datetime) else row.get('date', '')}\n"
                article_info += f"Content: {text_snippet}\n\n"
                news_articles_text.append(article_info)
            
            # Combine all article texts with reasonable length limits
            news_context = "\n\n".join(news_articles_text)
            
            # Truncate if too long for the model (typically 1024 tokens)
            if len(news_context) > 4000:  # Rough character count estimation
                news_context = news_context[:4000] + "..."
            
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
            
            # Format date range for display
            if 'date' in group.columns:
                min_date = group['date'].min()
                max_date = group['date'].max()
                if isinstance(min_date, datetime) and isinstance(max_date, datetime):
                    date_range = f"{min_date.strftime('%Y-%m-%d')} to {max_date.strftime('%Y-%m-%d')}"
                else:
                    date_range = "Unknown date range"
            else:
                date_range = "Unknown date range"
            
            # Add to summaries list
            summaries.append({
                "pair": pair,
                "summary": formatted_summary,
                "source_count": len(group),
                "date_range": date_range,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            
        except Exception as e:
            error_msg = f"Error generating summary for {pair}: {str(e)}"
            st.error(error_msg)
            # Also add the error to summaries to ensure it doesn't disappear
            summaries.append({
                "pair": pair,
                "summary": f"**ERROR:** {error_msg}\n\nPlease check the model settings and try again.",
                "source_count": len(group) if not group.empty else 0,
                "date_range": "Error",
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "error": True
            })
            # Log the full error for debugging
            print(f"Full error details: {e}")
    
    progress_bar.progress(1.0)
    time.sleep(0.5)
    progress_bar.empty()
    
    return summaries

#---------------------------------------------------------------
# Sidebar for configurations
#---------------------------------------------------------------
with st.sidebar:
    st.header("Configuration")
    
    # News directory path
    st.subheader("News Data Source")
    news_folder = st.text_input(
        "News Files Directory", 
        value="fx_news/scrapers/news",
        help="Path to directory containing news article files"
    )
    
    # Debug mode option
    debug_mode = st.checkbox("Debug Mode", value=False, help="Show detailed debug information")
    
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
    fx_currencies = {
        'EUR': 'Euro',
        'USD': 'US Dollar',
        'GBP': 'British Pound',
        'JPY': 'Japanese Yen',
        'AUD': 'Australian Dollar',
        'CAD': 'Canadian Dollar',
        'CHF': 'Swiss Franc'
    }
    
    # Create currency pair options
    currency_pairs = {}
    
    # Check available pairs from news directory
    is_valid, report = check_news_file_structure(news_folder, show_report=False)
    
    if is_valid and report["currency_pairs_found"]:
        # Use currency pairs found in files
        for pair in sorted(report["currency_pairs_found"]):
            currency_pairs[pair] = st.checkbox(pair, value=True)
    else:
        # Fallback to predefined pairs
        predefined_pairs = [
            "EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD", 
            "USD/CAD", "USD/CHF", "NZD/USD"
        ]
        for pair in predefined_pairs:
            currency_pairs[pair] = st.checkbox(pair, value=pair in ["EUR/USD", "GBP/USD"])
    
    # News sources selection
    st.subheader("News Sources")
    
    # Get available sources from directory
    available_sources = get_available_sources(news_folder)
    news_sources = {}
    for source in available_sources:
        news_sources[source] = st.checkbox(source, value=True)
    
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

    # Add news file diagnostics tool - Replace the existing expander with this
    st.subheader("News Files Diagnostics")
    if st.button("Check News Files Structure"):
        # We'll use a session state variable to indicate we want to display the report
        # in the main area rather than in the sidebar
        st.session_state.show_file_report = True
        st.rerun()  # Rerun to show the report in the main area
    
    # Navigation
    st.markdown("---")
    st.subheader("Navigation")
    
    # Button to navigate to FX Monitor
    if st.button("💱 Go to FX Monitor", use_container_width=True):
        st.switch_page("pages/1_FX_Monitor.py")
    
    # Button to return to home
    if st.button("🏠 Return to Home", use_container_width=True):
        st.switch_page("Home.py")

#---------------------------------------------------------------
# Main content area with tabs
#---------------------------------------------------------------
tab1, tab2, tab3 = st.tabs(["Summaries", "Raw News Data", "About"])

# File Diagnostic Display
# File structure report (conditionally displayed)
if st.session_state.get('show_file_report', False):
    # Create a container with a close button
    report_container = st.container()
    with report_container:
        col1, col2 = st.columns([5, 1])
        with col1:
            st.header("News Files Structure Report")
        with col2:
            if st.button("✖️ Close"):
                st.session_state.show_file_report = False
                st.rerun()
        
        # Run the file check function but don't have it display the report itself
        is_valid, report_data = check_news_file_structure(news_folder, show_report=False)
        
        # Summary metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Files", report_data["total_files"])
        with col2:
            st.metric("Valid Files", report_data["valid_files"])
        with col3:
            st.metric("Invalid Files", report_data["invalid_files"])
        
        # Source directories
        st.markdown("### Source Directories")
        if report_data["directories_found"]:
            st.write(", ".join(report_data["directories_found"]))
        else:
            st.error("No source directories found")
        
        # Currency pairs
        st.markdown("### Currency Pairs Found")
        if report_data["currency_pairs_found"]:
            st.write(", ".join(sorted(report_data["currency_pairs_found"])))
        else:
            st.warning("No currency pairs identified")
        
        # Date ranges
        st.markdown("### Date Range")
        if report_data["date_ranges"]["oldest"] and report_data["date_ranges"]["newest"]:
            st.write(f"Oldest: {report_data['date_ranges']['oldest'].strftime('%Y-%m-%d %H:%M:%S')}")
            st.write(f"Newest: {report_data['date_ranges']['newest'].strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            st.warning("Could not determine date range")
        
        # Issues
        if report_data["issues"]:
            st.markdown("### Issues Found")
            for issue in report_data["issues"]:
                st.error(issue)
        
        # File samples - displayed in a cleaner way
        st.markdown("### File Samples")
        if report_data["file_samples"]:
            # Create tabs for each sample instead
            sample_tabs = st.tabs([f"{i+1}. {sample['source']}/{sample['filename'][:15]}..." 
                                  for i, sample in enumerate(report_data["file_samples"][:5])])
            
            for i, tab in enumerate(sample_tabs):
                with tab:
                    sample = report_data["file_samples"][i]
                    
                    # Show validity at the top with color
                    if sample['valid']:
                        st.success("✅ Valid File")
                    else:
                        st.error("❌ Invalid File")
                    
                    # Create two columns for details
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("**File Details:**")
                        st.markdown(f"**Filename:** {sample['filename']}")
                        st.markdown(f"**Source:** {sample['source']}")
                        if 'currency_pair' in sample:
                            st.markdown(f"**Currency Pair:** {sample.get('currency_pair', 'Unknown')}")
                        st.markdown(f"**Size:** {sample['size']} bytes")
                    
                    with col2:
                        if 'date' in sample:
                            st.markdown(f"**Date:** {sample['date'].strftime('%Y-%m-%d %H:%M:%S')}")
                        
                        if sample["issues"]:
                            st.markdown("**Issues:**")
                            for issue in sample["issues"]:
                                st.warning(f"- {issue}")
                    
                    # Content sample
                    st.markdown("**File Content:**")
                    try:
                        # Read the full file content (up to a reasonable limit)
                        file_path = os.path.join(news_folder, sample['source'], sample['filename'])
                        if os.path.exists(file_path):
                            with open(file_path, 'r', encoding='utf-8') as f:
                                # Read up to 5000 characters (reasonable limit for preview)
                                content = f.read(5000)
                                if len(content) == 5000:
                                    content += "\n\n[... content truncated (showing first 5000 characters) ...]"
                        else:
                            content = "File not found or cannot be accessed."
                    except Exception as e:
                        content = f"Error reading file: {str(e)}"

                    # Display the content with line numbers
                    lines = content.split('\n')
                    numbered_content = '\n'.join([f"{i+1}: {line}" for i, line in enumerate(lines)])
                    st.text_area("", value=numbered_content, height=300, key=f"sample_full_{i}")

                    # Add file information
                    file_path = os.path.join(news_folder, sample['source'], sample['filename'])
                    if os.path.exists(file_path):
                        file_size = os.path.getsize(file_path)
                        file_size_readable = f"{file_size:,} bytes"
                        if file_size > 1024:
                            file_size_readable += f" ({file_size/1024:.1f} KB)"
                        
                        modified_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                        
                        st.caption(f"Full Path: {file_path}")
                        st.caption(f"File Size: {file_size_readable}")
                        st.caption(f"Last Modified: {modified_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        st.markdown("---")

#---------------------------------------------------------------
# Main app logic
#---------------------------------------------------------------
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
            news_df = search_fx_news(currency_pairs, news_sources, time_range, base_dir=news_folder, debug=debug_mode)
            
            # Check if any news was found
            if news_df.empty:
                st.warning(f"No news files found for the selected currency pairs in {news_folder}. Using mock data instead.")
                
                # Get currencies from the selected pairs
                currencies = []
                for pair in selected_pairs:
                    base, quote = pair.split('/')
                    if base not in currencies:
                        currencies.append(base)
                    if quote not in currencies:
                        currencies.append(quote)
                
                # Create mock news
                mock_data = create_mock_news(currencies)
                news_df = pd.DataFrame(mock_data)
            
            # Store raw news in session state for the Raw Data tab
            st.session_state.raw_news = news_df
            
            # Generate summaries
            summaries = generate_summaries(
                news_df, 
                summary_length, 
                include_sentiment, 
                st.session_state.tokenizer, 
                st.session_state.model,
                debug=debug_mode
            )
            
            # Store the results
            st.session_state.summaries = summaries
            st.session_state.last_run = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        st.session_state.is_processing = False
        st.rerun()

#---------------------------------------------------------------
# Display summaries in the first tab
#---------------------------------------------------------------
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

            # Extract the actual summary text (without the markdown formatting)
            summary_text = summary["summary"]
            if summary_text.startswith("## "):
                # Strip away the header
                summary_text = "\n".join(summary_text.split("\n")[1:])
            
            # Analyze sentiment
            sentiment_result = analyze_sentiment_with_finbert(summary_text)
            
            # Add sentiment information to the summary
            summary["sentiment"] = sentiment_result["sentiment"]
            summary["sentiment_score"] = sentiment_result["score"]
            summary["sentiment_color"] = sentiment_result["color"]
            summary["sentiment_confidence"] = sentiment_result["confidence"]

            # Check if this summary contains an error
            if summary.get('error', False):
                any_errors = True
                with error_container:
                    st.error(summary['summary'])
            
            with st.expander(f"📊 {summary['pair']} Summary", expanded=True):
                # Add sentiment badge
                sentiment = summary.get('sentiment', 'neutral')
                sentiment_color = summary.get('sentiment_color', '#9E9E9E')
                sentiment_score = summary.get('sentiment_score', 0)
                sentiment_confidence = summary.get('sentiment_confidence', 0)
                
                # Create header with sentiment badge
                pair_name = summary['pair']
                
                # Extract the header and content
                summary_lines = summary['summary'].split('\n')
                if len(summary_lines) > 0 and summary_lines[0].startswith('## '):
                    header = summary_lines[0][3:]  # Remove the '## ' prefix
                    content = '\n'.join(summary_lines[1:])
                else:
                    header = pair_name
                    content = summary['summary']
                
                # Create a header with custom styling for sentiment
                st.markdown(f"""
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                    <h3 style="margin: 0;">{header}</h3>
                    <div style="display: flex; align-items: center;">
                        <span style="background-color: {sentiment_color}; color: white; padding: 3px 8px; 
                            border-radius: 12px; font-size: 0.8rem; margin-right: 5px;">
                            {sentiment.title()} ({sentiment_score:.2f})
                        </span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # Apply a subtle background tint based on sentiment
                bg_color = f"rgba({sentiment_color[1:3]}, {sentiment_color[3:5]}, {sentiment_color[5:7]}, 0.05)"
                st.markdown(f"""
                <div style="padding: 10px; border-radius: 5px; background-color: {bg_color};">
                    {content}
                </div>
                """, unsafe_allow_html=True)
                
                # Add metadata
                st.caption(f"Based on {summary['source_count']} articles from {summary['date_range']}")
                
                # Add confidence info
                st.caption(f"Sentiment Analysis Confidence: {sentiment_confidence:.2f}")
                
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

#---------------------------------------------------------------
# Display raw news data in the second tab
#---------------------------------------------------------------
with tab2:
    if not st.session_state.raw_news.empty:
        st.subheader("Raw News Data")
        
        # Create a dataframe with clickable links
        df_display = st.session_state.raw_news.copy()
        
        # If URL column exists, format as clickable link
        if 'url' in df_display.columns:
            df_display['url'] = df_display['url'].apply(lambda x: f'<a href="{x}" target="_blank">Link</a>' if x else '')
        
        # Create a more readable display
        st.markdown("### News Articles")
        
        # Display each article in a card
        for i, row in df_display.iterrows():
            with st.expander(f"{row.get('title', 'Untitled')} ({row.get('source', 'Unknown')} - {row.get('date', 'Unknown date')})", expanded=False):
                # Create two columns
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    # Show article text
                    st.markdown("**Article Text:**")
                    st.text_area("", value=row.get('text', 'No content available'), height=200, key=f"text_{i}")
                
                with col2:
                    # Show metadata
                    st.markdown("**Metadata:**")
                    st.write(f"Source: {row.get('source', 'Unknown')}")
                    st.write(f"Date: {row.get('date', 'Unknown date')}")
                    st.write(f"Currency: {row.get('currency', 'Unknown')}")
                    
                    # Show sentiment if available
                    if 'sentiment' in row:
                        sentiment_color = {
                            'positive': 'green',
                            'negative': 'red',
                            'neutral': 'gray'
                        }.get(row['sentiment'], 'gray')
                        
                        st.markdown(f"Sentiment: <span style='color:{sentiment_color};font-weight:bold;'>{row.get('sentiment', 'Unknown')}</span> ({row.get('score', 'N/A')})", unsafe_allow_html=True)
                    
                    # Show URL if available
                    if 'url' in row and row['url']:
                        st.markdown(f"[View Original Article]({row['url']})")
                    
                    # Show file path if available
                    if 'file_path' in row:
                        st.caption(f"File: {os.path.basename(row['file_path'])}")
        
        # Add CSV download button
        if len(df_display) > 0:
            # Prepare for CSV export (remove complex objects like sets)
            export_df = df_display.copy()
            if 'currency_pairs' in export_df.columns:
                export_df['currency_pairs'] = export_df['currency_pairs'].apply(lambda x: ','.join(x) if isinstance(x, set) else x)
            
            csv = export_df.to_csv(index=False)
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name=f"fx_news_data_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
            )
    else:
        st.info("Raw news data will appear here after you run the app.", icon="ℹ️")

#---------------------------------------------------------------
# About tab
#---------------------------------------------------------------
with tab3:
    st.subheader("About this App")
    st.markdown("""
    ### FX News Summarizer with DistilBART

    This Streamlit application helps forex traders and financial analysts stay informed about the 
    foreign exchange market by searching for relevant news and generating AI-powered summaries using
    the DistilBART CNN model running locally.

    #### Features:
    - Reads news from local files in your fx_news/scrapers/news directory
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

    #### File Structure Requirements:
    - News files should be organized in source-specific subdirectories
    - Expected filename format: article_YYYYMMDD_HHMMSS_currency_currency.txt
    - Files should contain article title on the first line and content in the following lines

    #### Requirements:
    - Python 3.7+
    - Streamlit
    - PyTorch
    - Transformers (Hugging Face)
    - Pandas
    - NumPy
    """)
#---------------------------------------------------------------
# Footer
#---------------------------------------------------------------
st.markdown("---")
st.markdown("📰 **FX News Summarizer** | Built with Streamlit and DistilBART")
st.caption("Disclaimer: This app is for informational purposes only and should not be considered financial advice.")


