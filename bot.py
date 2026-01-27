import ccxt
import pandas as pd
import asyncio
import requests
import os

# GitHub Secrets okuma
TOKEN = os.getenv('TELEGRAM_TOKEN')
MY_ID = os.getenv('CHAT_ID')

# Short Filtreleri
VOL_MULTIPLIER = 1.3  # Düşüşlerde 1.3x hacim artışı genellikle yeterli panik göstergesidir
PIVOT_RIGHT_LEFT = 3  # Destek tespiti hassasiyeti
LOOKBACK = 100        

def send_msg(text):
    if not TOKEN or not MY_ID: return
    url = f"https://api.telegram.org/bot{TOKEN.strip()}/sendMessage"
    payload = {"chat_id": MY_ID.strip(), "text": text, "parse_mode": "Markdown"}
    try: requests.post(url, json=payload)
    except: pass

async def scan():
    print("🔻 Sadece Short Taraması Başlatıldı...")
    exchange = ccxt.okx({'enableRateLimit': True})
    try:
        markets = exchange.load_markets()
        # Sadece Spot ve USDT pariteleri
        symbols = [s for s in markets if '/USDT' in s and markets[s].get('active') and markets[s].get('type') == 'spot']
        
        tickers = exchange.fetch_tickers(symbols)
        # Hacme göre ilk 150 coin (likidite için önemli)
        top_150 = sorted([s for s in symbols if s in tickers and tickers[s].get('quoteVolume')], 
                        key=lambda x: tickers[x]['quoteVolume'], reverse=True)[:150]

        for symbol in top_150:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe='1h', limit=LOOKBACK)
            if not ohlcv: continue
            
            df = pd.DataFrame(ohlcv, columns=['ts', 'open', 'high', 'low', 'close', 'volume'])
            
            # GARANTİCİ MOD: Son (canlı) mumu atla, sadece kapanmış muma bak
            df = df.iloc[:-1].copy() 
            
            curr_vol = df['volume'].iloc[-1]
            prev_vol_avg = df['volume'].iloc[-4:-1].mean()
            vol_ratio = round(curr_vol/prev_vol_avg, 2)
            
            # Hacim artışı olmayan "cılız" düşüşleri ele
            if prev_vol_avg == 0 or vol_ratio < VOL_MULTIPLIER: continue

            # Pivot Low (Destek) Tespiti
            df['p_l'] = 0.0
            for i in range(PIVOT_RIGHT_LEFT, len(df) - PIVOT_RIGHT_LEFT):
                part_l = df['low'].iloc[i - PIVOT_RIGHT_LEFT : i + PIVOT_RIGHT_LEFT + 1]
                if df['low'].iloc[i] == part_l.min(): 
                    df.at[df.index[i], 'p_l'] = df['low'].iloc[i]
            
            p_lows = df[df['p_l'] > 0]['p_l'].tolist()
            if len(p_lows) < 2: continue
            
            sup = p_lows[-1]      # En son oluşan ana destek
            pre_sup = p_lows[-2]  # Bir önceki destek (direnç testi için)
            price = df['close'].iloc[-1]   # Son kapanış fiyatı
            p_close = df['close'].iloc[-2] # Bir önceki kapanış fiyatı
            
            link = f"https://www.tradingview.com/chart/?symbol=OKX:{symbol.replace('/', '')}"

            # --- SADECE SHORT SENARYOLARI ---

            # 1. Senaryo: Destek Altı Kapanış (Şelale Başlangıcı)
            if p_close >= sup and price < sup:
                msg = (f"🔻 *{symbol}* DESTEK KIRILDI! (SHORT)\n"
                       f"💰 Kapanış: `{price}`\n"
                       f"📉 Kırılan Destek: `{sup}`\n"
                       f"📊 Satış Hacmi: `{vol_ratio}x` artış\n"
                       f"🔗 [Grafiği Aç]({link})")
                send_msg(msg)

            # 2. Senaryo: S/R Flip Short (Eski destek artık direnç - Onaylı Short)
            elif price < pre_sup and price > sup * 0.985:
                # Bu senaryo fiyatın eski dibin altında kalmaya devam ettiğini gösterir
                msg = (f"⚓ *{symbol}* ESKİ DİP DİRENÇ OLDU! (SHORT)\n"
                       f"💰 Fiyat: `{price}`\n"
                       f"📉 Yeni Direnç: `{pre_sup}`\n"
                       f"📊 Hacim Onayı: `{vol_ratio}x`\n"
                       f"🔗 [Grafiği Aç]({link})")
                send_msg(msg)

            await asyncio.sleep(0.05) # Rate limit koruması
            
    except Exception as e:
        print(f"Hata: {e}")

if __name__ == "__main__":
    asyncio.run(scan())
