"""
ml_pipeline.py - 機器學習管線模組

提供以下功能：
1. FeatureLabeler - 特徵標注系統
2. AnomalyDetector - 異常偵測
3. EnergyPredictor - 能耗預測模型
"""

import pandas as pd
import numpy as np
import json
import os
from datetime import datetime
from sklearn.ensemble import IsolationForest, RandomForestRegressor
from sklearn.preprocessing import StandardScaler
import pickle


class FeatureLabeler:
    """
    特徵標注系統 - 管理數據的手動/自動標籤
    
    標籤類型:
    - normal: 正常運作
    - anomaly: 異常
    - maintenance: 維護中
    - unknown: 未知/未標注
    """
    
    LABEL_TYPES = ['normal', 'anomaly', 'maintenance', 'unknown']
    
    def __init__(self, project_name, labels_dir='labels'):
        self.project_name = project_name
        self.labels_dir = labels_dir
        self.labels_file = os.path.join(labels_dir, f"{project_name}_labels.json")
        self.labels = []
        
        # 確保 labels 目錄存在
        os.makedirs(labels_dir, exist_ok=True)
        
        # 載入現有標籤
        self._load_labels()
    
    def _load_labels(self):
        """載入現有標籤檔案"""
        if os.path.exists(self.labels_file):
            try:
                with open(self.labels_file, 'r', encoding='utf-8') as f:
                    self.labels = json.load(f)
            except Exception as e:
                print(f"載入標籤時發生錯誤: {e}")
                self.labels = []
    
    def _save_labels(self):
        """儲存標籤到檔案"""
        try:
            with open(self.labels_file, 'w', encoding='utf-8') as f:
                json.dump(self.labels, f, ensure_ascii=False, indent=2, default=str)
            return True
        except Exception as e:
            print(f"儲存標籤時發生錯誤: {e}")
            return False
    
    def add_label(self, start_time, end_time, label_type, description=''):
        """
        新增標籤
        
        Args:
            start_time: 開始時間 (datetime or str)
            end_time: 結束時間 (datetime or str)
            label_type: 標籤類型 (normal/anomaly/maintenance/unknown)
            description: 描述文字
        """
        if label_type not in self.LABEL_TYPES:
            raise ValueError(f"無效的標籤類型。可用類型: {self.LABEL_TYPES}")
        
        label = {
            'id': len(self.labels) + 1,
            'start_time': str(start_time),
            'end_time': str(end_time),
            'label_type': label_type,
            'description': description,
            'created_at': str(datetime.now())
        }
        
        self.labels.append(label)
        self._save_labels()
        return label
    
    def remove_label(self, label_id):
        """移除指定標籤"""
        self.labels = [l for l in self.labels if l['id'] != label_id]
        self._save_labels()
    
    def get_labels(self):
        """取得所有標籤"""
        return self.labels
    
    def get_labels_for_period(self, start_time, end_time):
        """取得特定時間區間內的標籤"""
        result = []
        for label in self.labels:
            label_start = pd.to_datetime(label['start_time'])
            label_end = pd.to_datetime(label['end_time'])
            
            if label_start <= pd.to_datetime(end_time) and label_end >= pd.to_datetime(start_time):
                result.append(label)
        
        return result
    
    def apply_labels_to_df(self, df):
        """
        將標籤應用到 DataFrame，新增 'label' 欄位
        """
        df['label'] = 'unknown'
        
        for label in self.labels:
            label_start = pd.to_datetime(label['start_time'])
            label_end = pd.to_datetime(label['end_time'])
            
            mask = (df.index >= label_start) & (df.index <= label_end)
            df.loc[mask, 'label'] = label['label_type']
        
        return df


class AnomalyDetector:
    """
    異常偵測器 - 使用 Isolation Forest 演算法
    """
    
    def __init__(self, contamination=0.05, random_state=42):
        """
        Args:
            contamination: 預期異常比例 (0.0 - 0.5)
            random_state: 隨機種子
        """
        self.contamination = contamination
        self.random_state = random_state
        self.model = None
        self.scaler = StandardScaler()
        self.feature_cols = []
    
    def fit_predict(self, df, feature_cols=None):
        """
        訓練模型並預測異常
        
        Args:
            df: DataFrame with features
            feature_cols: 要使用的特徵欄位列表，若為 None 則自動偵測數值欄位
            
        Returns:
            DataFrame with 'is_anomaly' column added
        """
        if feature_cols is None:
            # 自動選擇數值欄位，排除已知的衍生欄位
            exclude_patterns = ['label', 'is_anomaly', 'predicted']
            feature_cols = [c for c in df.select_dtypes(include=[np.number]).columns 
                           if not any(p in c.lower() for p in exclude_patterns)]
        
        self.feature_cols = feature_cols
        
        if not feature_cols:
            print("警告：沒有可用的特徵欄位進行異常偵測")
            df['is_anomaly'] = False
            df['anomaly_score'] = 0
            return df
        
        # 準備特徵
        X = df[feature_cols].copy()
        
        # 處理缺失值 - 使用前向填充
        X = X.ffill().bfill()
        
        # 如果仍有缺失值，填 0
        X = X.fillna(0)
        
        # 標準化
        X_scaled = self.scaler.fit_transform(X)
        
        # 訓練 Isolation Forest
        self.model = IsolationForest(
            contamination=self.contamination,
            random_state=self.random_state,
            n_estimators=100
        )
        
        predictions = self.model.fit_predict(X_scaled)
        scores = self.model.decision_function(X_scaled)
        
        # -1 表示異常, 1 表示正常
        df['is_anomaly'] = predictions == -1
        df['anomaly_score'] = scores
        
        return df
    
    def get_anomaly_periods(self, df):
        """
        取得異常時段列表
        
        Returns:
            List of (start_time, end_time) tuples
        """
        if 'is_anomaly' not in df.columns:
            return []
        
        periods = []
        in_anomaly = False
        start_time = None
        
        for idx, row in df.iterrows():
            if row['is_anomaly'] and not in_anomaly:
                # 開始新的異常區段
                in_anomaly = True
                start_time = idx
            elif not row['is_anomaly'] and in_anomaly:
                # 結束異常區段
                in_anomaly = False
                periods.append((start_time, idx))
        
        # 處理最後一個區段
        if in_anomaly:
            periods.append((start_time, df.index[-1]))
        
        return periods


class EnergyPredictor:
    """
    能耗預測模型 - 使用 Random Forest
    """
    
    def __init__(self, random_state=42):
        self.random_state = random_state
        self.model = None
        self.scaler = StandardScaler()
        self.feature_cols = []
        self.target_col = None
        self.is_trained = False
    
    def prepare_features(self, df):
        """
        準備時間特徵
        """
        df_copy = df.copy()
        
        # 時間特徵
        if df_copy.index.dtype == 'datetime64[ns]' or hasattr(df_copy.index, 'hour'):
            df_copy['hour'] = df_copy.index.hour
            df_copy['dayofweek'] = df_copy.index.dayofweek
            df_copy['is_weekend'] = df_copy.index.dayofweek >= 5
            df_copy['month'] = df_copy.index.month
        
        return df_copy
    
    def train(self, df, target_col='derived_Total_Power', feature_cols=None):
        """
        訓練預測模型
        
        Args:
            df: 訓練資料
            target_col: 目標欄位（要預測的欄位）
            feature_cols: 特徵欄位列表
        """
        if target_col not in df.columns:
            raise ValueError(f"目標欄位 '{target_col}' 不存在於資料中")
        
        self.target_col = target_col
        
        # 準備特徵
        df_prep = self.prepare_features(df)
        
        if feature_cols is None:
            # 自動選擇特徵
            exclude_patterns = [target_col, 'label', 'is_anomaly', 'anomaly_score', 'predicted']
            feature_cols = [c for c in df_prep.select_dtypes(include=[np.number]).columns 
                           if not any(p in c for p in exclude_patterns)]
        
        self.feature_cols = feature_cols
        
        # 準備訓練資料
        X = df_prep[feature_cols].copy()
        y = df_prep[target_col].copy()
        
        # 移除缺失值
        valid_mask = X.notna().all(axis=1) & y.notna()
        X = X[valid_mask]
        y = y[valid_mask]
        
        if len(X) < 10:
            raise ValueError("訓練資料不足（需要至少 10 筆有效資料）")
        
        # 標準化
        X_scaled = self.scaler.fit_transform(X)
        
        # 訓練模型
        self.model = RandomForestRegressor(
            n_estimators=100,
            random_state=self.random_state,
            n_jobs=-1
        )
        self.model.fit(X_scaled, y)
        self.is_trained = True
        
        # 計算訓練分數
        train_score = self.model.score(X_scaled, y)
        print(f"模型訓練完成。R² 分數: {train_score:.4f}")
        
        return train_score
    
    def predict(self, df):
        """
        預測能耗
        """
        if not self.is_trained:
            raise ValueError("模型尚未訓練")
        
        df_prep = self.prepare_features(df)
        
        X = df_prep[self.feature_cols].copy()
        X = X.ffill().bfill().fillna(0)
        
        X_scaled = self.scaler.transform(X)
        predictions = self.model.predict(X_scaled)
        
        df['predicted_power'] = predictions
        return df
    
    def get_feature_importance(self):
        """取得特徵重要性"""
        if not self.is_trained:
            return {}
        
        importance = dict(zip(self.feature_cols, self.model.feature_importances_))
        return dict(sorted(importance.items(), key=lambda x: x[1], reverse=True))
    
    def save_model(self, path):
        """儲存模型"""
        if not self.is_trained:
            raise ValueError("模型尚未訓練")
        
        model_data = {
            'model': self.model,
            'scaler': self.scaler,
            'feature_cols': self.feature_cols,
            'target_col': self.target_col
        }
        
        with open(path, 'wb') as f:
            pickle.dump(model_data, f)
    
    def load_model(self, path):
        """載入模型"""
        with open(path, 'rb') as f:
            model_data = pickle.load(f)
        
        self.model = model_data['model']
        self.scaler = model_data['scaler']
        self.feature_cols = model_data['feature_cols']
        self.target_col = model_data['target_col']
        self.is_trained = True


def add_time_features(df):
    """
    新增時間相關特徵到 DataFrame
    """
    df_copy = df.copy()
    
    if hasattr(df_copy.index, 'hour'):
        df_copy['feature_hour'] = df_copy.index.hour
        df_copy['feature_dayofweek'] = df_copy.index.dayofweek
        df_copy['feature_is_weekend'] = (df_copy.index.dayofweek >= 5).astype(int)
        df_copy['feature_month'] = df_copy.index.month
    
    return df_copy


def add_rolling_features(df, power_col='derived_Total_Power', windows=[4, 12, 24]):
    """
    新增滾動統計特徵
    
    Args:
        df: DataFrame
        power_col: 電力欄位名稱
        windows: 滾動視窗大小列表（以資料點數計算）
    """
    df_copy = df.copy()
    
    if power_col not in df_copy.columns:
        return df_copy
    
    for w in windows:
        df_copy[f'rolling_mean_{w}'] = df_copy[power_col].rolling(window=w, min_periods=1).mean()
        df_copy[f'rolling_std_{w}'] = df_copy[power_col].rolling(window=w, min_periods=1).std()
    
    return df_copy
