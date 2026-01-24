import pandas as pd
import numpy as np


def get_cols_by_keyword(df, keywords):
    """
    Helper to find columns matching a list of keywords.
    """
    found_cols = []
    if not keywords:
        return found_cols
        
    for col in df.columns:
        for kw in keywords:
            if kw in col:
                found_cols.append(col)
                # break inner loop to avoid adding same col twice if it matches multiple keywords
                break 
    return list(set(found_cols))

def clean_data(df, config=None):
    """
    Cleans the merged dataframe.
    """
    print("Starting data cleaning...")
    
    # Defaults
    keywords_hum = ["OAH", "Humidity"]
    keywords_valve = [".CV"]
    
    if config and 'tag_keywords' in config:
        keywords_hum = config['tag_keywords'].get('out_air_humidity', keywords_hum)
        keywords_valve = config['tag_keywords'].get('valve_opening', keywords_valve)

    # 1. Drop rows where index (timestamp) is NaT
    df = df[df.index.notna()]
    
    # 2. Handle missing values
    # For HVAC data, forward fill is often appropriate for short gaps (sensors hold value)
    # But for now, let's just keep NaNs or interpolate
    # df = df.interpolate(method='time', limit=4) # limit to 1 hour (if 15 min data)
    
    # 3. Clean Outliers (Simple Range Checks)
    # Humidity should be 0-100
    hum_cols = get_cols_by_keyword(df, keywords_hum)
    for col in hum_cols:
        df.loc[(df[col] < 0) | (df[col] > 100), col] = np.nan
            
    # Valve opening 0-100
    valve_cols = get_cols_by_keyword(df, keywords_valve)
    for col in valve_cols:
         df.loc[(df[col] < 0) | (df[col] > 100), col] = np.nan
    
    print("Data cleaning complete.")
    return df

def calculate_dewpoint(T, RH):
    """
    Approximation of Dew Point from Temp (C) and RH (%).
    Magnus formula.
    """
    # Constants
    b = 17.62
    c = 243.12
    
    gamma = (b * T / (c + T)) + np.log(RH / 100.0)
    dewpoint = (c * gamma) / (b - gamma)
    return dewpoint

def calculate_wetbulb(T, RH):
    """
    Stull's formula for Wet Bulb Temperature (C).
    T in Celsius, RH in %
    """
    tw = T * np.arctan(0.151977 * (RH + 8.313659)**0.5) + \
         np.arctan(T + RH) - np.arctan(RH - 1.676331) + \
         0.00391838 * (RH**1.5) * np.arctan(0.023101 * RH) - 4.686035
    return tw

def feature_engineering(df, config=None):
    """
    Adds derived features like Wet Bulb, Dew Point.
    """
    print("Starting feature engineering...")
    
    # Defaults
    keywords_oat = ["OAT"]
    keywords_oah = ["OAH"]
    keywords_power = ["KWH"]
    
    if config and 'tag_keywords' in config:
        keywords_oat = config['tag_keywords'].get('out_air_temp', keywords_oat)
        keywords_oah = config['tag_keywords'].get('out_air_humidity', keywords_oah)
        keywords_power = config['tag_keywords'].get('power_kwh', keywords_power)
    
    # Check if we have OAT and OAH
    oat_cols = get_cols_by_keyword(df, keywords_oat)
    oah_cols = get_cols_by_keyword(df, keywords_oah)
    
    oat_col = oat_cols[0] if oat_cols else None
    oah_col = oah_cols[0] if oah_cols else None
        
    if oat_col and oah_col:
        print(f"Found OAT: {oat_col}, OAH: {oah_col}. Calculating Psychrometrics.")
        
        T = df[oat_col]
        RH = df[oah_col]
        
        df['derived_OA_DewPoint'] = calculate_dewpoint(T, RH)
        df['derived_OA_WetBulb'] = calculate_wetbulb(T, RH)
        
    else:
        print("OAT/OAH columns not found. Skipping Psychrometrics.")
        
    # Calculate Total Power if possible
    # Sum all columns containing 'KWH'
    kwh_cols = get_cols_by_keyword(df, keywords_power)
    if kwh_cols:
        df['derived_Total_Power'] = df[kwh_cols].sum(axis=1)
        print(f"Calculated Total Power from {len(kwh_cols)} sensors.")
        
    return df

def run_pipeline(raw_df, config=None):
    df = clean_data(raw_df, config)
    df = feature_engineering(df, config)
    df = add_ml_features(df)
    return df


def add_ml_features(df):
    """
    新增機器學習相關特徵
    """
    # 時間特徵
    if hasattr(df.index, 'hour'):
        df['feature_hour'] = df.index.hour
        df['feature_dayofweek'] = df.index.dayofweek
        df['feature_is_weekend'] = (df.index.dayofweek >= 5).astype(int)
        df['feature_month'] = df.index.month
    
    # 滾動統計特徵 (如果有總耗電量欄位)
    if 'derived_Total_Power' in df.columns:
        # 4 筆 = 1 小時 (15分鐘資料)
        df['rolling_mean_1h'] = df['derived_Total_Power'].rolling(window=4, min_periods=1).mean()
        df['rolling_std_1h'] = df['derived_Total_Power'].rolling(window=4, min_periods=1).std()
        
        # 24 筆 = 6 小時
        df['rolling_mean_6h'] = df['derived_Total_Power'].rolling(window=24, min_periods=1).mean()
    
    return df
