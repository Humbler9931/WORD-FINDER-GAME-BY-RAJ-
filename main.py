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
    logger.warning("ADMIN_USER_ID not set or invalid in .env. Broadcast/Admin checks might fail.")

# --- Configuration ---
DIFFICULTY_CONFIG = {
    'easy': {'length': 4, 'max_guesses': 30, 'base_points': 5, 'example': 'GAME'},
    'medium': {'length': 5, 'max_guesses': 30, 'base_points': 10, 'example': 'APPLE'},
    'hard': {'length': 8, 'max_guesses': 30, 'base_points': 20, 'example': 'FOOTBALL'},
    'extreme': {'length': 10, 'max_guesses': 30, 'base_points': 50, 'example': 'BASKETBALL'}
}

# --- Word List and Pre-processing (Same as before, assumed to be valid) ---
RAW_WORDS = [
    "GAME", "FOUR", "FIRE", "WORD", "PLAY", "CODE", "RUNS", "STOP", "LOOK", "CALL", "BACK", "BEST", "FAST", "SLOW", "HIGH", "LOWS", 
    "OPEN", "CLOS", "READ", "WRIT", "BOOK", "PAGE", "LINE", "JUMP", "WALK", "TALK", "QUIZ", "TEST", "RAIN", "SNOW", "SUNY", "COLD", 
    "HEAT", "WIND", "MIST", "DUST", "ROCK", "SAND", "SOIL", "GRAS", "TREE", "LEAF", "ROOT", "STEM", "SEED", "GROW", "CROP", "FARM", 
    "CITY", "TOWN", "HOME", "ROOM", "DOOR", "WALL", "ROOF", "FLOR", "GIFT", "SEND", "TAKE", "GIVE", "HELP", "NEED", "WANT", "HAVE", 
    "FIND", "LOSE", "PUTS", "GETS", "MAKE", "DONE", "HITS", "MISS", "KICK", "PULL", "PUSH", "TURN", "STAR", "MOON", "PLAN", "MARS", 
    "EARH", "AIRS", "BOAT", "SHIP", "CARS", "BUSY", "TRAK", "RAIL", "ROAD", "MAPS", "HUES", "PINK", "BLUE", "GREN", "YELL", "BLAK", 
    "WHIT", "GRYY", "BRWN", "PURP", 
    "APPLE", "HEART", "WATER", "TABLE", "PLANT", "TIGER", "EAGLE", "SNAKE", "WHALE", "ZEBRA", "SOUND", "MUSIC", "RADIO", "VOICE", 
    "BEACH", "OCEAN", "RIVER", "LAKE", "FIELD", "CABLE", "WIRED", "PHONE", "EMAIL", "SCARY", "HAPPY", "FUNNY", "SADLY", "ANGER", 
    "BRAVE", "CHAIR", "BENCH", "CUPPY", "GLASS", "PLATE", "FORKS", "KNIFE", "SPOON", "SUGAR", "SALTZ", "BREAD", "CHEES", "MEATS", 
    "SALAD", "PIZZA", "PASTA", "RICEE", "GRAIN", "DRINK", "JUICE", "HORSE", "COWWS", "SHEEP", "GOATS", "DUCKS", "GEESE", "PIGGY", 
    "MOUZE", "RATSS", "FROGG", "CLOUD", "STORM", "LIGHT", "THUND", "SHELL", "CORAL", "ALGAE", "WEEDS", "BLADE", "POINT", "FENCE", 
    "GATES", "BARNS", "SHEDS", "TOOLS", "NAILS", "SCREW", "WOODZ", "STEEL", "METAL", "FLIES", "BUGSY", "WORMS", "BEESZ", "WASPS", 
    "ANTEE", "TERMS", "SPIDE", "MOTHS", "SQUIR", "BEARS", "DEERS", "ELKSS", "FOXES", "WOLFS", "LYNXS", "SHOES", "SOCKS", "GLOVE", 
    "HATTS", "COATS", "SKIRT", "PANTS", "DRESS", "SHIRT", "SWEAT", "MONEY", "WALET", "PURSE", "COINS", "BILLZ", "NOTES", "CHECK", 
    "BANKK", "LOANS", "DEBTS", "PAPER", "INKED", "PENCI", "ERASE", "RULER", "CRAFT", "GLUEE", "TAPEZ", "SCISS", "BOXES", "TRAIN", 
    "PLANE", "CYCLE", "SCOOT", "TRUCK", "VANCE", "JEEPZ", "MOTOP", "WAGON", "CARTT", "WINGS", "FEATH", "CLAWW", "TAILS", "MUZZL", 
    "TEETH", "HORNZ", "SKULL", "BONES", "SPINE", "GOLFF", "TENNI", "SOCCR", "CRICK", "RUGBY", "HOCKY", "BOXIN", "KARAT", "JUDOZ", 
    "SWIMM", "MOVIE", "ACTOR", "STAGE", "SCENE", "DRAMA", "COMIC", "NOVEL", "POEMS", "LYRIC", "SONGS", "EARLY", "LATER", "TODAY", 
    "YESTA", "TOMOR", "WEEKS", "MONTH", "YEARS", "AGING", "YOUNG", "STORY", "MYTHS", "LEGEND", "FOLKS", "TALES", "FABLE", "PICTS", 
    "PAINT", "SKETCH", "DRAWN", "FANCY", "SMART", "CLEAN", "DIRTY", "MESSY", "TIDYY", "BRISK", "QUICK", "SLOWW", "HUMID",
    "FOOTBALL", "COMPUTER", "KEYBOARD", "MEMORIZE", "INTERNET", "PROGRAMS", "SOFTWARE", "HARDWARE", "DATABASE", "ALGORISM", 
    "SECURITY", "PASSWORD", "TELEGRAM", "BUSINESS", "FINANCES", "MARKETIN", "ADVERTSZ", "STRATEGY", "MANUFACT", "PRODUCTS", 
    "SERVICES", "OPERATIO", "INNOVATE", "CREATIVE", "RESEARCH", "ANALYSES", "SOLUTION", "DEVELOPR", "ACADEMIC", "STUDENTS",
    "BASKETBALL", "CHALLENGEZ", "INCREDIBLE", "STRUCTURES", "GLOBALIZAT", "TECHNOLOGY", "INNOVATION", "INTELLIGEN", "CYBERSECUR", 
    "ARTIFICIAL", "MANAGEMENT", "LEADERSHIP", "MOTIVATION", "ORGANIZATI", "PRODUCTIVE", "EFFICIENCY", "SUSTAINABL", 
    "ENVIRONMENT", "CONSERVATN"
]

WORDS_BY_LENGTH: Dict[int, List[str]] = {}
for word in RAW_WORDS:
    cleaned_word = "".join(filter(str.isalpha, word.upper())) 
    length = len(cleaned_word)
    if length in [c['length'] for c in DIFFICULTY_CONFIG.values()]:
         WORDS_BY_LENGTH.setdefault(length, []).append(cleaned_word)
         
# --- MongoDB Manager Class (Unchanged) ---

class MongoDBManager:
    """Handles all interactions with MongoDB."""
    def __init__(self, mongo_url: str, db_name: str):
        if not mongo_url:
            raise ValueError("MONGO_URL not provided.")
        
        # Increase timeout to avoid connection issues on slow starts
        self.client = MongoClient(mongo_url, serverSelectionTimeoutMS=5000) 
        self.db = self.client[db_name]
        self.leaderboard_collection = self.db['leaderboard']
        self.games_collection = self.db['active_games']
        self.chats_collection = self.db['known_chats'] 
        
        self.leaderboard_collection.create_index("user_id", unique=True)
        self.games_collection.create_index("chat_id", unique=True)
        self.chats_collection.create_index("chat_id", unique=True)
        logger.info("MongoDB connection and indexing successful.")

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
        logger.error("MONGO_URL not set. Running without database features.")
except Exception as e:
    logger.error(f"FATAL: Could not connect to MongoDB. Error: {e}")
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
        if guess[i] == secret_word[i]:
            feedback[i] = '🟩'
            remaining_letters[guess[i]] -= 1

    # Second pass: Yellow (Correct letter, wrong position)
    for i in range(length):
        if feedback[i] == '🟥':
            letter = guess[i]
            if letter in remaining_letters and remaining_letters[letter] > 0:
                feedback[i] = '🟨'
                remaining_letters[letter] -= 1
    
    return "".join(feedback)

def calculate_points(difficulty: str, guesses: int) -> int:
    """Calculates points based on difficulty and efficiency."""
    config = DIFFICULTY_CONFIG[difficulty]
    base = config['base_points']
    # Award bonus for fewer guesses: (5 guesses or less = max bonus)
    bonus = max(0, 5 - (guesses - 1)) 
    return base + bonus

async def start_new_game_logic(chat_id: int, difficulty: str) -> Tuple[bool, str]:
    if not mongo_manager: return False, "Database Error. Cannot start game."
    
    difficulty = difficulty.lower()
    if difficulty not in DIFFICULTY_CONFIG:
        # Default to medium if invalid, but inform the user
        difficulty = 'medium'
        
    config = DIFFICULTY_CONFIG[difficulty]
    length = config['length']
    word_list = WORDS_BY_LENGTH.get(length)
    
    if not word_list:
        return False, f"Error: No words found for {difficulty} ({length} letters). Contact admin."
    
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
        f"**Game started!** Difficulty set to **{difficulty.capitalize()}**\n"
        f"Guess the **{length} letters word**!"
    )

async def process_guess_logic(chat_id: int, guess: str) -> Tuple[str, bool, str, int, List[str]]:
    """Processes a user's guess and returns feedback, win status, and points."""
    if not mongo_manager: return "", False, "Database Error.", 0, []

    game = mongo_manager.get_game_state(chat_id)
    if not game:
        return "", False, "No active game.", 0, []
    
    secret_word = game['word']
    guess = guess.strip().upper()
    guess_clean = "".join(filter(str.isalpha, guess))

    config = DIFFICULTY_CONFIG[game['difficulty']]
    length = config['length']
    
    # 1. Validation for length
    if len(guess_clean) != length:
        return "", False, f"❌ **{guess.upper()}** must be exactly **{length}** letters long.", 0, game.get('guess_history', [])
    
    # 2. Validation against word list (Crucial for the "not a valid word" message)
    if guess_clean not in WORDS_BY_LENGTH.get(length, []):
         return "", False, f"❌ **{guess_clean}** is not a valid word.", 0, game.get('guess_history', [])

    game['guesses_made'] += 1
    
    # 3. Generate Feedback and update history
    feedback_str = get_feedback(secret_word, guess_clean)
    game['guess_history'].append(f"{feedback_str} - {guess_clean}")
    
    # 4. Check for Win
    if guess_clean == secret_word:
        guesses = game['guesses_made']
        points = calculate_points(game['difficulty'], guesses)
        mongo_manager.delete_game_state(chat_id) 
        return feedback_str, True, "WIN", points, game['guess_history']

    # 5. Check for Loss
    remaining = game['max_guesses'] - game['guesses_made']
    mongo_manager.save_game_state(chat_id, game)
    
    if remaining <= 0:
        mongo_manager.delete_game_state(chat_id) 
        return feedback_str, False, "LOSS", 0, game['guess_history']
    
    return feedback_str, False, f"Guesses left: **{remaining}**", 0, game['guess_history']

# --- Telegram UI & Handler Functions ---

async def is_group_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Checks if the user is an admin or creator in a group, or is in a private chat."""
    if update.effective_chat.type == ChatType.PRIVATE:
        return True
    try:
        member = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
        return member.status in ['administrator', 'creator']
    except Exception:
        return False

# --- Inline Keyboard Builders (Unchanged, matches UI) ---

def get_start_keyboard():
    keyboard = [
        [InlineKeyboardButton("Help Menu", callback_data="show_help_menu")],
        [
            InlineKeyboardButton("Play & Report", url="https://t.me/teamrajweb"), 
            InlineKeyboardButton("Updates", url="https://t.me/narzob") 
        ],
        [InlineKeyboardButton("Add me to your chat", url="https://t.me/narzowordbot?startgroup=true")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_help_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("How to play", callback_data="show_how_to_play")],
        [InlineKeyboardButton("Commands 📚", callback_data="show_commands")],
        [InlineKeyboardButton("🔙 Back to start", callback_data="back_to_start")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_play_again_keyboard():
    keyboard = [
        [InlineKeyboardButton("Play Again", callback_data="new_game_menu")] 
    ]
    return InlineKeyboardMarkup(keyboard)

def get_new_game_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("Easy (4 letters)", callback_data="start_easy"),
            InlineKeyboardButton("Medium (5 letters)", callback_data="start_medium")
        ],
        [
            InlineKeyboardButton("Hard (8 letters)", callback_data="start_hard"),
            InlineKeyboardButton("Extreme (10 letters)", callback_data="start_extreme")
        ],
        [InlineKeyboardButton("🔙 Back to Start", callback_data="back_to_start")]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- Command Handlers (Unchanged) ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if mongo_manager and update.effective_message:
        mongo_manager.add_chat(update.effective_chat.id, update.effective_chat.type.name, update.effective_message.date.timestamp())
    
    await update.message.reply_text(
        "👋 Welcome back to ** @narzowordbot**,\n"
        "The ultimate word challenge — fun, fast, and competitive\n"
        "with leaderboard, only on Telegram!\n\n"
        "1. Use **/new** to start a game. Add me to a group with admin permission to play with your friends.\n"
        "Click in the Help Menu button below To get more information, How to play and about commands.\n\n"
        "**Telegram**\n"
        "**WordRush**\n"
        "Simple & Intresting Words\n"
        "Guess bot, Use **/new** to start game.\n"
        "Play & Report: **@narzob**\n"
        "Updates,: **@narzoxbot**",
        reply_markup=get_start_keyboard(),
        parse_mode='Markdown'
    )

async def new_game_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if mongo_manager and update.effective_message:
        mongo_manager.add_chat(chat_id, update.effective_chat.type.name, update.effective_message.date.timestamp())

    difficulty = context.args[0].lower() if context.args else 'medium'
    
    if mongo_manager and mongo_manager.get_game_state(chat_id):
        await update.message.reply_text("A game is already active. Use **/end** to stop it first (Admins only).")
        return

    success, message = await start_new_game_logic(chat_id, difficulty)
    await update.message.reply_text(message, parse_mode='Markdown')

async def end_game_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    
    if not mongo_manager or not mongo_manager.get_game_state(chat_id):
        await update.message.reply_text("No game is currently running to end.")
        return
        
    if not await is_group_admin(update, context):
        await update.message.reply_text("❌ You must be a **Group Admin** to end the game.", parse_mode='Markdown')
        return

    game_state = mongo_manager.get_game_state(chat_id)
    word = game_state.get('word', 'UNKNOWN')
    mongo_manager.delete_game_state(chat_id)
    
    await update.message.reply_text(
        f"Game ended by Admin. The secret word was **{word}**.", 
        parse_mode='Markdown'
    )

async def difficulty_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not context.args:
        available_diffs = '/'.join(DIFFICULTY_CONFIG.keys())
        await update.message.reply_text(
            f"Available difficulty: {available_diffs.upper()}\n\nValid usage\n`/difficulty easy`\nLike this!",
            parse_mode='Markdown'
        )
        return
        
    if not await is_group_admin(update, context):
        await update.message.reply_text("❌ You must be a **Group Admin** to change difficulty.", parse_mode='Markdown')
        return

    difficulty = context.args[0].lower()
    if difficulty not in DIFFICULTY_CONFIG:
        await update.message.reply_text(f"❌ Invalid difficulty. Choose from: {'/'.join(DIFFICULTY_CONFIG.keys())}.", parse_mode='Markdown')
        return
        
    if mongo_manager.get_game_state(chat_id):
        await update.message.reply_text("A game is currently active. Ending the old game and starting a new one...")
        mongo_manager.delete_game_state(chat_id)

    success, message = await start_new_game_logic(chat_id, difficulty)
    await update.message.reply_text(message, parse_mode='Markdown')


async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if mongo_manager and update.effective_message:
        mongo_manager.add_chat(update.effective_chat.id, update.effective_chat.type.name, update.effective_message.date.timestamp())
        
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
            message += f"**{i+1}.** {name} - **{points}** points ({wins} wins)\n"

    await update.message.reply_text(message, parse_mode='Markdown')

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a message to all known chats (Admin only)."""
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return

    if not context.args:
        await update.message.reply_text("Usage: `/broadcast <your message here>`", parse_mode='Markdown')
        return
    
    if not mongo_manager:
        await update.message.reply_text("Database error. Cannot retrieve chat list.")
        return

    message_to_send = " ".join(context.args)
    chat_ids = mongo_manager.get_all_chat_ids()
    
    success_count = 0
    fail_count = 0
    
    await update.message.reply_text(f"Attempting to broadcast message to {len(chat_ids)} chats...")

    for chat_id in chat_ids:
        try:
            await context.bot.send_message(chat_id=chat_id, text=message_to_send, parse_mode='Markdown')
            success_count += 1
        except error.Forbidden:
            logger.warning(f"Failed to send broadcast to chat {chat_id}: Bot blocked or user left.")
            fail_count += 1
        except Exception as e:
            logger.error(f"Failed to send broadcast to chat {chat_id}: {e}")
            fail_count += 1
            
    await update.message.reply_text(f"Broadcast complete.\nSuccessful: **{success_count}**\nFailed: **{fail_count}**", parse_mode='Markdown')

# --- Callback Handler (Unchanged) ---

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer() 
    chat_id = query.message.chat_id
    
    if query.data == "back_to_start":
        # ... (Start menu message content)
        await query.edit_message_text(
            "👋 Welcome back to **WordRushBot**,\n"
            "The ultimate word challenge — fun, fast, and competitive\n"
            "with leaderboard, only on Telegram!\n\n"
            "1. Use **/new** to start a game. Add me to a group with admin permission to play with your friends.\n"
            "Click in the Help Menu button below To get more information, How to play and about commands.\n\n"
            "**Telegram**\n"
            "**WordRush**\n"
            "Simple & Intresting Words\n"
            "Guess bot, Use **/new** to start game.\n"
            "Play & Report: **@astrabotz_chat**\n"
            "Updates,: **@astrabotz**",
            reply_markup=get_start_keyboard(),
            parse_mode='Markdown'
        )
    
    elif query.data == "show_help_menu":
        # ... (Help menu message content)
        await query.edit_message_text(
            "WordRush's Help menu\n"
            "Choose the category you want to help with WordRush\n\n"
            "Any problem ask your doubt at **WordRush Play & Report**",
            reply_markup=get_help_menu_keyboard(),
            parse_mode='Markdown'
        )

    elif query.data == "show_how_to_play":
        # ... (How to play content)
        commands_list = (
            "❓ **How to play Word Rush**\n"
            "1. You have to guess a secret word.\n"
            f"   • Easy → 4-letter word (example: {DIFFICULTY_CONFIG['easy']['example'].lower()})\n"
            f"   • Medium → 5-letter word (example: {DIFFICULTY_CONFIG['medium']['example'].lower()})\n"
            f"   • Hard → 8-letter word (example: {DIFFICULTY_CONFIG['hard']['example'].lower()})\n"
            f"   • Extreme → 10-letter word (example: {DIFFICULTY_CONFIG['extreme']['example'].lower()})\n\n"
            "2. After every guess, you will get hints:\n"
            "   • 🟢 **Green** = Correct letter in the right place.\n"
            "   • 🟡 **Yellow** = Correct letter but in the wrong place.\n"
            "   • 🔴 **Red** = Letter not in the word.\n\n"
            f"3. You can make up to 30 guesses. The game continues until someone finds the correct word.\n"
            "4. The first person who guesses the word correctly is the **winner** 🏆.\n"
            "5. Winners get points based on difficulty. More difficult = more points.\n"
            "6. All points are saved in the **Leaderboard**.\n"
            "Tip: Use the hints smartly and try to win with fewer guesses to earn more points!"
        )
        await query.edit_message_text(commands_list, reply_markup=get_help_menu_keyboard(), parse_mode='Markdown')

    elif query.data == "show_commands":
        # ... (Commands content)
        commands_list = (
            "📖 **Word Rush Commands**\n"
            "• **/new** (or **/new easy|medium|hard|extreme**) → Start a new game. You can set difficulty while starting.\n"
            "• **/end** → End the current game (**Group Admins only**).\n"
            "• **/difficulty** (easy|medium|hard|extreme) → Change difficulty for the current chat (**Group Admins only**).\n"
            "• **/leaderboard** → Show the global and group leaderboard.\n"
            "• **/help** → Show the help menu."
        )
        await query.edit_message_text(commands_list, reply_markup=get_help_menu_keyboard(), parse_mode='Markdown')
    
    elif query.data == "new_game_menu":
        await query.edit_message_text(
            "Choose your difficulty for the new game:",
            reply_markup=get_new_game_keyboard(),
            parse_mode='Markdown'
        )
    
    elif query.data.startswith("start_"):
        difficulty = query.data.split('_')[1]
        
        if mongo_manager and mongo_manager.get_game_state(chat_id):
            await query.edit_message_text("A game is already active. Use **/end** to stop it first (Admins only).")
            return

        success, message = await start_new_game_logic(chat_id, difficulty)
        if success:
            await query.edit_message_text(message, parse_mode='Markdown')
        else:
            await query.edit_message_text(f"Game start failed: {message}", parse_mode='Markdown')

# --- Guess Handler (Main Game Loop) ---

async def handle_guess(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user = update.effective_user
    
    if not mongo_manager or not mongo_manager.get_game_state(chat_id):
        # Ignore message if no game is running
        return

    guess = update.message.text.strip()
    
    # 1. Process guess
    # feedback: Last guess's color blocks (e.g., "🟩🟨🟥")
    # status_message: WIN/LOSS/Guesses left
    feedback, is_win, status_message, points, guess_history = await process_guess_logic(chat_id, guess)
    
    # 2. Handle validation errors (Clean message: "❌ NUMBE is not a valid word.")
    if status_message.startswith("❌"):
        await update.message.reply_text(status_message, parse_mode='Markdown')
        return

    # 3. Handle Win/Loss
    if status_message == "WIN":
        word_was = mongo_manager.get_game_state(chat_id)['word'] if mongo_manager.get_game_state(chat_id) else "UNKNOWN"
        username = user.username or user.first_name 
        
        # Update Leaderboard
        if mongo_manager:
            mongo_manager.update_leaderboard(user.id, username, points)
        
        reply_text = (
            f"Congratulations **{username}**!\n"
            f"You earned **{points} Points**\n\n"
            f"You guessed the correct word!\n"
            f"Word was **{word_was}**!"
        )
        reply_markup = get_play_again_keyboard()

    elif status_message == "LOSS":
        word_was = mongo_manager.get_game_state(chat_id)['word'] if mongo_manager.get_game_state(chat_id) else "UNKNOWN"
        reply_text = (
            f"💔 **Game Over!**\n"
            f"The word was **{word_was}**.\n\n"
            f"Try again!"
        )
        reply_markup = get_play_again_keyboard()

    else:
        # 4. Ongoing game message (The crucial fix: Only send the latest block line)
        
        # We only take the LATEST guess from the history.
        latest_guess_line = guess_history[-1] 
        
        reply_text = (
            f"{latest_guess_line}\n\n" # Example: 🟩🟨🟥 - HELLO
            f"{status_message}" # Example: Guesses left: **27**
        )
        reply_markup = None
    
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
    application.add_handler(CommandHandler("difficulty", difficulty_command))
    
    if ADMIN_USER_ID != 0 and mongo_manager is not None:
        application.add_handler(CommandHandler("broadcast", broadcast_command))
    
    application.add_handler(CommandHandler("help", start_command)) 

    # Callback query handler for inline buttons
    application.add_handler(CallbackQueryHandler(callback_handler))
    
    # Message handler for all text messages that aren't commands (i.e., guesses)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_guess))

    logger.info("Final Cleaned WordRush Bot is running...")
    
    # Run polling
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
