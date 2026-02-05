import tkinter as tk
from tkinter import ttk, messagebox
import threading
import ccxt
import pandas as pd
import time
import requests 
from datetime import datetime

# --- MODÜLLERİMİZİ İÇERİ ALIYORUZ ---
import config as cfg
import database as db
from ai_engine import AIEngine

# --- GRAFİK ---
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

# --- GLOBAL DEĞİŞKENLER ---
bot_calisiyor = False
pozisyonda_mi = False
alis_fiyati = 0.0
exchange_data = None
exchange_trade = None
son_df = None
ai_beyin = AIEngine() # AI Sınıfımızı başlattık

# --- BORSA BAĞLANTILARI ---
def baglanti_kur():
    global exchange_data, exchange_trade
    # 1. Gerçek Veri (Mainnet)
    exchange_data = ccxt.binance({'enableRateLimit': True, 'options': {'defaultType': 'spot'}})
    
    # 2. Sanal İşlem (Testnet)
    exchange_trade = ccxt.binance({
        'apiKey': cfg.API_KEY, 'secret': cfg.SECRET_KEY,
        'enableRateLimit': True, 'options': {'defaultType': 'spot'}
    })
    exchange_trade.set_sandbox_mode(True)

def veri_cek():
    try:
        bars = exchange_data.fetch_ohlcv(cfg.SYMBOL, cfg.TIMEFRAME, limit=cfg.LIMIT)
        df = pd.DataFrame(bars, columns=['ts', 'open', 'high', 'low', 'close', 'vol'])
        df['ts'] = pd.to_datetime(df['ts'], unit='ms')
        # İndikatör hesabı artık AI motorunun içinde yapılıyor
        return df
    except: return None

def telegram_gonder(mesaj):
    try:
        url = f"https://api.telegram.org/bot{cfg.TELEGRAM_TOKEN}/sendMessage"
        requests.get(url, params={'chat_id': cfg.TELEGRAM_CHAT_ID, 'text': mesaj})
    except: pass

def emir_ver(taraf, fiyat, sebep):
    global pozisyonda_mi, alis_fiyati
    try:
        if taraf == 'buy':
            miktar = exchange_trade.amount_to_precision(cfg.SYMBOL, cfg.TRADE_MIKTARI_USDT / fiyat)
            pozisyonda_mi = True
            alis_fiyati = fiyat
            db.db_ekle("ALIM", fiyat, float(miktar), sebep)
            log_yaz(f"🟢 ALIM: {fiyat} ({sebep})")
            telegram_gonder(f"🟢 ALINDI\nFiyat: {fiyat}\nSebep: {sebep}")
        else:
            pozisyonda_mi = False
            db.db_ekle("SATIŞ", fiyat, 0, sebep)
            log_yaz(f"🔴 SATIŞ: {fiyat} ({sebep})")
            telegram_gonder(f"🔴 SATILDI\nFiyat: {fiyat}\nSebep: {sebep}")
        return True
    except Exception as e:
        log_yaz(f"Hata: {e}")
        return False

# --- ANA DÖNGÜ ---
def bot_dongusu():
    global bot_calisiyor, son_df
    baglanti_kur()
    db.db_kur()
    log_yaz("Modüler AI Bot Başlatıldı...")
    telegram_gonder("🚀 Sistem Devrede!")

    while bot_calisiyor:
        try:
            df = veri_cek()
            if df is None: continue
            
            # AI Tahmini
            beklenen_fiyat = ai_beyin.egit_ve_tahmin_et(df)
            son_df = ai_beyin.veriyi_hazirla(df) # Grafikler için işlenmiş veriyi al
            
            fiyat = float(df.iloc[-1]['close'])
            rsi = float(son_df.iloc[-1]['RSI'])
            
            fark = beklenen_fiyat - fiyat
            yuzde_fark = (fark / fiyat) * 100
            ai_yon = "YUKARI 📈" if fark > 0 else "AŞAĞI 📉"

            root.after(0, arayuz_guncelle, fiyat, rsi, ai_yon, beklenen_fiyat)
            root.after(0, grafik_ciz)

            # STRATEJİ
            if not pozisyonda_mi:
                if yuzde_fark > 0.1 and rsi < 70:
                    emir_ver('buy', fiyat, f"AI Hedef: {beklenen_fiyat:.1f}")
            else:
                if fiyat <= alis_fiyati * (1 - cfg.STOP_LOSS): emir_ver('sell', fiyat, "STOP LOSS")
                elif fiyat >= alis_fiyati * (1 + cfg.TAKE_PROFIT): emir_ver('sell', fiyat, "TAKE PROFIT")
                elif yuzde_fark < -0.2: emir_ver('sell', fiyat, "AI DÜŞÜŞ SİNYALİ")

            time.sleep(10)
        except Exception as e:
            log_yaz(f"Hata: {e}")
            time.sleep(5)

# --- ARAYÜZ (GUI) ---
def arayuz_guncelle(fiyat, rsi, ai_yon, beklenen):
    lbl_fiyat.config(text=f"${fiyat:.2f}")
    lbl_rsi.config(text=f"{rsi:.2f}", fg="green" if rsi < 30 else "black")
    lbl_ai.config(text=f"{ai_yon}\nHedef: ${beklenen:.2f}", fg="green" if "YUKARI" in ai_yon else "red")
    lbl_durum.config(text=f"POZİSYONDA ({alis_fiyati})" if pozisyonda_mi else "BEKLİYOR...", fg="blue" if pozisyonda_mi else "orange")

def grafik_ciz():
    if son_df is None: return
    prices = son_df['close'].tail(50)
    dates = range(len(prices))
    ax1.clear(); ax1.plot(dates, prices, 'b'); ax1.grid(True, alpha=0.3)
    if ai_beyin.son_tahmin > 0: ax1.plot(len(prices), ai_beyin.son_tahmin, 'ro')
    canvas.draw()

def gecmisi_guncelle():
    for i in tree.get_children(): tree.delete(i)
    for kayit in db.db_getir(): tree.insert("", "end", values=kayit)

def baslat():
    global bot_calisiyor
    if not bot_calisiyor:
        bot_calisiyor = True; threading.Thread(target=bot_dongusu, daemon=True).start()
        btn_baslat.config(state="disabled"); btn_durdur.config(state="normal")

def durdur():
    global bot_calisiyor
    bot_calisiyor = False; log_yaz("Durduruldu."); btn_baslat.config(state="normal"); btn_durdur.config(state="disabled")

def log_yaz(mesaj):
    list_log.insert(0, f"[{datetime.now().strftime('%H:%M')}] {mesaj}")

# --- PENCERE ---
root = tk.Tk(); root.title("PRO MODULAR TRADER"); root.geometry("500x700")
notebook = ttk.Notebook(root); notebook.pack(pady=10, expand=True, fill="both")

tab1 = ttk.Frame(notebook); notebook.add(tab1, text='Kontrol')
frame_ust = tk.Frame(tab1); frame_ust.pack(fill="x", padx=10, pady=5)
lbl_fiyat = tk.Label(frame_ust, text="$---", font=("Arial", 22, "bold")); lbl_fiyat.pack(side="left", padx=10)
frame_ai = tk.Frame(frame_ust, bg="#f0f0f0", bd=2, relief="groove"); frame_ai.pack(side="right", padx=10)
lbl_ai = tk.Label(frame_ai, text="AI BAŞLATILIYOR", font=("Arial", 10, "bold"), fg="gray"); lbl_ai.pack(padx=5, pady=5)

lbl_rsi = tk.Label(tab1, text="RSI: --"); lbl_rsi.pack()
lbl_durum = tk.Label(tab1, text="HAZIR", fg="gray"); lbl_durum.pack(pady=5)
fig = Figure(figsize=(5, 3), dpi=100); ax1 = fig.add_subplot(111); fig.tight_layout()
canvas = FigureCanvasTkAgg(fig, master=tab1); canvas.get_tk_widget().pack(fill="both", expand=True, padx=10)

frame_alt = tk.Frame(tab1); frame_alt.pack(fill="x", padx=10, pady=5)
btn_baslat = tk.Button(frame_alt, text="BAŞLAT", bg="#8e44ad", fg="white", command=baslat); btn_baslat.pack(side="left", padx=5)
btn_durdur = tk.Button(frame_alt, text="DURDUR", bg="red", fg="white", command=durdur, state="disabled"); btn_durdur.pack(side="left", padx=5)
list_log = tk.Listbox(frame_alt, height=6, font=("Consolas", 8)); list_log.pack(side="right", fill="x", expand=True)

tab2 = ttk.Frame(notebook); notebook.add(tab2, text='Geçmiş')
tree = ttk.Treeview(tab2, columns=('tarih', 'islem', 'fiyat', 'miktar', 'sebep'), show='headings')
for col in ('tarih', 'islem', 'fiyat', 'miktar', 'sebep'): tree.heading(col, text=col.title()); tree.column(col, width=80)
tree.pack(fill="both", expand=True)

if __name__ == "__main__":
    db.db_kur()
    gecmisi_guncelle()
    root.mainloop()