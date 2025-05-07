import time
from mega import Mega
from concurrent.futures import ThreadPoolExecutor
import telebot
from telebot import types

# Telegram bot token
API_TOKEN = '7672174618:AAHzcj2jeD10w5wOe7LPIsUkTTtPDLlLehA'

bot = telebot.TeleBot(API_TOKEN)

# In-memory storage for user credentials
user_credentials = {}

# Function to get all files in Mega account (excluding folders)
def get_all_files(mega_instance):
    files = []
    all_items = mega_instance.get_files()

    for file_id, file_info in all_items.items():
        if 'a' in file_info:  # Only add files, skip folders
            files.append(file_info)
    return files

# Function to rename a single file with retry mechanism
def rename_file_with_retry(mega_instance, file_info, file_number, retries=3):
    original_file_name = file_info['a']['n']
    new_name = f"@ Telegram {file_number}{original_file_name[original_file_name.rfind('.'):]}"
    
    for attempt in range(retries):
        try:
            # Rename the file
            file = mega_instance.find(original_file_name)
            if file:
                mega_instance.rename(file, new_name)
                return f"Renamed: '{original_file_name}' → '{new_name}'"
            else:
                return f"File '{original_file_name}' not found."
        except Exception as e:
            time.sleep(2)  # Wait before retrying
    return f"Failed to rename '{original_file_name}' after {retries} attempts."

# Start command handler
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "Welcome to the Mega Rename Bot!")
    bot.send_message(message.chat.id, "Please enter your Mega email:")

# Handle email input
@bot.message_handler(func=lambda message: message.text and not user_credentials.get(message.chat.id, {}).get('email'))
def get_email(message):
    user_id = message.chat.id
    email = message.text
    if user_id not in user_credentials:
        user_credentials[user_id] = {}
    user_credentials[user_id]['email'] = email
    bot.send_message(user_id, "Please enter your Mega password:")

# Handle password input
@bot.message_handler(func=lambda message: message.text and user_credentials.get(message.chat.id, {}).get('email') and not user_credentials.get(message.chat.id, {}).get('password'))
def get_password(message):
    user_id = message.chat.id
    password = message.text
    user_credentials[user_id]['password'] = password
    
    email = user_credentials[user_id]['email']
    bot.send_message(user_id, f"Logging in with email: {email}")
    
    # Mega login
    mega = Mega()
    try:
        mega_instance = mega.login(email, password)
        bot.send_message(user_id, "Login successful!")
        
        # Fetch all files in the Mega account
        all_files = get_all_files(mega_instance)

        if all_files:
            bot.send_message(user_id, f"Found {len(all_files)} files in your Mega account. Starting bulk rename...")

            # Using ThreadPoolExecutor for parallel processing
            with ThreadPoolExecutor(max_workers=20) as executor:
                results = [executor.submit(rename_file_with_retry, mega_instance, file_info, file_number)
                           for file_number, file_info in enumerate(all_files, start=1)]

            for future in results:
                bot.send_message(user_id, future.result())

            bot.send_message(user_id, "Bulk rename completed!")
        else:
            bot.send_message(user_id, "No files found in your Mega account.")
    except Exception as e:
        bot.send_message(user_id, f"Login failed: {e}")

# Run the bot
bot.polling()
