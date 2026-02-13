import ccxt
import pandas as pd
import asyncio
import requests
import os

TOKEN = os.getenv('TELEGRAM_TOKEN')
MY_ID = os.getenv('CHAT_ID')

async def scan():
    exchange = ccxt.okx({'enableRateLimit': True})
    print("🚀 Aile Geçindiren Bot Başlatıldı...")
    
    try:
        markets = exchange.load_markets()
        symbols = [s for s in markets if '/USDT' in s and markets[s].get('active') and markets[s].get('type') == 'spot']
        tickers = exchange.fetch_tickers(symbols)
        top_coins = sorted([s for s in symbols if s in tickers and tickers[s].get('quoteVolume')], 
                          key=lambda x: tickers[x]['quoteVolume'], reverse=True)[:100]

        for symbol in top_coins:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe='15m', limit=50)
            if not ohlcv: continue
            df = pd.DataFrame(ohlcv, columns=['ts', 'open', 'high', 'low', 'close', 'volume'])
            
            # Göstergeler
            df['sma'] = df['close'].rolling(20).mean()
            df['std'] = df['close'].rolling(20).std()
            df['lower'] = df['sma'] - (df['std'] * 2)
            
            # RSI
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            df['rsi'] = 100 - (100 / (1 + (gain/loss)))

            # Son Değerler
            price = df['close'].iloc[-1]
            lower_b = df['lower'].iloc[-1]
            rsi = df['rsi'].iloc[-1]
            vol_ratio = df['volume'].iloc[-1] / df['volume'].iloc[-6:-1].mean()

            # --- EKMEK YEDİREN KOŞULLAR ---
            # 1. Bollinger Alt Bant Kırılımı
            # 2. RSI 30-45 arası (Aşırı satım değil ama düşüş güçlü)
            # 3. Hacim normalin 1.5 katı
            if price < lower_b and 30 < rsi < 48 and vol_ratio > 1.5:
                link = f"https://www.tradingview.com/chart/?symbol=OKX:{symbol.replace('/', '')}"
                msg = (f"🚨 **GÜÇLÜ SHORT SİNYALİ**\n"
                       f"🪙 Coin: `{symbol}`\n"
                       f"💰 Fiyat: `{price}`\n"
                       f"📉 RSI: `{round(rsi, 1)}` | Hacim: `{round(vol_ratio, 1)}x`\n"
                       f"⚠️ Bandın Altındayız! | [Grafik]({link})")
                send_msg(msg)
            
            await asyncio.sleep(0.1)
    except Exception as e: print(f"Hata: {e}")

def send_msg(text):
    if not TOKEN or not MY_ID: return
    try: requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                       json={"chat_id": MY_ID, "text": text, "parse_mode": "Markdown"})
    except: pass

if __name__ == "__main__":
    asyncio.run(scan())
