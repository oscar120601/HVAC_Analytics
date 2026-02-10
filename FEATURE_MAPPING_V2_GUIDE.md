# Feature Mapping V3 - HVAC 物理系統層級特徵分類

## 概述

Feature Mapping V3 是專為 HVAC 冰水主機系統設計的**物理系統層級特徵分類架構**，將原有的 10 個類別擴展為 **13 個標準類別**，並按照 HVAC 系統的實際物理架構進行組織。

### 為什麼要升級到 V3？

| 版本 | 類別數 | 組織方式 | 適用場景 |
|-----|-------|---------|---------|
| V1 | 7種 | 功能導向 | 基礎能耗預測 |
| V2 | 10種 | 功能導向 | 擴展監測點 |
| **V3** | **13種** | **物理系統分組** | **精細化系統分析與診斷** |

V3 的物理系統分組設計讓你能夠：
- 🔍 **精確定位問題**：快速識別是哪個子系統異常
- 📊 **分層分析**：冰水側、冷卻水側、冷卻水塔獨立分析
- 🎯 **優化控制**：針對特定設備群組進行最佳化
- 📝 **符合工程習慣**：與 HVAC 工程師的系統思維一致

---

## V3 物理系統架構

```
┌─────────────────────────────────────────────────────────────────┐
│                    HVAC 冰水主機系統                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────┐    ┌─────────────────────────────┐ │
│  │  ❄️ 冰水側系統          │    │  🔥 冷卻水側系統             │ │
│  │  (Chilled Water Side)   │    │  (Condenser Water Side)     │ │
│  │                         │    │                             │ │
│  │  • chiller (冰水機)     │◄──►│  • cw_pump (冷卻水泵)       │ │
│  │  • chw_pump (冰水泵)    │    │  • cw_temp (冷卻水溫)       │ │
│  │  • scp_pump (區域泵)    │    │  • cw_pressure (冷卻水壓)   │ │
│  │  • chw_temp (冰水溫)    │    │  • cw_flow (冷卻水流)       │ │
│  │  • chw_pressure (冰水壓)│    │                             │ │
│  │  • chw_flow (冰水流)    │    │                             │ │
│  └─────────────────────────┘    └─────────────────────────────┘ │
│              │                              │                   │
│              │      ┌─────────────┐         │                   │
│              └─────►│   冷媒循環   │◄────────┘                   │
│                     │  (Refrigerant)│                           │
│                     └──────┬──────┘                           │
│                            │                                   │
│                     ┌──────▼──────┐                           │
│                     │ 🏭 冷卻水塔  │                           │
│                     │ cooling_tower│                          │
│                     │  (散熱設備)  │                           │
│                     └─────────────┘                           │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 🌍 Environment    │    ⚡🎯 System Level                │   │
│  │ 外氣溫濕度        │    總用電 / COP / kW/RT             │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 13 個標準類別詳細說明

### ❄️ 冰水側系統 (Chilled Water Side) - 6個類別

| 類別 ID | 名稱 | 物理意義 | 典型欄位 | 單位 |
|---------|------|---------|---------|------|
| `chiller` | 冰水機 (Chiller) ❄️ | 製冷能力與運行狀態 | `CH_0_RT`, `CH_0_KW` | RT, kW |
| `chw_pump` | 冰水泵 (CHW Pump) 💧 | 一次側循環泵頻率/功率 | `CHP_01_VFD_OUT`, `CHP_01_KW` | Hz, kW |
| `scp_pump` | 區域泵/二次泵 (SCP) 🔄 | 二次側/區域泵頻率/功率 | `SCP_01_VFD_OUT`, `SCP_01_KW` | Hz, kW |
| `chw_temp` | 冰水溫度 🌡️ | 供水/回水溫度與溫差 | `CH_0_SWT`, `CH_0_RWT` | °C |
| `chw_pressure` | 冰水壓力 📊 | 供水/回水壓力與壓差 | `CHW_S_PRESSURE`, `CHW_R_PRESSURE` | kPa |
| `chw_flow` | 冰水流量 🌊 | 循環水流量 | `CHW_FLOW`, `CH_0_LPM` | LPM |

### 🔥 冷卻水側系統 (Condenser Water Side) - 4個類別

| 類別 ID | 名稱 | 物理意義 | 典型欄位 | 單位 |
|---------|------|---------|---------|------|
| `cw_pump` | 冷卻水泵 (CW Pump) 🔥 | 冷卻水循環泵頻率/功率 | `CWP_01_VFD_OUT`, `CWP_01_KW` | Hz, kW |
| `cw_temp` | 冷卻水溫度 🌡️ | 供水/回水溫度與溫差 | `CW_SYS_SWT`, `CW_SYS_RWT` | °C |
| `cw_pressure` | 冷卻水壓力 📊 | 供水/回水壓力與壓差 | `CW_S_PRESSURE`, `CW_R_PRESSURE` | kPa |
| `cw_flow` | 冷卻水流量 🌊 | 循環水流量 | `CW_FLOW`, `CW_SYS_LPM` | LPM |

### 🏭 冷卻水塔系統 (Cooling Tower) - 1個類別

| 類別 ID | 名稱 | 物理意義 | 典型欄位 | 單位 |
|---------|------|---------|---------|------|
| `cooling_tower` | 冷卻水塔 🏭 | 風扇頻率、功率、趨近溫度 | `CT_01_VFD_OUT`, `CT_01_KW`, `CT_APPROACH` | Hz, kW, °C |

### 🌍 環境參數 (Environment) - 1個類別

| 類別 ID | 名稱 | 物理意義 | 典型欄位 | 單位 |
|---------|------|---------|---------|------|
| `environment` | 環境參數 🌍 | 外氣溫度、濕度、濕球溫度 | `CT_SYS_OAT`, `CT_SYS_OAH`, `CT_SYS_WBT` | °C, % |

### ⚡🎯 系統層級 (System Level) - 1個類別

| 類別 ID | 名稱 | 物理意義 | 典型欄位 | 單位 |
|---------|------|---------|---------|------|
| `system_level` | 系統效率指標 ⚡🎯 | 總用電、COP、kW/RT | `CH_SYS_TOTAL_KW`, `SYS_COP`, `SYS_KW_RT` | kW, -, kW/RT |

---

## 三種配置方式

### 方式一：自動識別 (Auto-detect)

系統根據欄位名稱自動識別 13 個類別：

```python
from config.feature_mapping_v2 import FeatureMapping

# 自動識別所有欄位
mapping = FeatureMapping.create_from_dataframe(
    df_columns=your_columns,
    auto_patterns=True  # 使用內建 V3 識別規則
)
```

**自動識別規則範例：**

| 類別 | 識別模式 | 範例欄位 |
|-----|---------|---------|
| `chiller` | 包含 "CH_" + ("RT" 或 "KW") | `CH_0_RT`, `CH_1_KW` |
| `chw_pump` | 包含 "CHP" + ("VFD" 或 "HZ" 或 "KW") | `CHP_01_VFD_OUT` |
| `scp_pump` | 包含 "SCP" + ("VFD" 或 "HZ" 或 "KW") | `SCP_01_VFD_OUT` |
| `chw_temp` | 包含 "CHW" + "TEMP" 或 "CH_" + ("SWT"/"RWT") | `CHW_TEMP`, `CH_0_SWT` |
| `chw_pressure` | 包含 "CHW" + "PRESSURE" | `CHW_SUPPLY_PRESSURE` |
| `chw_flow` | 包含 "CHW" + "FLOW" | `CHW_FLOW_RATE` |
| `cw_pump` | 包含 "CWP" + ("VFD" 或 "HZ" 或 "KW") | `CWP_01_VFD_OUT` |
| `cooling_tower` | 包含 "CT_" + ("VFD" 或 "KW" 或 "APPROACH") | `CT_01_VFD_OUT` |
| `environment` | 包含 "OAT"/"OAH"/"WBT" | `CT_SYS_OAT` |
| `system_level` | 包含 "TOTAL" + "KW" 或 "COP" 或 "KW_RT" | `CH_SYS_TOTAL_KW` |

### 方式二：手動對應 (Manual Mapping)

在 UI 中使用多選下拉框手動分配欄位：

```python
# 在 Streamlit UI 中
for cat_id in STANDARD_CATEGORIES.keys():
    info = mapping.get_category_info(cat_id)
    selected = st.multiselect(
        f"{info['icon']} {info['name']}",
        options=available_cols,
        default=mapping.get_columns(cat_id)
    )
    mapping.set_category_columns(cat_id, selected)
```

### 方式三：萬用字元模式 (Wildcard Mode) 🆕

V3 新增萬用字元模式，支援使用 `*` 和 `?` 進行批量欄位匹配：

```python
# 萬用字元規則範例
wildcard_patterns = {
    "chiller": ["CH_*_RT", "CH_*_KW"],           # 匹配所有冰水機
    "chw_pump": ["CHP_*_VFD_OUT", "CHP_*_KW"],   # 匹配所有冰水泵
    "scp_pump": ["SCP_*_VFD_OUT", "SCP_*_KW"],   # 匹配所有區域泵
    "chw_temp": ["CH_*_SWT", "CH_*_RWT"],        # 匹配所有冰水溫度
    "cooling_tower": ["CT_*_VFD_OUT", "CT_*_KW"] # 匹配所有冷卻水塔
}

# 套用萬用字元規則
mapping.apply_wildcard_patterns(wildcard_patterns, df_columns)
```

**萬用字元符號：**
- `*` - 匹配任意字元序列（0個或多個）
- `?` - 匹配單一任意字元

---

## 實際範例：完整的 V3 映射配置

```python
from config.feature_mapping_v2 import FeatureMapping

# 案場的完整監控點列表（含 13 個類別）
columns = [
    # ❄️ chiller - 冰水機
    "CH_0_RT", "CH_1_RT", "CH_2_RT", "CH_3_RT",
    "CH_0_KW", "CH_1_KW", "CH_2_KW", "CH_3_KW",
    
    # 💧 chw_pump - 冰水泵
    "CHP_01_VFD_OUT", "CHP_02_VFD_OUT",
    "CHP_01_KW", "CHP_02_KW",
    
    # 🔄 scp_pump - 區域泵
    "SCP_01_VFD_OUT", "SCP_02_VFD_OUT",
    "SCP_01_KW", "SCP_02_KW",
    
    # 🌡️ chw_temp - 冰水溫度
    "CH_0_SWT", "CH_0_RWT",
    "CH_1_SWT", "CH_1_RWT",
    
    # 📊 chw_pressure - 冰水壓力
    "CHW_SUPPLY_PRESSURE", "CHW_RETURN_PRESSURE",
    
    # 🌊 chw_flow - 冰水流量
    "CHW_FLOW",
    
    # 🔥 cw_pump - 冷卻水泵
    "CWP_01_VFD_OUT", "CWP_02_VFD_OUT",
    "CWP_01_KW", "CWP_02_KW",
    
    # 🌡️ cw_temp - 冷卻水溫度
    "CW_SYS_SWT", "CW_SYS_RWT",
    
    # 📊 cw_pressure - 冷卻水壓力
    "CW_SUPPLY_PRESSURE", "CW_RETURN_PRESSURE",
    
    # 🌊 cw_flow - 冷卻水流量
    "CW_FLOW",
    
    # 🏭 cooling_tower - 冷卻水塔
    "CT_01_VFD_OUT", "CT_02_VFD_OUT",
    "CT_01_KW", "CT_02_KW",
    "CT_APPROACH_TEMP",
    
    # 🌍 environment - 環境參數
    "CT_SYS_OAT", "CT_SYS_OAH", "CT_SYS_WBT",
    
    # ⚡🎯 system_level - 系統層級
    "CH_SYS_TOTAL_KW",
]

# 方法 1: 自動識別
mapping = FeatureMapping.create_from_dataframe(columns)

# 方法 2: 使用萬用字元
wildcard_rules = {
    "chiller": ["CH_*_RT", "CH_*_KW"],
    "chw_pump": ["CHP_*_VFD_OUT", "CHP_*_KW"],
    "scp_pump": ["SCP_*_VFD_OUT"],
    "chw_temp": ["CH_*_SWT", "CH_*_RWT"],
    "cw_pump": ["CWP_*_VFD_OUT", "CWP_*_KW"],
    "cooling_tower": ["CT_*_VFD_OUT", "CT_*_KW"],
    "system_level": ["CH_SYS_TOTAL_KW"],
}
mapping.apply_wildcard_patterns(wildcard_rules, columns)

# 查看結果
print(f"總共 {len(mapping.get_all_categories())} 個類型")
for cat_id, cols in mapping.get_all_categories().items():
    if cols:
        info = mapping.get_category_info(cat_id)
        print(f"{info['icon']} {info['name']}: {len(cols)} 欄位")
```

**輸出：**
```
總共 13 個類型
❄️ 冰水機 (Chiller): 8 欄位
💧 冰水泵 (CHW Pump): 4 欄位
🔄 區域泵 (SCP Pump): 2 欄位
🌡️ 冰水溫度 (CHW Temperature): 4 欄位
📊 冰水壓力 (CHW Pressure): 2 欄位
🌊 冰水流量 (CHW Flow): 1 欄位
🔥 冷卻水泵 (CW Pump): 4 欄位
🌡️ 冷卻水溫度 (CW Temperature): 2 欄位
📊 冷卻水壓力 (CW Pressure): 2 欄位
🌊 冷卻水流量 (CW Flow): 1 欄位
🏭 冷卻水塔 (Cooling Tower): 5 欄位
🌍 環境參數 (Environment): 3 欄位
⚡🎯 系統效率 (System Level): 1 欄位
```

---

## JSON 配置範例（V3 格式）

```json
{
  "version": "3.0",
  "organization": "hvac_physical_system",
  
  "chilled_water_side": {
    "chiller": ["CH_0_RT", "CH_0_KW", "CH_1_RT", "CH_1_KW"],
    "chw_pump": ["CHP_01_VFD_OUT", "CHP_02_VFD_OUT"],
    "scp_pump": ["SCP_01_VFD_OUT", "SCP_02_VFD_OUT"],
    "chw_temp": ["CH_0_SWT", "CH_0_RWT"],
    "chw_pressure": ["CHW_SUPPLY_PRESSURE", "CHW_RETURN_PRESSURE"],
    "chw_flow": ["CHW_FLOW"]
  },
  
  "condenser_water_side": {
    "cw_pump": ["CWP_01_VFD_OUT", "CWP_02_VFD_OUT"],
    "cw_temp": ["CW_SYS_SWT", "CW_SYS_RWT"],
    "cw_pressure": ["CW_SUPPLY_PRESSURE", "CW_RETURN_PRESSURE"],
    "cw_flow": ["CW_FLOW"]
  },
  
  "cooling_tower": {
    "cooling_tower": ["CT_01_VFD_OUT", "CT_02_VFD_OUT", "CT_APPROACH_TEMP"]
  },
  
  "environment": {
    "environment": ["CT_SYS_OAT", "CT_SYS_OAH", "CT_SYS_WBT"]
  },
  
  "system_level": {
    "system_level": ["CH_SYS_TOTAL_KW"]
  },
  
  "custom_categories": {
    "valve": ["CHW_VALVE_01", "CHW_VALVE_02"]
  },
  
  "wildcard_patterns": {
    "chiller": ["CH_*_RT", "CH_*_KW"],
    "chw_pump": ["CHP_*_VFD_OUT"],
    "scp_pump": ["SCP_*_VFD_OUT"]
  },
  
  "category_metadata": {
    "chiller": {
      "name": "冰水機 (Chiller)",
      "icon": "❄️",
      "unit": "RT/kW",
      "description": "冰水主機製冷能力與功率"
    },
    "scp_pump": {
      "name": "區域泵 (SCP)",
      "icon": "🔄",
      "unit": "Hz/kW",
      "description": "二次側/區域循環泵"
    }
  }
}
```

---

## Target 選擇說明

在 V3 中，Target（預測目標）可以是：

| Target 類型 | 說明 | 典型欄位 | 適用模型 |
|------------|------|---------|---------|
| **總用電功率** | 系統總功耗 | `CH_SYS_TOTAL_KW` | 能耗預測 |
| **COP (性能係數)** | 製冷效率 | `SYS_COP`, `CH_0_COP` | 效率優化 |
| **kW/RT (單位冷噸能耗)** | 系統效率指標 | `SYS_KW_RT` | 效率基準 |

```python
# 設定不同類型的 Target
mapping.set_target_column("CH_SYS_TOTAL_KW")   # 預測總用電
mapping.set_target_column("SYS_COP")           # 預測 COP
mapping.set_target_column("SYS_KW_RT")         # 預測 kW/RT
```

---

## 從 V2 遷移到 V3

### 類別對照表

| V2 類別 | V3 類別 | 遷移說明 |
|--------|--------|---------|
| `load` | `chiller` | 負載欄位移至 chiller |
| `chw_pump` | `chw_pump` | 不變 |
| `cw_pump` | `cw_pump` | 不變 |
| `ct_fan` | `cooling_tower` | 更名為 cooling_tower |
| `temperature` | `chw_temp` + `cw_temp` | 拆分為冰水和冷卻水溫度 |
| `pressure` | `chw_pressure` + `cw_pressure` | 拆分為冰水和冷卻水壓力 |
| `flow` | `chw_flow` + `cw_flow` | 拆分為冰水和冷卻水流量 |
| `power` | `chiller` + `chw_pump` + `cw_pump` + `cooling_tower` | 分散至各設備類別 |
| `environment` | `environment` | 不變 |
| `target` | `system_level` | 更名為 system_level |

### 遷移腳本範例

```python
from config.feature_mapping_v2 import FeatureMapping

# 載入舊版 V2 JSON
import json
with open('v2_mapping.json') as f:
    v2_config = json.load(f)

# 建立 V3 映射
v3_mapping = FeatureMapping()

# 遷移欄位
v3_mapping.set_category_columns('chiller', v2_config.get('load_cols', []))
v3_mapping.set_category_columns('chw_pump', v2_config.get('chw_pump_hz_cols', []))
v3_mapping.set_category_columns('cw_pump', v2_config.get('cw_pump_hz_cols', []))
v3_mapping.set_category_columns('cooling_tower', v2_config.get('ct_fan_hz_cols', []))
# ... 繼續遷移其他類別

# 儲存為 V3 格式
v3_mapping.save('v3_mapping.json', version='3.0')
```

---

## 總結

### V3 核心優勢

1. **物理系統分組**：按 HVAC 實際架構組織，符合工程思維
2. **13 個標準類別**：涵蓋冰水側、冷卻水側、冷卻水塔、環境、系統層級
3. **萬用字元模式**：支援 `*` 和 `?` 批量匹配，簡化大量欄位配置
4. **靈活 Target**：支援總用電、COP、kW/RT 等多種預測目標
5. **向後相容**：可讀取 V2 配置並自動遷移

### 建議做法

- **新案場**：直接使用 V3 自動識別或萬用字元模式
- **現有案場**：使用遷移腳本將 V2 配置升級至 V3
- **大量欄位**：優先使用萬用字元模式（`CH_*_RT`、`CHP_*_KW`）
- **自定義需求**：使用 `add_custom_category()` 擴展

---

**文件版本**: V3.0  
**更新日期**: 2026-02-10  
**適用系統**: HVAC Analytics ETL Pipeline
