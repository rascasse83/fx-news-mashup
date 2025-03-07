import streamlit as st

# Configure page
st.set_page_config(
    page_title="FX Pulsar Hub",
    page_icon="https://images.seeklogo.com/logo-png/60/1/lmax-digital-icon-black-logo-png_seeklogo-609777.png",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 3rem !important;
        font-weight: 700 !important;
        margin-bottom: 1rem !important;
        color: white;
    }
    .sub-header {
        font-size: 1.5rem !important;
        margin-bottom: 2rem !important;
        color: #a0a0a0;
    }
    .card {
        background-color: #1E1E1E;
        border-radius: 10px;
        padding: 20px;
        margin: 10px 0px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        transition: transform 0.3s ease;
    }
    .card:hover {
        transform: translateY(-5px);
    }
    .card-title {
        font-size: 1.8rem !important;
        font-weight: 600 !important;
        margin-bottom: 0.5rem !important;
        color: white;
    }
    .card-text {
        color: #a0a0a0;
        margin-bottom: 1rem;
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

# Header
st.markdown("<h1 class='main-header'>🌐 FX Pulsar Hub</h1>", unsafe_allow_html=True)
st.markdown("<p class='sub-header'>Comprehensive Foreign Exchange and Crypto Market Analysis Tools</p>", unsafe_allow_html=True)

# Main content with cards for each page
col1, col2 = st.columns(2)

with col1:
    st.markdown("""
    <div class="card">
        <h2 class="card-title">💱 FX Market Monitor</h2>
        <p class="card-text">
            Real-time monitoring of foreign exchange and cryptocurrency markets with market sentiment analysis, 
            volatility tracking, and economic calendar integration.
        </p>
        <ul style="color: #a0a0a0;">
            <li>Live currency pair tracking</li>
            <li>Interactive heatmaps and visualizations</li>
            <li>Real-time market volatility indicators</li>
            <li>Economic calendar integration</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
    
    monitor_btn = st.button("Go to FX Monitor", use_container_width=True)
    if monitor_btn:
        st.switch_page("pages/1_FX_Monitor.py")

with col2:
    st.markdown("""
    <div class="card">
        <h2 class="card-title">📰 FX News Summarizer</h2>
        <p class="card-text">
            AI-powered summaries of the latest FX and crypto news, helping you stay informed about 
            market-moving events and trends without information overload.
        </p>
        <ul style="color: #a0a0a0;">
            <li>AI-generated market summaries</li>
            <li>Customizable currency pair tracking</li>
            <li>Sentiment analysis integration</li>
            <li>Downloadable reports</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
    
    news_btn = st.button("Go to News Summarizer", use_container_width=True)
    if news_btn:
        st.switch_page("pages/2_News_Summarizer.py")

# Footer
st.markdown("---")
st.markdown("FX Pulsar Hub | Comprehensive Market Analysis Platform")
st.caption("Disclaimer: This app is for informational purposes only and should not be considered financial advice.")