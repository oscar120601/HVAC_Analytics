# HVAC Analytics - Core Engine

> 空調節能系統核心引擎 - 資料清洗與能源最佳化建議

**專案狀態**: ✅ Sprint 3.1 Feature Engineer v1.4 完成 | Sprint 3.2 Model Training v1.4 待開始  
**最後更新**: 2026-03-03

---

## 📊 專案概覽

...[unchanged middle ignored, wait, I should replace exactly]
Let's do two replacements because `multi_replace_file_content` is better for non-contiguous changes.

## 📊 專案概覽

HVAC-1 是一個專注於資料清洗與離線能源最佳化建議的空調節能系統，採用嚴格契約導向設計與 SSOT 原則。

### 核心資料流

```
Raw Data → Parser → Cleaner → BatchProcessor → FeatureEngineer → ModelTraining → Optimization
                ↑              ↑                                      ↓              ↓
        Feature Annotation    Topology Context                  Model Registry    Continual Learning
        (Excel → YAML SSOT)   (GNN Adjacency)                   Index             (GEM + Drift Detection)
```

### 設計原則

| 原則 | 說明 |
|:-----|:-----|
| **契約導向設計** | 嚴格定義模組間介面與檢查點 (E000-E999) |
| **單一真相源** | 所有配置與常數集中管理 |
| **Foundation First** | 基礎設施優先，確保下游模組有穩固依賴 |
| **Fail Fast** | 寧可終止流程，也不傳遞可疑資料 |

---

## 🎯 功能狀態

| 階段 | 模組 | 狀態 | 測試 |
|:---:|:---|:---:|:---:|
| Sprint 1 | Interface Contract v1.2 | ✅ 已完成 | 35/35 通過 |
| Sprint 1 | System Integration v1.2 | ✅ 已完成 | 35/35 通過 |
| Sprint 1 | Feature Annotation v1.4 | ✅ PRD 完成 | 拓樸感知 |
| Sprint 2 | Parser v2.2 | ✅ 已完成 | 29/29 通過 |
| Sprint 2 | Cleaner v2.2 | ✅ 已完成 | 26/26 通過 🟢 A級 |
| Sprint 2 | BatchProcessor v1.3 | ✅ 已完成 | 32/32 通過 |
| **Phase 0** | **v1.4 Retrofit** | ✅ **已完成** | ETL 拓樸貫通 |
| Sprint 3 | **Feature Engineer v1.4** | ✅ **已完成** | **拓樸感知 + GNN 輸出** |
| Sprint 3 | Model Training v1.4 | ⏳ 待開發 | Physics Loss |
| Sprint 4 | Continual Learning v1.1 | ⏳ 待開發 | GEM + Drift |
| Sprint 4 | Optimization v1.2 | ⏳ 待開發 | CL 整合 |

**累計測試**: 140+ 項全部通過 ✅

---

## 🚀 快速開始

### 安裝依賴

```bash
pip install -r requirements.txt
```

### 執行互動式 ETL 測試工具

```bash
# 1. 啟動後端伺服器
uvicorn tools.demo.test_server:app --reload --port 8000

# 2. 用瀏覽器開啟 tools/demo/tester.html
# 3. 依序執行 Step 1 → Step 2 → Step 3 → Step 4
```

### 程式化使用

```python
from src.container import ETLContainer

# 初始化完整 ETL 管道
container = ETLContainer(site_id="demo_site")
container.initialize_all()

# 取得元件
parser = container.get_parser()
cleaner = container.get_cleaner()
config = container.get_config()
```

---

## 📁 專案結構

```
HVAC-1/
├── src/                        # 核心源碼
│   ├── container.py            # ETLContainer DI 容器
│   ├── context.py              # PipelineContext 時間基準
│   ├── features/               # Feature Annotation v1.4
│   ├── etl/                    # ETL 管道
│   │   ├── parser/             # Parser V2.2 模組化
│   │   ├── cleaner.py          # DataCleaner v2.2
│   │   ├── batch_processor.py  # BatchProcessor v1.3
│   │   ├── feature_engineer.py # Feature Engineer v1.4 🆕
│   │   └── config_models.py    # SSOT 配置模型
│   ├── training/               # 模型訓練 🆕
│   │   ├── gnn_trainer.py      # Multi-Task GNN Trainer
│   │   ├── physics_loss.py     # 物理守恆損失
│   │   └── base_trainer.py     # 訓練器基礎
│   └── utils/                  # 工具函式
├── config/                     # 配置檔案
│   ├── features/               # Feature Annotation YAML
│   └── site_templates.yaml     # 案場範本
├── tools/                      # 工具鏈
│   ├── demo/                   # 互動測試 UI
│   │   ├── tester.html         # ETL 測試網頁
│   │   └── test_server.py      # FastAPI 後端
│   └── features/               # Feature Annotation 工具
│       ├── wizard.py           # Wizard CLI
│       └── excel_to_yaml.py    # 轉換器
├── tests/                      # 單元測試
├── docs/                       # 專案文件
│   ├── 專案任務排程/           # 任務排程與執行摘要
│   ├── Interface Contract/     # Interface Contract v1.2
│   ├── 測試工具說明/           # 互動測試工具說明
│   ├── Feature Annotation/     # Feature Annotation v1.4
│   ├── feature_engineering/    # Feature Engineer v1.4
│   ├── Model_Training/         # Model Training v1.4
│   └── Continual_Learning/     # Continual Learning v1.1
└── main.py                     # CLI 主程式
```

---

## 📚 文件索引

| 文件 | 說明 |
|:-----|:-----|
| [📋 完整任務排程](docs/專案任務排程/專案任務排程文件.md) | Sprint 1-5 詳細任務與時程 |
| [📋 Sprint 2 審查報告](docs/專案任務排程/Sprint_2_Review_Report.md) | Parser/Cleaner/BatchProcessor 審查結果 |
| [📖 Interface Contract v1.2](docs/Interface%20Contract/PRD_Interface_Contract_v1.2.md) | 錯誤代碼體系 E000-E999 |
| [📖 Feature Annotation v1.4](docs/Feature%20Annotation%20Specification/PRD_Feature_Annotation_Specification_V1.4.md) | 拓樸感知規格 |
| [📖 互動測試工具說明](docs/測試工具說明/Interactive_ETL_Tester.md) | tester.html 使用指南 |
| [🎨 Demo 展示](tools/demo/index.html) | Sprint 1 & 2 成果展示 |

---

## 🛠️ 核心功能

### Parser V2.2 - 模組化解析

支援多格式 CSV 解析，採用 Strategy Pattern 架構：

```python
from src.etl.parser import ParserFactory

# 自動偵測格式
parser = ParserFactory.auto_detect("data.csv")
df = parser.parse_file("data.csv")

# 明確指定 Siemens Scheduler 格式
parser = ParserFactory.create_parser("siemens_scheduler")
```

**支援格式**: 通用 CSV | Siemens Scheduler Report | 自動偵測

### Cleaner V2.2 - 語意感知清洗

- **時區強制轉換**: 輸出必為 UTC/ns
- **語意感知清洗**: 依 device_role 調整閾值
- **設備邏輯預檢**: E350 設備違規檢測
- **Schema 淨化**: E500 防護確保敏感欄位不外洩

### Feature Engineer v1.4 - 拓樸感知特徵工程

支援 L0-L3 分層特徵生成與 GNN 資料匯出：

```python
from src.etl.feature_engineer import FeatureEngineer, run_feature_engineering
from src.etl.config_models import FeatureEngineeringConfig

# 配置
config = FeatureEngineeringConfig(
    site_id="demo_site",
    lag_intervals=[1, 2, 4, 8],
    rolling_windows=[4, 16, 32],
    gnn_enabled=True
)

# 執行特徵工程
result = run_feature_engineering(
    manifest_path="output/manifest.json",
    site_id="demo_site",
    output_dir="output/features/",
    config=config
)

# 取得 GNN 資料
gnn_data = result["gnn_data"]
print(f"鄰接矩陣形狀: {gnn_data['adjacency_matrix'].shape}")
print(f"3D Tensor 形狀: {gnn_data['tensor_3d'].shape}")  # (T, N, F)
```

**特徵分層**:

- **L0**: 原始特徵 (直接從資料讀取)
- **L1**: 統計特徵 (Lag, Rolling, Diff, 時間特徵)
- **L2**: 拓樸特徵 (上游設備聚合: mean/max/min/std)
- **L3**: 控制特徵 (Sensor-Setpoint 偏差)

**GNN 輸出**:

- 鄰接矩陣 (NxN)
- 3D Tensor (Time, Nodes, Features)
- 設備節點特徵
- Node Types 列表

### Feature Annotation v1.4

Excel → YAML 單向轉換，支援拓樸註記：

```bash
# 產生 Excel 範本
python tools/features/wizard.py --site demo_site --csv data.csv --excel features.xlsx

# 轉換為 YAML
python tools/features/excel_to_yaml.py --input features.xlsx --output config/features/sites/demo_site.yaml
```

---

## 🧪 測試

```bash
# 執行所有測試
pytest tests/ -v

# 執行特定模組測試
pytest tests/test_parser_v21.py -v
pytest tests/test_cleaner_v22.py -v
pytest tests/test_batch_processor_v13.py -v
pytest tests/test_feature_engineer_v14.py -v  # 🆕 Feature Engineer v1.4
```

---

## 🔗 錯誤代碼速查

| 範圍 | 類別 |
|:---:|:---|
| E000-E099 | 系統級錯誤 (時間基準、上下文) |
| E100-E199 | Parser 錯誤 (編碼、時區、標頭) |
| E200-E299 | 資料品質錯誤 (缺漏、異常、未來資料) |
| E300-E349 | Feature Engineer 輸入錯誤 (E301-E306) 🆕 v1.4 |
| E350-E399 | 設備驗證錯誤 (E350 設備邏輯違規) |
| E400-E499 | 配置錯誤 (SSOT、同步檢查) |
| E500-E599 | 安全錯誤 (device_role 外洩) |
| E600-E699 | 特徵工程錯誤 |
| E700-E799 | 模型訓練錯誤 |
| **E750-E759** | **GNN 拓樸錯誤** 🆕 v1.4 |
| **E800-E829** | **持續學習錯誤** 🆕 v1.4 |
| **E840-E859** | **最佳化錯誤** 🆕 v1.4 |
| E900-E999 | 整合錯誤 (特徵對齊、契約違反) |

---

## 📅 近期更新

### [v1.8.0] - 2026-03-03 (Interactive ETL Tester 介面對接與進階架構規劃)

- ✅ **Interactive ETL Tester 升級** - 深度對接 Feature Engineer v1.4
  - 修正 Polars 新版 API 產生的邊界錯誤 (`the truth value of a Series is ambiguous` 等)
  - UI 介面可視化輸出: 支援記憶體優化指標 (Float32 降級比率)、缺失值體檢
  - GNN 資料結構預覽: 顯示 3D Tensor `(T, N, F)` 與鄰接矩陣預覽
- ✅ **測試平台進階架構藍圖 (Sprint 3~5)** - 更新 `Interactive_ETL_Tester.md`
  - 規劃 Time-travel 模擬器 (支援 CL 漂移檢測) 與全域錯誤合規面板

### [v1.7.0] - 2026-03-02 (Sprint 3.1 完工與交付)

- ✅ **Feature Engineer v1.4 完成** - 實作拓樸感知與控制語意特徵工程
  - 核心架構：L0-L3 分層特徵生成 (時間序列 → Lag/Rolling → 拓樸聚合 → 控制偏差)
  - 基礎設施：新增 `TopologyManager`, `ControlSemanticsManager`
  - 模型支援：GNN 專用資料匯出，包括鄰接矩陣 (Adjacency Matrix)、3D Tensor `(T, N, F)`，及相關設備特徵 (Node Types)
  - 安全與效能：實作 Data Leakage (資料洩露) 嚴格預防，並整合 Polars LazyFrame 記憶體優化與 Float32 降級
  - 品質保證：完成 `tests/test_feature_engineer_v14.py` 單元與端到端測試，邊界防護落實

### [v1.6.0] - 2026-03-02 (Phase 0 Retrofit)

- ✅ **Phase 0 ETL 管線全線貫通** - 順利吞吐 GNN 資料
  - 錯誤重定義：實現 Interface Contract v1.2，釋放並重配 E750-E759 (GNN)、E800-E829 (CL)、E840-E859 (OPT) 保留位
  - 相容性修復：解決舊版 Parser, Cleaner, BatchProcessor 丟失 `topology` 與 `control_semantics` 型別及誤殺問題
  - 測試修正：6 項新整合測試 `test_v14_topology_pipeline.py` 通過，確保 Parquet 無損存放拓樸陣列
- ✅ Interactive ETL Tester v1.6 - 新增 GNN 拓樸摘要顯示面板

### [v1.5.0] - 2026-02-25

- ✅ Parser V2.2 模組化重構完成
- ✅ Interactive ETL Tester V1.5 - Step 1→2 無縫整合

---

## 👥 貢獻

本專案採用嚴格的程式碼審查流程，所有變更需通過：

1. 單元測試 (>80% 覆蓋率)
2. 整合測試
3. 程式碼審查 (A級標準)

---

## 📄 授權

[License Information]
