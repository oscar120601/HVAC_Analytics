# 資料持久化實作計劃

## 問題定義

目前 HVAC Analytics 專案使用 **記憶體狀態管理** (`app_state` 字典)，造成以下問題：

1. **資料遺失風險**: 伺服器重啟後，所有上傳的資料和處理結果消失
2. **無法多使用者**: 不同使用者無法共享或查看歷史處理結果
3. **缺乏版本控制**: 無法追蹤資料處理與模型訓練的歷史記錄
4. **擴展性受限**: 無法水平擴展 (Scale-out)

---

## User Review Required

> [!IMPORTANT]
> **技術選擇決策**
> 
> 本計劃建議使用 **混合式持久化策略**：
> - **SQLite**: 元資料、配置、歷史記錄 (~適合單機部署)
> - **Redis**: Session 管理、資料快取
> - **檔案系統**: 大型 Parquet/CSV 檔案儲存
> 
> **替代方案**: 如果未來需要多伺服器部署，可遷移至 PostgreSQL。

> [!WARNING]
> **向後相容性**
> 
> 此變更將修改 Backend API 的資料存取層，但**不會**破壞前端 API 介面。
> 現有的 FastAPI endpoints (`/api/parse`, `/api/clean`) 保持相同的請求/回應格式。

---

## Proposed Changes

### Component 1: 資料庫層 (Database Layer)

#### [NEW] [`backend/database.py`](file:///d:/DeltaBox/oscar.chang/OneDrive%20-%20Delta%20Electronics,%20Inc/HVAC_Analytics/backend/database.py)

建立資料庫連線管理與 ORM 模型：

```python
# SQLite + SQLAlchemy ORM
# 儲存 5 張核心資料表:
# 1. upload_sessions - 上傳會話
# 2. parsed_datasets - 解析後的資料集元資料
# 3. cleaning_jobs - 清洗任務記錄
# 4. trained_models - 模型訓練歷史
# 5. optimization_runs - 最佳化執行記錄
```

**Schema 設計** (詳見下方):
- `upload_sessions`: 追蹤每次檔案上傳
- `parsed_datasets`: 儲存解析後的資料集資訊 (不儲存實際資料)
- `cleaning_jobs`: 記錄清洗參數與結果
- `trained_models`: 模型訓練的元資料 (實際模型檔案存在 `models/` 目錄)

---

#### [NEW] [`backend/models.py`](file:///d:/DeltaBox/oscar.chang/OneDrive%20-%20Delta%20Electronics,%20Inc/HVAC_Analytics/backend/models.py)

SQLAlchemy ORM 模型定義：

```python
from sqlalchemy import Column, String, Integer, Float, DateTime, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class UploadSession(Base):
    __tablename__ = 'upload_sessions'
    id = Column(String, primary_key=True)  # UUID
    created_at = Column(DateTime)
    files_count = Column(Integer)
    total_rows = Column(Integer)
    status = Column(String)  # 'uploaded', 'parsed', 'cleaned'

class ParsedDataset(Base):
    __tablename__ = 'parsed_datasets'
    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey('upload_sessions.id'))
    file_path = Column(String)  # Parquet 檔案路徑
    row_count = Column(Integer)
    column_count = Column(Integer)
    columns = Column(JSON)  # 欄位名稱列表
    created_at = Column(DateTime)
```

---

#### [NEW] [`backend/storage.py`](file:///d:/DeltaBox/oscar.chang/OneDrive%20-%20Delta%20Electronics,%20Inc/HVAC_Analytics/backend/storage.py)

資料檔案儲存管理器：

```python
# 管理大型 DataFrame 的儲存與讀取
# 策略: 使用 Parquet 格式壓縮儲存
# 目錄結構:
#   data/sessions/{session_id}/
#     ├── parsed_data.parquet
#     └── cleaned_data.parquet
```

---

### Component 2: Redis Session 管理

#### [NEW] [`backend/redis_client.py`](file:///d:/DeltaBox/oscar.chang/OneDrive%20-%20Delta%20Electronics,%20Inc/HVAC_Analytics/backend/redis_client.py)

Redis 連線與 Session 管理：

```python
# 功能:
# 1. 快取資料預覽 (TTL: 1小時)
# 2. 追蹤進行中的處理任務
# 3. 儲存臨時狀態 (替代 app_state)
```

---

### Component 3: API 層重構

#### [MODIFY] [`backend/main.py`](file:///d:/DeltaBox/oscar.chang/OneDrive%20-%20Delta%20Electronics,%20Inc/HVAC_Analytics/backend/main.py)

**變更內容**:

1. **移除 `app_state` 字典**
   ```python
   # 刪除:
   app_state = {
       "current_df": None,
       "cleaned_df": None,
       "models": {}
   }
   ```

2. **加入資料庫依賴注入**
   ```python
   from backend.database import get_db
   from backend.storage import DataStorage
   
   @app.post("/api/parse")
   def parse_files(request: ParseRequest, db: Session = Depends(get_db)):
       # 1. 建立 UploadSession 記錄
       # 2. 解析檔案
       # 3. 儲存為 Parquet
       # 4. 建立 ParsedDataset 記錄
       # 5. 回傳 session_id 給前端
   ```

3. **修改資料讀取邏輯**
   - 從 `session_id` 查詢資料庫
   - 從 Parquet 檔案讀取 DataFrame

---

### Component 4: 配置檔案

#### [NEW] [`backend/.env.example`](file:///d:/DeltaBox/oscar.chang/OneDrive%20-%20Delta%20Electronics,%20Inc/HVAC_Analytics/backend/.env.example)

環境變數範例：

```env
DATABASE_URL=sqlite:///./hvac_analytics.db
REDIS_URL=redis://localhost:6379/0
DATA_STORAGE_PATH=./data/sessions
```

---

#### [MODIFY] [`backend/requirements.txt`](file:///d:/DeltaBox/oracle.chang/OneDrive%20-%20Delta%20Electronics,%20Inc/HVAC_Analytics/backend/requirements.txt)

新增依賴：

```txt
sqlalchemy==2.0.23
alembic==1.13.1        # Database migrations
redis==5.0.1
pyarrow==14.0.1        # Parquet support
python-dotenv==1.0.0
```

---

## 詳細資料庫 Schema

```sql
-- upload_sessions: 上傳會話
CREATE TABLE upload_sessions (
    id TEXT PRIMARY KEY,              -- UUID
    created_at TIMESTAMP,
    files_count INTEGER,
    subfolder TEXT,                   -- data/CGMH-TY/...
    total_rows INTEGER,
    status TEXT,                      -- 'uploaded', 'parsed', 'cleaned'
    metadata JSON                     -- 自由格式元資料
);

-- parsed_datasets: 解析後的資料集
CREATE TABLE parsed_datasets (
    id TEXT PRIMARY KEY,
    session_id TEXT REFERENCES upload_sessions(id),
    file_path TEXT,                   -- data/sessions/{uuid}/parsed.parquet
    row_count INTEGER,
    column_count INTEGER,
    columns JSON,                     -- ["CH_0_RT", "CH_0_KW", ...]
    created_at TIMESTAMP
);

-- cleaning_jobs: 清洗任務
CREATE TABLE cleaning_jobs (
    id TEXT PRIMARY KEY,
    dataset_id TEXT REFERENCES parsed_datasets(id),
    parameters JSON,                  -- 清洗參數 (resample_interval, etc.)
    original_rows INTEGER,
    cleaned_rows INTEGER,
    retention_rate REAL,
    output_path TEXT,                 -- cleaned.parquet 路徑
    created_at TIMESTAMP,
    status TEXT                       -- 'running', 'completed', 'failed'
);

-- trained_models: 模型訓練記錄
CREATE TABLE trained_models (
    id TEXT PRIMARY KEY,
    name TEXT,
    dataset_id TEXT REFERENCES parsed_datasets(id),
    feature_mapping JSON,             -- Feature Mapping V3 配置
    training_metrics JSON,            -- {"mape": 5.2, "r2": 0.95}
    model_file_path TEXT,             -- models/CGMH-TY/model_xxx.joblib
    created_at TIMESTAMP
);

-- optimization_runs: 最佳化執行記錄
CREATE TABLE optimization_runs (
    id TEXT PRIMARY KEY,
    model_id TEXT REFERENCES trained_models(id),
    input_data JSON,
    predicted_power REAL,
    recommendations JSON,
    created_at TIMESTAMP
);
```

---

## 實作順序

### Step 1: 設定資料庫基礎設施 (1-2 天)
1. 建立 `backend/database.py` - SQLAlchemy 連線
2. 建立 `backend/models.py` - ORM 模型
3. 建立 `backend/alembic/` - 資料庫遷移管理
4. 執行初始遷移: `alembic revision --autogenerate -m "Initial schema"`

### Step 2: 實作資料儲存層 (1-2 天)
1. 建立 `backend/storage.py` - Parquet 檔案管理
2. 測試大型 DataFrame 的存取效能

### Step 3: 重構 API - Parse Endpoint (1 天)
1. 修改 `/api/parse` 使用資料庫
2. 回傳 `session_id` 而非直接回傳資料
3. 測試向後相容性

### Step 4: 重構 API - Clean Endpoint (1 天)
1. 修改 `/api/clean` 接受 `session_id`
2. 建立 `CleaningJob` 記錄
3. 儲存清洗結果為 Parquet

### Step 5: 整合 Redis (1 天)
1. 建立 `backend/redis_client.py`
2. 實作資料預覽快取
3. 設定 TTL 策略

### Step 6: 模型歷史追蹤 (1 天)
1. 修改 `/api/models/train` 建立資料庫記錄
2. `/api/models` endpoint 從資料庫讀取

---

## Verification Plan

### Automated Tests

#### 1. 資料庫操作測試
```bash
# 檔案: backend/tests/test_database.py
# 執行:
cd backend
python -m pytest tests/test_database.py -v
```

**測試內容**:
- ✅ 建立 UploadSession 並儲存
- ✅ 查詢 ParsedDataset by session_id
- ✅ 資料庫 rollback 測試

---

#### 2. 儲存層測試
```bash
# 檔案: backend/tests/test_storage.py
# 執行:
python -m pytest tests/test_storage.py -v
```

**測試內容**:
- ✅ 儲存 Polars DataFrame 為 Parquet
- ✅ 讀取 Parquet 並驗證資料完整性
- ✅ 壓縮率測試 (Parquet vs CSV)

---

#### 3. API 整合測試
```bash
# 檔案: backend/tests/test_api_persistence.py
# 執行:
python -m pytest tests/test_api_persistence.py -v
```

**測試內容**:
- ✅ POST `/api/parse` 回傳 `session_id`
- ✅ GET `/api/data/preview?session_id=xxx` 回傳資料
- ✅ 重啟伺服器後資料仍存在

---

### Manual Verification

#### 4. 前端整合測試

**步驟**:
1. 啟動後端: `cd backend && python main.py`
2. 啟動前端: `cd frontend && npm run dev`
3. 上傳測試檔案 (使用 `data/CGMH-TY/` 中的 5 個檔案)
4. 驗證前端顯示 `session_id`
5. 重啟後端伺服器
6. 前端點擊「載入歷史資料」
7. **預期結果**: 能看到之前上傳的資料

---

#### 5. 資料庫檢查

**步驟**:
```bash
# 打開 SQLite CLI
sqlite3 backend/hvac_analytics.db

# 查詢上傳記錄
SELECT * FROM upload_sessions;

# 查詢資料集
SELECT id, session_id, row_count, column_count FROM parsed_datasets;
```

**預期結果**: 看到對應的資料庫記錄

---

#### 6. 效能基準測試

**步驟**:
```bash
# 測試大檔案處理 (214 個檔案, 72,480 rows)
cd backend
python benchmark_persistence.py
```

**預期結果**:
- Parquet 儲存時間 < 5 秒
- Parquet 讀取時間 < 2 秒
- 檔案大小壓縮率 > 70% (相較 CSV)

---

## 向後相容性說明

### API 介面變更

| Endpoint | 變更前 | 變更後 | 影響 |
|---------|-------|-------|-----|
| `POST /api/parse` | 回傳完整 DataFrame preview | 回傳 `session_id` + preview | ✅ 前端需小幅調整 |
| `GET /api/data/preview` | 無參數 (使用 app_state) | 需提供 `?session_id=xxx` | ❌ Breaking Change |
| `POST /api/clean` | 無參數 | 需提供 `session_id` in body | ❌ Breaking Change |

### 遷移策略

**選項 1: 漸進式遷移** (推薦)
- 保留 `app_state` 作為 fallback
- 如果 `session_id` 未提供，使用記憶體狀態
- 3 個月後完全移除

**選項 2: 硬遷移**
- 直接要求所有 API 提供 `session_id`
- 前端一次性更新
- 需要與前端團隊協調

---

## 風險評估

| 風險 | 影響 | 機率 | 緩解措施 |
|-----|------|------|---------|
| SQLite 效能瓶頸 | 中 | 低 | 並發量 <100 RPS 時無問題；超過則遷移 PostgreSQL |
| Parquet 相容性 | 低 | 低 | 使用標準 PyArrow，主流工具支援 |
| 資料遷移失敗 | 高 | 中 | 提供備份腳本與 rollback 程序 |
| Redis 依賴增加 | 低 | 高 | Redis 為可選服務，降級時使用本地快取 |

---

## 部署前檢查清單

- [ ] 執行所有自動化測試
- [ ] 手動驗證前端整合
- [ ] 備份現有資料
- [ ] 更新 `README.md` 環境需求
- [ ] 建立 `MIGRATION_GUIDE.md`
- [ ] 更新 Docker Compose (如果有)
- [ ] 通知前端團隊 API 變更

---

## 預估工時

- **資料庫設計與實作**: 2 天
- **API 重構**: 2-3 天
- **測試撰寫**: 1-2 天
- **文件更新**: 0.5 天
- **總計**: **5.5 - 7.5 天** (約 1.5 週)

---

**文件版本**: 1.0  
**撰寫日期**: 2026-02-11  
**審查狀態**: 待審查
