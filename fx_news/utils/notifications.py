# import streamlit as st
# import time
# from datetime import datetime

# def add_notification(message, type='system'):
#     """
#     Add a notification to the session state
    
#     Args:
#         message (str): The notification message
#         type (str): Type of notification ('system', 'price', 'error', 'info', 'success')
#     """
#     # Initialize notifications list if it doesn't exist
#     if 'notifications' not in st.session_state:
#         st.session_state.notifications = []
        
#     notification = {
#         "id": int(time.time() * 1000),
#         "message": message,
#         "type": type,
#         "timestamp": datetime.now()
#     }
#     st.session_state.notifications.insert(0, notification)
    
#     # Keep only the 20 most recent notifications
#     if len(st.session_state.notifications) > 20:
#         st.session_state.notifications = st.session_state.notifications[:20]

#     # Play sound for price alerts if configured
#     if type == 'price':
#         st.markdown(
#             """
#             <audio autoplay>
#                 <source src="price_sound.mp3" type="audio/mpeg">
#             </audio>
#             """,
#             unsafe_allow_html=True
#         )


"""
Notification handling utilities for the FX Pulsar application.
Contains functions for creating and managing notifications.
"""
import time
import streamlit as st
from datetime import datetime
from typing import List, Dict, Any, Optional

def add_notification(message: str, type: str = 'system'):
    """
    Add a notification to the session state.
    
    Args:
        message: Notification message text
        type: Notification type ('system', 'price', 'error', 'info', 'success')
    """
    # Create the notification object
    notification = {
        "id": int(time.time() * 1000),
        "message": message,
        "type": type,
        "timestamp": datetime.now()
    }
    
    # Initialize notifications list if not exists
    if 'notifications' not in st.session_state:
        st.session_state.notifications = []
    
    # Add notification to the beginning of the list
    st.session_state.notifications.insert(0, notification)
    
    # Keep only the most recent notifications
    max_notifications = 20
    if len(st.session_state.notifications) > max_notifications:
        st.session_state.notifications = st.session_state.notifications[:max_notifications]

    # Play sound for price alert notifications (in a real app)
    if type == 'price':
        play_alert_sound()

def clear_notifications():
    """Clear all notifications from the session state."""
    st.session_state.notifications = []
    add_notification("All notifications cleared", "system")

def display_notification(notification: Dict[str, Any]):
    """
    Display a single notification.
    
    Args:
        notification: Notification dictionary
    """
    # Format timestamp
    timestamp = notification["timestamp"].strftime("%H:%M:%S")
    
    # Determine icon based on notification type
    if notification['type'] == 'price':
        emoji = "💰"
        color = "orange"
    elif notification['type'] == 'error':
        emoji = "❌"
        color = "red"
    elif notification['type'] == 'info':
        emoji = "ℹ️"
        color = "blue"
    elif notification['type'] == 'success':
        emoji = "✅"
        color = "green"
    else:  # system
        emoji = "🔔"
        color = "gray"
    
    # Create a custom notification element
    st.markdown(
        f"""<div style="padding:8px; margin-bottom:8px; border-left:4px solid {color}; background-color:#f8f9fa;">
            <div>{emoji} <strong>{notification['message']}</strong></div>
            <div style="font-size:0.8em; color:#6c757d;">{timestamp}</div>
        </div>""",
        unsafe_allow_html=True
    )

def display_notifications(max_count: Optional[int] = None):
    """
    Display all notifications in the session state.
    
    Args:
        max_count: Optional maximum number of notifications to display
    """
    if 'notifications' not in st.session_state or not st.session_state.notifications:
        st.info("No notifications to display")
        return
    
    notifications = st.session_state.notifications
    
    # Limit the number of notifications if specified
    if max_count and len(notifications) > max_count:
        notifications = notifications[:max_count]
    
    # Display each notification
    for notification in notifications:
        display_notification(notification)

def play_alert_sound():
    """
    Play an alert sound for notifications.
    This would use the browser's audio API in a real application.
    """
    # In a real application, this would play a sound
    # For now, we'll just add a markdown element that could trigger sound
    # (but won't actually play anything)
    sound_html = """
    <audio autoplay>
        <source src="price_sound.mp3" type="audio/mpeg">
    </audio>
    """
    # In a real app, you would uncomment this:
    # st.markdown(sound_html, unsafe_allow_html=True)