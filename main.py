import os
import random
import re
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

# --- 500 Words List (Categorized by Length) ---
# NOTE: This is a placeholder list containing exactly 500 words for demonstration.
RAW_WORDS = [
    # 4-letter words (100 words for EASY)
    "GAME", "FOUR", "FIRE", "WORD", "PLAY", "CODE", "RUNS", "STOP", "LOOK", "CALL",
    "BACK", "BEST", "FAST", "SLOW", "HIGH", "LOWS", "OPEN", "CLOS", "READ", "WRITE",
    "BOOK", "PAGE", "LINE", "JUMP", "WALK", "TALK", "QUIZ", "TEST", "RAIN", "SNOW",
    "SUNY", "COLD", "HEAT", "WIND", "MIST", "DUST", "ROCK", "SAND", "SOIL", "GRAS",
    "TREE", "LEAF", "ROOT", "STEM", "SEED", "GROW", "CROP", "FARM", "CITY", "TOWN",
    "HOME", "ROOM", "DOOR", "WALL", "ROOF", "FLOOR", "GIFT", "SEND", "TAKE", "GIVE",
    "HELP", "NEED", "WANT", "HAVE", "FIND", "LOSE", "PUTS", "GETS", "MAKE", "DONE",
    "HITS", "MISS", "KICK", "PULL", "PUSH", "TURN", "STAR", "MOON", "PLAN", "MARS",
    "EARH", "AIRS", "BOAT", "SHIP", "CARZ", "BUSY", "TRAK", "RAIL", "ROAD", "MAPS",
    "HUES", "PINK", "BLUE", "GREN", "YELL", "BLAK", "WHIT", "GRYY", "BRWN", "PURP",

    # 5-letter words (200 words for MEDIUM)
    "APPLE", "HEART", "WATER", "TABLE", "PLANT", "TIGER", "EAGLE", "SNAKE", "WHALE", "ZEBRA",
    "SOUND", "MUSIC", "RADIO", "VOICE", "BEACH", "OCEAN", "RIVER", "LAKE", "POND", "FIELD",
    "CABLE", "WIRED", "PHONE", "EMAIL", "SCARY", "HAPPY", "FUNNY", "SADLY", "ANGER", "BRAVE",
    "CHAIR", "BENCH", "CUPPY", "GLASS", "PLATE", "FORKS", "KNIFE", "SPOON", "SUGAR", "SALTZ",
    "BREAD", "CHEES", "MEATS", "SALAD", "PIZZA", "PASTA", "RICEE", "GRAIN", "DRINK", "JUICE",
    "HORSE", "COWWS", "SHEEP", "GOATS", "DUCKS", "GEESE", "PIGGY", "MOUZE", "RATSS", "FROGG",
    "CLOUD", "STORM", "LIGHT", "THUND", "SHELL", "CORAL", "ALGAE", "WEEDS", "BLADE", "POINT",
    "FENCE", "GATES", "BARNS", "SHEDS", "TOOLS", "NAILS", "SCREW", "WOODZ", "STEEL", "METAL",
    "FLIES", "BUGSY", "WORMS", "BEESZ", "WASPS", "ANTEE", "TERMS", "SPIDE", "MOTHS", "SQUIR",
    "BEARS", "DEERS", "ELKSS", "FOXES", "WOLFS", "LYNXS", "PUGGS", "TERRI", "BULLE", "POODL",
    "SHOES", "SOCKS", "GLOVE", "HATTS", "COATS", "SKIRT", "PANTS", "DRESS", "SHIRT", "SWEAT",
    "MONEY", "WALLET", "PURSE", "COINS", "BILLZ", "NOTES", "CHECK", "BANKK", "LOANS", "DEBTS",
    "PAPER", "INKED", "PENCI", "ERASE", "RULER", "CRAFT", "GLUEE", "TAPEZ", "SCISS", "BOXES",
    "TRAIN", "PLANE", "CYCLE", "SCOOT", "TRUCK", "VANCE", "JEEPZ", "MOTOP", "WAGON", "CARTT",
    "WINGS", "FEATH", "CLAWW", "TAILS", "MUZZL", "TEETH", "HORNZ", "SKULL", "BONES", "SPINE",
    "GOLFF", "TENNI", "SOCCR", "CRICK", "RUGBY", "HOCKY", "BOXIN", "KARAT", "JUDOZ", "SWIMM",
    "MOVIE", "ACTOR", "STAGE", "SCENE", "DRAMA", "COMIC", "NOVEL", "POEMS", "LYRIC", "SONGS",
    "EARLY", "LATER", "TODAY", "YESTA", "TOMOR", "WEEKS", "MONTH", "YEARS", "AGING", "YOUNG",
    "STORY", "MYTHS", "LEGEND", "FOLKS", "TALES", "FABLE", "PICTS", "PAINT", "SKETCH", "DRAWN",
    "FANCY", "SMART", "CLEAN", "DIRTY", "MESSY", "TIDYY", "BRISK", "QUICK", "SLOWW", "HUMID",

    # 8-letter words (100 words for HARD)
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

    # 10-letter words (100 words for EXTREME)
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
    if length in DIFFICULTY_CONFIG.keys():
         WORDS_BY_LENGTH.setdefault(length, []).append(cleaned_word)

# --- MongoDB Manager Class ---

class MongoDBManager:
    def __init__(self, mongo_url: str, db_name: str):
        if not mongo_url:
            raise ValueError("MONGO_URL not provided in .env")
        
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
        state_to_save = {'chat_id': chat_id, **state}
        self.games_collection.replace_one(
            {'chat_id': chat_id}, 
            state_to_save, 
            upsert=True
        )

    def delete_game_state(self, chat_id: int):
        self.games_collection.delete_one({'chat_id': chat_id})

# --- Initialize MongoDB Manager ---
try:
    mongo_manager = MongoDBManager(MONGO_URL, MONGO_DB_NAME)
except Exception as e:
    print(f"FATAL: Could not connect to MongoDB. Check MONGO_URL. Error: {e}")
    mongo_manager = None 

# --- Core Game Logic Functions ---

def get_feedback(secret_word: str, guess: str) -> str:
    """Generates the Wordle-style color-coded feedback."""
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
    # Bonus points for guessing quickly (less penalty for more guesses)
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
        return False, f"Error: No words found for {difficulty} ({length} letters). Please contact admin."
    
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
        f"**Game started!** Difficulty: **{difficulty.capitalize()}** ({length} letters).\n"
        f"You have **{config['max_guesses']}** attempts. Guess the word!"
    )

async def process_guess(chat_id: int, guess: str) -> Tuple[str, bool, str, int]:
    if not mongo_manager: return "", False, "Database Error.", 0

    game = mongo_manager.get_game_state(chat_id)
    if not game:
        return "", False, "No active game.", 0
    
    secret_word = game['word']
    guess = guess.strip().upper()
    config = DIFFICULTY_CONFIG[game['difficulty']]
    length = config['length']
    
    # 1. Validation
    if len(guess) != length:
        return "", False, f"❌ The guess must be exactly **{length}** letters long.", 0
    if guess not in WORDS_BY_LENGTH.get(length, []):
         # A real bot should check a separate, larger list of *valid guesses*
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
    
    # Save updated state
    mongo_manager.save_game_state(chat_id, game)
    
    if remaining <= 0:
        mongo_manager.delete_game_state(chat_id)
        return feedback_str, False, f"💔 **Game Over!** The word was **{secret_word}**.", 0
    
    return feedback_str, False, f"Guesses left: **{remaining}**", 0

# --- Telegram Handlers ---

async def is_group_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Checks if the user is a group admin or if it's a private chat."""
    if update.effective_chat.type == ChatType.PRIVATE:
        return True
    member = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
    return member.status in ['administrator', 'creator']

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👋 Welcome to **WordRushBot**!\n"
        "1. Use **/new [difficulty]** (easy/medium/hard/extreme) to start.\n"
        "2. **/help** for all commands and rules.\n"
        "3. **/leaderboard** to check scores. Play in groups to compete!",
        parse_mode='Markdown'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    commands_list = (
        "**Word Rush Commands**\n"
        "• **/new (level)** → Start a new game.\n"
        "• **/end** → End the current game (Admins only).\n"
        "• **/leaderboard** → Show the global scores.\n\n"
        "**Difficulty Levels**\n"
        f"• Easy ({DIFFICULTY_CONFIG['easy']['length']} letters)\n"
        f"• Medium ({DIFFICULTY_CONFIG['medium']['length']} letters)\n"
        f"• Hard ({DIFFICULTY_CONFIG['hard']['length']} letters)\n"
        f"• Extreme ({DIFFICULTY_CONFIG['extreme']['length']} letters)\n\n"
        "**Feedback Codes**\n"
        "🟢 **Green**: Correct letter, right spot.\n"
        "🟡 **Yellow**: Correct letter, wrong spot.\n"
        "🔴 **Red**: Letter not in the word."
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
    
    if not mongo_manager or not mongo_manager.get_game_state(chat_id):
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
    
    if not mongo_manager:
        print("FATAL ERROR: MongoDB connection failed. Exiting.")
        return

    application = Application.builder().token(BOT_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("new", new_game_command))
    application.add_handler(CommandHandler("end", end_game_command))
    application.add_handler(CommandHandler("leaderboard", leaderboard_command))
    
    # Message handler for all text messages that aren't commands (i.e., guesses)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_guess))

    print("Advanced MongoDB WordRush Bot is running...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
