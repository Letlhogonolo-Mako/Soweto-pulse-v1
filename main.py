import os, json, requests
from datetime import datetime, timedelta, time as dtime
import pytz
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN")
SA_TZ = pytz.timezone("Africa/Johannesburg")
MEMORY_FILE = "memory.json"

def load_memory():
    try:
        with open(MEMORY_FILE) as f: return json.load(f)
    except: return {"last_signals": {}, "wins": 0, "losses": 0}
def save_memory(m):
    try:
        with open(MEMORY_FILE,"w") as f: json.dump(m,f)
    except: pass
memory = load_memory()

PAIRS = {
    "GOLD": ("GC=F", 0.1),
    "US30": ("^DJI", 1),
    "NAS100": ("^NDX", 1),
    "USTECH": ("^NDX", 1),
    "EURUSD": ("EURUSD=X", 0.0001),
    "GBPUSD": ("GBPUSD=X", 0.0001),
}

def get_data(symbol, range_="5d", interval="15m"):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range={range_}&interval={interval}"
    r = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=15).json()
    res = r["chart"]["result"][0]
    q = res["indicators"]["quote"][0]
    closes=[c for c in q["close"] if c is not None]
    highs=[h for h in q["high"] if h is not None]
    lows=[l for l in q["low"] if l is not None]
    return closes, highs, lows

def rsi(closes, p=14):
    if len(closes)<p+1: return 50
    gains=[]; losses=[]
    for i in range(1,p+1):
        d=closes[-i]-closes[-i-1]
        (gains if d>0 else losses).append(abs(d))
    ag=sum(gains)/p if gains else 0; al=sum(losses)/p if losses else 0.0001
    return 100-(100/(1+ag/al))

def ema(closes,p):
    if len(closes)<p: return closes[-1]
    k=2/(p+1); e=closes[-p]
    for price in closes[-p:]: e=price*k+e*(1-k)
    return e

def atr(highs,lows,closes,p=14):
    trs=[]
    for i in range(1,min(len(closes),p+1)):
        trs.append(max(highs[-i]-lows[-i], abs(highs[-i]-closes[-i-1]), abs(lows[-i]-closes[-i-1])))
    return sum(trs)/len(trs) if trs else closes[-1]*0.001

def get_news_today():
    try:
        url="https://nfs.faireconomy.media/ff_calendar_thisweek.json"
        r=requests.get(url,timeout=10).json()
        today=datetime.now(SA_TZ).strftime("%Y-%m-%d")
        return [e for e in r if e.get("date")==today and e.get("impact")=="High"]
    except: return []

def is_news_time():
    events=get_news_today()
    now=datetime.now(SA_TZ)
    for e in events:
        try:
            t=datetime.strptime(e["time"],"%I:%M%p") + timedelta(hours=7)
            news_time=now.replace(hour=t.hour, minute=t.minute, second=0)
            diff=abs((now-news_time).total_seconds()/60)
            if diff<30: return True, e['title']
        except: pass
    return False, ""

def get_signal(name):
    symbol, pip = PAIRS[name]
    closes, highs, lows = get_data(symbol)
    try:
        closes_h,_,_ = get_data(symbol, "5d", "1h")
        htf_trend = "UP" if closes_h[-1] > ema(closes_h,50) else "DOWN"
    except: htf_trend="UNKNOWN"
    price=closes[-1]; r=rsi(closes); e9=ema(closes,9); e21=ema(closes,21); e50=ema(closes,50)
    e12=ema(closes,12); e26=ema(closes,26); macd_val=e12-e26
    a=atr(highs,lows,closes)
    support=min(lows[-50:]); resistance=max(highs[-50:])
    sma20=sum(closes[-20:])/20
    variance = sum((x - sma20)**2 for x in closes[-20:]) / 20
    std = variance ** 0.5
    upper=sma20+2*std; lower=sma20-2*std
    hour=datetime.now(SA_TZ).hour
    session_name = "London+NY" if 15 <= hour <= 19 else ("London" if 10 <= hour <= 15 else ("NY" if 15 <= hour <= 23 else "Asian"))
    news_block, news_title = is_news_time()
    buy=0; sell=0
    reasons_buy=[]; reasons_sell=[]
    if price>e9>e21: buy+=1; reasons_buy.append("EMA Bullish")
    if price<e9<e21: sell+=1; reasons_sell.append("EMA Bearish")
    if macd_val>0: buy+=1; reasons_buy.append("MACD +")
    if macd_val<0: sell+=1; reasons_sell.append("MACD -")
    if 50<r<68: buy+=1; reasons_buy.append("RSI Bull")
    if 32<r<50: sell+=1; reasons_sell.append("RSI Bear")
    if price>sma20: buy+=1
    if price<sma20: sell+=1
    if htf_trend=="UP": buy+=1; reasons_buy.append("HTF UP")
    if htf_trend=="DOWN": sell+=1; reasons_sell.append("HTF DOWN")
    if price<=lower+(upper-lower)*0.1: buy+=1; reasons_buy.append("Bounce off Low")
    if price>=upper-(upper-lower)*0.1: sell+=1; reasons_sell.append("Reject High")
    if price>resistance: buy+=1; reasons_buy.append("Breakout!")
    if price<support: sell+=1; reasons_sell.append("Breakdown!")
    sl_dist=a*1.5; tp1_dist=a*2.0; tp2_dist=a*3.0; tp3_dist=a*4.5
    now=datetime.now(SA_TZ).strftime('%H:%M %d %b')
    last=memory.get("last_signals",{}).get(name,"None yet")

    # ONLY CHANGE: ALWAYS BUY OR SELL - NO WAIT - PICK STRONGER SIDE
    if buy >= sell:
        action="BUY"; direction="🟢 BUY"; entry=price; sl=entry-sl_dist; tp1=entry+tp1_dist; tp2=entry+tp2_dist; tp3=entry+tp3_dist
        score=buy; reasons=reasons_buy
        if buy>=6: conf="HIGH 🔥🔥"
        elif buy>=5: conf="HIGH 🔥"
        elif buy>=3: conf="MEDIUM"
        else: conf="LOW - Small lot only"
    else:
        action="SELL"; direction="🔴 SELL"; entry=price; sl=entry+sl_dist; tp1=entry-tp1_dist; tp2=entry-tp2_dist; tp3=entry-tp3_dist
        score=sell; reasons=reasons_sell
        if sell>=6: conf="HIGH 🔥🔥"
        elif sell>=5: conf="HIGH 🔥"
        elif sell>=3: conf="MEDIUM"
        else: conf="LOW - Small lot only"

    memory["last_signals"][name]=f"{action} @ {price:.5f} - {now}"
    save_memory(memory)
    def pips(v): return abs(v-entry)/pip
    news_warn = f"\n⚠️ RED NEWS NOW: {news_title} - Be careful!" if news_block else ""
    return (f"🔥 {name} SIGNAL 🔥\n🕐 {now} | {session_name} | HTF: {htf_trend}{news_warn}\n\n{direction} {name}\nConfidence: {conf} | Score: {score}/7\nReasons: {', '.join(reasons) if reasons else 'Trend'}\n\n🎯 ENTRY: {entry:,.5f}\n🛑 STOP LOSS: {sl:,.5f} ({pips(sl):.0f} pips)\n✅ TP1: {tp1:,.5f} (+{pips(tp1):.0f} pips)\n✅ TP2: {tp2:,.5f} (+{pips(tp2):.0f} pips)\n🚀 TP3: {tp3:,.5f} (+{pips(tp3):.0f} pips)\n\n📐 RSI: {r:.1f} | MACD: {macd_val:.5f}\n🧱 Support: {support:,.5f} | Resistance: {resistance:,.5f}\n\n💰 RISK: 1-2% ONLY. Take 50% at TP1, move SL to breakeven.\n🧠 Last: {last}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔥 SOWETO PULSE V5.3 - ALWAYS BUY/SELL + TP 🔥\n\n/gold /us30 /nas100 /ustech\n/eurusd /gbpusd\n/market /signal /news /memory /money /risk /briefing")
    memory["chat_id"] = update.effective_chat.id
    save_memory(memory)

async def send_sig(update, name):
    await update.message.reply_text(f"🧠 AI Scanning {name}...")
    try: await update.message.reply_text(get_signal(name))
    except Exception as e: await update.message.reply_text(f"{name} error: {e}")
async def gold(u,c): await send_sig(u,"GOLD")
async def us30(u,c): await send_sig(u,"US30")
async def nas100(u,c): await send_sig(u,"NAS100")
async def ustech(u,c): await send_sig(u,"USTECH")
async def eurusd(u,c): await send_sig(u,"EURUSD")
async def gbpusd(u,c): await send_sig(u,"GBPUSD")
async def market(u,c):
    await u.message.reply_text("🧠 Scanning ALL 6...")
    for n in ["GOLD","US30","NAS100","USTECH","EURUSD","GBPUSD"]:
        await send_sig(u,n)
async def signal_cmd(u,c): await market(u,c)
async def news(u,c):
    ev=get_news_today()
    if not ev: await u.message.reply_text("📰 No HIGH impact news today.")
    else:
        txt="📰 TODAY RED NEWS:\n\n"
        for e in ev: txt+=f"⏰ {e['time']} - {e['country']} {e['title']}\n"
        await u.message.reply_text(txt)
async def memory_cmd(u,c):
    mem=load_memory(); txt="🧠 BOT MEMORY:\n\n"
    for k,v in mem.get("last_signals",{}).items(): txt+=f"{k}: {v}\n"
    await u.message.reply_text(txt if mem.get("last_signals") else "No signals yet. Try /eurusd")
async def money_cmd(u,c):
    await u.message.reply_text("💰 HOW TO MAKE MONEY:\n1. ONLY HIGH 6/7 or 7/7 - full lot\n2. MEDIUM - half lot\n3. LOW - skip or very small\n4. EURUSD/GBPUSD Best 15:30-18:00\n5. Risk 1-2% only\n6. Take 50% at TP1\n7. Max 2 trades/day")
async def risk_cmd(u,c): await u.message.reply_text("💰 RISK: 1-2% per trade. R1000 = R10-R20 risk. 2 losses = STOP today.")
async def briefing_cmd(u,c):
    await u.message.reply_text("☀️ MORNING BRIEFING - Building...")
    await market(u,c)
    await news(u,c)
async def auto_morning_briefing(context: ContextTypes.DEFAULT_TYPE):
    mem = load_memory()
    chat_id = mem.get("chat_id")
    if not chat_id: return
    try:
        await context.bot.send_message(chat_id=chat_id, text="☀️ GOOD MORNING - 09:00 BRIEFING ☀️\n\nHere is your plan for today:")
        for n in ["GOLD","US30","NAS100","USTECH","EURUSD","GBPUSD"]:
            try: await context.bot.send_message(chat_id=chat_id, text=get_signal(n))
            except: pass
        ev = get_news_today()
        if ev:
            txt="📰 TODAY RED NEWS:\n"
            for e in ev: txt+=f"{e['time']} - {e['title']}\n"
            await context.bot.send_message(chat_id=chat_id, text=txt)
    except: pass

def main():
    app=ApplicationBuilder().token(BOT_TOKEN).build()
    for cmd,fn in [("start",start),("gold",gold),("us30",us30),("nas100",nas100),("ustech",ustech),("eurusd",eurusd),("gbpusd",gbpusd),("market",market),("signal",signal_cmd),("news",news),("memory",memory_cmd),("money",money_cmd),("risk",risk_cmd),("briefing",briefing_cmd)]:
        app.add_handler(CommandHandler(cmd,fn))
    try:
        app.job_queue.run_daily(auto_morning_briefing, time=dtime(hour=7, minute=0), days=(0,1,2,3,4))
    except: pass
    print("V5.3 started...")
    app.run_polling()
if __name__=="__main__": main()