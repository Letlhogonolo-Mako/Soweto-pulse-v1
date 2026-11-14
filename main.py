import os, requests, asyncio, datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")
CHAT_FILE = "chat_id.txt"

# ORIGINAL + ADDED - NOTHING REMOVED
PAIRS = {
    "gold": ("GC=F", "GOLD"),
    "us30": ("^DJI", "US30"),
    "nas100": ("^NDX", "NAS100"),
    "ustech": ("^NDX", "USTech"),
    "eurusd": ("EURUSD=X", "EURUSD"),
    "gbpusd": ("GBPUSD=X", "GBPUSD"),
}

def get_closes(symbol):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=5d&interval=1h"
        r = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=10).json()
        c = r["chart"]["result"][0]["indicators"]["quote"][0]["close"]
        return [x for x in c if x is not None]
    except:
        return None

def ema(data, period):
    k = 2/(period+1)
    e = sum(data[:period])/period
    for p in data[period:]:
        e = p*k + e*(1-k)
    return e

def rsi(data, period=14):
    gains=[]; losses=[]
    for i in range(1, len(data)):
        d=data[i]-data[i-1]
        gains.append(max(d,0)); losses.append(max(-d,0))
    ag=sum(gains[-period:])/period; al=sum(losses[-period:])/period
    if al==0: return 70
    return 100-(100/(1+ag/al))

def build_signal(symbol, name):
    closes = get_closes(symbol)
    if not closes or len(closes)<25:
        return f"⏳ Scanning {name}... try again"
    price=closes[-1]; e9=ema(closes,9); e21=ema(closes,21); r=rsi(closes)
    now=datetime.datetime.now().strftime("%H:%M %d %b SA Time")
    if price>e9 and price>e21:
        side="BUY"; conf="HIGH" if 45<r<65 else "MEDIUM"
    elif price<e9 and price<e21:
        side="SELL"; conf="HIGH" if 35<r<55 else "MEDIUM"
    else:
        side="BUY" if price>e21 else "SELL"; conf="MEDIUM"
    step = price*0.0008 if "USD" in name else price*0.0012
    if side=="BUY":
        sl=price-step; tp1=price+step*1.3; tp2=price+step*2.0; tp3=price+step*3.0
    else:
        sl=price+step; tp1=price-step*1.3; tp2=price-step*2.0; tp3=price-step*3.0
    dec=5 if "USD" in name else 2
    dot="🟢" if side=="BUY" else "🔴"
    return (f"🔥 {name} SIGNAL 🔥\n"
            f"🕐 {now}\n\n"
            f"{dot} {side} {name}\n"
            f"Confidence: {conf}\n\n"
            f"🎯 ENTRY: {price:,.{dec}f}\n"
            f"🛑 SL: {sl:,.{dec}f}\n"
            f"✅ TP1: {tp1:,.{dec}f}\n"
            f"✅ TP2: {tp2:,.{dec}f}\n"
            f"🚀 TP3: {tp3:,.{dec}f}\n\n"
            f"📐 RSI: {r:.1f} | EMA9: {e9:,.{dec}f} | EMA21: {e21:,.{dec}f}\n"
            f"💡 Move SL to breakeven at TP1.\n"
            f"⚠️ 1-2% risk only. Not financial advice.")

# SAME AS SCREENSHOT - ONLY V5+ AND 3 ADDED LINES
WELCOME = ("🔥 SOWETO PULSE V5+ - FINAL BOSS 🔥\n\n"
"✅ AUTO-ALERTS ON! You will now get:\n"
"• 09:00 Morning Briefing\n"
"• Auto signals 10:00-19:00\n"
"• RED news warnings\n"
"• NY Open alert 15:30\n\n"
"Commands:\n"
"/gold - GOLD Signal + TP/SL\n"
"/us30 - US30 Signal + TP/SL\n"
"/nas100 - NAS100 Signal + TP/SL\n"
"/ustech - USTech Signal + TP/SL\n"
"/eurusd - EURUSD Signal + TP/SL\n"
"/gbpusd - GBPUSD Signal + TP/SL\n"
"/market - All 6\n"
"/news - Today's News\n"
"/alerts - Check if alerts are ON\n"
"/session - Sessions\n"
"/risk - Risk Rules")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    open(CHAT_FILE,"w").write(str(update.effective_chat.id))
    await update.message.reply_text(WELCOME)
async def pulse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📍 SOWETO PULSE V5+ - Soweto is LIVE! 🔥")
async def do_pair(update, key):
    sym,name=PAIRS[key]
    await update.message.reply_text(f"⏳ Scanning {name}...")
    await update.message.reply_text(build_signal(sym,name))
async def gold(update: Update, context: ContextTypes.DEFAULT_TYPE): await do_pair(update,"gold")
async def us30(update: Update, context: ContextTypes.DEFAULT_TYPE): await do_pair(update,"us30")
async def nas100(update: Update, context: ContextTypes.DEFAULT_TYPE): await do_pair(update,"nas100")
async def ustech(update: Update, context: ContextTypes.DEFAULT_TYPE): await do_pair(update,"ustech")
async def eurusd(update: Update, context: ContextTypes.DEFAULT_TYPE): await do_pair(update,"eurusd")
async def gbpusd(update: Update, context: ContextTypes.DEFAULT_TYPE): await do_pair(update,"gbpusd")
async def market(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Scanning ALL...")
    for k in PAIRS:
        sym,name=PAIRS[k]
        await update.message.reply_text(build_signal(sym,name))
async def news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📰 TODAY'S NEWS - V5+\n\n• London 10:00 SAST\n• NY Open 15:30 SAST - RED news risk\n• USD news moves GOLD + EURUSD + GBPUSD + USTech fast\n• Don't trade 5 min before/after RED news")
async def alerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ ALERTS ARE ON!\n• 09:00 Briefing\n• 10:00-19:00 Auto Signals\n• 15:30 NY Open")
async def session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🕐 SESSIONS SAST\n\n• London: 10:00-18:00 - Best for EURUSD/GBPUSD\n• NY: 15:30-22:00 - Best for USTech + GOLD\n• Overlap 15:30-18:00 = MOST volatility 🔥")
async def risk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🛡️ RISK RULES V5+\n\n• 1-2% risk per trade ONLY\n• Move SL to breakeven at TP1\n• Max 2 trades per session\n• No revenge trading")

async def morning_briefing(context: ContextTypes.DEFAULT_TYPE):
    try: chat_id=open(CHAT_FILE).read().strip()
    except: return
    now=datetime.datetime.now().strftime("%d %b %Y")
    msg=f"☀️ GOOD MORNING SOWETO - {now}\n\n📍 SOWETO PULSE V5+ BRIEFING\n\n"
    for k in PAIRS:
        sym,name=PAIRS[k]
        msg+=build_signal(sym,name)+"\n\n"
    await context.bot.send_message(chat_id=chat_id, text=msg)

async def auto_signal(context: ContextTypes.DEFAULT_TYPE):
    try: chat_id=open(CHAT_FILE).read().strip()
    except: return
    for k in PAIRS:
        sym,name=PAIRS[k]
        await context.bot.send_message(chat_id=chat_id, text=build_signal(sym,name))

async def ny_alert(context: ContextTypes.DEFAULT_TYPE):
    try: chat_id=open(CHAT_FILE).read().strip()
    except: return
    await context.bot.send_message(chat_id=chat_id, text="🔔 NY OPEN 15:30! Volatility coming for GOLD + USTech + EURUSD + GBPUSD. Wait for first 15min candle.")

app=ApplicationBuilder().token(TOKEN).build()
for cmd,fn in [("start",start),("pulse",pulse),("gold",gold),("us30",us30),("nas100",nas100),("ustech",ustech),("eurusd",eurusd),("gbpusd",gbpusd),("market",market),("news",news),("alerts",alerts),("session",session),("risk",risk)]:
    app.add_handler(CommandHandler(cmd,fn))
jq=app.job_queue
jq.run_daily(morning_briefing, time=datetime.time(hour=9, minute=0), days=(0,1,2,3,4))
jq.run_daily(ny_alert, time=datetime.time(hour=15, minute=30), days=(0,1,2,3,4))
for h in [10,11,12,13,14,16,17,18,19]:
    jq.run_daily(auto_signal, time=datetime.time(hour=h, minute=0), days=(0,1,2,3,4))
print("Bot running V5+")
asyncio.set_event_loop(asyncio.new_event_loop())
app.run_polling()
