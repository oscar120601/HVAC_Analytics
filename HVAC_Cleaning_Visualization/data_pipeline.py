import pandas as pd
import numpy as np

def clean_data(df):
    """
    Cleans the merged dataframe.
    """
    print("Starting data cleaning...")
    
    # 1. Drop rows where index (timestamp) is NaT
    df = df[df.index.notna()]
    
    # 2. Handle missing values
    # For HVAC data, forward fill is often appropriate for short gaps (sensors hold value)
    # But for now, let's just keep NaNs or interpolate
    # df = df.interpolate(method='time', limit=4) # limit to 1 hour (if 15 min data)
    
    # 3. Clean Outliers (Simple Range Checks)
    # Humidity should be 0-100
    for col in df.columns:
        if 'OAH' in col or 'Humidity' in col:
            df.loc[(df[col] < 0) | (df[col] > 100), col] = np.nan
            
    # Valve opening 0-100
    for col in df.columns:
        if '.CV' in col: 
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

def feature_engineering(df):
    """
    Adds derived features like Wet Bulb, Dew Point.
    """
    print("Starting feature engineering...")
    
    # Identify OAT (Outer Air Temp) and OAH (Humidity) columns
    # We look for columns ending in 'OAT' or 'OAH' from our parser metadata
    # Or specific column names if known. 
    # Based on file inspection: 'Point_27' -> 'OAH', 'Point_28' -> 'OAT' in air_temp file
    
    # We need to find the specific column names in the merged DF.
    # The merged DF will have columns like 'OAT', 'OAH', 'AH01-1.CV', etc.
    
    # Check if we have OAT and OAH
    oat_col = None
    oah_col = None
    
    for col in df.columns:
        if 'OAT' in col: oat_col = col
        if 'OAH' in col: oah_col = col
        
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
    kwh_cols = [c for c in df.columns if 'KWH' in c]
    if kwh_cols:
        df['derived_Total_Power'] = df[kwh_cols].sum(axis=1)
        print(f"Calculated Total Power from {len(kwh_cols)} sensors.")
        
    return df

def run_pipeline(raw_df):
    df = clean_data(raw_df)
    df = feature_engineering(df)
    return df
