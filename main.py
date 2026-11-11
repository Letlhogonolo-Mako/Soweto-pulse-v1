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
    vols=[v for v in q.get("volume",[]) if v is not None] if q.get("volume") else []
    return closes, highs, lows, vols

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
    return sum(trs)/len(trs)