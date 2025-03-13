import streamlit as st
import json
import os
import logging
from datetime import datetime, timedelta
import glob
from io import StringIO
from streamlit_push_notifications import send_push
# https://github.com/yunisguliyev/streamlit-notifications?tab=readme-ov-file
import boto3
import base64
import os
import csv
import io
from pydub import AudioSegment
import requests
import tempfile
from dotenv import load_dotenv
# import wave
# import numpy as np

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.WARNING
)
logger = logging.getLogger("fx_pulsar_hub")

# Load environment variables from .env file
load_dotenv()

# Get credentials
aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")

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

send_push(title="Hello, Trader!",
            body="This application is in beta testing, please send your ideas and issues to our #fx-pulsar slack channel ",
            icon_path="https://images.seeklogo.com/logo-png/60/1/lmax-digital-icon-black-logo-png_seeklogo-609777.png",
            sound_path="./fx_news/price_sound.mp3",
            tag="beta")

# Check if debug mode is in session state, initialize if not
if 'debug_mode' not in st.session_state:
    st.session_state.debug_mode = False

# Initialize report selection state
if 'report_view' not in st.session_state:
    st.session_state.report_view = "today"

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
        .report-toggle {
            display: flex;
            justify-content: center;
            margin-bottom: 20px;
        }
        .report-toggle button {
            padding: 10px 20px;
            margin: 0 5px;
            border-radius: 5px;
            border: none;
            cursor: pointer;
            font-weight: 500;
        }
        .active-report {
            background-color: #4682B4;
            color: white;
        }
        .inactive-report {
            background-color: #f0f2f6;
            color: #333;
        }
    </style>
""", unsafe_allow_html=True)

# Function to read AWS credentials from CSV file
def get_aws_credentials():
    """
    Read AWS credentials from the CSV file
    
    Returns:
    tuple: (access_key_id, secret_access_key)
    """
    try:
        csv_path = os.path.join("fx_news", "access_keys", "fxpulsar_user_accessKeys.csv")
        
        if not os.path.exists(csv_path):
            logger.error(f"AWS credentials file not found at {csv_path}")
            return None, None
            
        with open(csv_path, 'r') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                # AWS CSV typically has these headers
                access_key_id = row.get('Access key ID')
                secret_access_key = row.get('Secret access key')
                
                # If headers are different, try alternate keys
                if not access_key_id:
                    access_key_id = row.get('AccessKeyId')
                if not secret_access_key:
                    secret_access_key = row.get('SecretAccessKey')
                
                return access_key_id, secret_access_key
                
        logger.error("No credentials found in CSV file")
        return None, None
    except Exception as e:
        logger.error(f"Error reading AWS credentials: {str(e)}")
        return None, None

# Update the background music function to use your local MP3 file
def add_background_music(narration_path, volume_reduction=20):
    """
    Add background music to narration audio using a local MP3 file
    
    Parameters:
    narration_path (str): Path to the narration MP3 file
    volume_reduction (int): How much to reduce the music volume in dB
    
    Returns:
    str: Path to the mixed audio file
    """
    try:
        # List of available music files
        music_files = [
            "fx_news/audio/halt.mp3",
            "fx_news/audio/halt.mp3"
        ]
        
        # Randomly select a music file
        import random
        background_path = random.choice(music_files)
        
        if not os.path.exists(background_path):
            logger.error(f"Background music file not found at {background_path}")
            return narration_path
            
        logger.info(f"Using local background music from: {background_path}")
        
        # Load the narration and background music
        narration = AudioSegment.from_mp3(narration_path)
        background = AudioSegment.from_mp3(background_path)
        
        # Adjust background volume (reduce by specified dB)
        background = background - volume_reduction
        
        # If background is shorter than narration, loop it
        while len(background) < len(narration):
            background = background + background
        
        # Trim background to match narration length
        background = background[:len(narration)]
        
        # Mix narration with background
        mixed = narration.overlay(background)
        
        # Save the mixed audio
        mixed_path = narration_path.replace(".mp3", "_with_music.mp3")
        mixed.export(mixed_path, format="mp3")
        
        return mixed_path
    except Exception as e:
        logger.error(f"Error adding background music: {str(e)}")
        return narration_path  # Return original narration if there's an error

# Simplified chunked narration function with your local background music
def generate_chunked_narration_with_music(text, voice_id="Joanna"):
    """
    Handle longer texts by splitting into smaller chunks at sentence boundaries
    and add background music from local file
    
    Parameters:
    text (str): The long text to convert to speech
    voice_id (str): Voice ID to use
    
    Returns:
    str: HTML audio player with base64 encoded audio
    """
    try:
        import re
        import io
        from pydub import AudioSegment
        
        # Initialize AWS Polly client with environment variables
        polly_client = boto3.client('polly',
                                aws_access_key_id=aws_access_key,
                                aws_secret_access_key=aws_secret_key,
                                region_name='us-east-1')
        
        # Split text into chunks at sentence boundaries
        sentences = re.split(r'(?<=[.!?])\s+', text)
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            # If adding this sentence exceeds the limit, start a new chunk
            if len(current_chunk) + len(sentence) > 2900:
                chunks.append(current_chunk)
                current_chunk = sentence
            else:
                # Add to current chunk
                if current_chunk:
                    current_chunk += " " + sentence
                else:
                    current_chunk = sentence
        
        # Add the last chunk if it's not empty
        if current_chunk:
            chunks.append(current_chunk)
        
        logger.info(f"Split text into {len(chunks)} chunks")
        
        # Create an empty audio segment
        combined = AudioSegment.empty()
        
        # Process each chunk and append to the combined audio
        for i, chunk in enumerate(chunks):
            logger.info(f"Processing chunk {i+1}/{len(chunks)} ({len(chunk)} chars)")
            response = polly_client.synthesize_speech(
                Text=chunk,
                OutputFormat="mp3",
                VoiceId=voice_id,
                Engine="neural"
            )
            
            # Read audio data into an in-memory file-like object
            audio_data = io.BytesIO(response['AudioStream'].read())
            
            # Load with pydub and append to the combined audio
            segment = AudioSegment.from_mp3(audio_data)
            combined += segment
        
        # Save the combined audio
        narration_file_path = "temp_narration.mp3"
        combined.export(narration_file_path, format="mp3")
        
        # Add background music
        final_audio_path = add_background_music(narration_file_path)
        
        # Read the file and encode as base64
        with open(final_audio_path, "rb") as audio_file:
            audio_bytes = audio_file.read()
        audio_base64 = base64.b64encode(audio_bytes).decode()
        
        # Create HTML audio player
        audio_player = f"""
        <audio controls autoplay style="width: 100%;">
            <source src="data:audio/mp3;base64,{audio_base64}" type="audio/mp3">
            Your browser does not support the audio element.
        </audio>
        """
        
        return audio_player
    except Exception as e:
        logger.error(f"Error generating chunked narration with music: {str(e)}")
        
        # If pydub is not installed, suggest installing it
        if "No module named 'pydub'" in str(e):
            return """
            <p>Error: The pydub module is required for narrations with background music.</p>
            <p>Please install it with: <code>pip install pydub</code></p>
            <p>You will also need ffmpeg installed on your system.</p>
            """
        
        return f"<p>Error generating audio: {str(e)}</p>"

def create_detailed_narration(report_data, formatted_date):
    """
    Create a more detailed narration script from the report data
    
    Parameters:
    report_data (dict): The transformed report data
    formatted_date (str): The formatted date string
    
    Returns:
    str: A detailed narration script
    """
    # Extract title/overview
    title = report_data.get('title', 'Daily Market Report')
    
    # Extract the overview from the title
    overview = title
    if title.startswith("Daily Market Report: "):
        overview = title[len("Daily Market Report: "):]
    
    # Start with introduction
    narration_text = f"Welcome to the Market Report for {formatted_date}. {overview} "
    
    # Add trends section with important details
    trends = report_data.get("trends", [])
    if trends:
        narration_text += "Key market trends today include: "
        
        # Limit to 5 most important trends to keep the narration manageable
        for i, trend in enumerate(trends[:5]):
            currency = trend.get('currency', '')
            direction = trend.get('direction', 'neutral')
            description = trend.get('description', '')
            
            direction_word = "rising" if direction == "up" else "falling" if direction == "down" else "showing neutral movement"
            
            narration_text += f"{currency} is {direction_word}. {description} "
    
    # Add drivers summary
    drivers = report_data.get("drivers", [])
    if drivers:
        narration_text += "Market drivers include: "
        
        # Limit to 5 most important drivers
        for i, driver in enumerate(drivers[:5]):
            narration_text += f"{driver}. "
    
    # Add outlook with future implications
    outlook = report_data.get("outlook", {})
    if outlook:
        description = outlook.get('description', '')
        sentiment = outlook.get('sentiment', 'neutral')
        
        if description:
            narration_text += "Looking ahead, "
            
            if sentiment == "positive":
                narration_text += "the outlook is positive. "
            elif sentiment == "negative":
                narration_text += "we're cautious about market conditions. "
            else:
                narration_text += "we maintain a neutral stance. "
                
            narration_text += f"{description} "
    
    # Add closing remarks
    narration_text += "That concludes our market report for today. Remember that market conditions can change rapidly. Thank you for listening to the FX Pulsar Hub market update."
    
    return narration_text

# Add a function for the brief narration
def create_brief_narration(report_data, formatted_date):
    """
    Create a concise narration script from the report data
    
    Parameters:
    report_data (dict): The transformed report data
    formatted_date (str): The formatted date string
    
    Returns:
    str: A brief narration script
    """
    # Extract title/overview
    title = report_data.get('title', 'Daily Market Report')
    
    # Extract the overview from the title
    overview = title
    if title.startswith("Daily Market Report: "):
        overview = title[len("Daily Market Report: "):]
    
    # Start with a brief introduction
    narration_text = f"Market Report for {formatted_date}. {overview}. "
    
    # Add key trends
    trends = report_data.get("trends", [])
    if trends:
        narration_text += "Key market trends include: "
        for i, trend in enumerate(trends[:3]):  # Limit to first 3 trends for brevity
            direction = "increasing" if trend.get("direction") == "up" else "decreasing" if trend.get("direction") == "down" else "stable"
            narration_text += f"{trend.get('currency', '')} is {direction}, {trend.get('description', '')}. "
    
    # Include outlook
    outlook = report_data.get("outlook", {})
    if outlook:
        description = outlook.get('description', '')
        if description:
            narration_text += f"Market Outlook: {description}"
    
    return narration_text

# Update display_market_report function to offer the choice between brief and detailed narration
def display_market_report(report_data):
    """Display market report using native Streamlit components with enhanced styling and voice narration options."""
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
    
    # Display the date
    st.subheader(f"Market Report for {formatted_date}")
    
    # Add narration buttons - now with three options
    st.write("Choose a narration style:")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        brief_btn = st.button("🔊 Brief Summary", key="brief_narration_btn", use_container_width=True)
    with col2:
        detailed_btn = st.button("🎙️ Detailed Report", key="detailed_narration_btn", use_container_width=True)
    with col3:
        music_btn = st.button("🎵 With Background Music", key="music_narration_btn", use_container_width=True)
    
    # Display title
    title = report_data.get('title', 'Daily Market Report')
    st.title(title)
    
    # Handle narration based on button clicks
    if brief_btn or detailed_btn or music_btn:
        # Determine which narration to create
        if brief_btn:
            narration_text = create_brief_narration(report_data, formatted_date)
            narration_type = "brief"
            spinner_text = "Generating brief narration..."
            use_music = False
        elif detailed_btn:
            narration_text = create_detailed_narration(report_data, formatted_date)
            narration_type = "detailed"
            spinner_text = "Generating detailed voice narration..."
            use_music = False
        else:  # music_btn
            narration_text = create_detailed_narration(report_data, formatted_date)
            narration_type = "detailed"
            spinner_text = "Generating narration with background music..."
            use_music = True
        
        # Show a spinner while generating the narration
        with st.spinner(spinner_text):
            # Get the selected voice from session state
            voice_id = st.session_state.get('selected_voice', 'Amy')
            
            # Generate audio based on whether music is enabled
            if use_music:
                # Use the function with background music
                audio_player = generate_chunked_narration_with_music(narration_text, voice_id)
                audio_file_path = "temp_narration_with_music.mp3"
            else:
                # Regular narration without music
                if len(narration_text) > 2900:
                    # Long text needs chunking
                    audio_player = generate_chunked_narration(narration_text, voice_id)
                else:
                    # Short text can use simple method
                    audio_player = generate_narration_with_polly(narration_text, voice_id)
                audio_file_path = "temp_narration.mp3"
            
            # Display the audio player
            st.markdown(audio_player, unsafe_allow_html=True)
            
            # Add a download button for the narration
            try:
                if os.path.exists(audio_file_path):
                    with open(audio_file_path, "rb") as audio_file:
                        audio_bytes = audio_file.read()
                        
                    music_label = " with Music" if use_music else ""
                    st.download_button(
                        label=f"Download {narration_type.capitalize()}{music_label} Audio Report",
                        data=audio_bytes,
                        file_name=f"market_report_{report_date}_{narration_type}{music_label.replace(' ', '_')}.mp3",
                        mime="audio/mp3"
                    )
            except Exception as e:
                logger.error(f"Error preparing download button: {str(e)}")
    
    # Summary with more visible styling - only display if not empty
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

# Function to generate audio using AWS Polly
def generate_narration_with_polly(text, voice_id="Joanna"):
    """
    Generate voice narration using AWS Polly with support for longer texts
    by chunking the text into smaller segments.
    
    Parameters:
    text (str): Text to convert to speech
    voice_id (str): Voice ID to use (e.g., "Joanna", "Matthew")
    
    Returns:
    str: HTML audio player with base64 encoded audio
    """
    try:
        # Check if text is too long
        if len(text) > 2900:  # Keep some buffer below the 3000 char limit
            logger.info(f"Text length ({len(text)}) exceeds limit, chunking...")
            return generate_chunked_narration(text, voice_id)
        
        # Initialize AWS Polly client with environment variables
        polly_client = boto3.client('polly',
                                   aws_access_key_id=aws_access_key,
                                   aws_secret_access_key=aws_secret_key,
                                   region_name='us-east-1')
        
        # Request speech synthesis
        response = polly_client.synthesize_speech(
            Text=text,
            OutputFormat="mp3",
            VoiceId=voice_id,
            Engine="neural"  # Use neural for better quality
        )
        
        # Read the audio stream
        audio_stream = response['AudioStream'].read()
        
        # Create a temporary file for the audio
        audio_file_path = "temp_narration.mp3"
        with open(audio_file_path, "wb") as f:
            f.write(audio_stream)
        
        # Read the file and encode as base64
        with open(audio_file_path, "rb") as audio_file:
            audio_bytes = audio_file.read()
        audio_base64 = base64.b64encode(audio_bytes).decode()
        
        # Create HTML audio player
        audio_player = f"""
        <audio controls autoplay style="width: 100%;">
            <source src="data:audio/mp3;base64,{audio_base64}" type="audio/mp3">
            Your browser does not support the audio element.
        </audio>
        """
        
        return audio_player
    except Exception as e:
        logger.error(f"Error generating audio with AWS Polly: {str(e)}")
        return f"<p>Error generating audio: {str(e)}</p>"

def generate_chunked_narration(text, voice_id="Joanna"):
    """
    Handle longer texts by splitting into smaller chunks at sentence boundaries
    
    Parameters:
    text (str): The long text to convert to speech
    voice_id (str): Voice ID to use
    
    Returns:
    str: HTML audio player with base64 encoded audio
    """
    try:
        import io
        from pydub import AudioSegment
        import re
        
        # Initialize AWS Polly client with environment variables
        polly_client = boto3.client('polly',
                                aws_access_key_id=aws_access_key,
                                aws_secret_access_key=aws_secret_key,
                                region_name='us-east-1')
        
        # Split text into chunks at sentence boundaries
        sentences = re.split(r'(?<=[.!?])\s+', text)
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            # If adding this sentence exceeds the limit, start a new chunk
            if len(current_chunk) + len(sentence) > 2900:
                chunks.append(current_chunk)
                current_chunk = sentence
            else:
                # Add to current chunk
                if current_chunk:
                    current_chunk += " " + sentence
                else:
                    current_chunk = sentence
        
        # Add the last chunk if it's not empty
        if current_chunk:
            chunks.append(current_chunk)
        
        logger.info(f"Split text into {len(chunks)} chunks")
        
        # Create an empty audio segment
        combined = AudioSegment.empty()
        
        # Process each chunk and append to the combined audio
        for i, chunk in enumerate(chunks):
            logger.info(f"Processing chunk {i+1}/{len(chunks)} ({len(chunk)} chars)")
            response = polly_client.synthesize_speech(
                Text=chunk,
                OutputFormat="mp3",
                VoiceId=voice_id,
                Engine="neural"
            )
            
            # Read audio data into an in-memory file-like object
            audio_data = io.BytesIO(response['AudioStream'].read())
            
            # Load with pydub and append to the combined audio
            segment = AudioSegment.from_mp3(audio_data)
            combined += segment
        
        # Save the combined audio
        audio_file_path = "temp_narration.mp3"
        combined.export(audio_file_path, format="mp3")
        
        # Read the file and encode as base64
        with open(audio_file_path, "rb") as audio_file:
            audio_bytes = audio_file.read()
        audio_base64 = base64.b64encode(audio_bytes).decode()
        
        # Create HTML audio player
        audio_player = f"""
        <audio controls autoplay style="width: 100%;">
            <source src="data:audio/mp3;base64,{audio_base64}" type="audio/mp3">
            Your browser does not support the audio element.
        </audio>
        """
        
        return audio_player
    except Exception as e:
        logger.error(f"Error generating chunked narration: {str(e)}")
        
        # If pydub is not installed, suggest installing it
        if "No module named 'pydub'" in str(e):
            return """
            <p>Error: The pydub module is required for longer narrations.</p>
            <p>Please install it with: <code>pip install pydub</code></p>
            <p>You will also need ffmpeg installed on your system.</p>
            """
        
        return f"<p>Error generating audio: {str(e)}</p>"

def add_narration_options_to_sidebar():
    with st.sidebar:
        st.markdown("### Narration Options")
        voice_options = {
            "Amy": "Female (British)",
            "Brian": "Male (British)",
            "Joanna": "Female (US)",
            "Matthew": "Male (US)",
            "Aria": "Female (New Zealand)",
            "Kajal": "Female (Indian English)"
        }
        
        if 'selected_voice' not in st.session_state:
            st.session_state.selected_voice = "Amy"
            
        selected_voice = st.selectbox("Select Voice", 
                                     options=list(voice_options.keys()),
                                     format_func=lambda x: f"{x} - {voice_options[x]}",
                                     index=list(voice_options.keys()).index(st.session_state.selected_voice))
        
        st.session_state.selected_voice = selected_voice

def transform_json_structure(original_data, report_type="legacy"):
    """
    Transform different JSON structures to a unified format for display
    
    Parameters:
    original_data (dict): Original JSON data
    report_type (str): Type of report - "legacy" (old format) or "new" (new format)
    
    Returns:
    dict: Transformed data in the expected format for the display function
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
    
    if report_type == "legacy":
        # Transform legacy format (old JSON structure)
        # Extract from market_summary if it exists
        market_summary = original_data.get("market_summary", {})
        if market_summary:
            logger.debug("Processing market_summary section for legacy format")
            
            # Date
            if "date" in market_summary:
                transformed["date"] = market_summary["date"].replace("-", "") if "-" in market_summary["date"] else market_summary["date"]
                logger.debug(f"Extracted date: {transformed['date']}")
            
            # Title and summary
            if "overview" in market_summary:
                overview = market_summary["overview"]
                transformed["title"] = "Daily Market Report: " + overview
                transformed["summary"] = ""  # Don't duplicate the overview in the summary
                logger.debug(f"Extracted title only, avoiding duplication")
            
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
    
    else:
        # Transform new format
        market_summary = original_data.get("market_summary", {})
        if market_summary:
            logger.debug("Processing market_summary section for new format")
            
            # Date
            if "date" in market_summary:
                transformed["date"] = market_summary["date"].replace("-", "") if "-" in market_summary["date"] else market_summary["date"]
                logger.debug(f"Extracted date: {transformed['date']}")
            
            # Title and summary
            if "overview" in market_summary:
                overview = market_summary["overview"]
                transformed["title"] = "Daily Market Report: " + overview
                transformed["summary"] = "" # overview
                logger.debug(f"Extracted title and summary from overview")
            
            # Create trends from key factors
            trends = []
            key_factors = market_summary.get("key_factors", {})
            
            # Process US trade tariffs
            us_tariffs = key_factors.get("US_trade_tariffs", {})
            if us_tariffs:
                trends.append({
                    "currency": "US Trade Tariffs",
                    "direction": "up",  # Assuming tariffs are increasing
                    "description": us_tariffs.get("impact", "") + " " + us_tariffs.get("details", "")
                })
            
            # Process central bank policies
            central_banks = key_factors.get("central_bank_policies", {})
            for bank_name, details in central_banks.items():
                if isinstance(details, dict):  # Check if it's a nested structure
                    trends.append({
                        "currency": bank_name.replace("_", " "),
                        "direction": "neutral",  # Default to neutral for central banks
                        "description": details.get("focus", "") + " " + details.get("details", "")
                    })
            
            # Process market uncertainty
            uncertainty = market_summary.get("market_uncertainty", {})
            if uncertainty:
                trends.append({
                    "currency": "Market Uncertainty",
                    "direction": "up",  # Assuming uncertainty is increasing
                    "description": uncertainty.get("impact", "")
                })
            
            # Process safe haven assets
            safe_havens = market_summary.get("safe_haven_assets", {})
            for asset, details in safe_havens.items():
                trends.append({
                    "currency": asset.capitalize(),
                    "direction": "up",  # Assuming safe havens are strengthening
                    "description": details.get("status", "") + " " + details.get("details", "")
                })
            
            transformed["trends"] = trends
            
            # Create drivers from economic indicators and top events
            drivers = []
            
            # Process economic indicators
            econ_indicators = market_summary.get("economic_indicators", {})
            for indicator, details in econ_indicators.items():
                driver_text = f"{indicator.replace('_', ' ')}: {details.get('importance', '')}. {details.get('details', '')}"
                drivers.append(driver_text.strip())
            
            # Process top economic events
            top_events = market_summary.get("top_economic_events", [])
            for event in top_events:
                driver_text = f"{event.get('event', '')}: {event.get('importance', '')}. {event.get('details', '')}"
                drivers.append(driver_text.strip())
            
            transformed["drivers"] = drivers
            
            # Create outlook
            transformed["outlook"] = {
                "sentiment": "neutral",
                "description": market_summary.get("overview", "")
            }
            
            # If we have market uncertainty info, use that for the outlook
            if uncertainty:
                uncertainty_drivers = uncertainty.get("drivers", [])
                uncertainty_desc = uncertainty.get("impact", "")
                if uncertainty_drivers and uncertainty_desc:
                    transformed["outlook"] = {
                        "sentiment": "negative",  # Usually uncertainty is negative
                        "description": f"Key factors driving uncertainty: {', '.join(uncertainty_drivers)}. {uncertainty_desc}"
                    }
    
    logger.debug(f"Transformation complete. New keys: {list(transformed.keys())}")
    return transformed

def get_latest_report(report_view="today"):
    """
    Get market report based on selected view (today or yesterday)
    
    Parameters:
    report_view (str): "today" or "yesterday" to determine which report to fetch
    
    Returns:
    dict: Transformed report data ready for display
    """
    # Define possible base directory paths
    base_dirs = ["fx_news", "fxnews"]
    
    # Initialize variables
    report_data = None
    report_type = "legacy"  # Default to legacy format
    
    # Determine subdirectory based on report view
    subfolder = "tday" if report_view == "today" else "yday"
    
    logger.info(f"Looking for {report_view}'s report in {subfolder} folder")
    
    # Search in both possible base directories
    for base_dir in base_dirs:
        if not os.path.exists(base_dir):
            logger.debug(f"Directory {base_dir} does not exist, skipping")
            continue
            
        # Check if the subfolder exists
        reports_dir = os.path.join(base_dir, "reports", subfolder)
        if not os.path.exists(reports_dir):
            logger.debug(f"Subfolder {reports_dir} does not exist, trying reports directly")
            # Try the direct reports folder as fallback
            reports_dir = os.path.join(base_dir, "reports")
            
        if not os.path.exists(reports_dir):
            logger.debug(f"Directory {reports_dir} does not exist, skipping")
            continue
            
        logger.info(f"Looking for reports in: {reports_dir}")
        
        # Get all JSON files in the directory
        report_files = glob.glob(os.path.join(reports_dir, "*.json"))
        
        if not report_files:
            logger.warning(f"No report files found in {reports_dir}")
            continue
            
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
                        
                        # Determine the report type based on structure
                        if "market_summary" in original_data and "key_factors" in original_data.get("market_summary", {}):
                            report_type = "new"
                            logger.info("Detected new report format")
                        else:
                            report_type = "legacy"
                            logger.info("Detected legacy report format")
                        
                        # Transform the data structure to match expected format
                        transformed_data = transform_json_structure(original_data, report_type)
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
    logger.warning(f"No valid {report_view} report files found in any directory")
    return None


# Function to render report toggle UI
def render_report_toggle():
    # Use native Streamlit components for the toggle
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        toggle_cols = st.columns(2)
        with toggle_cols[0]:
            if st.button("Today's Report", use_container_width=True, 
                          type="primary" if st.session_state.report_view == "today" else "secondary"):
                st.session_state.report_view = "today"
                st.rerun()
        with toggle_cols[1]:
            if st.button("Yesterday's Report", use_container_width=True,
                          type="primary" if st.session_state.report_view == "yesterday" else "secondary"):
                st.session_state.report_view = "yesterday"
                st.rerun()

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
    
    # Add narration options
    add_narration_options_to_sidebar()

# Main content - using a two-column layout
# First get the market report data based on the selected view
logger.info(f"Fetching {st.session_state.report_view}'s market report")
report_data = get_latest_report(st.session_state.report_view)

# Display the report toggle above the report
render_report_toggle()

# If no valid report, generate a sample
if not report_data:
    logger.warning(f"No valid {st.session_state.report_view} report found, using sample data")
    # Sample report data varies based on the report view
    if st.session_state.report_view == "today":
        sample_json = {
            "market_summary": {
                "date": "2025-03-12",
                "overview": "US tariffs, inflation, and recession fears are driving global trade tensions, central bank adjustments, and market uncertainty.",
                "key_factors": {
                    "US_trade_tariffs": {
                        "impact": "Ignited global trade tensions, affecting numerous countries including Canada, which has prompted retaliatory measures.",
                        "details": "The European Union has responded with countermeasures valued at 26 billion Euros."
                    },
                    "central_bank_policies": {
                        "Federal_Reserve": {
                            "focus": "Monitoring US Consumer Price Index (CPI) data for potential inflation trends.",
                            "expectations": "Potential interest rate cuts are being closely watched."
                        }
                    }
                },
                "market_uncertainty": {
                    "drivers": [
                        "US tariff policies",
                        "Inflation concerns",
                        "Potential economic slowdown"
                    ],
                    "impact": "Heightened market uncertainty, with investors revising economic projections for 2025."
                }
            }
        }
        # Transform using the new format handler
        report_data = transform_json_structure(sample_json, "new")
    else:
        # Legacy format sample (yesterday)
        sample_json = {
            "market_summary": {
                "date": "2025-03-11",
                "overview": "Stocks plunged to a six-month low amid ongoing uncertainty about the impact of policies from the Trump White House and concerns about the U.S. economy.",
                "major_indexes": {
                    "Dow Jones Industrial Average": {
                        "performance": "Fell 2.1%, equivalent to a near-900 point decline.",
                        "status": "Closed at its lowest level since last September."
                    },
                    "S&P 500": {
                        "performance": "Shed 2.7%.",
                        "status": "Closed at its lowest level since last September."
                    }
                }
            },
            "market_tendencies_for_tomorrow": {
                "overview": "Investors are concerned about President Trump's plans for widespread tariffs and the retaliatory measures announced by other countries."
            }
        }
        # Transform the sample data using the legacy handler
        report_data = transform_json_structure(sample_json, "legacy")

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