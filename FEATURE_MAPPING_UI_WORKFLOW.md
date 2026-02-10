# Feature Mapping UI 工作順序與使用指南

## 工作順序總覽

| 順序 | 任務 | 狀態 |
|:---:|------|:----:|
| **1** | 更新 FeatureMapping 支援環境參數 (env_cols) | ✅ 完成 |
| **2** | 更新 ModelConfig 和 ChillerEnergyModel | ✅ 完成 |
| **3** | 建立 CLI 映射編輯器 | ✅ 完成 |
| **4** | 整合至 ETL UI | ✅ 完成 |
| **5** | 移至最佳化模擬模式 | ✅ 完成 |

---

## UI 結構更新

### 特徵映射位置變更

```
舊結構（已淘汰）：
├── 側邊欄
│   └── 🗺️ 特徵映射 (Feature Mapping)
│       ├── 選擇映射配置
│       ├── 查看當前映射
│       └── 萬用字元模式

新結構（當前）：
├── ⚡ 最佳化模擬模式
│   ├── 🗺️ 特徵映射 (第一個分頁)
│   ├── 🎯 即時最佳化
│   ├── 📊 特徵重要性
│   ├── 📈 歷史追蹤
│   └── 🔧 模型訓練
```

### 為什麼這樣改變？

1. **職責分離**：批次處理專注於資料處理，特徵映射專注於模型準備
2. **工作流程順暢**：載入資料 → 配置映射 → 訓練模型 → 最佳化
3. **減少混淆**：統一在最佳化模擬模式下完成所有模型相關設定

---

## 新增功能

### 1. 環境參數支援

新增 `environment` 類別，包含以下監控點：

| 欄位名稱 | 說明 |
|---------|------|
| `CT_SYS_OAT` | 外氣溫度 (Outdoor Air Temperature) |
| `CT_SYS_OAH` | 外氣濕度 (Outdoor Air Humidity) |
| `CT_SYS_WBT` | 外氣濕球溫度 (Wet Bulb Temperature) |

### 2. 自動識別功能

在「🗺️ 特徵映射」分頁中，點擊「🤖 執行自動識別」後，系統會自動識別：

| 類別 | 圖示 | 說明 | 識別模式 |
|-----|------|------|---------|
| 冰水機 | ❄️ | 冷凍機負載 (RT) | RT |
| 冰水泵 | 💧 | 冷凍水幫浦頻率 (Hz) | CHP + VFD |
| 區域泵 | 🔄 | 區域泵頻率 (Hz) | SCP + VFD |
| 冷卻水泵 | 🔥 | 冷卻水幫浦頻率 (Hz) | CWP + VFD |
| 冷卻水塔 | 🏭 | 冷卻塔風扇頻率 (Hz) | CT_ + VFD |
| 冰水溫度 | 🌡️ | 冰水溫度 (°C) | SWT/RWT |
| 冷卻水溫度 | 🌡️ | 冷卻水溫度 (°C) | CW + SWT/RWT |
| 冰水壓力 | 📊 | 冰水壓力 (kPa) | CHW + PRESSURE |
| 冷卻水壓力 | 📊 | 冷卻水壓力 (kPa) | CW + PRESSURE |
| 冰水流量 | 🌊 | 冰水流量 (LPM/GPM) | CHW + FLOW |
| 冷卻水流量 | 🌊 | 冷卻水流量 (LPM/GPM) | CW + FLOW |
| 環境參數 | 🌍 | 外氣參數 (°C/%) | OAT/OAH/WBT |
| 系統層級 | ⚡ | 總用電功率 (kW) | TOTAL_KW |

---

## 快速使用指南

### 第一次使用（新流程）

```
1. 啟動 UI
   streamlit run etl_ui.py

2. 載入資料
   → 選擇「批次處理（整個資料夾）」或「單一檔案」
   → 執行資料處理

3. 配置特徵映射
   → 切換到「⚡ 最佳化模擬」模式
   → 進入「🗺️ 特徵映射」分頁
   → 點擊「🤖 執行自動識別」
   → 展開「📋 當前映射配置」確認結果

4. 訓練模型
   → 進入「🔧 模型訓練」分頁
   → 輸入模型名稱
   → 點擊「開始訓練」

5. 執行最佳化
   → 進入「🎯 即時最佳化」分頁
   → 調整參數並執行最佳化
```

### 切換不同案場

```
1. 回到「批次處理」模式載入新案場資料
2. 切換到「⚡ 最佳化模擬」模式
3. 在「🗺️ 特徵映射」分頁重新執行自動識別
4. 繼續訓練或最佳化
```

---

## 配置文件範例

### 完整的 feature_mapping.json (V3 格式)

```json
{
  "version": "3.0",
  "chilled_water_side": {
    "chiller": ["CH_0_RT", "CH_1_RT", "CH_2_RT", "CH_3_RT"],
    "chw_pump": ["CHP_01_VFD_OUT", "CHP_02_VFD_OUT", "CHP_03_VFD_OUT", "CHP_04_VFD_OUT"],
    "scp_pump": ["SCP_01_VFD_OUT", "SCP_02_VFD_OUT"],
    "chw_temp": ["CH_0_SWT", "CH_0_RWT", "CH_1_SWT", "CH_1_RWT"],
    "chw_pressure": ["CHW_S_PRESSURE", "CHW_R_PRESSURE"],
    "chw_flow": ["CHW_FLOW"]
  },
  "condenser_water_side": {
    "cw_pump": ["CWP_01_VFD_OUT", "CWP_02_VFD_OUT", "CWP_03_VFD_OUT", "CWP_04_VFD_OUT"],
    "cw_temp": ["CW_SYS_SWT", "CW_SYS_RWT"],
    "cw_pressure": ["CW_S_PRESSURE", "CW_R_PRESSURE"],
    "cw_flow": ["CW_FLOW"]
  },
  "cooling_tower": {
    "cooling_tower": ["CT_01_VFD_OUT", "CT_02_VFD_OUT", "CT_03_VFD_OUT", "CT_04_VFD_OUT"]
  },
  "environment": {
    "environment": ["CT_SYS_OAT", "CT_SYS_OAH", "CT_SYS_WBT"]
  },
  "system_level": {
    "system_level": ["CH_SYS_TOTAL_KW"]
  }
}
```

---

## 建立的新檔案

| 檔案 | 說明 |
|------|------|
| `src/config/feature_mapping.py` | 特徵映射核心模組（V3，含環境參數） |
| `src/config/feature_mapping_v2.py` | V2 版本（按物理系統分組） |
| `mapping_editor_ui.py` | 獨立的 Streamlit Web UI（可選使用） |

---

## 驗證結果

```
[OK] FeatureMapping V3 loaded
[OK] Auto-detect working
[OK] Integrated into Optimization Mode
[OK] Model training using mapping
```

---

## 下一步建議

1. **測試新流程**
   ```bash
   streamlit run etl_ui.py
   ```
   - 載入資料 → 最佳化模擬 → 特徵映射 → 訓練

2. **驗證特徵重要性**
   - 訓練完成後查看「📊 特徵重要性」分頁
   - 確認環境參數 (CT_SYS_OAT/OAH/WBT) 出現在排名中

3. **回饋調整**
   - 根據使用體驗調整界面文案
   - 回報任何識別錯誤的欄位模式

---

**更新日期**: 2026-02-10  
**版本**: V3.1  
**更新說明**: 特徵映射已移至「⚡ 最佳化模擬」模式，與模型訓練流程整合
