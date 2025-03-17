import logging
import requests
import json
import re
# Your other imports here

# Set up logging properly
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Mistral API usage stats
# https://console.mistral.ai/usage

def analyze_sentiment_with_mistral(text: str, api_key: str) -> tuple[str, float]:
    """
    Analyze sentiment using Mistral AI's LLM API with improved text handling
    
    Args:
        text: Text to analyze
        api_key: Mistral API key
    
    Returns:
        tuple: (sentiment_label, sentiment_score)
    """
    url = "https://api.mistral.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # Clean the text to remove problematic characters
    cleaned_text = text
    
    # Remove or replace problematic characters
    cleaned_text = re.sub(r'[^\x00-\x7F]+', ' ', cleaned_text)  # Remove non-ASCII
    cleaned_text = re.sub(r'[\r\n\t]+', ' ', cleaned_text)      # Replace newlines and tabs
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text)            # Normalize whitespace
    cleaned_text = cleaned_text.strip()
    
    # Limit text length to avoid token limits
    if len(cleaned_text) > 2000:
        cleaned_text = cleaned_text[:2000] + "..."
    
    # Create a prompt that instructs the model to perform sentiment analysis
    prompt = f"""Analyze the sentiment of the following financial news text. 
Respond with only one word: 'positive', 'negative', or 'neutral', followed by a confidence score between 0 and 1.
Format your response exactly like this: "positive 0.87" or "negative 0.65" or "neutral 0.55"

Text: {cleaned_text}

Sentiment:"""
    
    data = {
        "model": "mistral-small-latest",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,  # Lower temperature for more consistent results
        "max_tokens": 10     # We only need a few tokens for the response
    }
    
    try:
        logger.info(f"Sending request to Mistral API with {len(cleaned_text)} characters")  # Use print instead of logger
        response = requests.post(url, headers=headers, data=json.dumps(data), timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            reply = result['choices'][0]['message']['content'].strip().lower()
            
            # Extract sentiment and score from the response
            parts = reply.split()
            if len(parts) >= 2 and parts[0] in ['positive', 'negative', 'neutral']:
                sentiment_label = parts[0]
                try:
                    # Try to extract score as a float
                    sentiment_score = float(parts[1])
                    # Ensure the score is between -1 and 1 for consistency with TextBlob
                    if sentiment_label == 'negative':
                        sentiment_score = -sentiment_score
                    elif sentiment_label == 'neutral':
                        sentiment_score = sentiment_score * 0.5  # Scale neutral closer to 0
                except ValueError:
                    # If score can't be converted to float, assign a default
                    sentiment_score = 0.5 if sentiment_label == 'positive' else -0.5 if sentiment_label == 'negative' else 0.0
                
                return sentiment_label, round(sentiment_score, 2)
            else:
                print(f"Unexpected response format from Mistral: {reply}")  # Use print instead of logger
                # Fall back to neutral with low confidence
                return "neutral", 0.0
                
        else:
            print(f"Error from Mistral API: {response.status_code} - {response.text}")  # Use print instead of logger
            # Fall back to neutral sentiment
            return "neutral", 0.0
            
    except Exception as e:
        print(f"Exception during Mistral API call: {str(e)}")  # Use print instead of logger
        # Fall back to neutral sentiment
        return "neutral", 0.0
    
  
if __name__ == "__main__": 
    # api_key = os.getenv("MISTRAL_API_KEY")
    news_text = "The price of bitcoin (BTC-USD) continues falling despite efforts by President Donald Trump to give the crypto world more of what it wants, including a strategic bitcoin reserve that the administration touted at the end of last week while hosting crypto executives at the White House.The world’s largest cryptocurrency fell below $78,000 on Monday, hitting its lowest level since the days following Trump's election victory last November. It is now down 28% from its all-time high above $109,000 reached the day of Trump's inauguration in January."
    sentiment_label, sentiment_score = analyze_sentiment_with_mistral(news_text, api_key='1i1PR8oSJwazWAyOj3iXiRoiCThZI6qj')
    print(sentiment_label, sentiment_score)