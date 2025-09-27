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
# ADMIN_USER_ID is crucial for the broadcast feature. Ensure it's set in .env
try:
    ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID")) 
except (TypeError, ValueError):
    ADMIN_USER_ID = 0 
    logger.warning("ADMIN_USER_ID not set or invalid in .env. Broadcast disabled.")

# --- Configuration ---
DIFFICULTY_CONFIG = {
    'easy': {'length': 4, 'max_guesses': 30, 'base_points': 5, 'example': 'GAME'},
    'medium': {'length': 5, 'max_guesses': 30, 'base_points': 10, 'example': 'APPLE'},
    'hard': {'length': 8, 'max_guesses': 30, 'base_points': 20, 'example': 'FOOTBALL'},
    'extreme': {'length': 10, 'max_guesses': 30, 'base_points': 50, 'example': 'BASKETBALL'}
}

# --- 500 Words List --- (Same as before, ensuring advanced words are present)
RAW_WORDS = [
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

# Process words by length
WORDS_BY_LENGTH: Dict[int, List[str]] = {}
for word in RAW_WORDS:
    cleaned_word = re.sub(r'[^A-Z]', '', word.upper())
    length = len(cleaned_word)
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
        self.chats_collection = self.db['known_chats'] 
        
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

    # --- Chat Tracking Methods (for Broadcast) ---
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
    """Calculates points based on difficulty and efficiency."""
    config = DIFFICULTY_CONFIG[difficulty]
    base = config['base_points']
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
        f"Guess the **{length}** letters word!"
    )

async def process_guess_logic(chat_id: int, guess: str) -> Tuple[str, bool, str, int, List[str]]:
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
        mongo_manager.delete_game_state(chat_id) 
        return feedback_str, True, f"🥳 **CONGRATS!** You won in {guesses} guesses! (+{points} points)", points, game['guess_history']

    # 4. Check for Loss
    remaining = game['max_guesses'] - game['guesses_made']
    
    mongo_manager.save_game_state(chat_id, game)
    
    if remaining <= 0:
        mongo_manager.delete_game_state(chat_id) 
        return feedback_str, False, f"💔 **Game Over!** The word was **{secret_word}**.", 0, game['guess_history']
    
    return feedback_str, False, f"Guesses left: **{remaining}**", 0, game['guess_history']

# --- Telegram UI & Handler Functions ---

async def is_group_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if update.effective_chat.type == ChatType.PRIVATE:
        return True
    try:
        member = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
        return member.status in ['administrator', 'creator']
    except Exception as e:
        logger.error(f"Error checking admin status: {e}")
        return False

# --- Inline Keyboard Builders (Matching Image UI) ---

def get_start_keyboard():
    """Returns the keyboard for the /start command (Image 2)."""
    keyboard = [
        [InlineKeyboardButton("Help Menu", callback_data="show_help_menu")], # Corresponds to Help Menu button in Image 2
        [
            InlineKeyboardButton("Play & Report", url="https://t.me/WordRushBot"), # Placeholder for actual link
            InlineKeyboardButton("Updates", url="https://t.me/astrabotz") # Placeholder for actual channel
        ],
        [InlineKeyboardButton("Add me to your chat", url="https://t.me/WordRushBot?startgroup=true")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_help_menu_keyboard():
    """Returns the keyboard for the Help Menu (Image 4)."""
    keyboard = [
        [InlineKeyboardButton("How to play", callback_data="show_how_to_play")],
        [InlineKeyboardButton("Commands 📚", callback_data="show_commands")],
        [InlineKeyboardButton("🔙 Back to start", callback_data="back_to_start")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_play_again_keyboard():
    """Returns a simple 'Play Again' button (Image 1)."""
    keyboard = [
        [InlineKeyboardButton("Play Again", callback_data="new_game_menu")] # Navigates to difficulty select
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

# --- Command Handlers ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends welcome message and main menu keyboard (Image 2)."""
    if mongo_manager and update.effective_message:
        mongo_manager.add_chat(update.effective_chat.id, update.effective_chat.type.name, update.effective_message.date.timestamp())
    
    await update.message.reply_text(
        "👋 Welcome back to **WordRushBot**,\n"
        "The ultimate word challenge — fun, fast, and competitive\n"
        "with leaderboard, only on Telegram!\n\n"
        "1. Use **/new** to start a game. Add me to a group with admin permission to play with your friends.\n"
        "Click in the Help Menu button below To get more information, How to play and about commands.",
        reply_markup=get_start_keyboard(),
        parse_mode='Markdown'
    )

async def new_game_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Starts a new game with an optional difficulty argument."""
    chat_id = update.effective_chat.id
    if mongo_manager and update.effective_message:
        mongo_manager.add_chat(chat_id, update.effective_chat.type.name, update.effective_message.date.timestamp())

    difficulty = context.args[0].lower() if context.args else 'medium'
    
    # Check if a game is already running
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
            message += f"{i+1}. **{name}** - {points} points ({wins} wins)\n"

    await update.message.reply_text(message, parse_mode='Markdown')

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
            # We use try/except specifically for API errors common in broadcast
            await context.bot.send_message(chat_id=chat_id, text=message_to_send, parse_mode='Markdown')
            success_count += 1
        except error.Forbidden:
            logger.warning(f"Failed to send broadcast to chat {chat_id}: Bot blocked.")
            fail_count += 1
        except Exception as e:
            logger.error(f"Failed to send broadcast to chat {chat_id}: {e}")
            fail_count += 1
            
    await update.message.reply_text(f"Broadcast complete.\nSuccessful: {success_count}\nFailed: {fail_count}")

# --- Callback Handler (UI Logic) ---

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles inline keyboard button presses."""
    query = update.callback_query
    await query.answer() 
    chat_id = query.message.chat_id
    
    if query.data == "back_to_start":
        await query.edit_message_text(
            "👋 Welcome back to **WordRushBot**,\n"
            "The ultimate word challenge — fun, fast, and competitive\n"
            "with leaderboard, only on Telegram!\n\n"
            "1. Use **/new** to start a game. Add me to a group with admin permission to play with your friends.\n"
            "Click in the Help Menu button below To get more information, How to play and about commands.",
            reply_markup=get_start_keyboard(),
            parse_mode='Markdown'
        )
    
    # Help Menu Navigation (Image 4)
    elif query.data == "show_help_menu":
        await query.edit_message_text(
            "WordRush's Help menu\n"
            "Choose the category you want to help with WordRush\n\n"
            "Any problem ask your doubt at [WordRush Play & Report](https://t.me/WordRushBot)", # Adjusted text
            reply_markup=get_help_menu_keyboard(),
            parse_mode='Markdown',
            disable_web_page_preview=True
        )

    # Show How To Play (Image 7)
    elif query.data == "show_how_to_play":
        commands_list = (
            "**❓ How to Play Word Rush**\n"
            "1. You have to guess a **secret word**.\n"
            f"  • Easy → {DIFFICULTY_CONFIG['easy']['length']}-letter word (example: {DIFFICULTY_CONFIG['easy']['example']})\n"
            f"  • Medium → {DIFFICULTY_CONFIG['medium']['length']}-letter word (example: {DIFFICULTY_CONFIG['medium']['example']})\n"
            f"  • Hard → {DIFFICULTY_CONFIG['hard']['length']}-letter word (example: {DIFFICULTY_CONFIG['hard']['example']})\n"
            f"  • Extreme → {DIFFICULTY_CONFIG['extreme']['length']}-letter word (example: {DIFFICULTY_CONFIG['extreme']['example']})\n\n"
            "2. After every guess, you will get hints:\n"
            "  • 🟢 **Green** = Correct letter in the right place.\n"
            "  • 🟡 **Yellow** = Correct letter but in the wrong place.\n"
            "  • 🔴 **Red** = Letter not in the word.\n\n"
            f"3. You can make up to **{DIFFICULTY_CONFIG['easy']['max_guesses']}** guesses.\n"
            "4. The first person who guesses the word correctly is the **winner 🏆**.\n"
            "5. Winners get points based on difficulty. More difficult = more points.\n"
            "6. All points are saved in the **Leaderboard**.\n"
            "Tip: Try to win with fewer guesses to earn more points!"
        )
        await query.edit_message_text(commands_list, reply_markup=get_help_menu_keyboard(), parse_mode='Markdown')

    # Show Commands (Image 10)
    elif query.data == "show_commands":
        commands_list = (
            "📖 **Word Rush Commands**\n"
            "• **/new** (or **/new easy|medium|hard|extreme**) → Start a new game. You can set difficulty while starting.\n"
            "• **/end** → End the current game (Group Admins only).\n"
            "• **/leaderboard** → Show the global and group leaderboard.\n"
            "• **/help** → Show the help menu."
        )
        await query.edit_message_text(commands_list, reply_markup=get_help_menu_keyboard(), parse_mode='Markdown')
    
    # Start Game Menu
    elif query.data == "new_game_menu":
        await query.edit_message_text(
            "Choose your difficulty for the new game:",
            reply_markup=get_new_game_keyboard(),
            parse_mode='Markdown'
        )
    
    # Difficulty Select Logic
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
        return

    guess = update.message.text.strip()
    
    # 1. Process guess
    feedback, is_win, status_message, points, guess_history = await process_guess_logic(chat_id, guess)

    # 2. Handle validation errors
    if "❌" in status_message:
        await update.message.reply_text(status_message, parse_mode='Markdown')
        return

    # 3. Construct the reply message with full history (Image 1 style)
    game_progress_display = "\n".join(guess_history)
    
    reply_text = (
        f"**Game started!** Difficulty set to **{mongo_manager.get_game_state(chat_id).get('difficulty', 'Unknown').capitalize()}**\n"
        f"Guess the **{len(guess)}** letters word!\n\n"
        f"{game_progress_display}\n\n" # Display all previous guesses + current
        f"{status_message}"
    )
    
    reply_markup = None
    parse_mode = 'Markdown'

    # 4. Handle Win/Loss
    if is_win or "Game Over" in status_message:
        reply_markup = get_play_again_keyboard()
        word_was = guess.upper() if is_win else mongo_manager.get_game_state(chat_id).get('word', 'UNKNOWN')
        
        if is_win:
            username = user.username or str(user.id)
            mongo_manager.update_leaderboard(user.id, username, points)
            
            # Match the exact success message format from Image 1
            reply_text = (
                f"Congratulations **{user.first_name}**!\n"
                f"You earned **{points} Points**\n\n"
                f"You guessed the correct word!\n"
                f"Word was **{word_was}**!"
            )
        else:
            # Loss message
            reply_text = (
                f"💔 **Game Over!**\n"
                f"The word was **{word_was}**.\n\n"
                f"Try again!"
            )

    await update.message.reply_text(
        reply_text, 
        reply_markup=reply_markup, 
        parse_mode=parse_mode
    )

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

    # Register Handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("new", new_game_command))
    application.add_handler(CommandHandler("end", end_game_command))
    application.add_handler(CommandHandler("leaderboard", leaderboard_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    
    # The /help command will be handled via the inline keyboard for a clean UI
    application.add_handler(CommandHandler("help", lambda u, c: start_command(u, c))) 

    # Callback query handler for inline buttons
    application.add_handler(CallbackQueryHandler(callback_handler))
    
    # Message handler for all text messages that aren't commands (i.e., guesses)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_guess))

    logger.info("Final Advanced MongoDB WordRush Bot is running...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
