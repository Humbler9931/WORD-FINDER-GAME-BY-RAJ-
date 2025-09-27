import os
import random
import re
import logging
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, error
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram.constants import ChatType
from typing import Dict, List, Tuple
from pymongo import MongoClient

# --- Logging Configuration ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Load Environment Variables ---
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URL = os.getenv("MONGO_URL")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "WordRushDB")
try:
    ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID")) 
except (TypeError, ValueError):
    ADMIN_USER_ID = 0 
    logger.warning("⚠️ ADMIN_USER_ID not set or invalid. Admin features will be disabled.")

# --- Configuration (Capped at 8 letters and using only 8-letter for hard/extreme) ---
DIFFICULTY_CONFIG = {
    'easy': {'length': 4, 'max_guesses': 30, 'base_points': 5, 'example': 'GAME'},
    'medium': {'length': 5, 'max_guesses': 30, 'base_points': 10, 'example': 'APPLE'},
    'hard': {'length': 8, 'max_guesses': 30, 'base_points': 20, 'example': 'FOOTBALL'},
    'extreme': {'length': 8, 'max_guesses': 30, 'base_points': 50, 'example': 'FOOTBALL'} 
}

# --- Word List (Using only up to 8-letter words) ---
RAW_WORDS = [
    # 4-Letter Words
    "GAME", "FOUR", "FIRE", "WORD", "PLAY", "CODE", "RUNS", "STOP", "LOOK", "CALL", "BACK", "BEST", "FAST", "SLOW", "HIGH", "LOWS", 
    "OPEN", "CLOS", "READ", "WRIT", "BOOK", "PAGE", "LINE", "JUMP", "WALK", "TALK", "QUIZ", "TEST", "RAIN", "SNOW", "SUNY", "COLD", 
    "HEAT", "WIND", "MIST", "DUST", "ROCK", "SAND", "SOIL", "GRAS", "TREE", "LEAF", "ROOT", "STEM", "SEED", "GROW", "CROP", "FARM", 
    # 5-Letter Words
    "APPLE", "HEART", "WATER", "TABLE", "PLANT", "TIGER", "EAGLE", "SNAKE", "WHALE", "ZEBRA", "SOUND", "MUSIC", "RADIO", "VOICE", 
    "BEACH", "OCEAN", "RIVER", "LAKE", "FIELD", "CABLE", "WIRED", "PHONE", "EMAIL", "SCARY", "HAPPY", "FUNNY", "SADLY", "ANGER", 
    "BRAVE", "CHAIR", "BENCH", "CUPPY", "GLASS", "PLATE", "FORKS", "KNIFE", "SPOON", "SUGAR", "SALTZ", "BREAD", "CHEES", "MEATS", 
    # 8-Letter Words
    "FOOTBALL", "COMPUTER", "KEYBOARD", "MEMORIZE", "INTERNET", "PROGRAMS", "SOFTWARE", "HARDWARE", "DATABASE", "ALGORISM", 
    "SECURITY", "PASSWORD", "TELEGRAM", "BUSINESS", "FINANCES", "MARKETIN", "ADVERTSZ", "STRATEGY", "MANUFACT", "PRODUCTS", 
]

WORDS_BY_LENGTH: Dict[int, List[str]] = {}
for word in RAW_WORDS:
    cleaned_word = "".join(filter(str.isalpha, word.upper())) 
    length = len(cleaned_word)
    if length <= 8 and length in [c['length'] for c in DIFFICULTY_CONFIG.values()]: 
         WORDS_BY_LENGTH.setdefault(length, []).append(cleaned_word)
         
# --- MongoDB Manager Class (Unchanged) ---
class MongoDBManager:
    """Handles all interactions with MongoDB."""
    def __init__(self, mongo_url: str, db_name: str):
        if not mongo_url:
            raise ValueError("MONGO_URL not provided.")
        
        # Increased timeout slightly for better robustness
        self.client = MongoClient(mongo_url, serverSelectionTimeoutMS=10000) 
        self.db = self.client[db_name]
        self.leaderboard_collection = self.db['leaderboard']
        self.games_collection = self.db['active_games']
        self.chats_collection = self.db['known_chats'] 
        
        self.leaderboard_collection.create_index("user_id", unique=True)
        self.games_collection.create_index("chat_id", unique=True)
        self.chats_collection.create_index("chat_id", unique=True)
        logger.info("✅ MongoDB connection and indexing successful.")

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
        data = list(self.leaderboard_collection.find().sort('points', -1).limit(limit))
        result = []
        for doc in data:
            result.append((doc.get('username'), doc.get('points', 0), doc.get('wins', 0)))
        return result

    def get_game_state(self, chat_id: int) -> Dict | None:
        return self.games_collection.find_one({'chat_id': chat_id})

    def save_game_state(self, chat_id: int, state: Dict):
        state_to_save = {'chat_id': chat_id, **state}
        self.games_collection.replace_one(
            {'chat_id': chat_id}, 
            state_to_save, 
            upsert=True
        )

    def delete_game_state(self, chat_id: int):
        self.games_collection.delete_one({'chat_id': chat_id})

    def add_chat(self, chat_id: int, chat_type: str, date: float):
        self.chats_collection.update_one(
            {'chat_id': chat_id},
            {'$set': {'chat_type': chat_type, 'last_active': date}},
            upsert=True
        )

    def get_all_chat_ids(self) -> List[int]:
        return [doc['chat_id'] for doc in self.chats_collection.find({}, {'chat_id': 1})]

# --- Initialize MongoDB Manager ---
mongo_manager = None
try:
    if MONGO_URL:
        mongo_manager = MongoDBManager(MONGO_URL, MONGO_DB_NAME)
    else:
        logger.error("❌ MONGO_URL not set. Running without database features.")
except Exception as e:
    logger.error(f"❌ FATAL: Could not connect to MongoDB. Error: {e}")
    mongo_manager = None 

# --- Core Game Logic Functions ---

def get_feedback(secret_word: str, guess: str) -> str:
    """Generates the Wordle-style color-coded feedback (🟩, 🟨, 🟥)."""
    length = len(secret_word)
    feedback = ['🟥'] * length 
    remaining_letters = {}
    
    for letter in secret_word:
        remaining_letters[letter] = remaining_letters.get(letter, 0) + 1

    # First pass: Green (Correct position)
    for i in range(length):
        if i < len(guess) and guess[i] == secret_word[i]:
            feedback[i] = '🟩'
            remaining_letters[guess[i]] -= 1

    # Second pass: Yellow (Correct letter, wrong position)
    for i in range(length):
        if feedback[i] == '🟥' and i < len(guess):
            letter = guess[i]
            if letter in remaining_letters and remaining_letters[letter] > 0:
                feedback[i] = '🟨'
                remaining_letters[letter] -= 1
    
    return "".join(feedback)

def calculate_points(difficulty: str, guesses: int) -> int:
    """Calculates points based on difficulty and efficiency."""
    config = DIFFICULTY_CONFIG[difficulty]
    base = config['base_points']
    # Higher bonus for fewer guesses
    bonus = max(0, 10 - (guesses - 1) * 2) 
    return base + bonus

async def start_new_game_logic(chat_id: int, difficulty: str) -> Tuple[bool, str]:
    if not mongo_manager: return False, "❌ *Database Error*. Game cannot be started without database access."
    
    difficulty = difficulty.lower()
    if difficulty not in DIFFICULTY_CONFIG:
        difficulty = 'medium'
        
    config = DIFFICULTY_CONFIG[difficulty]
    length = config['length']
    word_list = WORDS_BY_LENGTH.get(length)
    
    if not word_list:
        return False, f"❌ *Error*: No secret words found for **{difficulty}** ({length} letters). Contact admin."
    
    # Select a secret word from the list
    secret_word = random.choice(word_list)
    
    initial_state = {
        'word': secret_word,
        'difficulty': difficulty,
        'guesses_made': 0,
        'max_guesses': config['max_guesses'],
        'guess_history': [] 
    }
    mongo_manager.save_game_state(chat_id, initial_state)
    
    return True, (
        f"**✨ New Word Rush Challenge!**\n"
        f"-------------------------------------\n"
        f"🎯 Difficulty: **{difficulty.capitalize()}**\n"
        f"📜 Word Length: **{length} letters** (Example: `{config['example']}`)\n"
        f"➡️ *Send your {length}-letter guess directly to the chat!*"
    )

async def process_guess_logic(chat_id: int, guess: str) -> Tuple[str, bool, str, int, List[str]]:
    """Processes a user's guess and returns feedback, win status, and points."""
    if not mongo_manager: return "", False, "Database Error.", 0, []

    game = mongo_manager.get_game_state(chat_id)
    if not game:
        return "", False, "No active game.", 0, []
    
    secret_word = game['word']
    # Guess is already cleaned by the MessageHandler filters, but ensure it's uppercase
    guess_clean = guess.upper()

    config = DIFFICULTY_CONFIG[game['difficulty']]
    length = config['length']
    
    # 1. Validation for length (Should match game length)
    if len(guess_clean) != length:
        # User message for incorrect length
        return "", False, f"❌ **`{guess.upper()}`** *must be exactly* **{length}** *letters long*.", 0, game.get('guess_history', [])
    
    game['guesses_made'] += 1
    
    # 2. Generate Feedback and update history
    feedback_str = get_feedback(secret_word, guess_clean)
    # Storing in the required format: Blocks - WORD
    game['guess_history'].append(f" `{feedback_str}` - **{guess_clean}**") 
    
    # 3. Check for Win
    if guess_clean == secret_word:
        guesses = game['guesses_made']
        points = calculate_points(game['difficulty'], guesses)
        game_word_for_loss = game['word']
        mongo_manager.delete_game_state(chat_id) 
        return feedback_str, True, "WIN", points, game['guess_history']

    # 4. Check for Loss
    remaining = game['max_guesses'] - game['guesses_made']
    
    if remaining <= 0:
        game_word_for_loss = game['word']
        mongo_manager.delete_game_state(chat_id) 
        # For loss, we return the secret word as status
        return feedback_str, False, f"LOSS_WORD:{game_word_for_loss}", 0, game['guess_history']
    
    # Status for ongoing game
    mongo_manager.save_game_state(chat_id, game)
    return feedback_str, False, f"Guesses left: **{remaining}**", 0, game['guess_history']

# --- Telegram UI & Handler Functions (Admin check updated for DM support) ---

async def is_group_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    # Any user is considered "admin" in a private chat for commands like /end and /difficulty
    if update.effective_chat.type == ChatType.PRIVATE:
        return True
    try:
        member = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
        return member.status in ['administrator', 'creator']
    except Exception:
        return False

# --- Keyboard Functions (Updated with better emojis) ---

def get_start_keyboard():
    keyboard = [
        [InlineKeyboardButton("❓ Help & Info", callback_data="show_help_menu")],
        [
            InlineKeyboardButton("💬 Report Bugs", url="https://t.me/Onlymrabhi01"), 
            InlineKeyboardButton("📢 Updates Channel", url="https://t.me/narzob") 
        ],
        [InlineKeyboardButton("➕ Add Bot to Group", url="https://t.me/narzowordseekbot?startgroup=true")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_help_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("📝 How to Play", callback_data="show_how_to_play")],
        [InlineKeyboardButton("📘 Commands List", callback_data="show_commands")],
        [InlineKeyboardButton("🏆 Leaderboard", callback_data="show_leaderboard_cb")], # New Callback
        [InlineKeyboardButton("🏠 Back to Start", callback_data="back_to_start")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_play_again_keyboard():
    keyboard = [
        [InlineKeyboardButton("🎯 Start New Game", callback_data="new_game_menu")] 
    ]
    return InlineKeyboardMarkup(keyboard)

def get_new_game_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("⭐ Easy (4 letters)", callback_data="start_easy"),
            InlineKeyboardButton("🌟 Medium (5 letters)", callback_data="start_medium")
        ],
        [
            InlineKeyboardButton("🔥 Hard (8 letters)", callback_data="start_hard"),
            InlineKeyboardButton("💎 Extreme (8 letters, High Pts)", callback_data="start_extreme")
        ],
        [InlineKeyboardButton("🏠 Back to Start", callback_data="back_to_start")]
    ]
    return InlineKeyboardMarkup(keyboard)


# --- Command Handlers ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if mongo_manager and update.effective_message:
        mongo_manager.add_chat(update.effective_chat.id, update.effective_chat.type.name, update.effective_message.date.timestamp())
    
    # Stylish Start Message
    await update.message.reply_text(
        "👋 *Hello! I'm* **@narzowordseekbot** 🤖\n"
        "-------------------------------------\n"
        "The **Ultimate Word Challenge** on Telegram!\n\n"
        "📜 **Goal:** *Guess the secret word using hints (🟩/🟨/🟥).*\n"
        "🏆 **Compete:** *Win to earn points and climb the Global Leaderboard!* 🌐\n\n"
        "👉 Tap **/new** or the button below to start your rush!\n"
        "-------------------------------------",
        reply_markup=get_start_keyboard(),
        parse_mode='Markdown'
    )

async def new_game_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if mongo_manager and update.effective_message:
        mongo_manager.add_chat(chat_id, update.effective_chat.type.name, update.effective_message.date.timestamp())

    difficulty = context.args[0].lower() if context.args else 'medium'
    
    if mongo_manager and mongo_manager.get_game_state(chat_id):
        await update.message.reply_text("⏳ *A game is already active*. Use **/end** to stop it first.")
        return

    success, message = await start_new_game_logic(chat_id, difficulty)
    await update.message.reply_text(message, parse_mode='Markdown')

async def end_game_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    
    if not mongo_manager or not mongo_manager.get_game_state(chat_id):
        await update.message.reply_text("❌ *No game is currently running to end*.")
        return
        
    if not await is_group_admin(update, context):
        await update.message.reply_text("🚨 *Admin Check Failed*. You must be an **Admin** to force-end the game.", parse_mode='Markdown')
        return

    game_state = mongo_manager.get_game_state(chat_id)
    word = game_state.get('word', 'UNKNOWN')
    mongo_manager.delete_game_state(chat_id)
    
    await update.message.reply_text(
        f"🛑 **Game Ended!**\n"
        f"*The secret word was:* **`{word}`**.", 
        parse_mode='Markdown'
    )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shows the current game status and guess history."""
    chat_id = update.effective_chat.id
    if not mongo_manager:
        await update.message.reply_text("❌ *Database Error*. Cannot fetch game status.")
        return

    game_state = mongo_manager.get_game_state(chat_id)
    if not game_state:
        await update.message.reply_text("🎯 *No active game*. Use **/new** to start a challenge!")
        return
    
    guess_history = game_state.get('guess_history', [])
    
    if not guess_history:
        history_display = "*No guesses made yet!*"
    else:
        history_display = "\n".join(guess_history)

    remaining = game_state['max_guesses'] - game_state['guesses_made']
    
    reply_text = (
        f"**📊 Current Word Rush Status**\n"
        f"-------------------------------------\n"
        f"Difficulty: **{game_state['difficulty'].capitalize()}**\n"
        f"Word Length: **{len(game_state['word'])} letters**\n"
        f"Guesses: **`{game_state['guesses_made']}`** / **`{game_state['max_guesses']}`**\n"
        f"Remaining: **`{remaining}`**\n\n"
        f"📜 **Guess History:**\n"
        f"{history_display}"
    )
    
    await update.message.reply_text(reply_text, parse_mode='Markdown')

async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if mongo_manager and update.effective_message:
        mongo_manager.add_chat(update.effective_chat.id, update.effective_chat.type.name, update.effective_message.date.timestamp())
        
    if not mongo_manager:
        await update.message.reply_text("❌ *Database Error*. Cannot fetch leaderboard.")
        return

    data = mongo_manager.get_leaderboard_data(limit=10)
    
    if not data:
        message = "🏆 **Global Leaderboard**\n\n*No scores recorded yet. Be the first to start a game!*"
    else:
        message = "🏆 **Global Leaderboard** (Top 10)\n"
        message += "-------------------------------------\n"
        for i, (username, points, wins) in enumerate(data):
            # Better rank styling
            rank_style = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"**{i+1}.**"
            name = f"@{username}" if username else f"User `{update.effective_user.id}`"
            message += f"{rank_style} {name} - **`{points}`** pts ({wins} wins)\n"

    await update.message.reply_text(message, parse_mode='Markdown')

async def difficulty_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shows available difficulty levels and their settings."""
    chat_id = update.effective_chat.id

    if not await is_group_admin(update, context):
        await update.message.reply_text("🚨 *Admin Check Failed*. You must be an **Admin** to view or change settings.", parse_mode='Markdown')
        return

    message = "**⚙️ Word Rush Difficulty Settings**\n"
    message += "-------------------------------------\n"
    
    for level, config in DIFFICULTY_CONFIG.items():
        message += f"**{level.capitalize()}**:\n"
        message += f"   - Word Length: **{config['length']}** letters\n"
        message += f"   - Max Guesses: **{config['max_guesses']}**\n"
        message += f"   - Base Points: **{config['base_points']}**\n"
        message += f"   - Example: `{config['example']}`\n\n"

    message += "👉 *Use* `/new <level>` *to start a game with a specific difficulty.* (e.g., `/new hard`)"

    await update.message.reply_text(message, parse_mode='Markdown')


# --- Broadcast Command (Unchanged, Admin only) ---

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a message to all known chats (Admin only)."""
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return

    if not context.args:
        await update.message.reply_text("Usage: `/broadcast <your message here>`", parse_mode='Markdown')
        return
    
    if not mongo_manager:
        await update.message.reply_text("❌ Database error. Cannot retrieve chat list.")
        return

    message_to_send = " ".join(context.args)
    chat_ids = mongo_manager.get_all_chat_ids()
    
    success_count = 0
    fail_count = 0
    
    await update.message.reply_text(f"📢 *Attempting to broadcast message to* **{len(chat_ids)}** *chats...*")

    for chat_id in chat_ids:
        try:
            await context.bot.send_message(chat_id=chat_id, text=message_to_send, parse_mode='Markdown')
            success_count += 1
        except error.Forbidden:
            logger.warning(f"Failed to send broadcast to chat {chat_id}: Bot blocked.")
            fail_count += 1
        except Exception as e:
            logger.error(f"Failed to send broadcast to chat {chat_id}: {e}")
            fail_count += 1
            
    await update.message.reply_text(f"✅ **Broadcast Complete**\nSuccessful: **{success_count}**\nFailed: **{fail_count}**", parse_mode='Markdown')

# --- Callback Handler (Added leaderboard callback) ---
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer() 
    chat_id = query.message.chat_id
    
    if query.data == "back_to_start":
        await query.edit_message_text(
            "👋 *Hello! I'm* **WordRush Bot** 🤖\n"
            "-------------------------------------\n"
            "The **Ultimate Word Challenge** on Telegram!\n\n"
            "📜 **Goal:** *Guess the secret word using hints (🟩/🟨/🟥).*\n"
            "🏆 **Compete:** *Win to earn points and climb the Global Leaderboard!* 🌐\n\n"
            "👉 Tap **/new** or the button below to start your rush!\n"
            "-------------------------------------",
            reply_markup=get_start_keyboard(),
            parse_mode='Markdown'
        )
    
    elif query.data == "show_help_menu":
        await query.edit_message_text(
            "📖 **WordRush Help Center**\n"
            "-------------------------------------\n"
            "*Choose a topic below to get assistance.*\n"
            "*For any issue, please ask in the Report group!*",
            reply_markup=get_help_menu_keyboard(),
            parse_mode='Markdown'
        )
    # ... other help menu callbacks (show_how_to_play, show_commands) ...
    elif query.data == "show_how_to_play":
        commands_list = (
            "🤔 **How to Play Word Rush** ❓\n"
            "-------------------------------------\n"
            "1. **The Word:** *Guess a secret word*, length depends on difficulty (4, 5, or 8 letters).\n\n"
            "2. **The Hints (`Boxes - Word`):**\n"
            "   • 🟢 *Green* = Correct letter, **Right Place**.\n"
            "   • 🟡 *Yellow* = Correct letter, **Wrong Place**.\n"
            "   • 🔴 *Red* = Letter **Not in the Word**.\n\n"
            "3. **The Game:** You have *30 guesses*. The person who wins with the fewest guesses gets the most points! 🥇"
        )
        await query.edit_message_text(commands_list, reply_markup=get_help_menu_keyboard(), parse_mode='Markdown')

    elif query.data == "show_commands":
        commands_list = (
            "📘 **Word Rush Commands List**\n"
            "-------------------------------------\n"
            "• **/new** [difficulty] → *Start a game*.\n"
            "• **/status** → *Show current game status and history* (New Feature!).\n"
            "• **/leaderboard** → *Show global rankings*.\n"
            "• **/end** → *End current game* (Admin Only / DM).\n"
            "• **/difficulty** → *Show difficulty settings* (Admin Only / DM).\n"
        )
        await query.edit_message_text(commands_list, reply_markup=get_help_menu_keyboard(), parse_mode='Markdown')
        
    elif query.data == "show_leaderboard_cb":
        # Calls the leaderboard logic via callback
        # Fake update object for leaderboard command
        leaderboard_update = Update(update_id=0, message=query.message) 
        await leaderboard_command(leaderboard_update, context) 
        # Re-edit the original message with the help menu keyboard to prevent the leaderboard from replacing it.
        # This requires a separate message. Or just replace the current message temporarily.
        await query.edit_message_reply_markup(reply_markup=get_help_menu_keyboard())

    elif query.data == "new_game_menu":
        await query.edit_message_text(
            "🎯 **Select Your Challenge Level:**\n"
            "*Choose the word length and point value.*",
            reply_markup=get_new_game_keyboard(),
            parse_mode='Markdown'
        )
    
    elif query.data.startswith("start_"):
        difficulty = query.data.split('_')[1]
        
        if mongo_manager and mongo_manager.get_game_state(chat_id):
            await query.edit_message_text("⏳ *A game is already active*. Use **/end** to stop it first.")
            return

        success, message = await start_new_game_logic(chat_id, difficulty)
        if success:
            await query.edit_message_text(message, parse_mode='Markdown')
        else:
            await query.edit_message_text(f"❌ *Game start failed*: {message}", parse_mode='Markdown')

# --- Updated Guess Handler (Uses filters.Regex for strict letter checking) ---

async def handle_guess(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user = update.effective_user
    guess = update.message.text.strip()
    
    # Advanced Log: See who is guessing
    username = user.username or user.first_name
    logger.info(f"Guess received in chat {chat_id} from {username}: {guess}")

    if not mongo_manager:
        # DB Error - don't respond to guesses to prevent spam
        return

    game_state = mongo_manager.get_game_state(chat_id)
    if not game_state:
        # Game not active - DO NOT RESPOND as requested
        return 

    # Since MessageHandler is now using filters.Regex('[a-zA-Z]{1,8}'), the guess
    # should be clean (only letters, 1 to 8 length). We pass it directly.
    
    # Process guess
    feedback, is_win, status_message, points, guess_history = await process_guess_logic(chat_id, guess)
    
    # 1. Handle validation errors (Incorrect length for current game)
    if status_message.startswith("❌"):
        await update.message.reply_text(status_message, parse_mode='Markdown')
        return

    reply_markup = None
    
    # 2. Construct the full history display
    game_history_display = "\n".join(guess_history)
    
    # 3. Handle Win/Loss/Ongoing
    
    if is_win:
        word_was = guess_history[-1].split(' - ')[-1].replace('**', '').strip() 
        
        mongo_manager.update_leaderboard(user.id, username, points)
        
        reply_text = (
            f"**🏆 GAME WON! 🥳**\n"
            f"-------------------------------------\n"
            f"*Congratulations* **{username}**!\n"
            f"You cracked the code in **{len(guess_history)}** attempts!\n"
            f"✨ Points earned: **`{points}`**\n\n"
            f"📜 **Final Board:**\n"
            f"{game_history_display}\n\n" 
            f"✅ *The secret word was:* **`{word_was}`**"
        )
        reply_markup = get_play_again_keyboard()

    elif status_message.startswith("LOSS_WORD:"):
        word_was = status_message.split(":")[1]
        
        reply_text = (
            f"💔 **GAME OVER! 😭**\n"
            f"-------------------------------------\n"
            f"*Maximum guesses reached* (**{game_state['max_guesses']}**).\n\n"
            f"📜 **Final Board:**\n"
            f"{game_history_display}\n\n" 
            f"❌ *The secret word was:* **`{word_was}`**"
        )
        reply_markup = get_play_again_keyboard()

    else:
        # Ongoing game message (Show full history + status)
        
        reply_text = (
            f"**Word Rush Challenge** 🎯\n"
            f"-------------------------------------\n"
            f"Attempts: **`{len(guess_history)}`** / **`{game_state['max_guesses']}`**\n\n"
            f"📜 **Guess History:**\n"
            f"{game_history_display}\n\n" 
            f"👉 {status_message}" # Displays: Guesses left: **27**
        )
    
    await update.message.reply_text(
        reply_text, 
        reply_markup=reply_markup, 
        parse_mode='Markdown'
    )

# --- Main Bot Runner ---

def main():
    """Start the bot."""
    if not BOT_TOKEN:
        logger.error("FATAL ERROR: BOT_TOKEN not found. Please set it in the .env file.")
        return
    
    application = Application.builder().token(BOT_TOKEN).build()

    # Register Handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("new", new_game_command))
    application.add_handler(CommandHandler("end", end_game_command))
    application.add_handler(CommandHandler("leaderboard", leaderboard_command))
    application.add_handler(CommandHandler("difficulty", difficulty_command)) # FIXED: Now points to the defined function
    application.add_handler(CommandHandler("status", status_command)) 
    
    if ADMIN_USER_ID != 0 and mongo_manager is not None:
        application.add_handler(CommandHandler("broadcast", broadcast_command))
    
    application.add_handler(CommandHandler("help", start_command)) 

    # Callback query handler for inline buttons
    application.add_handler(CallbackQueryHandler(callback_handler))
    
    # Message handler for guesses:
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.Regex(r'^[a-zA-Z]{1,8}$'), 
            handle_guess
        )
    )

    logger.info("🚀 WordRush Bot is running (Advanced, Stylish, DM-Ready)...")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
