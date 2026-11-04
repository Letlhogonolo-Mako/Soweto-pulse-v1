import os
import requests
from datetime import datetime
import pytz
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from apscheduler.schedulers.background import BackgroundScheduler

BOT_TOKEN = os.getenv("BOT_TOKEN")
SA_TZ = pytz.timezone("Africa/Johannesburg")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to Soweto Pulse V1!\n\n"
        "Commands:\n"
        "/start - Start\n"
        "/news - Latest SA News\n"
        "/weather - Soweto Weather\n"
        "/time - Current Time in Soweto\n"
        "/pulse - Soweto Pulse Update"
    )

async def news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        url = "https://newsapi.org/v2/top-headlines?country=za&apiKey=demo"
        # Fallback simple news via Google News RSS style
        await update.message.reply_text("📰 Top SA News:\n\n1. Soweto Pulse is LIVE!\n2. Check back for real headlines - bot is working!\n\nUse /weather for Soweto weather.")
    except Exception as e:
        await update.message.reply_text(f"News error: {e}")

async def weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Open-Meteo free, no key needed - Soweto coords
        url = "https://api.open-meteo.com/v1/forecast?latitude=-26.2485&longitude=27.8540&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m&timezone=Africa%2FJohannesburg"
        r = requests.get(url, timeout=10).json()
        cur = r.get("current", {})
        await update.message.reply_text(
            f"🌤️ Soweto Weather Now:\n"
            f"Temp: {cur.get('temperature_2m')}°C\n"
            f"Humidity: {cur.get('relative_humidity_2m')}%\n"
            f"Wind: {cur.get('wind_speed_10m')} km/h\n"
            f"Time: {cur.get('time')}"
        )
    except Exception as e:
        await update.message.reply_text(f"Weather error: {e}")

async def time_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(SA_TZ)
    await update.message.reply_text(f"🕐 Soweto Time:\n{now.strftime('%A, %d %B %Y %H:%M')}")

async def pulse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⚡ SOWETO PULSE:\n\nSoweto is alive! Bot is running 24/7.\nMore features coming soon - news, loadshedding, taxi updates.")

def main():
    if not BOT_TOKEN:
        print("No BOT_TOKEN found!")
        return
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("news", news))
    app.add_handler(CommandHandler("weather", weather))
    app.add_handler(CommandHandler("time", time_cmd))
    app.add_handler(CommandHandler("pulse", pulse))
    print("Bot started...")
    app.run_polling()

if __name__ == "__main__":
    main()
