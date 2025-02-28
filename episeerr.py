import os
import json
import time
import requests
import logging
import threading
import re
import asyncio
import websockets
from logging.handlers import RotatingFileHandler
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import telebot
from telebot import types

# Load environment variables
load_dotenv()

# Create logs directory in the current working directory
log_dir = os.path.join(os.getcwd(), 'logs')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, 'episeerr.log')

# Create logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Clear any existing handlers
logger.handlers.clear()

# Create rotating file handler
file_handler = RotatingFileHandler(
    log_file, 
    maxBytes=10*1024*1024,  # 10 MB
    backupCount=1,  # Keep one backup file
    encoding='utf-8'
)
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)

# Create console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(file_formatter)

# Add handlers to logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Sonarr connection details
SONARR_URL = os.getenv('SONARR_URL', 'http://sonarr:8989')
SONARR_API_KEY = os.getenv('SONARR_API_KEY')
SONARR_WS_URL = os.getenv('SONARR_WS_URL', 'ws://sonarr:8989/api/v3/notification')

# Telegram connection details
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
TELEGRAM_ADMIN_IDS = [int(id.strip()) for id in os.getenv('TELEGRAM_ADMIN_IDS', '').split(',') if id.strip()]
# Global variables
EPISODES_TAG_ID = None  # Will be set when create_episode_tag() is called
# Initialize Telegram bot
if TELEGRAM_TOKEN:
    bot = telebot.TeleBot(TELEGRAM_TOKEN)
    logger.info("Telegram bot initialized")
else:
    bot = None
    logger.warning("Telegram bot not initialized - token missing")



# Store pending episode selections
# Format: {series_id: {'title': 'Series Title', 'season': 1, 'episodes': [1, 2, 3, ...]}}
pending_selections = {}

def get_sonarr_headers():
    """Get headers for Sonarr API requests."""
    return {
        'X-Api-Key': SONARR_API_KEY,
        'Content-Type': 'application/json'
    }

        
def create_episode_tag():
    """Create a single 'episodes' tag in Sonarr and return its ID."""
    try:
        headers = get_sonarr_headers()
        logger.debug(f"Making request to {SONARR_URL}/api/v3/tag")
        
        # Get existing tags
        tags_response = requests.get(
            f"{SONARR_URL}/api/v3/tag",
            headers=headers
        )
        
        if not tags_response.ok:
            logger.error(f"Failed to get tags. Status: {tags_response.status_code}")
            return None

        # Look for existing episodes tag
        episodes_tag_id = None
        for tag in tags_response.json():
            if tag['label'].lower() == 'episodes':
                episodes_tag_id = tag['id']
                logger.info(f"Found existing 'episodes' tag with ID {episodes_tag_id}")
                break
        
        # Create episodes tag if it doesn't exist
        if episodes_tag_id is None:
            tag_create_response = requests.post(
                f"{SONARR_URL}/api/v3/tag",
                headers=headers,
                json={"label": "episodes"}
            )
            if tag_create_response.ok:
                episodes_tag_id = tag_create_response.json().get('id')
                logger.info(f"Created tag: 'episodes' with ID {episodes_tag_id}")
            else:
                logger.error(f"Failed to create episodes tag. Status: {tag_create_response.status_code}")
                return None
        
        # Store the episodes tag ID in a global variable for later use
        global EPISODES_TAG_ID
        EPISODES_TAG_ID = episodes_tag_id
        return episodes_tag_id
    except Exception as e:
        logger.error(f"Error creating episode tag: {str(e)}")
        return None

def unmonitor_season(series_id, season_number, headers):
    """Unmonitor all episodes in a specific season."""
    try:
        # Get episodes for the specific season
        episodes_response = requests.get(
            f"{SONARR_URL}/api/v3/episode?seriesId={series_id}&seasonNumber={season_number}",
            headers=headers
        )
        
        if not episodes_response.ok:
            logger.error(f"Failed to get episodes. Status: {episodes_response.status_code}")
            return False

        episodes = episodes_response.json()
        season_episode_ids = [ep['id'] for ep in episodes]
        
        if season_episode_ids:
            unmonitor_response = requests.put(
                f"{SONARR_URL}/api/v3/episode/monitor",
                headers=headers,
                json={"episodeIds": season_episode_ids, "monitored": False}
            )
            
            if not unmonitor_response.ok:
                logger.error(f"Failed to unmonitor episodes. Status: {unmonitor_response.status_code}")
                return False
            else:
                logger.info(f"Unmonitored all episodes in series ID {series_id} season {season_number}")
                return True
        else:
            logger.info(f"No episodes found for series ID {series_id} season {season_number}")
            return True
            
    except Exception as e:
        logger.error(f"Error unmonitoring season: {str(e)}", exc_info=True)
        return False
    

    
def get_episode_info(episode_id, headers):
    """Get episode information from Sonarr API"""
    try:
        response = requests.get(f"{SONARR_URL}/api/v3/episode/{episode_id}", headers=headers)
        if response.ok:
            return response.json()
        return None
    except Exception as e:
        logger.error(f"Error getting episode info: {str(e)}")
        return None

def get_series_title(series_id, headers):
    """Get series title from Sonarr API"""
    try:
        response = requests.get(f"{SONARR_URL}/api/v3/series/{series_id}", headers=headers)
        if response.ok:
            return response.json().get('title', 'Unknown Series')
        return 'Unknown Series'
    except Exception as e:
        logger.error(f"Error getting series title: {str(e)}")
        return 'Unknown Series'

def process_episode_selection(series_id, episode_numbers):
    """
    Process selected episodes by monitoring and searching for them.
    
    :param series_id: Sonarr series ID
    :param episode_numbers: List of episode numbers to process
    """
    try:
        series_id = int(series_id)
        headers = get_sonarr_headers()
        
        # Get series info
        series_response = requests.get(
            f"{SONARR_URL}/api/v3/series/{series_id}",
            headers=headers
        )
        
        if not series_response.ok:
            logger.error(f"Failed to get series. Status: {series_response.status_code}")
            return False
            
        series = series_response.json()
        season_number = pending_selections[str(series_id)]['season']
        
        logger.info(f"Processing episode selection for {series['title']} Season {season_number}: {episode_numbers}")
        
        # Get episode IDs for searching
        episodes = get_series_episodes(series_id, season_number, headers)
        
        if not episodes:
            logger.error(f"No episodes found for series {series_id} season {season_number}")
            send_telegram_message(f"⚠️ Error: No episodes found for {series['title']} Season {season_number}", cleanup_after=300)
            return False
        
        # Filter to only valid episode numbers
        valid_episode_numbers = []
        for num in episode_numbers:
            if any(ep['episodeNumber'] == num for ep in episodes):
                valid_episode_numbers.append(num)
            else:
                logger.warning(f"Episode {num} not found in {series['title']} Season {season_number}")
        
        if not valid_episode_numbers:
            logger.error(f"No valid episodes found for selection {episode_numbers}")
            send_telegram_message(f"⚠️ Error: No valid episodes found in {series['title']} Season {season_number}", cleanup_after=300)
            return False
            
        # Monitor selected episodes
        monitor_success = monitor_specific_episodes(
            series_id, 
            season_number, 
            valid_episode_numbers, 
            headers
        )
        
        if not monitor_success:
            logger.error(f"Failed to monitor episodes for series {series_id}")
            send_telegram_message(f"⚠️ Error: Failed to monitor episodes for {series['title']}", cleanup_after=300)
            return False
            
        # Get episode IDs for searching
        episode_ids = [
            ep['id'] for ep in episodes 
            if ep['episodeNumber'] in valid_episode_numbers
        ]
        
        if not episode_ids:
            logger.error(f"Failed to find episode IDs for {valid_episode_numbers}")
            send_telegram_message(f"⚠️ Error: Failed to find episode IDs for {series['title']}", cleanup_after=300)
            return False
        
        # Log episode IDs for debugging
        logger.info(f"Episode IDs for search: {episode_ids}")
        
        # Trigger search for the episodes
        search_success = search_episodes(series_id, episode_ids, headers)
        
        if search_success:
            logger.info(f"Successfully set up monitoring and search for {len(valid_episode_numbers)} episodes")
            
            # Create a more permanent final message with complete information
            episodes_str = ", ".join(str(e) for e in sorted(valid_episode_numbers))
            final_msg = send_telegram_message(
                f"✅ *Request Processed*: {series['title']} Season {season_number}\n\n"
                f"Selected Episodes: {episodes_str}\n\n"
                f"Search has been started for these episodes."
                # No cleanup_after - this message stays
            )
            return True
        else:
            logger.error(f"Failed to search for episodes")
            send_telegram_message(f"⚠️ Failed to search for episodes in {series['title']} Season {season_number}", cleanup_after=300)
            return False
            
    except Exception as e:
        logger.error(f"Error processing episode selection: {str(e)}", exc_info=True)
        return False
        
def cancel_download(queue_id, headers):
    """Cancel a download in Sonarr's queue"""
    try:
        # Primary method: Bulk remove with client removal
        payload = {
            "ids": [queue_id],
            "removeFromClient": True,
            "removeFromDownloadClient": True
        }
        response = requests.delete(f"{SONARR_URL}/api/v3/queue/bulk", headers=headers, json=payload)
        
        # If primary method fails, try alternative
        if not response.ok:
            logger.warning(f"Bulk removal failed for queue item {queue_id}. Trying alternative method.")
            response = requests.delete(
                f"{SONARR_URL}/api/v3/queue/{queue_id}", 
                headers=headers,
                params={
                    "removeFromClient": "true"
                }
            )
        
        return response.ok
    except Exception as e:
        logger.error(f"Error cancelling download: {str(e)}")
        return False
        
def monitor_specific_episodes(series_id, season_number, episode_numbers, headers):
    """
    Monitor specific episodes in a series season.
    
    :param series_id: Sonarr series ID
    :param season_number: Season number
    :param episode_numbers: List of episode numbers to monitor
    :param headers: Sonarr API headers
    :return: True if successful, False otherwise
    """
    try:
        episodes_response = requests.get(
            f"{SONARR_URL}/api/v3/episode?seriesId={series_id}",
            headers=headers
        )
        
        if not episodes_response.ok:
            logger.error(f"Failed to get episodes. Status: {episodes_response.status_code}")
            return False

        episodes = episodes_response.json()
        target_episodes = [
            ep for ep in episodes 
            if ep['seasonNumber'] == season_number and 
            ep['episodeNumber'] in episode_numbers
        ]
        
        if not target_episodes:
            logger.error(f"Target episodes {episode_numbers} not found in season {season_number}")
            return False
        
        monitor_episode_ids = [ep['id'] for ep in target_episodes]
        monitor_response = requests.put(
            f"{SONARR_URL}/api/v3/episode/monitor",
            headers=headers,
            json={"episodeIds": monitor_episode_ids, "monitored": True}
        )
        
        if not monitor_response.ok:
            logger.error(f"Failed to monitor episodes. Status: {monitor_response.status_code}")
            return False
        else:
            logger.info(f"Monitoring episodes {episode_numbers} in season {season_number}")
            return True
    
    except Exception as e:
        logger.error(f"Error monitoring specific episodes: {str(e)}", exc_info=True)
        return False

def search_episodes(series_id, episode_ids, headers):
    """
    Trigger a search for specific episodes in Sonarr.
    
    :param series_id: Sonarr series ID
    :param episode_ids: List of episode IDs to search for
    :param headers: Sonarr API headers
    :return: True if successful, False otherwise
    """
    try:
        if not episode_ids:
            logger.error("No episode IDs provided for search")
            return False
            
        logger.info(f"Searching for episodes: {episode_ids}")
            
        search_payload = {
            "name": "EpisodeSearch",
            "episodeIds": episode_ids
        }
        
        search_response = requests.post(
            f"{SONARR_URL}/api/v3/command",
            headers=headers,
            json=search_payload
        )
        
        if search_response.ok:
            logger.info(f"Triggered search for episodes {episode_ids}")
            return True
        else:
            logger.error(f"Failed to trigger search. Status: {search_response.status_code}")
            logger.error(f"Response content: {search_response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error searching for episodes: {str(e)}", exc_info=True)
        return False

def get_series_episodes(series_id, season_number, headers):
    """
    Get all episodes for a specific series and season.
    
    :param series_id: Sonarr series ID
    :param season_number: Season number
    :param headers: Sonarr API headers
    :return: List of episodes or empty list on failure
    """
    try:
        episodes_response = requests.get(
            f"{SONARR_URL}/api/v3/episode?seriesId={series_id}&seasonNumber={season_number}",
            headers=headers
        )
        
        if not episodes_response.ok:
            logger.error(f"Failed to get episodes. Status: {episodes_response.status_code}")
            return []

        return episodes_response.json()
        
    except Exception as e:
        logger.error(f"Error getting series episodes: {str(e)}", exc_info=True)
        return []

def get_overseerr_headers():
    """Get headers for Overseerr API requests."""
    return {
        'X-Api-Key': os.getenv('OVERSEERR_API_KEY'),
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }

def delete_overseerr_request(request_id):
    """
    Delete a specific request in Overseerr.
    
    :param request_id: ID of the request to delete
    :return: True if successful, False otherwise
    """
    try:
        overseerr_url = os.getenv('OVERSEERR_URL')
        headers = get_overseerr_headers()
        
        # Log the deletion attempt
        logger.info(f"Attempting to delete Jellyseerr request {request_id}")
        
        delete_response = requests.delete(
            f"{overseerr_url}/api/v1/request/{request_id}",
            headers=headers
        )
        
        # Log full response for debugging
        logger.debug(f"Delete Request Response Status: {delete_response.status_code}")
        try:
            response_json = delete_response.json()
            logger.debug(f"Delete Request Response JSON: {json.dumps(response_json, indent=2)}")
        except ValueError:
            logger.debug(f"Delete Request Response Text: {delete_response.text}")
        
        if delete_response.ok or delete_response.status_code == 404:
            # 404 means the request was already deleted
            logger.info(f"Successfully deleted or request not found: {request_id}")
            return True
        else:
            logger.error(f"Failed to delete request {request_id}. Status: {delete_response.status_code}")
            return False
    
    except Exception as e:
        logger.error(f"Error deleting Jellyseerr request: {str(e)}", exc_info=True)
        return False

def send_telegram_message(message, reply_to=None, cleanup_after=None):
    """
    Send a message to the configured Telegram chat.
    
    :param message: Message text to send
    :param reply_to: Optional message ID to reply to
    :param cleanup_after: Optional seconds to wait before deleting the message
    :return: Message object if successful, None otherwise
    """
    if not bot or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram not configured. Message not sent.")
        return None
    
    try:
        if reply_to:
            sent_msg = bot.send_message(TELEGRAM_CHAT_ID, message, reply_to_message_id=reply_to, parse_mode='Markdown')
        else:
            sent_msg = bot.send_message(TELEGRAM_CHAT_ID, message, parse_mode='Markdown')
        
        # Schedule message deletion if requested
        if cleanup_after and isinstance(cleanup_after, int) and cleanup_after > 0:
            threading.Timer(cleanup_after, delete_telegram_message, args=[sent_msg.chat.id, sent_msg.message_id]).start()
            
        return sent_msg
    except Exception as e:
        logger.error(f"Error sending Telegram message: {str(e)}", exc_info=True)
        return None

def delete_telegram_message(chat_id, message_id):
    """Delete a Telegram message by ID"""
    if not bot:
        return False
        
    try:
        bot.delete_message(chat_id, message_id)
        logger.debug(f"Deleted Telegram message {message_id}")
        return True
    except Exception as e:
        logger.error(f"Error deleting Telegram message: {str(e)}")
        return False

def send_episode_selection(series_id, title, season, episodes):
    """
    Send episode selection options to Telegram.
    
    :param series_id: Sonarr series ID
    :param title: Series title
    :param season: Season number
    :param episodes: List of episode dictionaries
    """
    if not bot or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram not configured. Episode selection not sent.")
        return False
    
    try:
        # Store the series info for later use
        pending_selections[str(series_id)] = {
            'title': title,
            'season': season,
            'episodes': episodes,
            'selected_episodes': set()  # Track selected episodes
        }
        
        # Create main message
        message = f"*{title} - Season {season}*\n\n"
        message += "Select episodes to download by tapping episode numbers below or sending a message with numbers.\n"
        message += "Example message: `3 5 10-15` for episodes 3, 5, and 10 through 15.\n\n"
        message += "Available episodes:\n"
        
        # Create episode list (limit to first 20 for readability)
        display_limit = 20
        displayed_episodes = episodes[:display_limit]
        
        for ep in displayed_episodes:
            ep_num = ep.get('episodeNumber')
            ep_title = ep.get('title', 'Unknown')
            message += f"{ep_num}. {ep_title}\n"
            
        if len(episodes) > display_limit:
            message += f"...and {len(episodes) - display_limit} more episodes\n"
        
        # Add selection instructions
        message += "\nSelected episodes: None\n"
        message += "\nClick multiple episodes then tap 'Send Selected' when done."
        
        # Create keyboard with multiple rows of buttons
        markup = types.InlineKeyboardMarkup(row_width=5)
        ep_buttons = []
        
        # Add episode number buttons (up to 25 buttons)
        max_buttons = min(25, len(episodes))
        for i in range(1, max_buttons + 1):
            ep_buttons.append(types.InlineKeyboardButton(
                text=str(i), 
                callback_data=f"sel_{series_id}_{i}"
            ))
        
        # Add buttons in rows of 5
        for i in range(0, len(ep_buttons), 5):
            markup.add(*ep_buttons[i:i+5])
        
        # Add control buttons
        control_buttons = [
            types.InlineKeyboardButton(text="Send Selected", callback_data=f"send_{series_id}"),
            types.InlineKeyboardButton(text="All Episodes", callback_data=f"all_{series_id}"),
            types.InlineKeyboardButton(text="Clear Selection", callback_data=f"clear_{series_id}")
        ]
        
        # Add control buttons in separate rows
        markup.add(control_buttons[0])  # Send Selected
        markup.add(control_buttons[1], control_buttons[2])  # All Episodes, Clear Selection
        
        # Send message with keyboard
        bot.send_message(TELEGRAM_CHAT_ID, message, reply_markup=markup, parse_mode='Markdown')
        return True
        
    except Exception as e:
        logger.error(f"Error sending episode selection: {str(e)}", exc_info=True)
        return False

@bot.callback_query_handler(func=lambda call: True)
def handle_callback_query(call):
    """Handle all callback queries from Telegram inline buttons"""
    try:
        data = call.data
        
        # Handle episode selection
        if data.startswith("sel_"):
            handle_episode_selection(call)
        # Handle "Send Selected" button
        elif data.startswith("send_"):
            handle_send_selected(call)
        # Handle "All Episodes" button
        elif data.startswith("all_"):
            handle_all_episodes(call)
        # Handle "Clear Selection" button
        elif data.startswith("clear_"):
            handle_clear_selection(call)
        else:
            bot.answer_callback_query(call.id, text="Unknown command")
    
    except Exception as e:
        logger.error(f"Error handling callback query: {str(e)}", exc_info=True)
        bot.answer_callback_query(call.id, text="Error processing selection")

def handle_episode_selection(call):
    """Handle single episode selection"""
    try:
        # Extract data from callback
        parts = call.data.split('_')
        series_id = parts[1]
        episode_num = int(parts[2])
        
        # Check if selection exists
        if series_id not in pending_selections:
            bot.answer_callback_query(call.id, text="Selection has expired. Please try again.")
            return
            
        series_info = pending_selections[series_id]
        
        # Toggle episode selection
        if episode_num in series_info.get('selected_episodes', set()):
            series_info['selected_episodes'].remove(episode_num)
            bot.answer_callback_query(call.id, text=f"Episode {episode_num} removed")
        else:
            series_info.setdefault('selected_episodes', set()).add(episode_num)
            bot.answer_callback_query(call.id, text=f"Episode {episode_num} added")
        
        # Update message to show selection
        update_selection_message(call.message, series_id)
    
    except Exception as e:
        logger.error(f"Error handling episode selection: {str(e)}", exc_info=True)
        bot.answer_callback_query(call.id, text="Error processing selection")

def handle_send_selected(call):
    """Handle 'Send Selected' button click"""
    try:
        # Extract series ID
        series_id = call.data.split('_')[1]
        
        # Check if selection exists
        if series_id not in pending_selections:
            bot.answer_callback_query(call.id, text="Selection has expired. Please try again.")
            return
            
        series_info = pending_selections[series_id]
        selected_episodes = list(series_info.get('selected_episodes', set()))
        
        if not selected_episodes:
            bot.answer_callback_query(call.id, text="No episodes selected. Please select at least one episode.")
            return
        
        # Process the selection
        success = process_episode_selection(series_id, selected_episodes)
        
        if success:
            bot.answer_callback_query(call.id, text="Processing your selection...")
            
            # Get previous message details for deletion later
            chat_id = call.message.chat.id
            message_id = call.message.message_id
            
            # Edit current message to show completion
            bot.edit_message_text(
                f"*{series_info['title']} - Season {series_info['season']}*\n\n"
                f"✅ Selected {len(selected_episodes)} episodes for download.\n"
                f"Episodes: {', '.join(str(e) for e in sorted(selected_episodes))}",
                chat_id,
                message_id,
                parse_mode='Markdown'
            )
            
            # Schedule deletion of the selection message after 5 minutes
            threading.Timer(300, delete_telegram_message, args=[chat_id, message_id]).start()
            
            # Remove from pending
            del pending_selections[series_id]
        else:
            bot.answer_callback_query(call.id, text="Error processing selection")
    
    except Exception as e:
        logger.error(f"Error handling send selected: {str(e)}", exc_info=True)
        bot.answer_callback_query(call.id, text="Error processing selection")

def handle_all_episodes(call):
    """Handle 'All Episodes' button click"""
    try:
        # Extract series ID
        series_id = call.data.split('_')[1]
        
        # Check if selection exists
        if series_id not in pending_selections:
            bot.answer_callback_query(call.id, text="Selection has expired. Please try again.")
            return
            
        series_info = pending_selections[series_id]
        all_episodes = [ep['episodeNumber'] for ep in series_info['episodes']]
        
        # Process the selection
        success = process_episode_selection(series_id, all_episodes)
        
        if success:
            bot.answer_callback_query(call.id, text="Processing all episodes...")
            
            # Get previous message details for deletion later
            chat_id = call.message.chat.id
            message_id = call.message.message_id
            
            # Edit current message to show completion
            bot.edit_message_text(
                f"*{series_info['title']} - Season {series_info['season']}*\n\n"
                f"✅ Selected all {len(all_episodes)} episodes for download.",
                chat_id,
                message_id,
                parse_mode='Markdown'
            )
            
            # Schedule deletion of the message after 5 minutes
            threading.Timer(300, delete_telegram_message, args=[chat_id, message_id]).start()
            
            # Remove from pending
            del pending_selections[series_id]
        else:
            bot.answer_callback_query(call.id, text="Error processing selection")
    
    except Exception as e:
        logger.error(f"Error handling all episodes: {str(e)}", exc_info=True)
        bot.answer_callback_query(call.id, text="Error processing selection")

def handle_clear_selection(call):
    """Handle 'Clear Selection' button click"""
    try:
        # Extract series ID
        series_id = call.data.split('_')[1]
        
        # Check if selection exists
        if series_id not in pending_selections:
            bot.answer_callback_query(call.id, text="Selection has expired. Please try again.")
            return
            
        # Clear the selection
        pending_selections[series_id]['selected_episodes'] = set()
        
        # Update the message
        update_selection_message(call.message, series_id)
        
        bot.answer_callback_query(call.id, text="Selection cleared")
    
    except Exception as e:
        logger.error(f"Error handling clear selection: {str(e)}", exc_info=True)
        bot.answer_callback_query(call.id, text="Error clearing selection")

def update_selection_message(message, series_id):
    """Update the message to show the current selection"""
    try:
        series_info = pending_selections[series_id]
        title = series_info['title']
        season = series_info['season']
        episodes = series_info['episodes']
        selected = series_info.get('selected_episodes', set())
        
        # Create updated message
        new_message = f"*{title} - Season {season}*\n\n"
        new_message += "Select episodes to download by tapping episode numbers below or sending a message with numbers.\n"
        new_message += "Example message: `3 5 10-15` for episodes 3, 5, and 10 through 15.\n\n"
        new_message += "Available episodes:\n"
        
        # Create episode list (limit to first 20 for readability)
        display_limit = 20
        displayed_episodes = episodes[:display_limit]
        
        for ep in displayed_episodes:
            ep_num = ep.get('episodeNumber')
            ep_title = ep.get('title', 'Unknown')
            
            # Mark selected episodes
            if ep_num in selected:
                new_message += f"{ep_num}. {ep_title} ✅\n"
            else:
                new_message += f"{ep_num}. {ep_title}\n"
            
        if len(episodes) > display_limit:
            new_message += f"...and {len(episodes) - display_limit} more episodes\n"
        
        # Show selected episodes
        if selected:
            new_message += f"\nSelected episodes: {', '.join(str(e) for e in sorted(selected))}\n"
        else:
            new_message += "\nSelected episodes: None\n"
            
        new_message += "\nClick multiple episodes then tap 'Send Selected' when done."
        
        # Update the message
        bot.edit_message_text(
            new_message,
            message.chat.id,
            message.message_id,
            reply_markup=message.reply_markup,
            parse_mode='Markdown'
        )
    
    except Exception as e:
        logger.error(f"Error updating selection message: {str(e)}", exc_info=True)

@bot.message_handler(func=lambda message: True)
def handle_text_message(message):
    """Handle text messages for episode selection or direct requests"""
    # Check if user is authorized
    if TELEGRAM_ADMIN_IDS and message.from_user.id not in TELEGRAM_ADMIN_IDS and str(message.chat.id) != str(TELEGRAM_CHAT_ID):
        logger.warning(f"Unauthorized user {message.from_user.id} attempted to use the bot")
        return
        
    text = message.text.strip()
    logger.info(f"Received text message: {text}")
    
    # Check if there are any pending selections
    if pending_selections:
        handle_pending_selection(message, text)
        return
    
    # If no pending selections, check if this is a direct show request
    
    # Check for multi-episode format: "Show Title S01E01,S01E03,S02E05"
    multi_ep_match = re.search(r'(.*?)\s+((?:s\d+(?:e|ep)\d+(?:-\d+)?(?:,\s*)?)+)', text, re.IGNORECASE)
    if multi_ep_match:
        handle_multi_episode_request(message, multi_ep_match)
        return
    
    # Check for single-episode format: "Show Title S01E01" or "Show Title S01EP01-03"
    direct_request_match = re.search(r'(.*?)\s+s(\d+)(?:e|ep)(\d+(?:-\d+)?)', text, re.IGNORECASE)
    if direct_request_match:
        handle_direct_request(message, direct_request_match)
        return
        
    # No match found
    bot.reply_to(message, "No pending selections. To request a show directly, use format: 'Show Title S01E01' or 'Show Title S01EP01-03'")

def handle_pending_selection(message, text):
    """Handle text message for a pending episode selection"""
    # Assume the message is for the most recent series
    series_id = list(pending_selections.keys())[-1]
    info = pending_selections[series_id]
    
    # Parse episode numbers from the message
    try:
        episode_numbers = []
        
        # Handle 'all' keyword
        if text.lower() == 'all':
            episode_numbers = [ep['episodeNumber'] for ep in info['episodes']]
        else:
            # Split by spaces or commas
            parts = [p.strip() for p in text.replace(',', ' ').split()]
            
            for part in parts:
                if '-' in part:
                    # Handle ranges like "1-5"
                    start, end = map(int, part.split('-'))
                    episode_numbers.extend(list(range(start, end + 1)))
                else:
                    # Handle single numbers
                    episode_numbers.append(int(part))
        
        # Process the selection
        if episode_numbers:
            process_episode_selection(series_id, episode_numbers)
            
            # Create confirmation message
            if len(episode_numbers) > 10:
                ep_display = f"{len(episode_numbers)} episodes"
            else:
                ep_display = ", ".join(str(num) for num in sorted(episode_numbers))
                
            bot.reply_to(
                message, 
                f"Selected episodes ({ep_display}) from {info['title']} Season {info['season']} for download."
            )
            
            # Remove from pending
            del pending_selections[series_id]
        else:
            bot.reply_to(message, "No valid episode numbers found. Please try again.")
            
    except Exception as e:
        logger.error(f"Error parsing episode selection: {str(e)}", exc_info=True)
        bot.reply_to(message, "Error processing your selection. Please use numbers separated by spaces (e.g., '1 3 5-7').")

def handle_multi_episode_request(message, match):
    """
    Handle a multi-episode show request from Telegram
    
    Format: "Show Title S01E01,S01E03,S02E05"
    """
    try:
        show_title = match.group(1).strip()
        episode_string = match.group(2)
        
        # Parse all season/episode combinations
        season_episode_map = {}
        pattern = re.compile(r's(\d+)(?:e|ep)(\d+(?:-\d+)?)', re.IGNORECASE)
        
        for se_match in pattern.finditer(episode_string):
            season = int(se_match.group(1))
            ep_range = se_match.group(2)
            
            # Parse episode numbers
            if '-' in ep_range:
                start, end = map(int, ep_range.split('-'))
                episodes = list(range(start, end + 1))
            else:
                episodes = [int(ep_range)]
                
            # Add to our mapping
            if season in season_episode_map:
                season_episode_map[season].extend(episodes)
            else:
                season_episode_map[season] = episodes
        
        # Reply to acknowledge the request
        details = []
        for season, episodes in season_episode_map.items():
            details.append(f"Season {season}: Episodes {', '.join(str(e) for e in sorted(episodes))}")
        
        reply = bot.reply_to(
            message,
            f"🔍 Searching for: *{show_title}*\n\n"
            f"{chr(10).join(details)}\n\n"
            f"Please wait while I process this request...",
            parse_mode='Markdown'
        )
        
        # Search for the show in Sonarr
        headers = get_sonarr_headers()
        response = requests.get(f"{SONARR_URL}/api/v3/series", headers=headers)
        
        if not response.ok:
            bot.edit_message_text(
                f"❌ Error: Failed to connect to Sonarr. Status: {response.status_code}",
                reply.chat.id,
                reply.message_id
            )
            return
            
        series_list = response.json()
        
        # Look for the show by title (fuzzy match)
        matching_series = find_matching_series(show_title, series_list)
        
        if not matching_series:
            bot.edit_message_text(
                f"❌ Show not found: *{show_title}*\n\n"
                f"The show wasn't found in Sonarr. Please check the spelling or add it first.",
                reply.chat.id,
                reply.message_id,
                parse_mode='Markdown'
            )
            return
            
        # Get the series and process it
        series = matching_series
        series_id = series['id']
        
        # Update reply with found show
        processing_details = []
        for season, episodes in season_episode_map.items():
            processing_details.append(f"Season {season}: Episodes {', '.join(str(e) for e in sorted(episodes))}")
        
        bot.edit_message_text(
            f"✅ Found: *{series['title']}*\n\n"
            f"Processing:\n{chr(10).join(processing_details)}...",
            reply.chat.id,
            reply.message_id,
            parse_mode='Markdown'
        )
        
        # Process each season
        results = []
        for season, episode_numbers in season_episode_map.items():
            # No need to unmonitor the season or cancel downloads for direct requests
            
            # Get episodes for the season
            episodes = get_series_episodes(series_id, season, headers)
            
            if not episodes:
                results.append(f"❌ Season {season}: No episodes found")
                continue
                
            # Filter to only valid episode numbers
            valid_episode_numbers = []
            for num in episode_numbers:
                if any(ep['episodeNumber'] == num for ep in episodes):
                    valid_episode_numbers.append(num)
                    
            if not valid_episode_numbers:
                results.append(f"❌ Season {season}: None of the specified episodes exist")
                continue
                
            # Monitor the selected episodes
            monitor_success = monitor_specific_episodes(
                series_id,
                season,
                valid_episode_numbers,
                headers
            )
            
            if not monitor_success:
                results.append(f"❌ Season {season}: Failed to monitor episodes")
                continue
                
            # Get episode IDs for searching
            episode_ids = [
                ep['id'] for ep in episodes 
                if ep['episodeNumber'] in valid_episode_numbers
            ]
            
            # Trigger search for the episodes
            search_success = search_episodes(series_id, episode_ids, headers)
            
            if search_success:
                results.append(f"✅ Season {season}: Episodes {', '.join(str(e) for e in sorted(valid_episode_numbers))} processed")
            else:
                results.append(f"⚠️ Season {season}: Episodes monitored but search failed")
        
        # Final message with results for each season
        bot.edit_message_text(
            f"📝 *Results for {series['title']}*\n\n"
            f"{chr(10).join(results)}",
            reply.chat.id,
            reply.message_id,
            parse_mode='Markdown'
        )
    
    except Exception as e:
        logger.error(f"Error processing multi-episode request: {str(e)}", exc_info=True)
        bot.reply_to(message, "Error processing your request. Please use format: 'Show Title S01E05,S02E03,S03E01-03'")

def handle_direct_request(message, match):
    """
    Handle a direct show request from Telegram
    
    Format: "Show Title S01E05" or "Show Title S01EP01-03"
    """
    try:
        show_title = match.group(1).strip()
        season_number = int(match.group(2))
        episode_part = match.group(3)
        
        # Parse episode numbers
        episode_numbers = []
        if '-' in episode_part:
            start, end = map(int, episode_part.split('-'))
            episode_numbers = list(range(start, end + 1))
        else:
            episode_numbers = [int(episode_part)]
            
        # Reply to acknowledge the request
        reply = bot.reply_to(
            message,
            f"🔍 Searching for: *{show_title}* Season {season_number}, Episodes: {', '.join(str(e) for e in episode_numbers)}\n\n"
            f"Please wait while I process this request...",
            parse_mode='Markdown'
        )
        
        # Search for the show in Sonarr
        headers = get_sonarr_headers()
        response = requests.get(f"{SONARR_URL}/api/v3/series", headers=headers)
        
        if not response.ok:
            bot.edit_message_text(
                f"❌ Error: Failed to connect to Sonarr. Status: {response.status_code}",
                reply.chat.id,
                reply.message_id
            )
            return
            
        series_list = response.json()
        
        # Look for the show by title (fuzzy match)
        matching_series = find_matching_series(show_title, series_list)
        
        if not matching_series:
            bot.edit_message_text(
                f"❌ Show not found: *{show_title}*\n\n"
                f"The show wasn't found in Sonarr. Please check the spelling or add it first.",
                reply.chat.id,
                reply.message_id,
                parse_mode='Markdown'
            )
            return
            
        # Get the series and process it
        series = matching_series
        series_id = series['id']
        
        # Update reply with found show
        bot.edit_message_text(
            f"✅ Found: *{series['title']}* Season {season_number}\n\n"
            f"Processing episodes: {', '.join(str(e) for e in episode_numbers)}...",
            reply.chat.id,
            reply.message_id,
            parse_mode='Markdown'
        )
        
        # No need to unmonitor the season or cancel downloads for direct requests
        
        # Get episodes for the season
        episodes = get_series_episodes(series_id, season_number, headers)
        
        if not episodes:
            bot.edit_message_text(
                f"❌ No episodes found for *{series['title']}* Season {season_number}",
                reply.chat.id,
                reply.message_id,
                parse_mode='Markdown'
            )
            return
            
        # Filter to only valid episode numbers
        valid_episode_numbers = []
        for num in episode_numbers:
            if any(ep['episodeNumber'] == num for ep in episodes):
                valid_episode_numbers.append(num)
                
        if not valid_episode_numbers:
            bot.edit_message_text(
                f"❌ None of the specified episodes exist for *{series['title']}* Season {season_number}",
                reply.chat.id,
                reply.message_id,
                parse_mode='Markdown'
            )
            return
            
        # Monitor the selected episodes
        monitor_success = monitor_specific_episodes(
            series_id,
            season_number,
            valid_episode_numbers,
            headers
        )
        
        if not monitor_success:
            bot.edit_message_text(
                f"❌ Failed to monitor episodes for *{series['title']}*",
                reply.chat.id,
                reply.message_id,
                parse_mode='Markdown'
            )
            return
            
        # Get episode IDs for searching
        episode_ids = [
            ep['id'] for ep in episodes 
            if ep['episodeNumber'] in valid_episode_numbers
        ]
        
        # Trigger search for the episodes
        search_success = search_episodes(series_id, episode_ids, headers)
        
        if search_success:
            # Final success message
            bot.edit_message_text(
                f"✅ *Request Processed*: {series['title']} Season {season_number}\n\n"
                f"Selected Episodes: {', '.join(str(e) for e in sorted(valid_episode_numbers))}\n\n"
                f"Search has been started for these episodes.",
                reply.chat.id,
                reply.message_id,
                parse_mode='Markdown'
            )
        else:
            bot.edit_message_text(
                f"⚠️ Episodes monitored but search failed for *{series['title']}* Season {season_number}",
                reply.chat.id,
                reply.message_id,
                parse_mode='Markdown'
            )
    
    except Exception as e:
        logger.error(f"Error processing direct request: {str(e)}", exc_info=True)
        bot.reply_to(message, "Error processing your request. Please use format: 'Show Title S01E05' or 'Show Title S01EP01-03'")

def find_matching_series(title, series_list):
    """
    Find a series by title with fuzzy matching
    
    :param title: Show title to search for
    :param series_list: List of series from Sonarr
    :return: Best matching series or None
    """
    # First try exact match
    for series in series_list:
        if series['title'].lower() == title.lower():
            return series
            
    # Try case-insensitive contains
    contains_matches = [s for s in series_list if title.lower() in s['title'].lower()]
    if contains_matches:
        return contains_matches[0]
        
    # Try checking if all words in the query are in the title
    query_words = set(title.lower().split())
    for series in series_list:
        series_words = set(series['title'].lower().split())
        if query_words.issubset(series_words):
            return series
            
    # No match found
    return None

def process_episode_selection(series_id, episode_numbers):
    """
    Process selected episodes by monitoring and searching for them.
    
    :param series_id: Sonarr series ID
    :param episode_numbers: List of episode numbers to process
    """
    try:
        series_id = int(series_id)
        headers = get_sonarr_headers()
        
        # Get series info
        series_response = requests.get(
            f"{SONARR_URL}/api/v3/series/{series_id}",
            headers=headers
        )
        
        if not series_response.ok:
            logger.error(f"Failed to get series. Status: {series_response.status_code}")
            return False
            
        series = series_response.json()
        season_number = pending_selections[str(series_id)]['season']
        
        logger.info(f"Processing episode selection for {series['title']} Season {season_number}: {episode_numbers}")
        
        # Get episode IDs for searching
        episodes = get_series_episodes(series_id, season_number, headers)
        
        if not episodes:
            logger.error(f"No episodes found for series {series_id} season {season_number}")
            send_telegram_message(f"⚠️ Error: No episodes found for {series['title']} Season {season_number}", cleanup_after=300)
            return False
        
        # Filter to only valid episode numbers
        valid_episode_numbers = []
        for num in episode_numbers:
            if any(ep['episodeNumber'] == num for ep in episodes):
                valid_episode_numbers.append(num)
            else:
                logger.warning(f"Episode {num} not found in {series['title']} Season {season_number}")
        
        if not valid_episode_numbers:
            logger.error(f"No valid episodes found for selection {episode_numbers}")
            send_telegram_message(f"⚠️ Error: No valid episodes found in {series['title']} Season {season_number}", cleanup_after=300)
            return False
            
        # Monitor selected episodes
        monitor_success = monitor_specific_episodes(
            series_id, 
            season_number, 
            valid_episode_numbers, 
            headers
        )
        
        if not monitor_success:
            logger.error(f"Failed to monitor episodes for series {series_id}")
            send_telegram_message(f"⚠️ Error: Failed to monitor episodes for {series['title']}", cleanup_after=300)
            return False
            
        # Get episode IDs for searching
        episode_ids = [
            ep['id'] for ep in episodes 
            if ep['episodeNumber'] in valid_episode_numbers
        ]
        
        if not episode_ids:
            logger.error(f"Failed to find episode IDs for {valid_episode_numbers}")
            send_telegram_message(f"⚠️ Error: Failed to find episode IDs for {series['title']}", cleanup_after=300)
            return False
        
        # Log episode IDs for debugging
        logger.info(f"Episode IDs for search: {episode_ids}")
        
        # Trigger search for the episodes
        search_success = search_episodes(series_id, episode_ids, headers)
        
        if search_success:
            logger.info(f"Successfully set up monitoring and search for {len(valid_episode_numbers)} episodes")
            
            # Create a more permanent final message with complete information
            episodes_str = ", ".join(str(e) for e in sorted(valid_episode_numbers))
            final_msg = send_telegram_message(
                f"✅ *Request Processed*: {series['title']} Season {season_number}\n\n"
                f"Selected Episodes: {episodes_str}\n\n"
                f"Search has been started for these episodes."
                # No cleanup_after - this message stays
            )
            return True
        else:
            logger.error(f"Failed to search for episodes")
            send_telegram_message(f"⚠️ Failed to search for episodes in {series['title']} Season {season_number}", cleanup_after=300)
            return False
            
    except Exception as e:
        logger.error(f"Error processing episode selection: {str(e)}", exc_info=True)
        return False
    
def process_series(tvdb_id, season_number, request_id=None):
    headers = get_sonarr_headers()
    
    for attempt in range(12):  # Max 12 attempts
        try:
            logger.info(f"Checking for series (attempt {attempt + 1}/12)")
            response = requests.get(f"{SONARR_URL}/api/v3/series", headers=headers)
            
            if not response.ok:
                logger.error(f"Failed to get series list. Status: {response.status_code}")
                time.sleep(5)
                continue

            series_list = response.json()
            matching_series = [s for s in series_list if str(s.get('tvdbId')) == str(tvdb_id)]
            
            if not matching_series:
                logger.warning(f"No matching series found for TVDB ID {tvdb_id}")
                time.sleep(5)
                continue

            series = matching_series[0]
            series_id = series['id']
            logger.info(f"Found series: {series['title']} (ID: {series_id})")
            
            # 1. Unmonitor episodes only for the requested season
            unmonitor_success = unmonitor_season(series_id, season_number, headers)
            
            
            # Send episode selection to Telegram if configured
            if bot and TELEGRAM_CHAT_ID:
                # Get episodes for the season (we already verified season_number exists)
                episodes = get_series_episodes(series_id, season_number, headers)
                
                if episodes:
                    # Sort episodes by episode number
                    episodes.sort(key=lambda ep: ep.get('episodeNumber', 0))
                    
                    # Send episode selection options
                    send_episode_selection(
                        series_id,
                        series['title'],
                        season_number,
                        episodes
                    )
                    logger.info(f"Sent episode selection options for {series['title']} Season {season_number}")
                else:
                    logger.warning(f"No episodes found for {series['title']} Season {season_number}")
                    send_telegram_message(
                        f"⚠️ *Warning*: No episodes found for {series['title']} Season {season_number}"
                    )
            else:
                logger.info("Telegram not configured or no season number - skipping episode selection")
            
            return True
            
        except Exception as e:
            logger.error(f"Error during processing: {str(e)}", exc_info=True)
            
        time.sleep(5)
    
    logger.error(f"Series not found after 12 attempts")
    return False

# Flask application
app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    """Handle incoming webhooks."""
    logger.info("Received webhook request")
    logger.debug(f"Headers: {dict(request.headers)}")
    
    try:
        payload = request.json
        logger.debug(f"Received payload: {json.dumps(payload, indent=2)}")

        # Extract requested season from extra data
        requested_season = None
        for extra in payload.get('extra', []):
            if extra.get('name') == 'Requested Seasons':
                requested_season = int(extra.get('value'))
                break

        # Process any approved request for TV content
        if ('APPROVED' in payload.get('notification_type', '').upper() and 
            payload.get('media', {}).get('media_type') == 'tv'):
            
            tvdb_id = payload.get('media', {}).get('tvdbId')
            if not tvdb_id:
                return jsonify({"error": "No TVDB ID"}), 400
                
            # Verify we have a season number
            if not requested_season:
                logger.error("Missing required season number")
                return jsonify({"error": "No season specified. Season-specific requests are required."}), 400
            
            # Extract request ID
            request_id = payload.get('request', {}).get('request_id')
            
            # Send notification to Telegram
            if bot and TELEGRAM_CHAT_ID:
                title = payload.get('media', {}).get('title', 'Unknown')
                season_text = f"Season {requested_season}"
                prep_msg = send_telegram_message(
                    f"🎬 *Preparing*: {title} - {season_text}\n\nPreparing episode selection...",
                    cleanup_after=60  # Delete after 60 seconds
                )
            
            # Process series
            success = process_series(tvdb_id, requested_season, request_id)
            
            # Always attempt to delete the request
            if request_id:
                try:
                    delete_success = delete_overseerr_request(request_id)
                    if not delete_success:
                        logger.error(f"Failed to delete request {request_id}")
                except Exception as delete_error:
                    logger.error(f"Exception during request deletion: {delete_error}")
            
            response = {
                "status": "success" if success else "failed",
                "message": "Set up series" if success else "Failed to process series"
            }
            return jsonify(response), 200 if success else 500

        logger.info("Event ignored - not an approved TV request")
        return jsonify({"message": "Ignored event"}), 200
        
    except Exception as e:
        logger.error(f"Webhook processing error: {str(e)}", exc_info=True)
        return jsonify({"error": "Processing failed"}), 500

# Start Telegram bot polling in a separate thread
def start_telegram_polling():
    """Start the Telegram bot polling in a separate thread with reconnection."""
    if bot:
        while True:
            try:
                logger.info("Starting Telegram bot polling")
                bot.infinity_polling(timeout=60, long_polling_timeout=30)
            except Exception as e:
                logger.error(f"Telegram polling error: {str(e)}", exc_info=True)
                logger.info("Attempting to reconnect Telegram bot in 10 seconds...")
                time.sleep(10)
def check_and_cancel_unmonitored_downloads(initial_check=False):
    """
    Check and cancel unmonitored episode downloads with enhanced logging.
    """
    headers = get_sonarr_headers()
    
    logger.info("Starting unmonitored download cancellation check")
    logger.info(f"Initial check: {initial_check}")
    
    try:
        # Retrieve current queue
        queue_response = requests.get(f"{SONARR_URL}/api/v3/queue", headers=headers)
        
        if not queue_response.ok:
            logger.error(f"Failed to retrieve queue. Status: {queue_response.status_code}")
            return
        
        queue = queue_response.json().get('records', [])
        logger.info(f"Total queue items: {len(queue)}")
        
        # Track cancelled items
        cancelled_count = 0
        
        for item in queue:
            # Detailed logging for each queue item
            logger.info(f"Examining queue item: {item.get('title', 'Unknown')}")
            logger.info(f"Series ID: {item.get('seriesId')}, Episode ID: {item.get('episodeId')}")
            
            # Check if this is a TV episode
            if item.get('seriesId') and item.get('episodeId'):
                # Get series details to check for 'episodes' tag
                series_response = requests.get(
                    f"{SONARR_URL}/api/v3/series/{item['seriesId']}", 
                    headers=headers
                )
                
                if not series_response.ok:
                    logger.error(f"Failed to get series details for ID {item['seriesId']}")
                    continue
                
                series = series_response.json()
                
                # Log series tags
                logger.info(f"Series tags: {series.get('tags', [])}")
                
                # Check if series has 'episodes' tag
                if EPISODES_TAG_ID not in series.get('tags', []):
                    logger.info(f"Series {series.get('title', 'Unknown')} does not have 'episodes' tag (ID:{EPISODES_TAG_ID}). Skipping.")
                    continue
                
                # Get episode details
                episode_info = get_episode_info(item['episodeId'], headers)
                
                if episode_info:
                    logger.info(f"Episode details: Number {episode_info.get('episodeNumber')}, Monitored: {episode_info.get('monitored')}")
                
                if episode_info and not episode_info.get('monitored', False):
                    # Unmonitored episode - cancel download
                    cancel_success = cancel_download(item['id'], headers)
                    
                    if cancel_success:
                        series_title = series.get('title', 'Unknown Series')
                        logger.info(
                            f"Cancelled unmonitored download for tagged series: "
                            f"{series_title} - Season {item.get('seasonNumber')} "
                            f"Episode {episode_info.get('episodeNumber')}"
                        )
                        
                        # Optional: Send Telegram notification
                        send_telegram_message(
                            f"❌ Cancelled unmonitored download:\n"
                            f"*{series_title}* - Season {item.get('seasonNumber')} "
                            f"Episode {episode_info.get('episodeNumber')}"
                        )
                        
                        cancelled_count += 1
                else:
                    logger.info("Episode is either monitored or no episode info found.")
        
        # Log summary
        logger.info(f"Cancellation check complete. Cancelled {cancelled_count} unmonitored downloads for tagged series")
    
    except Exception as e:
        logger.error(f"Error in download queue monitoring: {str(e)}", exc_info=True)

def start_queue_monitoring(initial_check=True):
    """
    Start queue monitoring with aggressive initial checks followed by periodic checks.
    
    :param initial_check: If True, perform immediate and follow-up checks
    """
    logger.info("Starting queue monitoring thread")
    
    def monitor_thread():
        if initial_check:
            # Immediate first check
            logger.info("Running initial queue check")
            check_and_cancel_unmonitored_downloads(initial_check=True)
            
            # Follow-up checks with increasing intervals
            check_intervals = [30, 60, 120, 300]  # seconds: 30s, 1min, 2min, 5min
            
            for interval in check_intervals:
                time.sleep(interval)
                logger.info(f"Running follow-up queue check after {interval} seconds")
                check_and_cancel_unmonitored_downloads(initial_check=True)
        
        # Long-term periodic check - every 10 minutes instead of hourly
        logger.info("Switching to regular interval checks")
        while True:
            time.sleep(600)  # Check every 10 minutes (600 seconds)
            check_and_cancel_unmonitored_downloads()
    
    queue_thread = threading.Thread(target=monitor_thread)
    queue_thread.daemon = True
    queue_thread.start()
    logger.info("Queue monitoring thread started successfully")

def main():
    # Log startup
    logger.info("EpisEERR Webhook Listener Starting")
    logger.info(f"Sonarr URL: {SONARR_URL}")

    # Create tag on startup
    create_episode_tag()
    
    # Start Telegram bot in a separate thread if configured
    if bot:
        telegram_thread = threading.Thread(target=start_telegram_polling)
        telegram_thread.daemon = True
        telegram_thread.start()
        logger.info("Telegram bot thread started")

    # Start queue monitoring
    start_queue_monitoring()
    
    # Start webhook listener
    logger.info("Starting webhook listener on port 5000")
    app.run(host='0.0.0.0', port=5000)
    

if __name__ == '__main__':
    main()
