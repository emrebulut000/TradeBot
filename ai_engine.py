import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression

class AIEngine:
    def __init__(self):
        self.model = LinearRegression()
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
        df['RSI'] = self.rsi_hesapla(df)
        df['SMA_10'] = df['close'].rolling(window=10).mean()
        df['SMA_30'] = df['close'].rolling(window=30).mean()
        df.dropna(inplace=True)
        return df

    def egit_ve_tahmin_et(self, df):
        """Modeli eğitir ve bir sonraki fiyatı tahmin eder"""
        df = self.veriyi_hazirla(df)
        
        # Hedef: Gelecek Mumun Kapanışı
        df['Hedef'] = df['close'].shift(-1)
        data = df.dropna().copy()

        if len(data) < 50: return 0

        features = ['close', 'RSI', 'SMA_10', 'SMA_30']
        X = data[features]
        y = data['Hedef']

        self.model.fit(X, y)

        # Son mum verisiyle tahmin
        son_veri = df.iloc[-1][features].values.reshape(1, -1)
        tahmin = self.model.predict(son_veri)[0]
        self.son_tahmin = tahmin
        return tahmin