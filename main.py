import os
import requests
from datetime import datetime, timedelta
import pytz
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN")
SA_TZ = pytz.timezone("Africa/Johannesburg")

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
    if len(closes) < period+1:
        return 50
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

def get_signal(name, symbol, pip_value):
    closes, highs, lows = get_data(symbol)
    price = closes[-1]
    r = rsi(closes)
    e9 = ema(closes, 9)
    e21 = ema(closes, 21)
    e50 = ema(closes, 50)
    a = atr(highs, lows, closes)

    # ATR based SL / TP - PRO method
    # SL = 1.5 x ATR, TP1 = 2 x ATR, TP2 = 3 x ATR
    sl_dist = a * 1.5
    tp1_dist = a * 2.0
    tp2_dist = a * 3.0
    tp3_dist = a * 4.5

    is_buy = price > e9 > e21
    is_sell = price < e9 < e21

    if is_buy and r < 68:
        direction = "🟢 BUY"
        action = "BUY"
        entry = price
        sl = entry - sl_dist
        tp1 = entry + tp1_dist
        tp2 = entry + tp2_dist
        tp3 = entry + tp3_dist
        confidence = "HIGH" if r > 50 else "MEDIUM"
    elif is_sell and r > 32:
        direction = "🔴 SELL"
        action = "SELL"
        entry = price
        sl = entry + sl_dist
        tp1 = entry - tp1_dist
        tp2 = entry - tp2_dist
        tp3 = entry - tp3_dist
        confidence = "HIGH" if r < 50 else "MEDIUM"
    elif r >= 70:
        direction = "🟡 WAIT - OVERBOUGHT"
        action = "WAIT"
        entry = price; sl = price; tp1 = price; tp2 = price; tp3 = price
        confidence = "LOW"
    elif r <= 30:
        direction = "🟡 WAIT - OVERSOLD"
        action = "WAIT"
        entry = price; sl = price; tp1 = price; tp2 = price; tp3 = price
        confidence = "LOW"
    else:
        direction = "🟡 WAIT - RANGING"
        action = "WAIT"
        entry = price; sl = price; tp1 = price; tp2 = price; tp3 = price
        confidence = "LOW"

    now = datetime.now(SA_TZ).strftime('%H:%M %d %b')
    # Pips calc
    def pips(v): return abs(v - entry) / pip_value

    if action == "WAIT":
        return (
            f"📊 {name}\n🕐 {now} SA Time\n\n"
            f"💰 Price: {price:,.2f}\n"
            f"{direction}\n"
            f"RSI: {r:.1f} | EMA9: {e9:,.2f} | EMA21: {e21:,.2f}\n\n"
            f"⚠️ NO TRADE - Wait for clear breakout.\n"
            f"Don't force trades."
        )
    else:
        return (
            f"🔥 {name} SIGNAL 🔥\n"
            f"🕐 {now} SA Time\n\n"
            f"{direction} {name}\n"
            f"Confidence: {confidence}\n\n"
            f"🎯 ENTRY: {entry:,.2f}\n"
            f"🛑 STOP LOSS: {sl:,.2f} ({pips(sl):.0f} pips)\n"
            f"✅ TP1: {tp1:,.2f} ({pips(tp1):.0f} pips)\n"
            f"✅ TP2: {tp2:,.2f} ({pips(tp2):.0f} pips)\n"
            f"🚀 TP3: {tp3:,.2f} ({pips(tp3):.0f} pips)\n\n"
            f"📐 RSI: {r:.1f} | EMA9: {e9:,.2f} | EMA21: {e21:,.2f} | EMA50: {e50:,.2f}\n"
            f"📊 Risk:Reward to TP2 = 1:{(tp2_dist/sl_dist):.1f}\n\n"
            f"💡 Move SL to breakeven when TP1 hits.\n"
            f"⚠️ Not financial advice - 1-2% risk only."
        )

def get_news():
    try:
        # Forex Factory calendar - free, no key - High Impact USD news
        url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
        r = requests.get(url, timeout=10).json()
        today = datetime.now(SA_TZ).strftime("%Y-%m-%d")
        # Filter today + high impact + USD / ALL
        events = []
        for e in r:
            if e.get("date") == today and e.get("impact") == "High":
                # Convert time to SA time - FF time is EST, +7 = SA approx
                events.append(e)
        if not events:
            return "📰 TODAY'S HIGH IMPACT NEWS:\n\nNo HIGH impact news today.\nMarket should be technical - good for signals.\n\nCheck /signal for setups."
        msg = "📰 TODAY'S HIGH IMPACT NEWS (SA Time)\n\n"
        for e in events[:10]:
            # FF time is like 8:30am EST, add 7h for SA
            try:
                t = datetime.strptime(e["time"], "%I:%M%p")
                sa_t = (t + timedelta(hours=7)).strftime("%H:%M")
            except:
                sa_t = e["time"]
            msg += f"⏰ {sa_t} - {e['country']} {e['title']}\n   Impact: {e['impact']} | Forecast: {e.get('forecast','-')} | Prev: {e.get('previous','-')}\n\n"
        msg += "⚠️ DON'T trade 15min before/after RED news!\nSpread will spike."
        return msg
    except Exception as e:
        return f"📰 NEWS:\n\n⚠️ News feed busy. Check ForexFactory.com calendar.\n\nKey rule: Avoid trading during NFP, CPI, FOMC - 15:30 SA Time usually.\nError: {e}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔥 SOWETO PULSE - TRADING PRO V3 🔥\n\n"
        "Commands:\n"
        "/gold - GOLD Signal + TP/SL\n"
        "/us30 - US30 Signal + TP/SL\n"
        "/nas100 - NAS100 Signal + TP/SL\n"
        "/market - All 3 Signals\n"
        "/signal - Best Signal Now\n"
        "/news - TODAY'S Trading News\n"
        "/session - Best Trading Times\n"
        "/risk - Risk Management"
    )

async def gold(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Scanning GOLD...")
    try: await update.message.reply_text(get_signal("GOLD / XAUUSD", "GC=F", 0.1))
    except Exception as e: await update.message.reply_text(f"Gold closed / error: {e}")

async def us30(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Scanning US30...")
    try: await update.message.reply_text(get_signal("US30", "^DJI", 1))
    except Exception as e: await update.message.reply_text(f"US30 error: {e}")

async def nas100(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Scanning NAS100...")
    try: await update.message.reply_text(get_signal("NAS100", "^NDX", 1))
    except Exception as e: await update.message.reply_text(f"NAS100 error: {e}")

async def market(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Scanning ALL markets...")
    for name, sym, pip in [("GOLD", "GC=F", 0.1), ("US30", "^DJI", 1), ("NAS100", "^NDX", 1)]:
        try: await update.message.reply_text(get_signal(name, sym, pip))
        except: await update.message.reply_text(f"{name} - no data")

async def signal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Finding BEST setup...")
    await market(update, context)

async def news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Fetching news...")
    await update.message.reply_text(get_news())

async def session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🕐 SESSIONS (SA Time)\n\n"
        "London: 10:00-18:00\n"
        "New York: 15:30-00:00\n"
        "🔥 GOLD BEST: 15:30-18:00\n"
        "🔥 US30/NAS100 BEST: 15:30-19:00\n"
        "⚠️ Check /news before trading!"
    )

async def risk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💰 RISK RULES\n\n"
        "Risk 1-2% per trade ONLY\n"
        "R1000 account = R10-R20 risk\n"
        "Always use SL from bot\n"
        "Move SL to breakeven at TP1\n"
        "Take 50% profit at TP1, let rest run to TP2\n"
        "Max 2 trades/day"
    )

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("gold", gold))
    app.add_handler(CommandHandler("xauusd", gold))
    app.add_handler(CommandHandler("us30", us30))
    app.add_handler(CommandHandler("nas100", nas100))
    app.add_handler(CommandHandler("nasdaq", nas100))
    app.add_handler(CommandHandler("market", market))
    app.add_handler(CommandHandler("signal", signal_cmd))
    app.add_handler(CommandHandler("news", news))
    app.add_handler(CommandHandler("session", session))
    app.add_handler(CommandHandler("risk", risk))
    print("Trading Bot V3 started...")
    app.run_polling()

if __name__ == "__main__":
    main()
