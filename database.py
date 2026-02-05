import sqlite3
from datetime import datetime
from config import SYMBOL

DB_NAME = 'trade_gecmisi.db'

def db_kur():
    """Veritabanı tablosunu oluşturur"""
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS islemler
                     (tarih TEXT, sembol TEXT, islem TEXT, fiyat REAL, miktar REAL, sebep TEXT)''')
        conn.commit()

def db_ekle(islem, fiyat, miktar, sebep):
    """Yeni işlem kaydeder"""
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        tarih = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute("INSERT INTO islemler VALUES (?, ?, ?, ?, ?, ?)", 
                  (tarih, SYMBOL, islem, fiyat, miktar, sebep))
        conn.commit()

def db_getir():
    """Tüm geçmişi listeler"""
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM islemler ORDER BY tarih DESC")
        return c.fetchall()