import time
import pandas as pd
import ccxt
import sys
from datetime import datetime

# --- MODÜLLER (Aynılarını Kullanıyoruz!) ---
import config as cfg
import database as db
from ai_engine import AIEngine

# --- GLOBAL ---
ai_beyin = AIEngine()
exchange_data = None
exchange_trade = None
pozisyonda_mi = False
alis_fiyati = 0.0

def baglanti_kur():
    global exchange_data, exchange_trade
    # 1. Veri (Gerçek)
    exchange_data = ccxt.binance({'enableRateLimit': True, 'options': {'defaultType': 'spot'}})
    # 2. İşlem (Sanal - Testnet)
    exchange_trade = ccxt.binance({
        'apiKey': cfg.API_KEY, 'secret': cfg.SECRET_KEY,
        'enableRateLimit': True, 'options': {'defaultType': 'spot'}
    })
    exchange_trade.set_sandbox_mode(True)

def veri_cek():
    try:
        bars = exchange_data.fetch_ohlcv(cfg.SYMBOL, cfg.TIMEFRAME, limit=cfg.LIMIT)
        df = pd.DataFrame(bars, columns=['ts', 'open', 'high', 'low', 'close', 'vol'])
        # İndikatör hesapları ai_engine içinde yapılıyor
        return df
    except Exception as e:
        print(f"⚠️ Veri Hatası: {e}")
        return None

def telegram_gonder(mesaj):
    try:
        import requests
        url = f"https://api.telegram.org/bot{cfg.TELEGRAM_TOKEN}/sendMessage"
        requests.get(url, params={'chat_id': cfg.TELEGRAM_CHAT_ID, 'text': mesaj})
    except: pass

def log_yaz(mesaj):
    # Ekrana değil, terminale yazacak
    zaman = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{zaman}] {mesaj}")

def emir_ver(taraf, fiyat, sebep):
    global pozisyonda_mi, alis_fiyati
    try:
        if taraf == 'buy':
            # 1. Alınacak miktarı hesapla
            miktar_str = exchange_trade.amount_to_precision(cfg.SYMBOL, cfg.TRADE_MIKTARI_USDT / fiyat)
            miktar = float(miktar_str)
            
            # 🔥 BİNANCE'E EMRİ İLET (Eksik olan kısım buydu)
            try:
                exchange_trade.create_market_buy_order(cfg.SYMBOL, miktar)
            except Exception as b_hata:
                telegram_gonder(f"⚠️ BİNANCE ALIM HATASI: Bakiyen yetersiz olabilir veya API hatası!\nDetay: {b_hata}")
                return False # Hata varsa işlemi durdur
            
            # 2. İşlem başarılıysa sistemi güncelle
            pozisyonda_mi = True
            alis_fiyati = fiyat
            db.db_ekle("ALIM", fiyat, miktar, sebep)
            
            msg = f"🟢 ALIM YAPILDI!\nFiyat: ${fiyat:.2f}\nSebep: {sebep}"
            log_yaz(msg)
            telegram_gonder(msg)
            
        else: # SATIŞ
            # 1. Satılacak miktarı hesapla (Daha önce aldığımız miktar kadar)
            miktar_str = exchange_trade.amount_to_precision(cfg.SYMBOL, cfg.TRADE_MIKTARI_USDT / alis_fiyati)
            miktar = float(miktar_str)
            
            # 🔥 BİNANCE'E EMRİ İLET
            try:
                exchange_trade.create_market_sell_order(cfg.SYMBOL, miktar)
            except Exception as b_hata:
                telegram_gonder(f"⚠️ BİNANCE SATIŞ HATASI: {b_hata}")
                return False

            # 2. İşlem başarılıysa sistemi güncelle
            pozisyonda_mi = False
            db.db_ekle("SATIŞ", fiyat, 0, sebep)
            
            kar_zarar = (fiyat - alis_fiyati) / alis_fiyati * 100
            durum = "KÂR 🤑" if kar_zarar > 0 else "ZARAR 🔻"
            
            msg = f"🔴 SATIŞ YAPILDI!\nFiyat: ${fiyat:.2f}\nSebep: {sebep}\nSonuç: {durum} (%{kar_zarar:.2f})"
            log_yaz(msg)
            telegram_gonder(msg)
            
        return True
    except Exception as e:
        log_yaz(f"❌ Emir Hatası: {e}")
        telegram_gonder(f"⚠️ SİSTEM HATASI: {e}")
        return False

# --- ANA DÖNGÜ (Server Loop) ---
if __name__ == "__main__":
    print("------------------------------------------------")
    print("👻 HEADLESS (HAYALET) MODU BAŞLATILIYOR...")
    print("💻 Arayüz Yok | ☁️ Sunucu Uyumlu | 🧠 AI Aktif")
    print("------------------------------------------------")
    
    baglanti_kur()
    db.db_kur()
    telegram_gonder("👻 Hayalet Bot Sunucuda Başladı! (v7.0)")
    
    while True:
        try:
            df = veri_cek()
            if df is None: 
                time.sleep(10)
                continue
            
            # 1. AI Tahmini
            beklenen_fiyat = ai_beyin.egit_ve_tahmin_et(df)
            
            # Veri Hazırlığı
            son_df = ai_beyin.veriyi_hazirla(df)
            fiyat = float(df.iloc[-1]['close'])
            rsi = float(son_df.iloc[-1]['RSI'])
            
            fark = beklenen_fiyat - fiyat
            yuzde_fark = (fark / fiyat) * 100
            
            # Terminale Durum Raporu (Her döngüde)
            log_yaz(f"Fiyat: {fiyat} | AI Hedef: {beklenen_fiyat:.1f} (%{yuzde_fark:.2f}) | RSI: {rsi:.1f}")
            
            # 2. STRATEJİ MOTORU
            if not pozisyonda_mi:
                if yuzde_fark > 0.1 and rsi < 70:
                    emir_ver('buy', fiyat, f"AI TAHMİNİ (Hedef: {beklenen_fiyat:.1f})")
            else:
                # Pozisyondaysak kar/zarar kontrolü
                if fiyat <= alis_fiyati * (1 - cfg.STOP_LOSS):
                    emir_ver('sell', fiyat, "STOP LOSS")
                elif fiyat >= alis_fiyati * (1 + cfg.TAKE_PROFIT):
                    emir_ver('sell', fiyat, "TAKE PROFIT")
                elif yuzde_fark < -0.2:
                    emir_ver('sell', fiyat, "AI DÜŞÜŞ SİNYALİ")
            
            # Sunucuyu yormamak için bekle
            time.sleep(15) 
            
        except KeyboardInterrupt:
            print("\n🛑 Bot elle durduruldu.")
            break
        except Exception as e:
            log_yaz(f"Beklenmeyen Hata: {e}")
            time.sleep(10)