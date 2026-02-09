# Feature Mapping 總結與擴展指南

## 問題一：為什麼是7種類型？

### 答案：物理模型驅動設計

這7種類型對應**冰水主機系統的關鍵設備群組**：

| # | 類型 | 設備 | 為什麼需要？ |
|---|------|------|------------|
| 1 | **負載** | 冷凍機 | 能耗的主要驅動力 |
| 2 | **冷凍泵** | CHW Pumps | 可優化的能耗設備 |
| 3 | **冷卻泵** | CW Pumps | 可優化的能耗設備 |
| 4 | **冷卻塔** | CT Fans | 可優化的能耗設備 |
| 5 | **溫度** | 溫度感測器 | 熱力學狀態變數 |
| 6 | **環境** | 外氣監測 | 外部擾動因素 |
| 7 | **目標** | 總電表 | 模型預測目標 |

這是**專為冰水主機優化問題設計**的最小完備集合。

---

## 問題二：可以增加更多類型嗎？

### 答案：當然可以！

我建立了 **Feature Mapping V2** (`src/config/feature_mapping_v2.py`)，支援：

### 內建10種標準類型

原有7種 + 新增3種：
- **pressure** - 壓力 (kPa)
- **flow** - 流量 (LPM/GPM)  
- **power** - 設備耗電 (kW)

### 無限制自定義類型

```python
from src.config.feature_mapping_v2 import FeatureMapping

mapping = FeatureMapping()

# 新增任意類型
mapping.add_custom_category(
    category_id="valve",              # 唯一ID
    columns=["VALVE_01", "VALVE_02"], # 欄位列表
    name="閥門開度",                   # 顯示名稱
    icon="🔧",                        # UI圖示
    unit="%",                         # 單位
    description="控制閥門開度"         # 描述
)
```

---

## 常見擴展類型建議

| 類型ID | 名稱 | 適用情境 | 單位 |
|--------|------|---------|------|
| `valve` | 閥門開度 | 有控制閥門 | % |
| `damper` | 風門開度 | 空調箱系統 | % |
| `fan_speed` | 風機轉速 | 送風機 | Hz/RPM |
| `level` | 水位 | 冷卻水塔水槽 | %/m |
| `vibration` | 振動 | 設備監測 | mm/s |
| `status` | 狀態 | 設備開關 | ON/OFF |

---

## 如何使用 V2？

### 1. 自動識別（含新類型）

```python
mapping = FeatureMapping.create_from_dataframe(
    df_columns=your_columns,
    auto_patterns={
        "pressure": ("壓力", ["PRESSURE", "PSI", "KPA"]),
        "valve": ("閥門", ["VALVE", "DAMPER"])
    }
)
```

### 2. 手動新增自定義類型

```python
mapping.add_custom_category(
    category_id="my_custom_type",
    columns=["COL1", "COL2"],
    name="我的自定義類型",
    icon="📦",
    unit="unit",
    description="描述"
)
```

### 3. 在 UI 中動態顯示

```python
# 顯示所有類型（包含自定義）
for cat_id, cols in mapping.get_all_categories().items():
    info = mapping.get_category_info(cat_id)
    st.markdown(f"**{info['icon']} {info['name']}**")
    st.multiselect(..., options=cols)
```

---

## 檔案說明

| 檔案 | 說明 |
|------|------|
| `src/config/feature_mapping.py` | 原版（7種類型） |
| `src/config/feature_mapping_v2.py` | 增強版（10+種類型，支援自定義） |
| `example_feature_mapping_v2.py` | 使用範例 |
| `FEATURE_MAPPING_V2_GUIDE.md` | 完整指南 |

---

## 建議

**如果你需要更多類型：**

1. **短期**：使用 `feature_mapping_v2.py` 的 `add_custom_category()`
2. **長期**：將常用的自定義類型加入 `STANDARD_CATEGORIES`

**是否要替換原版？**

- 如果只是**偶爾**需要額外類型 → 維持現狀，手動新增
- 如果**經常**需要多種類型 → 可考慮升級到 V2

---

## 快速測試

```python
# 測試 V2 是否可用
import sys
sys.path.insert(0, 'src')
from config.feature_mapping_v2 import FeatureMapping

mapping = FeatureMapping.create_from_dataframe([
    "CH_0_RT", "CHP_01_VFD_OUT",
    "CHW_PRESSURE",  # 壓力
    "CHW_FLOW"       # 流量
])

print(f"識別到 {len(mapping.get_all_categories())} 個類型")
for cat_id, cols in mapping.get_all_categories().items():
    if cols:
        print(f"  {cat_id}: {len(cols)} 欄位")
```

執行結果應該顯示壓力和流量被自動識別！
