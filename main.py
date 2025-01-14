import asyncio
import os
import subprocess
from datetime import datetime
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.helpers import escape_markdown
from telegram.ext import (ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, CallbackContext,
                          filters)
from yt_dlp import YoutubeDL
from ytmusicapi import YTMusic
from colorama import Fore, Style, init
import gettext
import sqlite3

# colorama initialize
init()

def init_db():
    conn = sqlite3.connect("user_data.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            language TEXT DEFAULT 'ru'
        )
    """)
    conn.commit()
    conn.close()

# initialize database
init_db()

# get user language from database
def get_user_language(user_id):
    conn = sqlite3.connect("user_data.db")
    cursor = conn.cursor()
    cursor.execute("SELECT language FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else "en"  # default to english if user not in database

# write user language to database
def set_user_language(user_id, language):
    conn = sqlite3.connect("user_data.db")
    cursor = conn.cursor()
    cursor.execute("REPLACE INTO users (user_id, language) VALUES (?, ?)", (user_id, language))
    conn.commit()
    conn.close()

# change language
async def change_language(update: Update, context: CallbackContext):
    await prompt_language_selection(update, context)

# prompt user to set language
async def prompt_language_selection(update: Update, context: CallbackContext):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🇬🇧English", callback_data="lang_en")],
        [InlineKeyboardButton("🇺🇦Українська", callback_data="lang_ua")],
        [InlineKeyboardButton("🇷🇺Русский", callback_data="lang_ru")]
    ])
    await update.message.reply_text(
        "Please choose your language:\nПожалуйста, выберите язык:\nБудь ласка, оберіть мову:",
        reply_markup=keyboard
    )

# set user language
async def set_language(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id
    lang_code = query.data.split("_")[1]

    if lang_code in LANGUAGES:
        set_user_language(user_id, lang_code)
        LANGUAGES[lang_code].install()
        _ = LANGUAGES[lang_code].gettext
        await query.answer()
        await query.message.reply_text(_("Language set successfully!"))
    else:
        await query.answer("Invalid language selection.", show_alert=True)

# language list
LANGUAGES = {
    "en": gettext.translation("bot", localedir="locales", languages=["en"]),
    "ru": gettext.translation("bot", localedir="locales", languages=["ru"]),
    "ua": gettext.translation("bot", localedir="locales", languages=["ua"]),
}

current_language = LANGUAGES["en"]
current_language.install()
_ = current_language.gettext

# constants
LOG_FILE_PATH = "bot_log.txt" # basically where log info is stored
TELEGRAM_BOT_TOKEN = "token" # bot API token
TELEGRAM_CHANNEL_ID = "@nekotune_db" # bot sending audios to this channel too...
DOWNLOAD_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads") # download path

# global
user_page = {} # track page for user
yt_music = YTMusic() # define YT Music
isFirtsDownload = True # bool that define if track is downloaded first time or not

# create or check download directory
os.makedirs(DOWNLOAD_PATH, exist_ok=True)

# logging function
def log(message, level="INFO"):
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    level_color = {
        "INFO": Fore.LIGHTGREEN_EX,
        "WARNING": Fore.YELLOW,
        "ERROR": Fore.RED,
        "DEBUG": Fore.CYAN
    }
    color = level_color.get(level, Fore.GREEN)
    formatted_message = f"{color}[{current_time}] [{level}] {message}{Style.RESET_ALL}"
    print(formatted_message)
    log_file_message = f"[{current_time}] [{level}] {message}\n"
    with open(LOG_FILE_PATH, "a", encoding="utf-8") as log_file:
        log_file.write(log_file_message)

# start command.........
async def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    user_language = get_user_language(user_id)
    _ = LANGUAGES[user_language].gettext

    # if the user is not in the database, prompt them to choose a language
    conn = sqlite3.connect("user_data.db")
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
    if not cursor.fetchone():
        conn.close()
        await prompt_language_selection(update, context)
    else:
        conn.close()
        await update.message.reply_text(
            _("*Hello!👋 Send me the name of a song, and I'll start searching for it!*Help command: /help."),
            parse_mode="Markdown"
        )


# help command!!!!!!!111!1!
async def help_command(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    user_language = get_user_language(user_id)
    _ = LANGUAGES[user_language].gettext
    help_text = (_(
    "*About bot:*\n"
    "• This bot can search and download music from *YouTube Music*!\n"
    "• Bot saves downloaded tracks — if track already exist in downloads, bot "
    "will send file *instantly*!\n"
    "• All downloaded tracks available in [this channel](https://t.me/"
    "nekotune_db).\n"
    "• Absolutely free and without ad, *no need to subscribe to any channels*!\n"
    "\n"
    "*Available commands:*\n"
    "• /start — Start using bot.\n"
    "• /help — Show this message with hints.\n"
    "• /setlang — Change language.\n"
    "\n"
    "*How to use:*\n"
    "1. Send song name to start searching.\n"
    "2. Choose track you need from list.\n"
    "3. Get ready MP3 file with album cover!\n"
    "\n"
    "*Hints:*\n"
    "• Make sure that entered song name is correct.\n"
    "• If song name is foreign language (like Japanese), its likely to write in "
    "that language.\n"
    "• If you cant see your track in list, try to narrow your search! Example: "
    "for track Animal - Deco27 write not only \"Animal\", but \"Animal Deco\".\n"
    "• If you run into problem, try again or DM me! [CLICK](https://t.me/"
    "nekohepott).\n"
    "\n"
    "This project is *open-source*! [GitHub](https://github.com/nekohepott32/NekoTune)"
    ))

    try:
        await update.message.reply_text(help_text, parse_mode="Markdown")
    except Exception as e:
        log(f"Error sending help message: {e}", "ERROR")
        await update.message.reply_text(_("❌ There was an error while sending hint message. Try again later."))

# search tracks by user query
async def search_music(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    user_language = get_user_language(user_id)
    _ = LANGUAGES[user_language].gettext
    query = update.message.text
    results = yt_music.search(query, filter="songs")
    tracks = [result for result in results if result['resultType'] == 'song']

    if not tracks:
        log(f"No results found for query: {query}", "WARNING")
        await update.message.reply_text(
        _("❌ Sadly, I couldn`t find track with query: *{query}*.").format(query=escape_markdown(query, version=2)),
        parse_mode="MarkdownV2"
        )
        return

    user_id = update.message.from_user.id
    user_page[user_id] = {
        'page': 0,
        'tracks': tracks,
        'query': query
    }

    await display_tracks(update, context, user_id)

# display track keyboard
async def display_tracks(update: Update, context: CallbackContext, user_id):
    user_id = update.effective_user.id
    user_language = get_user_language(user_id)
    _ = LANGUAGES[user_language].gettext
    user_data = user_page[user_id]
    current_page = user_data['page']
    tracks = user_data['tracks']
    query = user_data['query']

    tracks_per_page = 10
    start = current_page * tracks_per_page
    end = start + tracks_per_page
    tracks_to_display = tracks[start:end]

    keyboard = create_keyboard(tracks_to_display, current_page, len(tracks), tracks_per_page, update)
    await update.message.reply_text(
        _("🔍*Search:* _{query}_\n⬇️*Choose track:*").format(
            query=escape_markdown(query, version=2)
        ),
        parse_mode="MarkdownV2",
        reply_markup=keyboard
    )

# pagination and button function
async def page_selected(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = update.effective_user.id
    user_language = get_user_language(user_id)
    _ = LANGUAGES[user_language].gettext
    await query.answer()

    user_id = query.from_user.id
    if user_id not in user_page:
        await query.message.reply_text(_("❗Error: data empty."))
        return

    data = query.data
    if data.startswith("page_"): # user clicked page change button
        new_page = int(data.split("_")[1])
        user_page[user_id]['page'] = new_page
        await display_tracks(update, context, user_id)
    elif data.startswith("track_"): # user clicked track button
        track_id = data.split("_")[1]
        await process_track_selection(update, context, user_id, track_id)

# track selected function
async def process_track_selection(update: Update, context: CallbackContext, user_id, track_id):
    query = update.callback_query
    user_id = update.effective_user.id
    user_language = get_user_language(user_id)
    _ = LANGUAGES[user_language].gettext
    tracks = user_page[user_id]['tracks']
    track = next((t for t in tracks if t.get('videoId') == track_id), None)

    if not track:
        await update.callback_query.message.reply_text(_("Track not found."))
        return

    track_name = track.get('title', 'Unknown Title')
    artists = ', '.join(artist.get('name', 'Unknown Artist') for artist in track.get('artists', []))
    video_url = f"https://www.youtube.com/watch?v={track_id}"
    
    progress_message = await query.message.reply_animation(
    animation="https://i.imgur.com/XU3VQQf.gif",
    caption=_("🔄 _{track_name}_ - *Downloading...\nI changed bot server, tracks downloading takes more time, wait...*").format(track_name=escape_markdown(track_name, version=2)),
    parse_mode="Markdown")

    try:
        mp3_file = await download_track(track_name, artists, video_url, update, context)
        await progress_message.delete()
        await query.message.reply_audio(audio=open(mp3_file, 'rb'), title=track_name, performer=artists)
        if isFirstDownload == True: # if track first time downloaded, send to channel
            log(f"First time downloading this file, sending to {TELEGRAM_CHANNEL_ID}", "INFO")
            await context.bot.send_audio( 
                chat_id=TELEGRAM_CHANNEL_ID,
                audio=open(mp3_file, 'rb'),
                title=track_name,
                performer=artists
            )
        else:
            log(f"Not first time downloading this file, ignoring...", "INFO")
            isFirstDownload = True
            return
    except Exception as e:
        await progress_message.delete()
        await update.message.reply_text(_("❗ There was an error while downloading: {e}").format(e=e))

# download function
async def download_track(track_name, track_artists, video_url, update, context):
    user_id = update.effective_user.id
    user_language = get_user_language(user_id)
    _ = LANGUAGES[user_language].gettext
    log(f"Starting download for track: {track_name}, URL: {video_url}", "INFO")
    
    def sanitize_filename(name, max_length=100): # name sanitize, i guess it sanitizes names... honestly this function will almost never be used...
        sanitized_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in name)
        is_truncated = len(sanitized_name) > max_length
        if is_truncated: # if name over max lenght - cut
            sanitized_name = sanitized_name[:max_length]
        return sanitized_name, is_truncated
    
    try:
        sanitized_name, is_truncated = sanitize_filename(track_name)

        if is_truncated: # send message about cutting name
            log("File is truncated, cutting.", 'DEBUG')
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=_("⚠️ Track name was cut due to file system limits.")
            )

        video_id = video_url.split("v=")[-1]
        mp3_file = os.path.join(DOWNLOAD_PATH, f"{sanitized_name}_{video_id}.mp3")

        if os.path.exists(mp3_file): # if track file already in download directory, send it
            log(f"MP3 file already exists at path: {mp3_file}", "INFO")
            isFirstDownload = False # also will not send it to channel
            return mp3_file

        # some yt-dlp settings
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
            'outtmpl': os.path.join(DOWNLOAD_PATH, f"{sanitized_name}_%(id)s.%(ext)s"),
            'quiet': True,
        }

        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            downloaded_file = ydl.download([video_url])
            downloaded_file = ydl.prepare_filename(info).replace('.webm', '.mp3').replace('.m4a', '.mp3')

        cover_path = os.path.join(DOWNLOAD_PATH, f"{video_id}_cover.jpg")
        cover_url = f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"

        try:
            with open(cover_path, 'wb') as f:
                f.write(requests.get(cover_url).content)
        except Exception as e:
            log(f"❗ Error downloading cover: {e}", "ERROR")
            cover_path = None

        temp_file = os.path.join(DOWNLOAD_PATH, f"temp_{sanitized_name}_{video_id}.mp3")

        # ffmpeg settings
        ffmpeg_command = [
            "ffmpeg", "-i", downloaded_file,
            "-i", cover_path, "-map", "0", "-map", "1",
            "-metadata", f"title={track_name}",
            "-metadata", f"artist={track_artists}",
            "-c", "copy", "-id3v2_version", "3", temp_file, "-y"
        ]

        if cover_path:
            ffmpeg_command.extend(["-map", "1"])

        try:
            subprocess.run(ffmpeg_command, check=True)
            os.replace(temp_file, mp3_file)
        except Exception as e:
            print(f"Error embedding cover art: {e}")
            if os.path.exists(temp_file):
                os.remove(temp_file)
            return downloaded_file

        log(f"MP3 file created at path: {os.path.abspath(mp3_file)}", "INFO")

        return mp3_file # mp3 file created! will be sent to user...

    except asyncio.TimeoutError: # in case of timeout
        log("Timeout occurred while processing the download.", "WARNING")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=_("❗ There was an error: timeout. Try again later.")
        )
        return None
    except Exception as e: # in case of exception
        log(f"Unexpected error: {e}", "ERROR")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=_("❗ There was an error: {e}").format(e=e)
        )
        return None

# keyboard
def create_keyboard(tracks, current_page, total_tracks, tracks_per_page, update):
    user_id = update.effective_user.id
    user_language = get_user_language(user_id)
    _ = LANGUAGES[user_language].gettext
    keyboard = []
    for track in tracks:
        try:
            track_name = track.get('title', 'Unknown Title')
            artist_name = ', '.join(artist.get('name', 'Unknown Artist') for artist in track.get('artists', []))
            video_id = track.get('videoId', '')

            if video_id:
                keyboard.append([InlineKeyboardButton(f"{track_name} - {artist_name}", callback_data=f"track_{video_id}")])
        except Exception as e:
            log(f"Error processing track: {e}", "ERROR")
            continue

    pagination_buttons = []
    if current_page > 0:
        pagination_buttons.append(InlineKeyboardButton(_("⏪Previous"), callback_data=f"page_{current_page - 1}"))

    if (current_page + 1) * tracks_per_page < total_tracks:
        pagination_buttons.append(InlineKeyboardButton(_("Next⏩"), callback_data=f"page_{current_page + 1}"))

    if pagination_buttons:
        keyboard.append(pagination_buttons)

    return InlineKeyboardMarkup(keyboard)

# main function
def main():
    try:
        app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
        log("Bot started.", "INFO")
    
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CallbackQueryHandler(set_language, pattern="^lang_"))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(CommandHandler("setlang", change_language))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_music))
        app.add_handler(CallbackQueryHandler(page_selected))

        app.run_polling()
    except Exception as e:
        log(f"Error starting bot: {e}", "ERROR")

if __name__ == "__main__":
    main()
