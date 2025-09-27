import os
import random
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ChatType
from typing import Dict, List, Tuple
from pymongo import MongoClient

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URL = os.getenv("MONGO_URL")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "WordRushDB")

# --- Configuration ---
DIFFICULTY_CONFIG = {
    'easy': {'length': 4, 'max_guesses': 30, 'base_points': 5, 'example': 'GAME'},
    'medium': {'length': 5, 'max_guesses': 30, 'base_points': 10, 'example': 'APPLE'},
    'hard': {'length': 8, 'max_guesses': 30, 'base_points': 20, 'example': 'FOOTBALL'},
    'extreme': {'length': 10, 'max_guesses': 30, 'base_points': 50, 'example': 'BASKETBALL'}
}

# --- Dummy Word List (Must be large for production) ---
RAW_WORDS = [
    "GAME", "FOUR", "FIRE", "WORD", # Easy (4)
    "APPLE", "HEART", "WATER", "TABLE", "PLANT", # Medium (5)
    "FOOTBALL", "COMPUTER", "KEYBOARD", "MEMORIZE", # Hard (8)
    "BASKETBALL", "CHALLENGE", "INCREDIBLE", "STRUCTURE" # Extreme (10)
]

WORDS_BY_LENGTH: Dict[int, List[str]] = {}
for word in RAW_WORDS:
    length = len(word)
    WORDS_BY_LENGTH.setdefault(length, []).append(word)

# --- MongoDB Manager Class ---

class MongoDBManager:
    def __init__(self, mongo_url: str, db_name: str):
        self.client = MongoClient(mongo_url)
        self.db = self.client[db_name]
        self.leaderboard_collection = self.db['leaderboard']
        self.games_collection = self.db['active_games']
        
        # Ensure indexes for fast lookups
        self.leaderboard_collection.create_index("user_id", unique=True)
        self.games_collection.create_index("chat_id", unique=True)
        print("MongoDB connection and indexing successful.")

    # --- Leaderboard Methods ---
    def update_leaderboard(self, user_id: int, username: str, points_to_add: int):
        self.leaderboard_collection.update_one(
            {'user_id': user_id},
            {
                '$inc': {'points': points_to_add, 'wins': 1},
                '$set': {'username': username}
            },
            upsert=True
        )

    def get_leaderboard_data(self, limit=10) -> List[Tuple[str, int, int]]:
        data = list(self.leaderboard_collection.find()
                    .sort('points', -1)
                    .limit(limit))
        
        result = []
        for doc in data:
            result.append((doc.get('username'), doc.get('points', 0), doc.get('wins', 0)))
        return result

    # --- Game State Methods ---
    def get_game_state(self, chat_id: int) -> Dict | None:
        return self.games_collection.find_one({'chat_id': chat_id})

    def save_game_state(self, chat_id: int, state: Dict):
        # Store state by chat_id
        state_to_save = {'chat_id': chat_id, **state}
        self.games_collection.replace_one(
            {'chat_id': chat_id}, 
            state_to_save, 
            upsert=True
        )

    def delete_game_state(self, chat_id: int):
        self.games_collection.delete_one({'chat_id': chat_id})

# Initialize MongoDB Manager
try:
    mongo_manager = MongoDBManager(MONGO_URL, MONGO_DB_NAME)
except Exception as e:
    print(f"FATAL: Could not connect to MongoDB. Check MONGO_URL. Error: {e}")
    mongo_manager = None # Set to None if connection fails

# --- Game Logic Functions (Uses MongoDBManager) ---

def get_feedback(secret_word: str, guess: str) -> str:
    # (Implementation remains the same as previous advanced example)
    length = len(secret_word)
    feedback = ['🟥'] * length 
    remaining_letters = {}
    for letter in secret_word:
        remaining_letters[letter] = remaining_letters.get(letter, 0) + 1
    for i in range(length):
        if guess[i] == secret_word[i]:
            feedback[i] = '🟩'
            remaining_letters[guess[i]] -= 1
    for i in range(length):
        if feedback[i] == '🟥':
            letter = guess[i]
            if letter in remaining_letters and remaining_letters[letter] > 0:
                feedback[i] = '🟨'
                remaining_letters[letter] -= 1
    return "".join(feedback)

def calculate_points(difficulty: str, guesses: int) -> int:
    config = DIFFICULTY_CONFIG[difficulty]
    base = config['base_points']
    bonus = max(0, 5 - (guesses - 1) // 6) 
    return base + bonus

async def start_game(chat_id: int, difficulty: str) -> Tuple[bool, str]:
    if not mongo_manager: return False, "Database Error. Cannot start game."
    
    difficulty = difficulty.lower()
    if difficulty not in DIFFICULTY_CONFIG:
        return False, f"❌ Invalid difficulty. Choose from: {'/'.join(DIFFICULTY_CONFIG.keys())}."

    config = DIFFICULTY_CONFIG[difficulty]
    length = config['length']
    word_list = WORDS_BY_LENGTH.get(length)
    
    if not word_list:
        return False, f"Error: No words found for {difficulty} ({length} letters)."
    
    secret_word = random.choice(word_list)
    
    # Save initial game state to MongoDB
    initial_state = {
        'word': secret_word,
        'difficulty': difficulty,
        'guesses_made': 0,
        'max_guesses': config['max_guesses']
    }
    mongo_manager.save_game_state(chat_id, initial_state)
    
    return True, (
        f"Game started! Difficulty set to **{difficulty.capitalize()}** ({length} letters).\n"
        f"Guess the **{length}** letters word!"
    )

async def process_guess(chat_id: int, guess: str) -> Tuple[str, bool, str, int]:
    if not mongo_manager: return "", False, "Database Error.", 0

    game = mongo_manager.get_game_state(chat_id)
    if not game:
        return "", False, "No active game.", 0
    
    secret_word = game['word']
    guess = guess.upper()
    config = DIFFICULTY_CONFIG[game['difficulty']]
    length = config['last_guess'] # To hold previous guess for re-submission logic
    
    # 1. Validation
    if len(guess) != length:
        return "", False, f"❌ The guess must be exactly **{length}** letters long.", 0
    if guess not in WORDS_BY_LENGTH.get(length, []):
         return "", False, f"❌ **{guess}** is not a valid word.", 0

    game['guesses_made'] += 1
    
    # 2. Check for Win
    if guess == secret_word:
        guesses = game['guesses_made']
        points = calculate_points(game['difficulty'], guesses)
        mongo_manager.delete_game_state(chat_id)
        return "🟩" * length, True, f"🥳 **CONGRATS!** You won in {guesses} guesses! (+{points} points)", points

    # 3. Generate Feedback & Check for Loss
    feedback_str = get_feedback(secret_word, guess)
    remaining = game['max_guesses'] - game['guesses_made']
    
    # Save updated state before checking loss
    mongo_manager.save_game_state(chat_id, game)
    
    if remaining <= 0:
        mongo_manager.delete_game_state(chat_id)
        return feedback_str, False, f"💔 Game Over! The word was **{secret_word}**.", 0
    
    return feedback_str, False, f"Guesses left: **{remaining}**", 0

# --- Telegram Handlers ---

async def is_group_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if update.effective_chat.type == ChatType.PRIVATE:
        return True
    member = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
    return member.status in ['administrator', 'creator']

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👋 Welcome to **WordRushBot**!\n"
        "1. Use **/new [difficulty]** (easy/medium/hard/extreme) to start.\n"
        "2. **/help** for all commands.\n",
        parse_mode='Markdown'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    commands_list = (
        "**Word Rush Commands**\n"
        "• **/new (level)** → Start a new game.\n"
        "• **/end** → End the current game (Admins only).\n"
        "• **/leaderboard** → Show the global scores.\n\n"
        "**How to Play**\n"
        f"Easy: {DIFFICULTY_CONFIG['easy']['length']} letters (e.g., {DIFFICULTY_CONFIG['easy']['example']})\n"
        f"Medium: {DIFFICULTY_CONFIG['medium']['length']} letters (e.g., {DIFFICULTY_CONFIG['medium']['example']})\n"
        "..."
    )
    await update.message.reply_text(commands_list, parse_mode='Markdown')

async def new_game_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    difficulty = context.args[0].lower() if context.args else 'medium'
    
    success, message = await start_game(chat_id, difficulty)
    
    await update.message.reply_text(message, parse_mode='Markdown')

async def end_game_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    
    if not mongo_manager.get_game_state(chat_id):
        await update.message.reply_text("No game is currently running to end.")
        return
        
    if not await is_group_admin(update, context):
        await update.message.reply_text("❌ You must be a **Group Admin** to end the game.", parse_mode='Markdown')
        return

    # Fetch word before deleting
    word = mongo_manager.get_game_state(chat_id).get('word', 'UNKNOWN')
    mongo_manager.delete_game_state(chat_id)
    
    await update.message.reply_text(
        f"Game ended by Admin. The secret word was **{word}**.", 
        parse_mode='Markdown'
    )

async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not mongo_manager:
        await update.message.reply_text("Database Error. Cannot fetch leaderboard.")
        return

    data = mongo_manager.get_leaderboard_data(limit=10)
    
    if not data:
        message = "🏆 **Global Leaderboard**\n\nNo scores recorded yet. Start a game!"
    else:
        message = "🏆 **Global Leaderboard** (Top 10)\n\n"
        for i, (username, points, wins) in enumerate(data):
            name = f"User #{i+1}" if not username else f"@{username}"
            message += f"{i+1}. **{name}** - {points} points ({wins} wins)\n"

    await update.message.reply_text(message, parse_mode='Markdown')

async def handle_guess(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user = update.effective_user
    
    if not mongo_manager.get_game_state(chat_id):
        return

    guess = update.message.text.strip()
    
    feedback, is_win, status_message, points = await process_guess(chat_id, guess)

    if "❌" in status_message:
        await update.message.reply_text(status_message, parse_mode='Markdown')
        return

    reply_text = f"{feedback} - **{guess.upper()}**\n{status_message}"
    await update.message.reply_text(reply_text, parse_mode='Markdown')

    if is_win:
        username = user.username or str(user.id)
        mongo_manager.update_leaderboard(user.id, username, points)

# --- Main Bot Runner ---

def main():
    """Start the bot."""
    if not BOT_TOKEN:
        print("FATAL ERROR: BOT_TOKEN not found. Please set it in the .env file.")
        return

    application = Application.builder().token(BOT_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("new", new_game_command))
    application.add_handler(CommandHandler("end", end_game_command))
    application.add_handler(CommandHandler("leaderboard", leaderboard_command))
    
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_guess))

    print("Advanced MongoDB WordRush Bot is running...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

