import os, json, requests
from datetime import datetime, timedelta
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

# SYMBOLS - Yahoo Finance
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
    # Don't trade 30min before/after high impact news
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
    # HIGHER TIMEFRAME - 1H trend for intelligence
    try:
        closes_h,_,_ = get_data(symbol, "5d", "1h")
        htf_trend = "UP" if closes_h[-1] > ema(closes_h,50) else "DOWN"
    except: htf_trend="UNKNOWN"

    price=closes[-1]; r=rsi(closes); e9=ema(closes,9); e21=ema(closes,21); e50=ema(closes,50)
    e12=ema(closes,12); e26=ema(closes,26); macd_val=e12-e26
    a=atr(highs,lows,closes)
    support=min(lows[-50:]); resistance=max(highs[-50:])
    sma20=sum(closes[-20:])/20
    std=(sum 