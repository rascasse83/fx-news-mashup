import streamlit as st

def load_styles():
    """Load CSS styles for the application"""
    st.markdown("""
    <style>
        /* Custom expandable card */
        .currency-card {
            margin-bottom: 10px;
            border: 1px solid #333;
            border-radius: 5px;
            overflow: hidden;
        }
        .card-header {
            background-color: #1E1E1E;
            padding: 10px 15px;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #333;
        }
        .card-header:hover {
            background-color: #2C2C2C;
        }
        .card-header-left {
            font-weight: bold;
            font-size: 16px;
        }
        .card-header-right {
            display: flex;
            align-items: center;
        }
        .card-change {
            margin-right: 15px;
            font-weight: bold;
        }
        .card-sentiment {
            font-size: 13px;
        }
        .card-content {
            padding: 15px;
            display: none;
        }
        .show-content .card-content {
            display: block;
        }
        .arrow-icon {
            margin-left: 10px;
            transition: transform 0.3s;
        }
        .show-content .arrow-icon {
            transform: rotate(180deg);
        }
        /* Add colors */
        .positive {
            color: #4CAF50;
        }
        .negative {
            color: #F44336;
        }
        
        .header-container {
            background-color: #1E1E1E;
            border-radius: 5px 5px 0 0;
            padding: 10px 15px;
            margin-bottom: 0;
            border: 1px solid #333;
            border-bottom: none;
        }
        
        /* This helps reduce space around the header */
        header {
            visibility: hidden;
        }
        
        /* Optional: Reduce space taken by the sidebar header */
        #MainMenu {visibility: hidden;}
        .stDeployButton {display:none;}
        
        .block-container {
            padding-top: 1rem !important;
        }
    </style>
    """, unsafe_allow_html=True)