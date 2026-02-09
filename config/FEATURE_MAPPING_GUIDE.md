# Feature Mapping 特徵映射指南

這份文件說明如何自定義監控點名稱到模型特徵的映射。

## 為什麼需要 Feature Mapping？

不同案場的監控系統可能使用不同的命名規則：

| 案場 | 冷凍機負載命名 | 冷凍泵頻率命名 |
|------|--------------|---------------|
| 長庚桃園 | `CH_0_RT` | `CHP_01_VFD_OUT` |
| 案場 B | `CHILLER_01_LOAD` | `CHWP_01_HZ` |
| 案場 C | `C1_LOAD` | `PUMP_01_SPEED` |

**Feature Mapping 讓你可以指定你的監控點名稱對應到模型的哪個特徵類別。**

---

## 使用方法

### 方法一：使用預設映射 (推薦快速開始)

```bash
# 使用內建的 "cgmh_ty" 映射
python main.py train data/CGMH-TY --mapping cgmh_ty

# 使用預設映射 (等同於 cgmh_ty)
python main.py train data/CGMH-TY --mapping default
```

### 方法二：自動發現並生成映射

```bash
# 從一個 CSV 檔案自動分析並生成映射
python main.py discover_features data/sample.csv --output my_mapping.json

# 使用生成的映射進行訓練
python main.py train data/ --mapping my_mapping.json
```

### 方法三：手動建立 JSON 映射檔

建立 `my_mapping.json`：

```json
{
  "load_cols": [
    "CH_0_RT",
    "CH_1_RT"
  ],
  "chw_pump_hz_cols": [
    "CHP_01_VFD_OUT",
    "CHP_02_VFD_OUT"
  ],
  "cw_pump_hz_cols": [
    "CWP_01_VFD_OUT",
    "CWP_02_VFD_OUT"
  ],
  "ct_fan_hz_cols": [
    "CT_01_VFD_OUT",
    "CT_02_VFD_OUT"
  ],
  "temp_cols": [
    "CH_0_SWT",
    "CH_0_RWT"
  ],
  "target_col": "CH_SYS_TOTAL_KW"
}
```

然後使用：
```bash
python main.py train data/ --mapping my_mapping.json
```

---

## 程式碼中使用

### Python API

```python
from src.models.energy_model import ChillerEnergyModel
from src.config.feature_mapping import FeatureMapping

# 方式 1: 使用預設映射
model = ChillerEnergyModel(feature_mapping="cgmh_ty")

# 方式 2: 從 JSON 檔案
model = ChillerEnergyModel(feature_mapping="config/my_mapping.json")

# 方式 3: 直接建立 FeatureMapping
mapping = FeatureMapping(
    load_cols=["CH_0_RT", "CH_1_RT"],
    chw_pump_hz_cols=["CHP_01_VFD_OUT"],
    cw_pump_hz_cols=["CWP_01_VFD_OUT"],
    ct_fan_hz_cols=["CT_01_VFD_OUT"],
    temp_cols=["CH_0_SWT", "CH_0_RWT"],
    target_col="CH_SYS_TOTAL_KW"
)
model = ChillerEnergyModel(feature_mapping=mapping)

# 訓練
df = ...  # 你的資料
model.train(df)

# 查看特徵重要性
importance = model.get_feature_importance()
```

### 從 DataFrame 自動生成映射

```python
from src.config.feature_mapping import FeatureMapping
import polars as pl

# 讀取資料
df = pl.read_csv("data.csv")

# 根據欄位名稱自動生成映射
mapping = FeatureMapping.create_from_dataframe(
    df_columns=df.columns,
    load_pattern="RT",           # 識別負載的模式
    chw_pattern="CHP",           # 識別冷凍泵的模式
    cw_pattern="CWP",            # 識別冷卻泵的模式
    ct_pattern="CT_",            # 識別冷卻塔的模式
    temp_patterns=["SWT", "RWT", "TEMP"]  # 溫度相關模式
)

# 儲存供日後使用
mapping.save("auto_mapping.json")
```

---

## 特徵類別說明

| 類別 | 欄位名稱 | 說明 |
|------|---------|------|
| `load_cols` | 冷凍機負載 | 製冷噸數 (RT)，如 `CH_0_RT` |
| `chw_pump_hz_cols` | 冷凍水幫浦頻率 | 變頻器輸出頻率 (Hz)，如 `CHP_01_VFD_OUT` |
| `cw_pump_hz_cols` | 冷卻水幫浦頻率 | 變頻器輸出頻率 (Hz)，如 `CWP_01_VFD_OUT` |
| `ct_fan_hz_cols` | 冷卻塔風扇頻率 | 變頻器輸出頻率 (Hz)，如 `CT_01_VFD_OUT` |
| `temp_cols` | 溫度 | 水溫相關 (°C)，如 `CH_0_SWT` |
| `target_col` | 目標變數 | 總耗電量 (kW)，如 `CH_SYS_TOTAL_KW` |

---

## 預設映射列表

系統內建以下預設映射：

- `default` / `cgmh_ty`: 長庚桃園案場的命名規則
- `alternative_01`: 示範替代命名規則

查看所有預設映射：
```python
from src.config.feature_mapping import PREDEFINED_MAPPINGS

for name, mapping in PREDEFINED_MAPPINGS.items():
    print(f"{name}: {len(mapping.get_all_feature_cols())} features")
```

---

## 驗證映射

```python
from src.config.feature_mapping import FeatureMapping
import polars as pl

# 載入映射
mapping = FeatureMapping.load("my_mapping.json")

# 讀取資料
df = pl.read_csv("data.csv")

# 驗證映射是否適用於資料
result = mapping.validate_against_dataframe(df.columns)

print(f"匹配: {len(result['matched'])} 欄位")
print(f"缺失 (必要): {result['missing_required']}")
print(f"缺失 (可選): {result['missing_optional']}")
print(f"未映射的欄位: {result['available_in_df']}")
```

---

## 常見問題

### Q: 我的欄位名稱和預設不同怎麼辦？
使用 `discover_features` 命令自動分析：
```bash
python main.py discover_features data/sample.csv --output my_mapping.json
```

### Q: 可以只指定部分欄位嗎？
可以，未指定的欄位會被忽略。但建議至少包含：
- 1+ 個負載欄位 (`load_cols`)
- 1+ 個控制變數 (泵/風扇頻率)
- 目標欄位 (`target_col`)

### Q: 如何修改現有映射？
```bash
# 複製範例
cp config/examples/my_site_mapping.json my_mapping.json

# 編輯 JSON 檔案，修改欄位名稱
# 然後使用
python main.py train data/ --mapping my_mapping.json
```

### Q: 不同案場可以用不同映射嗎？
當然可以！每個案場建立自己的 JSON 映射檔：
```bash
# 案場 A
python main.py train data/site_a/ --mapping site_a_mapping.json

# 案場 B
python main.py train data/site_b/ --mapping site_b_mapping.json
```

---

## 範例映射檔

參見 `config/examples/` 目錄：
- `my_site_mapping.json` - 標準命名規則範例
- `alternative_naming.json` - 替代命名規則範例
