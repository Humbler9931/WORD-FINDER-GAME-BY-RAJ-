import os
import random
import re
import logging
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", 0)) # Convert to int

# --- Configuration ---
DIFFICULTY_CONFIG = {
    'easy': {'length': 4, 'max_guesses': 30, 'base_points': 5, 'example': 'GAME'},
    'medium': {'length': 5, 'max_guesses': 30, 'base_points': 10, 'example': 'APPLE'},
    'hard': {'length': 8, 'max_guesses': 30, 'base_points': 20, 'example': 'FOOTBALL'},
    'extreme': {'length': 10, 'max_guesses': 30, 'base_points': 50, 'example': 'BASKETBALL'}
}

# --- 500 Words List (For All Difficulty Levels) ---
RAW_WORDS = [
    # 4-letter words (100)
    "GAME", "FOUR", "FIRE", "WORD", "PLAY", "CODE", "RUNS", "STOP", "LOOK", "CALL",
    "BACK", "BEST", "FAST", "SLOW", "HIGH", "LOWS", "OPEN", "CLOS", "READ", "WRIT",
    "BOOK", "PAGE", "LINE", "JUMP", "WALK", "TALK", "QUIZ", "TEST", "RAIN", "SNOW",
    "SUNY", "COLD", "HEAT", "WIND", "MIST", "DUST", "ROCK", "SAND", "SOIL", "GRAS",
    "TREE", "LEAF", "ROOT", "STEM", "SEED", "GROW", "CROP", "FARM", "CITY", "TOWN",
    "HOME", "ROOM", "DOOR", "WALL", "ROOF", "FLOR", "GIFT", "SEND", "TAKE", "GIVE",
    "HELP", "NEED", "WANT", "HAVE", "FIND", "LOSE", "PUTS", "GETS", "MAKE", "DONE",
    "HITS", "MISS", "KICK", "PULL", "PUSH", "TURN", "STAR", "MOON", "PLAN", "MARS",
    "EARH", "AIRS", "BOAT", "SHIP", "CARS", "BUSY", "TRAK", "RAIL", "ROAD", "MAPS",
    "HUES", "PINK", "BLUE", "GREN", "YELL", "BLAK", "WHIT", "GRYY", "BRWN", "PURP",

    # 5-letter words (200)
    "APPLE", "HEART", "WATER", "TABLE", "PLANT", "TIGER", "EAGLE", "SNAKE", "WHALE", "ZEBRA",
    "SOUND", "MUSIC", "RADIO", "VOICE", "BEACH", "OCEAN", "RIVER", "LAKE", "PONDZ", "FIELD",
    "CABLE", "WIRED", "PHONE", "EMAIL", "SCARY", "HAPPY", "FUNNY", "SADLY", "ANGER", "BRAVE",
    "CHAIR", "BENCH", "CUPPY", "GLASS", "PLATE", "FORKS", "KNIFE", "SPOON", "SUGAR", "SALTZ",
    "BREAD", "CHEES", "MEATS", "SALAD", "PIZZA", "PASTA", "RICEE", "GRAIN", "DRINK", "JUICE",
    "HORSE", "COWWS", "SHEEP", "GOATS", "DUCKS", "GEESE", "PIGGY", "MOUZE", "RATSS", "FROGG",
    "CLOUD", "STORM", "LIGHT", "THUND", "SHELL", "CORAL", "ALGAE", "WEEDS", "BLADE", "POINT",
    "FENCE", "GATES", "BARNS", "SHEDS", "TOOLS", "NAILS", "SCREW", "WOODZ", "STEEL", "METAL",
    "FLIES", "BUGSY", "WORMS", "BEESZ", "WASPS", "ANTEE", "TERMS", "SPIDE", "MOTHS", "SQUIR",
    "BEARS", "DEERS", "ELKSS", "FOXES", "WOLFS", "LYNXS", "PUGGS", "TERRI", "BULLE", "POODL",
    "SHOES", "SOCKS", "GLOVE", "HATTS", "COATS", "SKIRT", "PANTS", "DRESS", "SHIRT", "SWEAT",
    "MONEY", "WALET", "PURSE", "COINS", "BILLZ", "NOTES", "CHECK", "BANKK", "LOANS", "DEBTS",
    "PAPER", "INKED", "PENCI", "ERASE", "RULER", "CRAFT", "GLUEE", "TAPEZ", "SCISS", "BOXES",
    "TRAIN", "PLANE", "CYCLE", "SCOOT", "TRUCK", "VANCE", "JEEPZ", "MOTOP", "WAGON", "CARTT",
    "WINGS", "FEATH", "CLAWW", "TAILS", "MUZZL", "TEETH", "HORNZ", "SKULL", "BONES", "SPINE",
    "GOLFF", "TENNI", "SOCCR", "CRICK", "RUGBY", "HOCKY", "BOXIN", "KARAT", "JUDOZ", "SWIMM",
    "MOVIE", "ACTOR", "STAGE", "SCENE", "DRAMA", "COMIC", "NOVEL", "POEMS", "LYRIC", "SONGS",
    "EARLY", "LATER", "TODAY", "YESTA", "TOMOR", "WEEKS", "MONTH", "YEARS", "AGING", "YOUNG",
    "STORY", "MYTHS", "LEGEND", "FOLKS", "TALES", "FABLE", "PICTS", "PAINT", "SKETCH", "DRAWN",
    "FANCY", "SMART", "CLEAN", "DIRTY", "MESSY", "TIDYY", "BRISK", "QUICK", "SLOWW", "HUMID",

    # 8-letter words (100)
    "FOOTBALL", "COMPUTER", "KEYBOARD", "MEMORIZE", "INTERNET", "PROGRAMS", "SOFTWARE", "HARDWARE", "DATABASE", "ALGORISM",
    "SECURITY", "PASSWORD", "TELEGRAM", "WEBSITEZ", "APPLICAN", "BUSINESS", "FINANCES", "MARKETIN", "ADVERTSZ", "STRATEGY",
    "MANUFACT", "PRODUCTS", "SERVICES", "OPERATIO", "INNOVATE", "CREATIVE", "RESEARCH", "ANALYSES", "SOLUTION", "DEVELOPR",
    "ACADEMIC", "STUDENTS", "TEACHERS", "COLLEGEZ", "UNIVERST", "EDUCATION", "LEARNING", "KNOWLEDGE", "HISTORYS", "SCIENTIS",
    "MEDICINE", "HOSPITAL", "SURGERYZ", "DOCTORSZ", "PATIENTS", "DIAGNOSZ", "THERAPYY", "VACCINEZ", "HEALTHY", "FITNESSS",
    "COMMUNIT", "NATIONAL", "GOVERNM", "POLITICS", "ELECTION", "DEMOCRAY", "JUSTICEZ", "SECURITY", "MILITARY", "DIPLOMAT",
    "ADVENTUR", "EXPLORER", "MOUNTAIN", "FORESTSS", "JUNGLEZ", "DESERTSS", "VOLCANOZ", "CLIMBING", "SAILINGZ", "JOURNEYS",
    "RELATION", "FRIENDLY", "FAMILIES", "MARRIAGE", "PARENTSS", "CHILDREN", "TRUSTED", "SUPPORTT", "EMOTIONZ", "HAPPINES",
    "ARCHITEC", "BUILDING", "SKYSCRAP", "PROPERTY", "DESIGNER", "CONSTRUC", "ENGINEER", "ELECTRIC", "PLUMBING", "PAINTING",
    "CELEBRAT", "FESTIVAL", "HOLIDAYZ", "BIRTHDAY", "WEDDINGZ", "PARTYING", "GATHERIN", "SPEECHZZ", "APPLAUSE", "PERFORMS",

    # 10-letter words (100)
    "BASKETBALL", "CHALLENGEZ", "INCREDIBLE", "STRUCTURES", "GLOBALIZAT", "TECHNOLOGY", "INNOVATION", "INTELLIGEN", "CYBERSECUR", "ARTIFICIAL",
    "MANAGEMENT", "LEADERSHIP", "MOTIVATION", "ORGANIZATI", "PRODUCTIVE", "EFFICIENCY", "SUSTAINABL", "ENVIRONMENT", "CONSERVATN", "RENEWABLES",
    "LITERATURE", "PHILOSOPHY", "PSYCHOLOGY", "SOCIOLOGYZ", "ANTHROPOLY", "LINGUISTIC", "GEOGRAPHYY", "ASTRONOMYZ", "MATHEMATCS", "STATISTICS",
    "BIOLOGICAL", "CHEMICALRY", "PHYSICALLY", "EXPERIMENT", "LABORATORY", "GENETICSZ", "EVOLUTIONN", "MICROBIOLG", "ECOLOGICAL", "GEOLOGICAL",
    "HOSPITALIT", "RESTAURANT", "CATERINGZ", "HOTELINGG", "TOURISMMS", "TRAVELINGS", "VACATIONSS", "DESTINATNZ", "EXPLORINGG", "LANDSCAPES",
    "ENTERTAINM", "TELEVISION", "BROADCASTG", "PUBLISHING", "JOURNALISM", "PHOTOGRAPH", "VIDEOGRAPH", "ANIMATIONS", "MULTIMEDIZ", "INTERACTVE",
    "COMMUNICAT", "NEGOTIATI", "COOPERATIO", "PARTNERSHP", "COLLABORAT", "AGREEMENTS", "CONTRACTSZ", "REGULATION", "LEGISLATIV", "COMPLIANCE",
    "DEMONSTRAT", "PROTESTING", "ACTIVISMS", "REVOLUTION", "MOVEMENTZ", "EQUALITYY", "FREEDOMMS", "JUSTIFYING", "CIVILRIGHT", "RESPONSIBL",
    "APPRECIATE", "UNDERSTAND", "COMPASSION", "GRATITUDEZ", "FORGIVENES", "PATIENCEZZ", "RESILIENCE", "PERSEVERAN", "DETERMINED", "ACHIEVEMEN",
    "DIFFERENCE", "SIMILARITY", "COMPARISON", "EVALUATING", "ASSESSMENT", "MEASUREMEN", "QUANTIFYES", "VERIFYINGG", "CONFIRMING", "VALIDATING"
]

# Process words by length (Ensure all words are uppercase and contain only letters)
WORDS_BY_LENGTH: Dict[int, List[str]] = {}
for word in RAW_WORDS:
    cleaned_word = re.sub(r'[^A-Z]', '', word.upper())
    length = len(cleaned_word)
    # Only include words whose length is defined in DIFFICULTY_CONFIG
    if length in [c['length'] for c in DIFFICULTY_CONFIG.values()]:
         WORDS_BY_LENGTH.setdefault(length, []).append(cleaned_word)
         
# --- MongoDB Manager Class ---

class MongoDBManager:
    """Handles all interactions with MongoDB for game state, leaderboard, and chat tracking."""
    def __init__(self, mongo_url: str, db_name: str):
        if not mongo_url:
            raise ValueError("MONGO_URL not provided.")
        
        self.client = MongoClient(mongo_url)
        self.db = self.client[db_name]
        self.leaderboard_collection = self.db['leaderboard']
        self.games_collection = self.db['active_games']
        self.chats_collection = self.db['known_chats'] # To track all chats for broadcast
        
        # Ensure indexes for fast lookups
        self.leaderboard_collection.create_index("user_id", unique=True)
        self.games_collection.create_index("chat_id", unique=True)
        self.chats_collection.create_index("chat_id", unique=True)
        logger.info("MongoDB connection and indexing successful.")

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
        """Retrieves the active game state for a chat."""
        return self.games_collection.find_one({'chat_id': chat_id})

    def save_game_state(self, chat_id: int, state: Dict):
        """Saves or updates the active game state for a chat."""
        state_to_save = {'chat_id': chat_id, **state}
        self.games_collection.replace_one(
            {'chat_id': chat_id}, 
            state_to_save, 
            upsert=True
        )

    def delete_game_state(self, chat_id: int):
        """Removes the active game state."""
        self.games_collection.delete_one({'chat_id': chat_id})

    # --- Chat Tracking Methods (for Broadcast) ---
    def add_chat(self, chat_id: int, chat_type: str):
        """Adds a chat to the known chats list."""
        self.chats_collection.update_one(
            {'chat_id': chat_id},
            {'$set': {'chat_type': chat_type, 'last_active': Update.effective_message.date.timestamp()}},
            upsert=True
        )

    def get_all_chat_ids(self) -> List[int]:
        """Retrieves all tracked chat IDs."""
        return [doc['chat_id'] for doc in self.chats_collection.find({}, {'chat_id': 1})]

# --- Initialize MongoDB Manager ---
mongo_manager = None
try:
    mongo_manager = MongoDBManager(MONGO_URL, MONGO_DB_NAME)
except Exception as e:
    logger.error(f"FATAL: Could not connect to MongoDB. Check MONGO_URL. Error: {e}")

# --- Core Game Logic Functions ---

def get_feedback(secret_word: str, guess: str) -> str:
    """Generates the Wordle-style color-coded feedback (🟩, 🟨, 🟥)."""
    length = len(secret_word)
    feedback = ['🟥'] * length 
    remaining_letters = {}
    for letter in secret_word:
        remaining_letters[letter] = remaining_letters.get(letter, 0) + 1

    # 1. Green Pass (Correct letter, correct position)
    for i in range(length):
        if guess[i] == secret_word[i]:
            feedback[i] = '🟩'
            remaining_letters[guess[i]] -= 1

    # 2. Yellow Pass (Correct letter, wrong position)
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
    # Bonus points for guessing quickly
    bonus = max(0, 5 - (guesses - 1) // 6) 
    return base + bonus

async def start_new_game_logic(chat_id: int, difficulty: str) -> Tuple[bool, str]:
    if not mongo_manager: return False, "Database Error. Cannot start game."
    
    difficulty = difficulty.lower()
    if difficulty not in DIFFICULTY_CONFIG:
        return False, f"❌ Invalid difficulty. Choose from: {'/'.join(DIFFICULTY_CONFIG.keys())}."

    config = DIFFICULTY_CONFIG[difficulty]
    length = config['length']
    word_list = WORDS_BY_LENGTH.get(length)
    
    if not word_list:
        return False, f"Error: No words found for {difficulty} ({length} letters). Contact admin."
    
    secret_word = random.choice(word_list)
    
    # Save initial game state to MongoDB, including a list for guesses
    initial_state = {
        'word': secret_word,
        'difficulty': difficulty,
        'guesses_made': 0,
        'max_guesses': config['max_guesses'],
        'guess_history': [] # To store past guesses and their feedback
    }
    mongo_manager.save_game_state(chat_id, initial_state)
    
    return True, (
        f"**Game started!** Difficulty: **{difficulty.capitalize()}** ({length} letters).\n"
        f"You have **{config['max_guesses']}** attempts. Guess the word!"
    )

async def process_guess_logic(chat_id: int, guess: str) -> Tuple[str, bool, str, int, List[str]]:
    """
    Processes a guess. Returns (feedback, is_win, status_message, points, updated_guess_history).
    """
    if not mongo_manager: return "", False, "Database Error.", 0, []

    game = mongo_manager.get_game_state(chat_id)
    if not game:
        return "", False, "No active game.", 0, []
    
    secret_word = game['word']
    guess = guess.strip().upper()
    config = DIFFICULTY_CONFIG[game['difficulty']]
    length = config['length']
    
    # 1. Validation
    if len(guess) != length:
        return "", False, f"❌ The guess must be exactly **{length}** letters long.", 0, game.get('guess_history', [])
    if guess not in WORDS_BY_LENGTH.get(length, []):
         return "", False, f"❌ **{guess}** is not a valid word.", 0, game.get('guess_history', [])

    game['guesses_made'] += 1
    
    # 2. Generate Feedback and update history
    feedback_str = get_feedback(secret_word, guess)
    game['guess_history'].append(f"{feedback_str} - {guess}")
    
    # 3. Check for Win
    if guess == secret_word:
        guesses = game['guesses_made']
        points = calculate_points(game['difficulty'], guesses)
        mongo_manager.delete_game_state(chat_id) # Game ends, delete state
        return feedback_str, True, f"🥳 **CONGRATS!** You won in {guesses} guesses! (+{points} points)", points, game['guess_history']

    # 4. Check for Loss
    remaining = game['max_guesses'] - game['guesses_made']
    
    # Save updated state (including new guess history)
    mongo_manager.save_game_state(chat_id, game)
    
    if remaining <= 0:
        mongo_manager.delete_game_state(chat_id) # Game ends, delete state
        return feedback_str, False, f"💔 **Game Over!** The word was **{secret_word}**.", 0, game['guess_history']
    
    return feedback_str, False, f"Guesses left: **{remaining}**", 0, game['guess_history']

# --- Telegram UI & Handler Functions ---

async def is_group_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Checks if the user is a group admin or if it's a private chat."""
    if update.effective_chat.type == ChatType.PRIVATE:
        return True
    try:
        member = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
        return member.status in ['administrator', 'creator']
    except Exception as e:
        logger.error(f"Error checking admin status: {e}")
        return False # Default to false on error

def get_start_keyboard():
    """Returns the keyboard for the /start command."""
    keyboard = [
        [InlineKeyboardButton("🎮 Start New Game", callback_data="new_game_menu")],
        [InlineKeyboardButton("❓ How to Play", callback_data="show_help")],
        [InlineKeyboardButton("📊 Leaderboard", callback_data="show_leaderboard")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_new_game_keyboard():
    """Returns the keyboard for choosing difficulty."""
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

def get_help_keyboard():
    """Returns the keyboard for the /help command menu."""
    keyboard = [
        [InlineKeyboardButton("🔙 Back to Start", callback_data="back_to_start")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_play_again_keyboard():
    """Returns a simple 'Play Again' button."""
    keyboard = [
        [InlineKeyboardButton("▶️ Play Again", callback_data="new_game_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends welcome message and main menu keyboard."""
    if mongo_manager:
        mongo_manager.add_chat(update.effective_chat.id, update.effective_chat.type)
    
    await update.message.reply_text(
        "👋 Welcome back to **WordRushBot**,\n"
        "The ultimate word challenge — fun, fast, and competitive\n"
        "with leaderboard, only on Telegram!",
        reply_markup=get_start_keyboard(),
        parse_mode='Markdown'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays the help menu and commands."""
    commands_list = (
        "**❓ How to Play Word Rush**\n"
        "You have to guess a secret word.\n\n"
        f"1. **Easy**: {DIFFICULTY_CONFIG['easy']['length']} letters (e.g., {DIFFICULTY_CONFIG['easy']['example']})\n"
        f"2. **Medium**: {DIFFICULTY_CONFIG['medium']['length']} letters (e.g., {DIFFICULTY_CONFIG['medium']['example']})\n"
        f"3. **Hard**: {DIFFICULTY_CONFIG['hard']['length']} letters (e.g., {DIFFICULTY_CONFIG['hard']['example']})\n"
        f"4. **Extreme**: {DIFFICULTY_CONFIG['extreme']['length']} letters (e.g., {DIFFICULTY_CONFIG['extreme']['example']})\n\n"
        "After every guess, you will get hints:\n"
        "🟢 **Green** = Correct letter in the right place.\n"
        "🟡 **Yellow** = Correct letter but in the wrong place.\n"
        "🔴 **Red** = Letter not in the word.\n\n"
        f"You can make up to {DIFFICULTY_CONFIG['easy']['max_guesses']} guesses. The game continues until someone finds the correct word.\n"
        "The first person who guesses the word correctly is the winner 🏆.\n"
        "Winners get points based on difficulty. More difficult = more points.\n"
        "All points are saved in the Leaderboard.\n"
        "Tip: Use the hints smartly and try to win with fewer guesses to earn more points!"
    )
    # Using reply_text here for consistent behavior with image, but a separate help_menu would normally use edit_message_text
    await update.message.reply_text(commands_list, reply_markup=get_help_keyboard(), parse_mode='Markdown')

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles inline keyboard button presses."""
    query = update.callback_query
    await query.answer() # Acknowledge the callback query
    chat_id = query.message.chat_id
    user_id = query.from_user.id
    
    if query.data == "back_to_start":
        await query.edit_message_text(
            "👋 Welcome back to **WordRushBot**,\n"
            "The ultimate word challenge — fun, fast, and competitive\n"
            "with leaderboard, only on Telegram!",
            reply_markup=get_start_keyboard(),
            parse_mode='Markdown'
        )
    elif query.data == "new_game_menu":
        await query.edit_message_text(
            "Choose your difficulty for the new game:",
            reply_markup=get_new_game_keyboard(),
            parse_mode='Markdown'
        )
    elif query.data.startswith("start_"):
        difficulty = query.data.split('_')[1]
        
        # Check if a game is already running
        if mongo_manager and mongo_manager.get_game_state(chat_id):
            await query.edit_message_text("A game is already active. Use **/end** to stop it first (Admins only).")
            return

        success, message = await start_new_game_logic(chat_id, difficulty)
        if success:
            await query.edit_message_text(message, parse_mode='Markdown')
        else:
            await query.edit_message_text(f"Game start failed: {message}", parse_mode='Markdown')
    elif query.data == "show_help":
        await query.edit_message_text(
            "**❓ How to Play Word Rush**\n"
            "You have to guess a secret word.\n\n"
            f"1. **Easy**: {DIFFICULTY_CONFIG['easy']['length']} letters (e.g., {DIFFICULTY_CONFIG['easy']['example']})\n"
            f"2. **Medium**: {DIFFICULTY_CONFIG['medium']['length']} letters (e.g., {DIFFICULTY_CONFIG['medium']['example']})\n"
            f"3. **Hard**: {DIFFICULTY_CONFIG['hard']['length']} letters (e.g., {DIFFICULTY_CONFIG['hard']['example']})\n"
            f"4. **Extreme**: {DIFFICULTY_CONFIG['extreme']['length']} letters (e.g., {DIFFICULTY_CONFIG['extreme']['example']})\n\n"
            "After every guess, you will get hints:\n"
            "🟢 **Green** = Correct letter in the right place.\n"
            "🟡 **Yellow** = Correct letter but in the wrong place.\n"
            "🔴 **Red** = Letter not in the word.\n\n"
            f"You can make up to {DIFFICULTY_CONFIG['easy']['max_guesses']} guesses. The game continues until someone finds the correct word.\n"
            "The first person who guesses the word correctly is the winner 🏆.\n"
            "Winners get points based on difficulty. More difficult = more points.\n"
            "All points are saved in the Leaderboard.\n"
            "Tip: Use the hints smartly and try to win with fewer guesses to earn more points!",
            reply_markup=get_help_keyboard(),
            parse_mode='Markdown'
        )
    elif query.data == "show_leaderboard":
        if not mongo_manager:
            await query.edit_message_text("Database Error. Cannot fetch leaderboard.")
            return

        data = mongo_manager.get_leaderboard_data(limit=10)
        
        if not data:
            message = "🏆 **Global Leaderboard**\n\nNo scores recorded yet. Start a game!"
        else:
            message = "🏆 **Global Leaderboard** (Top 10)\n\n"
            for i, (username, points, wins) in enumerate(data):
                name = f"User #{i+1}" if not username else f"@{username}"
                message += f"{i+1}. **{name}** - {points} points ({wins} wins)\n"
        
        await query.edit_message_text(message, reply_markup=get_help_keyboard(), parse_mode='Markdown')


async def new_game_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Starts a new game or shows difficulty menu."""
    chat_id = update.effective_chat.id
    
    if mongo_manager:
        mongo_manager.add_chat(update.effective_chat.id, update.effective_chat.type)

    if context.args:
        # If difficulty is provided directly, try to start game
        difficulty = context.args[0].lower()
        
        if mongo_manager and mongo_manager.get_game_state(chat_id):
            await update.message.reply_text("A game is already active. Use **/end** to stop it first (Admins only).")
            return

        success, message = await start_new_game_logic(chat_id, difficulty)
        await update.message.reply_text(message, parse_mode='Markdown')
    else:
        # If no difficulty, show menu
        await update.message.reply_text(
            "Choose your difficulty for the new game:",
            reply_markup=get_new_game_keyboard(),
            parse_mode='Markdown'
        )

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

async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if mongo_manager:
        mongo_manager.add_chat(update.effective_chat.id, update.effective_chat.type)

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
    
    if not mongo_manager or not mongo_manager.get_game_state(chat_id):
        return

    guess = update.message.text.strip()
    
    feedback, is_win, status_message, points, guess_history = await process_guess_logic(chat_id, guess)

    if "❌" in status_message:
        await update.message.reply_text(status_message, parse_mode='Markdown')
        return

    # Construct the reply message with full history
    game_progress_display = "\n".join(guess_history)
    
    reply_text = (
        f"{game_progress_display}\n\n" # Display all previous guesses + current
        f"{status_message}"
    )
    
    reply_markup = None
    if is_win or "Game Over" in status_message:
        reply_markup = get_play_again_keyboard()
        if is_win:
            username = user.username or str(user.id)
            mongo_manager.update_leaderboard(user.id, username, points)
            reply_text = (
                f"**Congratulations {user.mention_html()}!**\n"
                f"You earned **{points} Points**!\n"
                f"You guessed the correct word! Word was **{guess.upper()}**!\n\n"
                "**Game Over.**"
            )

    await update.message.reply_text(
        reply_text, 
        reply_markup=reply_markup, 
        parse_mode='HTML' if is_win else 'Markdown' # HTML for mention_html
    )

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a message to all known chats (Admin only)."""
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return

    if not context.args:
        await update.message.reply_text("Usage: `/broadcast <your message here>`", parse_mode='Markdown')
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
        except Exception as e:
            logger.warning(f"Failed to send broadcast to chat {chat_id}: {e}")
            fail_count += 1
            
    await update.message.reply_text(f"Broadcast complete.\nSuccessful: {success_count}\nFailed: {fail_count}")


# --- Main Bot Runner ---

def main():
    """Start the bot."""
    if not BOT_TOKEN:
        logger.error("FATAL ERROR: BOT_TOKEN not found. Please set it in the .env file.")
        return
    
    if not mongo_manager:
        logger.error("FATAL ERROR: MongoDB connection failed. Exiting.")
        return

    application = Application.builder().token(BOT_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("new", new_game_command))
    application.add_handler(CommandHandler("end", end_game_command))
    application.add_handler(CommandHandler("leaderboard", leaderboard_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command)) # Admin command

    # Callback query handler for inline buttons
    application.add_handler(CallbackQueryHandler(callback_handler))
    
    # Message handler for all text messages that aren't commands (i.e., guesses)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_guess))

    logger.info("Advanced MongoDB WordRush Bot is running...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
