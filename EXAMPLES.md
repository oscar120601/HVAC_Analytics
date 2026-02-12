# HVAC Analytics - 使用範例

本文件提供 HVAC Analytics 系統的實際使用範例。

## 環境設置

```bash
# 安裝依賴
pip install -r requirements.txt

# 驗證安裝
python -m pytest tests/ -v
```

## CLI 使用範例

### 1. 解析原始報表

```bash
# 解析單一檔案
python main.py parse data/CGMH-TY/TI_ANDY_SCHEDULER_USE_REPORT_01-01-17_15-10.csv \
    --output_file=data/parsed/cgmh_2017_01.csv

# 檢視解析結果
python -c "import polars as pl; df = pl.read_csv('data/parsed/cgmh_2017_01.csv'); print(df.head())"
```

### 2. 資料清洗

```bash
# 清洗資料（重採樣至 5 分鐘）
python main.py clean data/parsed/cgmh_2017_01.csv \
    --output_file=data/clean/cgmh_2017_01_clean.csv \
    --resample_interval=5m
```

### 3. 訓練能耗預測模型

```bash
# 訓練 XGBoost 模型
python main.py train data/clean/cgmh_2017_01_clean.csv \
    --model_output=models/cgmh_energy_model.pkl \
    --test_size=0.2 \
    --target_mape=0.05

# 模型會自動評估並報告：
# - MAPE (目標 < 5%)
# - RMSE
# - R²
# - 特徵重要性
```

### 4. 執行最佳化

```bash
# 找出最佳設備頻率設定
python main.py optimize \
    models/cgmh_energy_model.pkl \
    '{"chw_pump_hz": 50.0, "cw_pump_hz": 48.0, "tower_fan_hz": 45.0}' \
    '{"load_rt": 520, "temp_db_out": 88.0, "rh_out": 65.0}' \
    --method=slsqp \
    --output_file=results/optimization_result.json

# 輸出範例：
# Optimal Setpoints:
#   chw_pump_hz         : 42.50 Hz
#   cw_pump_hz          : 45.30 Hz
#   tower_fan_hz        : 48.20 Hz
# 
# Performance:
#   Baseline Power      : 285.40 kW
#   Optimized Power     : 272.15 kW
#   Savings             : 13.25 kW (4.64%)
```

### 5. 完整流程（一次執行）

```bash
# 從原始資料到訓練模型
python main.py pipeline data/CGMH-TY/TI_ANDY_SCHEDULER_USE_REPORT_01-01-17_15-10.csv \
    --model_output=models/auto_trained_model.pkl
```

## Python API 使用範例

### 基本使用

```python
from src.etl.parser import ReportParser
from src.etl.cleaner import DataCleaner
from src.models.energy_model import ChillerEnergyModel
from src.optimization.optimizer import ChillerOptimizer

# 1. 解析資料
parser = ReportParser()
df = parser.parse_file("data/raw/report.csv")

# 2. 清洗資料（基礎清洗）
cleaner = DataCleaner(resample_interval="5m")
df_clean = cleaner.clean_data(df)

# 2a. 進階清洗（啟用物理驗證）
df_clean = cleaner.clean_data(
    df,
    apply_steady_state=True,      # 穩態檢測
    apply_heat_balance=True,      # 熱平衡驗證
    apply_affinity_laws=True,     # 親和力定律檢查
    filter_invalid=True           # 移除無效資料
)

# 3. 訓練模型
model = ChillerEnergyModel(target_mape=0.05)
metrics = model.train(df_clean, test_size=0.2)
print(f"Model MAPE: {metrics['mape']:.2%}")

# 4. 儲存模型
model.save_model("models/my_model.pkl")

# 5. 載入模型並預測
loaded_model = ChillerEnergyModel()
loaded_model.load_model("models/my_model.pkl")
predictions = loaded_model.predict(df_clean)
```

### 最佳化範例

```python
import polars as pl
from src.optimization.optimizer import ChillerOptimizer, OptimizationConstraints

# 定義預測函數
def power_predictor(features):
    # 使用已訓練的模型進行預測
    df = pl.DataFrame([features])
    return model.predict(df)[0]

# 設定限制條件
constraints = OptimizationConstraints(
    min_pressure_diff=5.0,    # psi
    min_return_temp=42.0,     # °F
    min_frequency=30.0,       # Hz
    max_frequency=60.0        # Hz
)

# 建立最佳化器
optimizer = ChillerOptimizer(
    power_predictor=power_predictor,
    constraints=constraints
)

# 執行最佳化
current_setpoints = {
    'chw_pump_hz': 50.0,
    'cw_pump_hz': 48.0,
    'tower_fan_hz': 45.0
}

context = {
    'load_rt': 520,
    'temp_db_out': 88.0,
    'rh_out': 65.0,
    'supply_temp': 44.0
}

result = optimizer.optimize_slsqp(current_setpoints, context)

print(f"最佳設定: {result.optimal_setpoints}")
print(f"節能: {result.savings_kw:.2f} kW ({result.savings_pct:.2f}%)")
print(f"限制條件滿足: {result.constraints_satisfied}")
```

## 測試


```bash
# 執行所有測試
python -m pytest tests/ -v

# 執行特定測試
python -m pytest tests/test_etl_integration.py -v
python -m pytest tests/test_energy_model.py -v

# 檢視測試覆蓋率
python -m pytest tests/ --cov=src --cov-report=html
```

## 常見問題

### Q: MAPE 超過 5% 怎麼辦？
A: 
1. 增加訓練資料量
2. 調整 XGBoost 超參數（`model_params`）
3. 檢查特徵工程（是否有重要特徵遺漏）
4. 使用 `get_feature_importance()` 分析特徵

### Q: 最佳化結果違反限制條件
A: 
1. 檢查 `OptimizationConstraints` 設定是否合理
2. 使用 `optimize_global()` 代替 `optimize_slsqp()`
3. 調整懲罰係數

### Q: 如何處理缺失值？
A: DataCleaner 自動處理：
- 時間戳缺失：移除該列
- 數值缺失 < 30%：使用平均值填補
- 數值缺失 >= 30%：該欄位不使用於訓練

## 效能建議

- 使用 Polars lazy execution 處理大檔案
- 批次處理時啟用平行化
- 模型訓練使用 GPU（如果可用）
- 定期重新訓練模型以適應季節變化
