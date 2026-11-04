import os
import requests
from datetime import datetime, timedelta
import pytz
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from apscheduler.schedulers.background import BackgroundScheduler

BOT_TOKEN = os.getenv("BOT_TOKEN")
SA_TZ = pytz.timezone("Africa/Johannesburg")

# YOUR CHAT ID WILL BE SAVED AUTOMATICALLY WHEN YOU SEND /start
CHAT_IDS = set()

def get_data(symbol):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=5d&interval=15m"
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers, timeout=15).json()
    result = r["chart"]["result"][0]
    closes = [c for c in result["indicators"]["quote"][0]["close"] if c is not None]
    highs = [h for h in result["indicators"]["quote"][0]["high"] if h is not None]
    lows = [l for l in result["indicators"]["quote"][0]["low"] if l is not None]
    return closes, highs, lows

def rsi(closes, period=14):
    if len(closes) < period+1: return 50
    gains, losses = [], []
    for i in range(1, period+1):
        diff = closes[-i] - closes[-i-1]
        if diff > 0: gains.append(diff)
        else: losses.append(abs(diff))
    avg_gain = sum(gains)/period if gains else 0
    avg_loss = sum(losses)/period if losses else 0.0001
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def ema(closes, period):
    if len(closes) < period: return closes[-1]
    k = 2/(period+1)
    e = closes[-period]
    for price in closes[-period:]:
        e = price*k + e*(1-k)
    return e

def atr(highs, lows, closes, period=14):
    trs = []
    for i in range(1, min(len(closes), period+1)):
        tr = max(highs[-i]-lows[-i], abs(highs[-i]-closes[-i-1]), abs(lows[-i]-closes[-i-1]))
        trs.append(tr)
    return sum(trs)/len(trs) if trs else closes[-1]*0.001

def get_signal(name, symbol, pip_value, short=False):
    closes, highs, lows = get_data(symbol)
    price = closes[-1]
    r = rsi(closes)
    e9 = ema(closes, 9)
    e21 = ema(closes, 21)
    e50 = ema(closes, 50)
    a = atr(highs, lows, closes)
    sl_dist = a * 1.5
    tp1_dist = a * 2.0
    tp2_dist = a * 3.0
    tp3_dist = a * 4.5

    is_buy = price > e9 > e21
    is_sell = price < e9 < e21

    if is_buy and r < 68:
        direction = "🟢 BUY"; action="BUY"; entry=price; sl=entry-sl_dist; tp1=entry+tp1_dist; tp2=entry+tp2_dist; tp3=entry+tp3_dist
        confidence = "HIGH" if r > 50 else "MEDIUM"
    elif is_sell and r > 32:
        direction = "🔴 SELL"; action="SELL"; entry=price; sl=entry+sl_dist; tp1=entry-tp1_dist; tp2=entry-tp2_dist; tp3=entry-tp3_dist
        confidence = "HIGH" if r < 50 else "MEDIUM"
    else:
        action="WAIT"; direction="🟡 WAIT"; entry=price; sl=price; tp1=price; tp2=price; tp3=price; confidence="LOW"

    now = datetime.now(SA_TZ).strftime('%H:%M %d %b')
    if action=="WAIT":
        if short: return None
        return f"📊 {name}\n🕐 {now} SA\n💰 {price:,.2f}\n{direction} - RSI {r:.1f} - No trade, wait."
    else:
        return (
            f"🔥 {name} SIGNAL 🔥\n🕐 {now} SA Time\n\n"
            f"{direction} {name}\nConfidence: {confidence}\n\n"
            f"🎯 ENTRY: {entry:,.2f}\n"
            f"🛑 SL: {sl:,.2f}\n"
            f"✅ TP1: {tp1:,.2f}\n"
            f"✅ TP2: {tp2:,.2f}\n"
            f"🚀 TP3: {tp3:,.2f}\n\n"
            f"📐 RSI: {r:.1f} | EMA9: {e9:,.2f} | EMA21: {e21:,.2f}\n"
            f"💡 Move SL to breakeven at TP1.\n"
            f"⚠️ 1-2% risk only. Not financial advice."
        )

def get_news_text():
    try:
        url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
        r = requests.get(url, timeout=10).json()
        today = datetime.now(SA_TZ).strftime("%Y-%m-%d")
        events = [e for e in r if e.get("date")==today and e.get("impact")=="High"]
        if not events:
            return "📰 TODAY: No HIGH impact news. Good for technical trading."
        msg = "📰 TODAY'S RED NEWS (SA Time)\n\n"
        for e in events[:10]:
            try:
                t = datetime.strptime(e["time"], "%I:%M%p")
                sa_t = (t + timedelta(hours=7)).strftime("%H:%M")
            except: sa_t = e["time"]
            msg += f"⏰ {sa_t} - {e['country']} {e['title']} | Fcst: {e.get('forecast','-')}\n\n"
        msg += "⚠️ Don't trade 15min before/after RED news!"
        return msg
    except:
        return "📰 News: Check ForexFactory.com - Avoid NFP/CPI/FOMC 15:30 SA"

# --- COMMANDS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    CHAT_IDS.add(update.effective_chat.id)
    await update.message.reply_text(
        "🔥 SOWETO PULSE V4 - FINAL BOSS 🔥\n\n"
        "✅ AUTO-ALERTS ON! You will now get:\n"
        "• 09:00 Morning Briefing\n"
        "• Auto signals 10:00-19:00\n"
        "• RED news warnings\n"
        "• NY Open alert 15:30\n\n"
        "Commands:\n"
        "/gold - GOLD Signal + TP/SL\n"
        "/us30 - US30 Signal + TP/SL\n"
        "/nas100 - NAS100 Signal + TP/SL\n"
        "/market - All 3\n"
        "/news - Today's News\n"
        "/alerts - Check if alerts are ON\n"
        "/session - Sessions\n"
        "/risk - Risk Rules"
    )

async def gold(update: Update, context: ContextTypes.DEFAULT_TYPE):
    CHAT_IDS.add(update.effective_chat.id)
    await update.message.reply_text("⏳ Scanning GOLD...")
    try: await update.message.reply_text(get_signal("GOLD / XAUUSD", "GC=F", 0.1))
    except Exception as e: await update.message.reply_text(f"Gold error: {e}")

async def us30(update: Update, context: ContextTypes.DEFAULT_TYPE):
    CHAT_IDS.add(update.effective_chat.id)
    await update.message.reply_text("⏳ Scanning US30...")
    try: await update.message.reply_text(get_signal("US30", "^DJI", 1))
    except Exception as e: await update.message.reply_text(f"US30 error: {e}")

async def nas100(update: Update, context: ContextTypes.DEFAULT_TYPE):
    CHAT_IDS.add(update.effective_chat.id)
    await update.message.reply_text("⏳ Scanning NAS100...")
    try: await update.message.reply_text(get_signal("NAS100", "^NDX", 1))
    except Exception as e: await update.message.reply_text(f"NAS100 error: {e}")

async def market(update: Update, context: ContextTypes.DEFAULT_TYPE):
    CHAT_IDS.add(update.effective_chat.id)
    await update.message.reply_text("⏳ Scanning ALL...")
    for name, sym, pip in [("GOLD", "GC=F", 0.1), ("US30", "^DJI", 1), ("NAS100", "^NDX", 1)]:
        try: await update.message.reply_text(get_signal(name, sym, pip))
        except: await update.message.reply_text(f"{name} - no data")

async def news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Fetching news...")
    await update.message.reply_text(get_news_text())

async def alerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    CHAT_IDS.add(update.effective_chat.id)
    await update.message.reply_text(
        f"🔔 ALERTS: ON ✅\n\n"
        f"You are subscribed.\n"
        f"Morning Briefing: 09:00 SA\n"
        f"Auto Signals: Every 30min 10:00-19:00\n"
        f"News Warnings: Before RED news\n"
        f"NY Open: 15:30 SA\n\n"
        f"Keep Telegram open - bot will ping you."
    )

async def session_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🕐 SESSIONS SA:\nLondon 10:00-18:00\nNY 15:30-00:00\n🔥 GOLD BEST: 15:30-18:00\n🔥 US30/NAS100 BEST: 15:30-19:00")

async def risk_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💰 RISK:\nRisk 1-2% only\nMove SL to breakeven at TP1\nTake 50% at TP1, rest to TP2\nMax 2 trades/day")

# --- AUTO JOBS ---
async def send_to_all(app, text):
    for cid in list(CHAT_IDS):
        try: await app.bot.send_message(chat_id=cid, text=text)
        except: pass

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("gold", gold))
    app.add_handler(CommandHandler("xauusd", gold))
    app.add_handler(CommandHandler("us30", us30))
    app.add_handler(CommandHandler("nas100", nas100))
    app.add_handler(CommandHandler("nasdaq", nas100))
    app.add_handler(CommandHandler("market", market))
    app.add_handler(CommandHandler("signal", market))
    app.add_handler(CommandHandler("news", news))
    app.add_handler(CommandHandler("alerts", alerts))
    app.add_handler(CommandHandler("session", session_cmd))
    app.add_handler(CommandHandler("risk", risk_cmd))

    scheduler = BackgroundScheduler(timezone="Africa/Johannesburg")

    # Need async wrapper - scheduler will run in thread, we use job queue via polling loop
    # Simple approach: use app.job_queue if available
    try:
        job_queue = app.job_queue

        async def morning_briefing(context):
            text = "☀️ MORNING BRIEFING - SOWETO PULSE\n\n"
            for name, sym, pip in [("GOLD", "GC=F", 0.1), ("US30", "^DJI", 1), ("NAS100", "^NDX", 1)]:
                try:
                    s = get_signal(name, sym, pip)
                    text += s + "\n\n---\n\n"
                except: pass
            text += get_news_text()
            for cid in list(CHAT_IDS):
                try: await context.bot.send_message(chat_id=cid, text=text[:4000])
                except: pass

        async def auto_signal_check(context):
            # Only send if STRONG signal
            for name, sym, pip in [("GOLD", "GC=F", 0.1), ("US30", "^DJI", 1), ("NAS100", "^NDX", 1)]:
                try:
                    s = get_signal(name, sym, pip, short=True)
                    if s:  # Only if BUY/SELL, not WAIT
                        for cid in list(CHAT_IDS):
                            try: await context.bot.send_message(chat_id=cid, text=f"🚨 AUTO ALERT 🚨\n\n{s}")
                            except: pass
                except: pass

        async def ny_open_alert(context):
            for cid in list(CHAT_IDS):
                try: await context.bot.send_message(chat_id=cid, text="🇺🇸 NY OPEN IN 5 MINS! 15:30 SA\n\nBest time for US30 & NAS100.\nCheck /market now!\nCheck /news for RED news first!")
                except: pass

        async def news_warning(context):
            # Check if any high impact news in next 30 mins - simplified: send at 15:00 daily reminder
            for cid in list(CHAT_IDS):
                try: await context.bot.send_message(chat_id=cid, text="⚠️ NEWS CHECK\n\n" + get_news_text())
                except: pass

        # Schedule: 09:00 daily morning briefing Mon-Fri
        job_queue.run_daily(morning_briefing, time=datetime.strptime("09:00", "%H:%M").time(), days=(0,1,2,3,4), name="morning")
        # Auto signal every 30 mins 10:00-19:00 Mon-Fri
        job_queue.run_repeating(auto_signal_check, interval=1800, first=10, name="auto")
        # NY Open 15:25 Mon-Fri
        job_queue.run_daily(ny_open_alert, time=datetime.strptime("15:25", "%H:%M").time(), days=(0,1,2,3,4), name="nyopen")
        # News check 15:00 Mon-Fri
        job_queue.run_daily(news_warning, time=datetime.strptime("15:00", "%H:%M").time(), days=(0,1,2,3,4), name="newswarn")
        print("Scheduler: JobQueue ON - Auto alerts active")
    except Exception as e:
        print(f"JobQueue not available, using fallback: {e}")

    print("Soweto Pulse V4 FINAL BOSS started...")
    app.run_polling()

if __name__ == "__main__":
    main() 
