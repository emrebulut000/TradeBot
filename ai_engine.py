import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor 

class AIEngine:
    def __init__(self):
        self.model = RandomForestRegressor(n_estimators=100, random_state=42)
        self.son_tahmin = 0.0

    def rsi_hesapla(self, df, periyot=14):
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0))
        loss = (-delta.where(delta < 0, 0))
        avg_gain = gain.ewm(com=periyot - 1, min_periods=periyot).mean()
        avg_loss = loss.ewm(com=periyot - 1, min_periods=periyot).mean()
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def veriyi_hazirla(self, df):
        """İndikatörleri hesaplar ve veriyi temizler"""
        df = df.copy()
        
        # --- KLASİK SENSÖRLER ---
        df['RSI'] = self.rsi_hesapla(df)
        df['SMA_10'] = df['close'].rolling(window=10).mean()
        df['SMA_30'] = df['close'].rolling(window=30).mean()

        # --- YENİ EKLENEN SENSÖRLER (V2.0) ---
        # 1. MACD (Trend yönü ve momentumu)
        exp1 = df['close'].ewm(span=12, adjust=False).mean()
        exp2 = df['close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = exp1 - exp2
        df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()

        # 2. Volatilite (Piyasa ne kadar hareketli/stresli?)
        df['Volatility'] = df['close'].rolling(window=20).std()

        # 3. Hacim Trendi (Eğer veride 'volume' sütunu varsa kullanır)
        if 'volume' in df.columns:
            df['Volume_Trend'] = df['volume'].rolling(window=5).mean()

        df.dropna(inplace=True)
        return df

    def egit_ve_tahmin_et(self, df):
        """Modeli eğitir ve bir sonraki fiyatı tahmin eder"""
        df = self.veriyi_hazirla(df)
        
        # Hedef: Gelecek Mumun Kapanışı
        df['Hedef'] = df['close'].shift(-1)
        data = df.dropna().copy()

        if len(data) < 50: return 0

        # YENİ ÖZELLİKLERİ MODELE VERİYORUZ
        features = ['close', 'RSI', 'SMA_10', 'SMA_30', 'MACD', 'MACD_Signal', 'Volatility']
        if 'volume' in data.columns:
            features.append('Volume_Trend')

        X = data[features]
        y = data['Hedef']

        self.model.fit(X, y)

        # Son mum verisiyle tahmin (Pandas DataFrame olarak veriyoruz ki sklearn uyarı vermesin)
        son_veri = df.iloc[[-1]][features]
        tahmin = self.model.predict(son_veri)[0]
        self.son_tahmin = tahmin
        return tahmin