# Feature Mapping V2 - 擴展特徵類型指南

## 為什麼原來是7種類型？

原來的7種類型是根據**冰水主機系統的物理架構**設計的：

| 類型 | 設備群組 | 物理意義 | 為什麼需要 |
|-----|---------|---------|-----------|
| **負載 (Load)** | 冷凍機 | 製冷能力 (RT) | 預測能耗的主要驅動力 |
| **冷凍泵 (CHW)** | 冷凍水幫浦 | 輸送冷凍水 (Hz) | 影響能耗 + 可優化控制 |
| **冷卻泵 (CW)** | 冷卻水幫浦 | 輸送冷卻水 (Hz) | 影響能耗 + 可優化控制 |
| **冷卻塔 (CT)** | 冷卻塔風扇 | 散熱 (Hz) | 影響能耗 + 可優化控制 |
| **溫度 (Temp)** | 溫度感測器 | 系統狀態 (°C) | 熱力學狀態變數 |
| **環境 (Env)** | 外氣監測 | 外部條件 (°C/%) | 外部擾動因素 |
| **目標 (Target)** | 電表 | 預測目標 (kW) | 模型輸出 |

這是**物理模型驅動**的設計，涵蓋了冰水主機系統的所有關鍵設備群組。

---

## V2 新增哪些類型？

Feature Mapping V2 內建 **10種標準類型**：

### 原有7種
1. 🏭 **load** - 負載 (RT)
2. 💧 **chw_pump** - 冷凍泵 (Hz)
3. 🌊 **cw_pump** - 冷卻泵 (Hz)
4. 🌀 **ct_fan** - 冷卻塔 (Hz)
5. 🌡️ **temperature** - 溫度 (°C)
6. 🌍 **environment** - 環境 (°C/%)
7. 🎯 **target** - 目標 (kW)

### 新增3種
8. 📊 **pressure** - 壓力 (kPa)
9. 🌊 **flow** - 流量 (LPM/GPM)
10. ⚡ **power** - 設備耗電 (kW)

---

## 如何增加更多類型？

### 方式一：使用現有的 Standard Categories

```python
from src.config.feature_mapping_v2 import FeatureMapping

# 建立映射時會自動識別新增的類型
mapping = FeatureMapping.create_from_dataframe(
    df_columns=your_columns,
    auto_patterns={
        "pressure": ("壓力", ["PRESSURE", "PSI", "KPA", "BAR"]),
        "flow": ("流量", ["FLOW", "LPM", "GPM"]),
        "power": ("耗電", ["POWER", "KW"])
    }
)
```

### 方式二：動態新增自定義類型

```python
from src.config.feature_mapping_v2 import FeatureMapping

# 建立基礎映射
mapping = FeatureMapping()

# 動態新增「壓力」類型
mapping.add_custom_category(
    category_id="pressure",           # 唯一識別碼
    columns=["CHW_PRESSURE", "CW_PRESSURE", "PUMP_PRESSURE"],
    name="壓力 (Pressure)",            # 顯示名稱
    icon="📊",                        # UI 圖示
    unit="kPa",                       # 單位
    description="水系統壓力監測"       # 描述
)

# 動態新增「流量」類型
mapping.add_custom_category(
    category_id="flow_rate",
    columns=["CHW_FLOW", "CW_FLOW", "CHILLED_WATER_FLOW"],
    name="流量 (Flow Rate)",
    icon="🌊",
    unit="LPM",
    description="水流量監測"
)

# 動態新增「閥門開度」類型
mapping.add_custom_category(
    category_id="valve_position",
    columns=["CHW_VALVE", "CW_VALVE", "BYPASS_VALVE"],
    name="閥門開度 (Valve Position)",
    icon="🔧",
    unit="%",
    description="閥門開度控制"
)
```

---

## 實際範例：完整的多類型映射

```python
from src.config.feature_mapping_v2 import FeatureMapping

# 案場的完整監控點列表
columns = [
    # 原有欄位
    "CH_0_RT", "CH_1_RT", "CH_2_RT", "CH_3_RT",
    "CHP_01_VFD_OUT", "CHP_02_VFD_OUT",
    "CWP_01_VFD_OUT", "CWP_02_VFD_OUT",
    "CT_01_VFD_OUT", "CT_02_VFD_OUT",
    "CH_0_SWT", "CH_0_RWT", "CW_SYS_SWT", "CW_SYS_RWT",
    "CT_SYS_OAT", "CT_SYS_OAH", "CT_SYS_WBT",
    "CH_SYS_TOTAL_KW",
    
    # 新增欄位：壓力
    "CHW_SUPPLY_PRESSURE", "CHW_RETURN_PRESSURE",
    "CW_SUPPLY_PRESSURE", "CW_RETURN_PRESSURE",
    
    # 新增欄位：流量
    "CHW_FLOW_RATE", "CW_FLOW_RATE",
    
    # 新增欄位：個別設備耗電
    "CH_0_KW", "CH_1_KW", "CH_2_KW", "CH_3_KW",
    "CHP_01_KW", "CHP_02_KW",
    
    # 新增欄位：閥門開度
    "CHW_VALVE_01", "CHW_VALVE_02",
    "CW_VALVE_01", "CW_VALVE_02",
]

# 自動識別
mapping = FeatureMapping.create_from_dataframe(columns)

# 手動新增自定義類型（如果自動識別沒抓到）
mapping.add_custom_category(
    category_id="valve",
    columns=["CHW_VALVE_01", "CHW_VALVE_02", "CW_VALVE_01", "CW_VALVE_02"],
    name="閥門開度 (Valve)",
    icon="🔧",
    unit="%",
    description="閥門開度監測"
)

# 查看結果
print(f"總共 {len(mapping.get_all_categories())} 個類型")
for cat_id, cols in mapping.get_all_categories().items():
    if cols:
        info = mapping.get_category_info(cat_id)
        print(f"{info['icon']} {info['name']}: {len(cols)} 欄位")
```

**輸出：**
```
總共 11 個類型
🏭 負載 (Load): 4 欄位
💧 冷凍泵 (CHW Pumps): 2 欄位
🌊 冷卻泵 (CW Pumps): 2 欄位
🌀 冷卻塔 (CT Fans): 2 欄位
🌡️ 溫度 (Temperatures): 4 欄位
🌍 環境 (Environment): 3 欄位
📊 壓力 (Pressure): 4 欄位
🌊 流量 (Flow): 2 欄位
⚡ 設備耗電 (Device Power): 6 欄位
🔧 閥門開度 (Valve): 4 欄位
```

---

## 在 UI 中使用 V2

### 更新 etl_ui.py 的 import

```python
# 從舊版改為新版
# from config.feature_mapping import FeatureMapping
from config.feature_mapping_v2 import FeatureMapping, STANDARD_CATEGORIES
```

### 動態類型選擇器

```python
# 在批次處理後顯示所有類型（包含自定義）
mapping = st.session_state.batch_feature_mapping

for cat_id, cols in mapping.get_all_categories().items():
    if cols:  # 只顯示有資料的類型
        info = mapping.get_category_info(cat_id)
        
        st.markdown(f"**{info['icon']} {info['name']}**")
        st.caption(f"{info['description']} ({info['unit']})")
        
        # 多選下拉框
        selected = st.multiselect(
            f"選擇{info['name']}欄位",
            options=available_cols,
            default=cols,
            key=f"select_{cat_id}"
        )
        mapping.set_category_columns(cat_id, selected)
```

---

## JSON 配置範例

儲存時會包含所有自定義類型：

```json
{
  "load_cols": ["CH_0_RT", "CH_1_RT"],
  "chw_pump_hz_cols": ["CHP_01_VFD_OUT"],
  "cw_pump_hz_cols": ["CWP_01_VFD_OUT"],
  "ct_fan_hz_cols": ["CT_01_VFD_OUT"],
  "temp_cols": ["CH_0_SWT"],
  "env_cols": ["CT_SYS_OAT", "CT_SYS_OAH"],
  "target_col": "CH_SYS_TOTAL_KW",
  
  "custom_categories": {
    "pressure": ["CHW_PRESSURE", "CW_PRESSURE"],
    "flow": ["CHW_FLOW", "CW_FLOW"],
    "valve": ["CHW_VALVE_01", "CW_VALVE_01"]
  },
  
  "category_metadata": {
    "pressure": {
      "name": "壓力 (Pressure)",
      "icon": "📊",
      "unit": "kPa",
      "description": "水系統壓力監測"
    },
    "flow": {
      "name": "流量 (Flow)",
      "icon": "🌊",
      "unit": "LPM",
      "description": "水流量監測"
    },
    "valve": {
      "name": "閥門開度 (Valve)",
      "icon": "🔧",
      "unit": "%",
      "description": "閥門開度監測"
    }
  }
}
```

---

## 常見的自定義類型建議

| 類型 ID | 名稱 | 適用情境 | 範例欄位 |
|--------|------|---------|---------|
| `pressure` | 壓力 | 有壓力感測器 | `CHW_PRESSURE`, `PUMP_PRESSURE` |
| `flow` | 流量 | 有流量計 | `CHW_FLOW`, `FLOW_METER_01` |
| `power` | 設備耗電 | 個別設備電表 | `CH_0_KW`, `PUMP_KW` |
| `valve` | 閥門開度 | 有控制閥門 | `CHW_VALVE`, `BYPASS_VALVE` |
| `damper` | 風門開度 | 空調箱系統 | `OA_DAMPER`, `RA_DAMPER` |
| `fan_speed` | 風機轉速 | 送風機系統 | `AHU_FAN_SPEED` |
| `level` | 水位 | 冷卻水塔水槽 | `CT_BASIN_LEVEL` |
| `vibration` | 振動 | 設備監測 | `PUMP_VIBRATION` |

---

## 總結

**為什麼是7種？** - 因為這是冰水主機系統的標準物理架構。

**可以增加嗎？** - **當然可以！** Feature Mapping V2 支援：

1. **10種內建標準類型**（新增 pressure, flow, power）
2. **無限自定義類型** - 使用 `add_custom_category()`
3. **完整的元資料管理** - 名稱、圖示、單位、描述
4. **自動識別模式** - 可配置的自動檢測規則

**建議做法：**
- 先使用 `create_from_dataframe()` 自動識別
- 再使用 `add_custom_category()` 補充非標準類型
- 最後用 `save()` 儲存配置供日後使用
