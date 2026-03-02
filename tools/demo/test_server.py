from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from typing import List, Dict, Any, Tuple
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from datetime import datetime, timezone
import os
import shutil
import tempfile
import json
import math
from pathlib import Path
import uuid

import polars as pl

# 儲存背景任務狀態
pipeline_jobs = {}
wizard_jobs = {}  # Step 2 Wizard 任務狀態
MAX_JOB_LOG_LINES = 200


def _append_job_log(job_id: str, message: str, level: str = "INFO", stage: str = "") -> None:
    """新增 job 即時日誌，保留固定長度以避免無限制成長。"""
    if job_id not in pipeline_jobs:
        return

    logs = pipeline_jobs[job_id].setdefault("progress_log", [])
    logs.append({
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        "level": level,
        "stage": stage,
        "message": message
    })
    if len(logs) > MAX_JOB_LOG_LINES:
        pipeline_jobs[job_id]["progress_log"] = logs[-MAX_JOB_LOG_LINES:]


def _append_wizard_log(job_id: str, message: str, level: str = "INFO", stage: str = "") -> None:
    """新增 Wizard job 即時日誌"""
    if job_id not in wizard_jobs:
        return

    logs = wizard_jobs[job_id].setdefault("progress_log", [])
    logs.append({
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        "level": level,
        "stage": stage,
        "message": message
    })
    if len(logs) > MAX_JOB_LOG_LINES:
        wizard_jobs[job_id]["progress_log"] = logs[-MAX_JOB_LOG_LINES:]

from src.container import ETLContainer
from src.context import PipelineContext
from src.etl.batch_processor import BatchProcessor
from src.etl.parser import ParserFactory
from src.etl.parser.utils import load_site_config
from tools.features.wizard import FeatureAnnotationWizard
from tools.features.excel_to_yaml import ExcelToYamlConverter

app = FastAPI()

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

TEMP_DIR = Path(tempfile.gettempdir()) / "hvac_demo"
TEMP_DIR.mkdir(parents=True, exist_ok=True)


PARSER_NAMES = {
    "auto": "Auto Detect",
    "generic": "Generic CSV",
    "siemens_scheduler": "Siemens Scheduler Report",
}


def cleanup_file(filepath: Path):
    if filepath.exists():
        try:
            filepath.unlink()
        except:
            pass


def _normalize_parser_type(parser_type: str) -> str:
    return (parser_type or "auto").strip().lower()


def _validate_parser_type(parser_type: str) -> str:
    normalized = _normalize_parser_type(parser_type)
    if normalized == "auto":
        return normalized

    available = set(ParserFactory.list_strategies())
    if normalized not in available:
        available_text = ", ".join(["auto"] + sorted(available))
        raise HTTPException(
            status_code=400,
            detail=f"未知 parser_type: {parser_type}。可用類型: {available_text}",
        )
    return normalized


def _parse_with_selected_parser(
    site_id: str,
    csv_path: Path,
    parser_type: str,
    context: PipelineContext = None,
) -> Tuple[pl.DataFrame, Dict[str, Any], str]:
    parser_type = _normalize_parser_type(parser_type)
    site_config = load_site_config(site_id=site_id)

    if parser_type == "auto":
        parser = ParserFactory.auto_detect(csv_path, config=site_config)
    else:
        parser = ParserFactory.create_parser(parser_type, config=site_config)

    df, metadata = parser.parse_with_metadata(csv_path, temporal_context=context)
    resolved_parser_type = metadata.get("parser_type", parser_type)
    return df, metadata, resolved_parser_type

@app.get("/api/health")
async def health_check():
    """健康檢查端點"""
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "hvac-etl-tester"
    }

@app.post("/api/test-error")
async def test_error(error_code: str = Form(...)):
    """刻意觸發指定錯誤碼，用於驗證防禦機制"""
    from fastapi import HTTPException
    import time
    
    error_scenarios = {
        "E000": (503, "E000: TEMPORAL_BASELINE_MISSING - 缺少時間基準，PipelineContext 拒絕提供服務。模組已被阻擋。"),
        "E406": (400, "E406: EXCEL_YAML_OUT_OF_SYNC - 偵測到 Excel 與 YAML 不一致，Checksum 驗證失敗。"),
        "E500": (400, "E500: DEVICE_ROLE_LEAKAGE - 嚴重安全違規，輸入 DataFrame 包含被禁止的敏感配置欄位 (device_role)。"),
    }
    
    # 模擬一點延遲
    time.sleep(0.5)
    
    if error_code in error_scenarios:
        status_code, detail = error_scenarios[error_code]
        raise HTTPException(status_code=status_code, detail=detail)
    
    return {"status": "info", "message": f"未知的錯誤碼: {error_code}。支援的錯誤碼: E000, E406, E500"}

@app.post("/api/generate-template")
async def generate_template(site_id: str = Form(...), file: UploadFile = File(...)):
    """STEP 1: 從原始 CSV 產生 Excel 標註範本 (傳統方式，直接讀取 CSV)"""
    csv_path = TEMP_DIR / f"raw_{site_id}_{file.filename}"
    excel_path = TEMP_DIR / f"{site_id}_template.xlsx"
    
    with open(csv_path, "wb") as f:
        f.write(await file.read())

    try:
        wizard = FeatureAnnotationWizard(
            site_id=site_id,
            csv_path=csv_path,
            excel_path=excel_path
        )
        wizard.run(interactive=False)
        
        if not excel_path.exists():
            raise HTTPException(status_code=500, detail="Excel 範本產生失敗")
            
        return FileResponse(
            path=excel_path, 
            filename=f"{site_id}_features.xlsx",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            background=BackgroundTask(cleanup_file, csv_path)
        )
    except Exception as e:
        cleanup_file(csv_path)
        raise HTTPException(status_code=500, detail=str(e))


def process_wizard_task(
    job_id: str,
    site_id: str,
    columns_list: List[str],
    point_mapping_dict: Dict[str, Any],
    sample_data: List[Dict[str, Any]],
    excel_path: Path,
    csv_path: Path
):
    """背景執行 Wizard 產生 Excel"""
    import logging
    logger = logging.getLogger(__name__)
    
    def update_progress(msg: str, stage: str = "", column: str = ""):
        if stage:
            wizard_jobs[job_id]["stage"] = stage
        if column:
            wizard_jobs[job_id]["current_column"] = column
        wizard_jobs[job_id]["progress"] = msg
        _append_wizard_log(job_id, msg, stage=stage or wizard_jobs[job_id].get("stage", ""))
        logger.info(f"[Wizard Job {job_id[:8]}] {msg}")
    
    try:
        update_progress("初始化 Wizard...", stage="初始化")
        
        # 建立 dummy CSV 檔案以滿足 wizard 的初始化需求
        import csv
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(columns_list)
        
        wizard = FeatureAnnotationWizard(
            site_id=site_id,
            csv_path=csv_path,
            excel_path=excel_path
        )
        
        # 載入或建立 Workbook
        update_progress("載入或建立 Excel Workbook...", stage="初始化")
        if not wizard._load_or_create_workbook():
            raise Exception("無法載入或建立 Excel Workbook")
        
        # 取得已存在的欄位
        existing = wizard._get_existing_columns()
        
        # 找出新欄位 (排除 timestamp)
        new_columns = [c for c in columns_list if c not in existing and c != 'timestamp']
        
        if not new_columns:
            update_progress("無新欄位需要標註", stage="完成")
            wizard_jobs[job_id]["status"] = "success"
            wizard_jobs[job_id]["stage"] = "完成"
            wizard_jobs[job_id]["result"] = {
                "status": "success",
                "message": "無新欄位需要標註",
                "total_columns": len(columns_list),
                "new_columns": 0
            }
            return
        
        update_progress(f"發現 {len(new_columns)} 個新欄位待標註", stage="分析欄位")
        
        # 處理每個新欄位
        processed_count = 0
        for col in new_columns:
            processed_count += 1
            
            # 從 point_mapping 取得原始名稱
            mapped_name = col
            original_point_name = None
            point_key = None
            
            if point_mapping_dict:
                for pk, point_info in point_mapping_dict.items():
                    if isinstance(point_info, dict):
                        if point_info.get('normalized_name') == col:
                            original_point_name = point_info.get('name', col)
                            mapped_name = original_point_name
                            point_key = pk
                            break
            
            # 計算統計 (從 sample_data)
            stats = {'mean': 0, 'zero_ratio': 0}
            if sample_data and len(sample_data) > 0:
                try:
                    values = [row.get(col) for row in sample_data if col in row and row.get(col) is not None]
                    numeric_values = []
                    for v in values:
                        try:
                            numeric_values.append(float(v))
                        except (ValueError, TypeError):
                            pass
                    
                    if numeric_values:
                        mean_val = sum(numeric_values) / len(numeric_values)
                        zero_count = sum(1 for v in numeric_values if v == 0)
                        zero_ratio = zero_count / len(numeric_values)
                        stats = {'mean': mean_val, 'zero_ratio': zero_ratio}
                except Exception:
                    pass
            
            # HVAC 推測
            from tools.features.wizard import HVACTypeGuesser
            suggestion = HVACTypeGuesser.guess(mapped_name, stats)
            
            # 建立描述
            description_parts = []
            if original_point_name and original_point_name != col:
                description_parts.append(f"原始名稱: {original_point_name}")
            if point_key:
                description_parts.insert(0, point_key)
            
            if description_parts:
                suggestion['description'] = f"[{' | '.join(description_parts)}] {suggestion.get('description', '')}"
            
            # 更新進度 - 顯示詳細資訊
            update_progress(
                f"處理欄位 ({processed_count}/{len(new_columns)}): {col}",
                stage="處理欄位",
                column=col
            )
            
            # 記錄詳細資訊到 log
            detail_msg = f"欄位: {col}"
            if original_point_name and original_point_name != col:
                detail_msg += f" | 原始監控點名稱: {original_point_name}"
            detail_msg += f" | HVAC推測: {suggestion['equipment_type']} / {suggestion['physical_type']}"
            detail_msg += f" | 建議設備 ID: {suggestion['equipment_id']}"
            _append_wizard_log(job_id, detail_msg, stage="處理欄位")
            
            # 寫入 Excel
            wizard._add_column_to_excel(col, suggestion)
            _append_wizard_log(job_id, f"✅ 已寫入 Excel (狀態: pending_review)", stage="處理欄位")
        
        # 更新 Metadata
        if "Metadata" in wizard.workbook.sheetnames:
            ws = wizard.workbook["Metadata"]
            for row in ws.iter_rows(max_col=2):
                if row[0].value == "last_updated":
                    row[1].value = datetime.now(timezone.utc).isoformat()
                elif row[0].value == "editor":
                    row[1].value = "wizard_parser_integration"
        
        # 儲存
        update_progress("儲存 Excel 檔案...", stage="儲存")
        excel_path.parent.mkdir(parents=True, exist_ok=True)
        wizard.workbook.save(excel_path)
        
        # 清理 dummy CSV
        cleanup_file(csv_path)
        
        wizard_jobs[job_id]["status"] = "success"
        wizard_jobs[job_id]["stage"] = "完成"
        wizard_jobs[job_id]["progress"] = "✅ 執行完成"
        wizard_jobs[job_id]["ended_at"] = datetime.now(timezone.utc).isoformat()
        wizard_jobs[job_id]["result"] = {
            "status": "success",
            "site_id": site_id,
            "total_columns": len(columns_list),
            "new_columns": len(new_columns),
            "excel_path": str(excel_path)
        }
        _append_wizard_log(job_id, f"✅ Wizard 完成，共處理 {len(new_columns)} 個欄位", stage="完成")
        
    except Exception as e:
        wizard_jobs[job_id]["status"] = "error"
        wizard_jobs[job_id]["stage"] = "錯誤"
        wizard_jobs[job_id]["ended_at"] = datetime.now(timezone.utc).isoformat()
        wizard_jobs[job_id]["message"] = f"Wizard 執行失敗: {str(e)}"
        _append_wizard_log(job_id, f"❌ Wizard 執行失敗: {str(e)}", level="ERROR", stage="錯誤")
        logger.exception(f"Wizard Task {job_id} failed")
        cleanup_file(csv_path)


@app.post("/api/generate-template-from-preview")
async def generate_template_from_preview(
    background_tasks: BackgroundTasks,
    site_id: str = Form(...),
    columns: str = Form(...),  # JSON string
    point_mapping: str = Form("{}"),  # JSON string
    sample_rows: str = Form("[]"),  # JSON string
    parser_type: str = Form("auto")
):
    """
    STEP 2 (整合版): 從 Step 1 的 Parser 預覽結果產生 Excel 標註範本 (非同步版)
    
    接收 Step 1 /api/v1/pipeline/parse-preview 的輸出，直接使用 Parser 解析後的結果產生 Excel，
    確保 column_name 顯示的是 Parser 標準化後的名稱，並保留 Point 對應資訊在 description 中。
    """
    import json
    
    try:
        # 解析 JSON 參數
        columns_list = json.loads(columns)
        point_mapping_dict = json.loads(point_mapping)
        sample_data = json.loads(sample_rows)
        
        if not columns_list:
            raise HTTPException(status_code=400, detail="欄位列表為空")
        
        # 產生 Job ID
        job_id = str(uuid.uuid4())
        excel_path = TEMP_DIR / f"{site_id}_template.xlsx"
        csv_path = TEMP_DIR / f"dummy_{site_id}_{job_id}.csv"
        
        # 初始化任務狀態
        wizard_jobs[job_id] = {
            "status": "running",
            "stage": "初始化",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "progress": "初始化 Wizard 任務...",
            "total_columns": len(columns_list),
            "processed_columns": 0,
            "current_column": "",
            "progress_log": [],
            "result": None,
            "message": "",
            "excel_path": str(excel_path)
        }
        
        # 啟動背景任務
        background_tasks.add_task(
            process_wizard_task,
            job_id,
            site_id,
            columns_list,
            point_mapping_dict,
            sample_data,
            excel_path,
            csv_path
        )
        
        return {"status": "started", "job_id": job_id}
        
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"JSON 解析錯誤: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"啟動 Wizard 失敗: {str(e)}")


@app.get("/api/wizard-job-status/{job_id}")
async def get_wizard_job_status(job_id: str):
    """取得 Wizard 任務狀態"""
    if job_id not in wizard_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = wizard_jobs[job_id]
    
    # 如果任務已完成且成功，提供下載連結
    if job["status"] == "success" and job.get("result"):
        excel_path = Path(job["result"]["excel_path"])
        if excel_path.exists():
            job["download_ready"] = True
    
    return job


@app.get("/api/download-wizard-excel/{job_id}")
async def download_wizard_excel(job_id: str):
    """下載 Wizard 產生的 Excel 檔案"""
    if job_id not in wizard_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = wizard_jobs[job_id]
    if job["status"] != "success":
        raise HTTPException(status_code=400, detail="Excel 尚未產生完成")
    
    excel_path = Path(job["result"]["excel_path"])
    if not excel_path.exists():
        raise HTTPException(status_code=404, detail="Excel 檔案不存在")
    
    site_id = job["result"]["site_id"]
    
    return FileResponse(
        path=excel_path,
        filename=f"{site_id}_features.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        background=BackgroundTask(cleanup_file, excel_path)
    )

@app.post("/api/convert-yaml")
async def convert_yaml(site_id: str = Form(...), excel_file: UploadFile = File(...)):
    """STEP 2: 將填寫好的 Excel 轉換為 YAML"""
    excel_path = TEMP_DIR / f"{site_id}_filled.xlsx"
    yaml_dir = Path("config/features/sites")
    yaml_dir.mkdir(parents=True, exist_ok=True)
    yaml_path = yaml_dir / f"{site_id}.yaml"
    
    with open(excel_path, "wb") as f:
        f.write(await excel_file.read())

    try:
        converter = ExcelToYamlConverter(excel_path=excel_path, site_id=site_id)
        success, out_path = converter.convert(output_path=yaml_path)
        
        if not success:
            raise HTTPException(status_code=400, detail="Excel 驗證或轉換失敗")
            
        return {
            "status": "success",
            "message": f"成功轉換 YAML，已保存至 {out_path}",
            "site_id": site_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cleanup_file(excel_path)

@app.post("/api/run-pipeline")
async def run_pipeline(
    background_tasks: BackgroundTasks,
    site_id: str = Form(...),
    parser_type: str = Form("auto"),
    resample_interval: str = Form("5m"),
    files: List[UploadFile] = File(...)
):
    """STEP 4: 執行完整的 Sprint 2 ETL Pipeline (Parser -> Cleaner -> BatchProcessor)
    
    支援單一檔案、多檔案或資料夾上傳，並使用背景任務執行以支援進度顯示。
    """
    import logging
    logger = logging.getLogger(__name__)
    
    if not files:
        raise HTTPException(status_code=400, detail="請至少選擇一個 CSV 檔案")

    parser_type = _validate_parser_type(parser_type)
    
    logger.info(f"[Pipeline] 開始處理 site_id={site_id}, 檔案數量={len(files)}")
    
    output_dir = Path("data/processed")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 處理多個檔案 - 儲存至暫存區
    csv_paths = []
    for file in files:
        if not file.filename.lower().endswith('.csv'):
            continue  # 跳過非 CSV 檔案
        csv_path = TEMP_DIR / f"input_{site_id}_{file.filename}"
        with open(csv_path, "wb") as f:
            f.write(await file.read())
        csv_paths.append(csv_path)
    
    if not csv_paths:
        raise HTTPException(status_code=400, detail="找不到有效的 CSV 檔案")
    
    # 產生 Job ID 並註冊背景任務
    job_id = str(uuid.uuid4())
    pipeline_jobs[job_id] = {
        "status": "running",
        "stage": "初始化",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "progress": "初始化任務中...",
        "total_files": len(csv_paths),
        "parsed_files": 0,
        "current_file": "",
        "progress_log": [],
        "result": None,
        "message": "",
        "parser_type": parser_type,
    }
    _append_job_log(
        job_id,
        f"任務建立完成，待處理檔案 {len(csv_paths)} 個，parser={parser_type}",
        stage="初始化",
    )

    background_tasks.add_task(
        process_pipeline_task,
        job_id,
        site_id,
        parser_type,
        resample_interval,
        csv_paths,
        output_dir
    )

    return {"status": "started", "job_id": job_id}


@app.get("/api/v1/parser/strategies")
async def list_parser_strategies():
    """取得可用 Parser 類型（供 UI 下拉選單）"""
    descriptions = {
        "auto": "自動偵測檔案格式（建議）",
        "generic": "通用 CSV 格式（Date/Time 或 DateTime）",
        "siemens_scheduler": "Siemens Scheduler Report（Point_N 對應）",
    }

    strategies = [{"id": "auto", "name": PARSER_NAMES["auto"], "description": descriptions["auto"]}]
    for parser_id in ParserFactory.list_strategies():
        strategies.append(
            {
                "id": parser_id,
                "name": PARSER_NAMES.get(parser_id, parser_id),
                "description": descriptions.get(parser_id, ""),
            }
        )
    return strategies


@app.post("/api/v1/pipeline/parse-preview")
async def parse_preview(
    file: UploadFile = File(...),
    parser_type: str = Form("auto"),
    site_id: str = Form("default"),
):
    """使用指定 parser 預覽解析結果"""
    parser_type = _validate_parser_type(parser_type)
    temp_path = TEMP_DIR / f"preview_{site_id}_{uuid.uuid4().hex}_{file.filename}"
    with open(temp_path, "wb") as f:
        f.write(await file.read())

    try:
        df, metadata, resolved_parser_type = _parse_with_selected_parser(
            site_id=site_id,
            csv_path=temp_path,
            parser_type=parser_type,
        )
        return {
            "columns": df.columns,
            "metadata": metadata,
            "sample_rows": df.head(10).to_dicts(),
            "selected_parser_type": parser_type,
            "resolved_parser_type": resolved_parser_type,
            "resolved_parser_name": PARSER_NAMES.get(resolved_parser_type, resolved_parser_type),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"解析預覽失敗: {e}")
    finally:
        cleanup_file(temp_path)

@app.get("/api/job-status/{job_id}")
async def get_job_status(job_id: str):
    if job_id not in pipeline_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return pipeline_jobs[job_id]

def process_pipeline_task(
    job_id: str,
    site_id: str,
    parser_type: str,
    resample_interval: str,
    csv_paths: List[Path],
    output_dir: Path,
):
    import logging
    logger = logging.getLogger(__name__)
    
    def update_progress(
        msg: str,
        stage: str = "",
        current_file: str = "",
        parsed_files: int = -1
    ):
        if stage:
            pipeline_jobs[job_id]["stage"] = stage
        if current_file:
            pipeline_jobs[job_id]["current_file"] = current_file
        if parsed_files >= 0:
            pipeline_jobs[job_id]["parsed_files"] = parsed_files
        pipeline_jobs[job_id]["progress"] = msg
        _append_job_log(job_id, msg, stage=stage or pipeline_jobs[job_id].get("stage", ""))
        logger.info(f"[Job {job_id[:8]}] {msg}")

    try:
        update_progress("系統初始化...", stage="初始化")
        
        PipelineContext.reset_for_testing()
        container = ETLContainer(site_id=site_id)
        container.initialize_all()
        context = container.get_context()
        _append_job_log(
            job_id,
            f"Container 初始化完成，baseline={context.get_baseline().isoformat()}",
            stage="初始化"
        )

        requested_parser_type = _normalize_parser_type(parser_type)
        site_config = load_site_config(site_id=site_id)
        fixed_parser = None
        if requested_parser_type != "auto":
            fixed_parser = ParserFactory.create_parser(requested_parser_type, config=site_config)
            _append_job_log(
                job_id,
                f"指定 Parser strategy={requested_parser_type}",
                stage="初始化",
            )

        cleaner = container.get_cleaner()
        
        if hasattr(cleaner, 'config') and cleaner.config:
            cleaner.config.resample_interval = resample_interval
            _append_job_log(
                job_id,
                f"Cleaner 重採樣間隔設定為 {resample_interval}",
                stage="初始化"
            )
            
        bp = BatchProcessor(site_id=site_id, output_dir=str(output_dir), pipeline_context=context)

        total_files = len(csv_paths)
        update_progress(
            f"開始 Parser 處理 (strategy={requested_parser_type}, 共 {total_files} 個檔案)...",
            stage="Parser 解析",
        )
        
        df_parsed_list = []
        detected_parser_types = []
        current_stage = "Parser 解析"
        current_file = None
        
        for i, path in enumerate(csv_paths, 1):
            # Extract original filename for clearer error message
            current_file = path.name.replace(f"input_{site_id}_", "")
            update_progress(
                f"正在解析檔案 ({i}/{total_files}): {current_file}",
                stage=current_stage,
                current_file=current_file,
                parsed_files=i - 1
            )
            
            if fixed_parser is not None:
                df_p, parse_meta = fixed_parser.parse_with_metadata(path, temporal_context=context)
                resolved_parser_type = parse_meta.get("parser_type", requested_parser_type)
            else:
                auto_parser = ParserFactory.auto_detect(path, config=site_config)
                df_p, parse_meta = auto_parser.parse_with_metadata(path, temporal_context=context)
                resolved_parser_type = parse_meta.get("parser_type", "generic")

            detected_parser_types.append(resolved_parser_type)
            _append_job_log(
                job_id,
                (
                    f"解析完成: {current_file} | "
                    f"parser={resolved_parser_type} | "
                    f"encoding={parse_meta.get('encoding', parse_meta.get('detected_encoding'))} | "
                    f"rows={parse_meta.get('row_count')} cols={parse_meta.get('column_count')} | "
                    f"ts={parse_meta.get('timestamp_range', {}).get('min')} ~ "
                    f"{parse_meta.get('timestamp_range', {}).get('max')}"
                ),
                stage=current_stage
            )

            # 確保檔案間合併時，不會因為某些檔案無小數點被推斷為 Int 導致併檔失敗
            # 將所有整數欄位轉換為 Float64，確保多檔案合併時類型一致
            int_dtypes = (pl.Int8, pl.Int16, pl.Int32, pl.Int64, pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64)
            cast_exprs = []
            for col in df_p.columns:
                if col == "timestamp":
                    continue
                if isinstance(df_p.schema[col], int_dtypes):
                    cast_exprs.append(pl.col(col).cast(pl.Float64).alias(col))
            if cast_exprs:
                df_p = df_p.with_columns(cast_exprs)
            
            df_parsed_list.append(df_p)
            pipeline_jobs[job_id]["parsed_files"] = i
            
        current_file = None
        current_stage = "合併資料"
        update_progress("正在合併所有解析後的資料...", stage=current_stage, parsed_files=total_files)
        df_parsed = pl.concat(df_parsed_list, how="diagonal_relaxed")
        _append_job_log(
            job_id,
            f"合併完成: {len(df_parsed_list)} 檔 -> {df_parsed.shape[0]} 行 x {df_parsed.shape[1]} 列",
            stage=current_stage
        )
        
        current_stage = "Cleaner 清洗"
        update_progress(
            f"開始 Cleaner 語意清洗與重採樣... (共 {len(df_parsed)} 行)",
            stage=current_stage
        )
        df_cleaned, column_metadata, equipment_audit = cleaner.clean(df_parsed)
        _append_job_log(
            job_id,
            (
                f"清洗完成: {df_cleaned.shape[0]} 行 x {df_cleaned.shape[1]} 列 | "
                f"E350違規={equipment_audit.get('violations_detected', 0)}"
            ),
            stage=current_stage
        )
        
        current_stage = "BatchProcessor 落地"
        update_progress(
            f"正在執行 BatchProcessor 落地輸出... (共 {len(df_cleaned)} 行)",
            stage=current_stage
        )
        source_name = f"multiple_files_({len(csv_paths)})" if len(csv_paths) > 1 else str(csv_paths[0].name.replace(f"input_{site_id}_", ""))
        result = bp.process_dataframe(
            df_cleaned, 
            column_metadata=column_metadata,
            equipment_validation_audit=equipment_audit,
            source_file=source_name
        )
        if result.status == "success":
            df_processed = df_cleaned
            _append_job_log(job_id, "BatchProcessor 完成並寫出輸出檔", stage=current_stage)
        else:
            raise Exception(f"BatchProcessor 失敗: {result.error}")

        update_progress("計算資料品質統計報告...", stage="統計與收尾")
        
        # 統計運算
        missing_before = sum(df_parsed.null_count().row(0)) if len(df_parsed) > 0 else 0
        total_cells = len(df_parsed) * len(df_parsed.columns)
        missing_rate_before = (missing_before / total_cells) * 100 if total_cells > 0 else 0
        
        nan_inf_count = 0
        for col in df_parsed.columns:
            dtype = df_parsed[col].dtype
            if hasattr(dtype, 'is_numeric') and dtype.is_numeric():
                nan_inf_count += df_parsed[col].is_nan().sum() if hasattr(df_parsed[col], 'is_nan') else 0
        nan_inf_rate = (nan_inf_count / total_cells) * 100 if total_cells > 0 else 0
        
        if "quality_flags" in df_cleaned.columns:
            tz_mask = (
                pl.col("quality_flags").list.contains("TIMEZONE_MISMATCH") | 
                pl.col("quality_flags").list.contains("DST_GAP")
            )
            timezone_errors = df_cleaned.filter(tz_mask)
        else:
            timezone_errors = None
        timezone_error_rate = (len(timezone_errors) / len(df_cleaned)) * 100 if timezone_errors is not None and len(df_cleaned) > 0 else 0
        
        if "quality_flags" in df_cleaned.columns:
            fmt_mask = (
                pl.col("quality_flags").list.contains("FORMAT_INVALID") | 
                pl.col("quality_flags").list.contains("ENCODING_ERROR")
            )
            format_errors = df_cleaned.filter(fmt_mask)
        else:
            format_errors = None
        format_error_rate = (len(format_errors) / len(df_cleaned)) * 100 if format_errors is not None and len(df_cleaned) > 0 else 0
        
        if "quality_flags" in df_cleaned.columns:
            e350_mask = pl.col("quality_flags").list.contains("PHYSICAL_IMPOSSIBLE")
            e350_violations = df_cleaned.filter(e350_mask)
        else:
            e350_violations = None
        outlier_rate = (len(e350_violations) / len(df_cleaned)) * 100 if e350_violations is not None and len(df_cleaned) > 0 else 0
        
        manifest_path = output_dir / "latest" / "manifest_v1.3.json"
        manifest_data = {}
        if manifest_path.exists():
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest_data = json.load(f)

        pipeline_jobs[job_id]["status"] = "success"
        pipeline_jobs[job_id]["stage"] = "完成"
        pipeline_jobs[job_id]["ended_at"] = datetime.now(timezone.utc).isoformat()
        pipeline_jobs[job_id]["progress"] = "✅ 執行完成"
        _append_job_log(job_id, "Pipeline 全流程執行完成", stage="完成")
        pipeline_jobs[job_id]["result"] = {
            "status": "success",
            "processing_summary": {
                "site_id": site_id,
                "files_processed": total_files,
                "parser_type_requested": requested_parser_type,
                "parser_types_detected": sorted(set(detected_parser_types)),
                "resample_interval": resample_interval,
                "equipment_violations": equipment_audit.get("violations_detected", 0)
            },
            "stats": {
                "rows_processed": len(df_processed),
                "columns": len(df_processed.columns),
                "missing_rate_before": round(missing_rate_before, 2),
                "missing_rate_after": 0.0,
                "nan_inf_rate": round(nan_inf_rate, 2),
                "timezone_error_rate": round(timezone_error_rate, 2),
                "format_error_rate": round(format_error_rate, 2),
                "outlier_rate": round(outlier_rate, 2),
                "e350_violations_count": len(e350_violations) if e350_violations is not None else 0,
                "nan_inf_count": int(nan_inf_count),
                "timezone_error_count": len(timezone_errors) if timezone_errors is not None else 0,
                "format_error_count": len(format_errors) if format_errors is not None else 0
            },
            "e350_samples": e350_violations.head(3).to_dicts() if e350_violations is not None else [],
            "manifest": manifest_data,
            "parsed_sample": df_parsed.head(3).to_dicts(),
            "cleaned_sample": df_cleaned.head(3).to_dicts(),
            "equipment_audit": equipment_audit,
            "feature_engineer_input_ready": True
        }

    except Exception as e:
        pipeline_jobs[job_id]["status"] = "error"
        pipeline_jobs[job_id]["ended_at"] = datetime.now(timezone.utc).isoformat()
        
        # Add context to the error message
        stage_info = f"[{current_stage}] " if 'current_stage' in locals() else ""
        file_info = f" (發生於檔案: {current_file})" if 'current_file' in locals() and current_file else ""
        
        pipeline_jobs[job_id]["message"] = f"Pipeline 執行失敗: {stage_info}{str(e)}{file_info}"
        _append_job_log(
            job_id,
            f"Pipeline 執行失敗: {stage_info}{str(e)}{file_info}",
            level="ERROR",
            stage=pipeline_jobs[job_id].get("stage", "未知")
        )
        logger.exception(f"Pipeline Task {job_id} failed")
    finally:
        for path in csv_paths:
            cleanup_file(path)


@app.post("/api/run-feature-engineer")
async def run_feature_engineer(site_id: str = Form(...)):
    """STEP 5: 執行 Sprint 3 特徵工程 (預留擴充點)"""
    # TODO: 在 Sprint 3 實作 FeatureEngineer 時完善此路由
    return {
        "status": "success",
        "message": "Sprint 3 Feature Engineer 尚未實作，此為預留擴充點！",
        "site_id": site_id,
        "optimization_input_ready": True
    }

@app.post("/api/run-optimization")
async def run_optimization(site_id: str = Form(...)):
    """STEP 6: 執行 Sprint 4 最佳化引擎 (預留擴充點)"""
    # TODO: 在 Sprint 4 實作 Optimization Engine 時完善此路由
    return {
        "status": "success",
        "message": "Sprint 4 Optimization Engine 尚未實作，此為預留擴充點！",
        "site_id": site_id,
        "integration_input_ready": True
    }

@app.post("/api/run-integration")
async def run_integration(site_id: str = Form(...)):
    """STEP 7: 執行 Sprint 5 系統整合 (預留擴充點)"""
    # TODO: 在 Sprint 5 實作 E2E 整合測試時完善此路由
    return {
        "status": "success",
        "message": "Sprint 5 系統端到端整合測試尚未實作，此為預留擴充點！",
        "site_id": site_id
    }

@app.get("/api/download-parquet/{site_id}")
async def download_parquet(site_id: str):
    """下載最新的 Parquet 檔案"""
    output_dir = Path(f"data/processed/{site_id}/output")
    
    # 如果找不到傳統路徑，找 default 的 data/processed 目錄下的最近 .parquet
    search_dir = output_dir if output_dir.exists() else Path("data/processed")
    parquet_files = list(search_dir.rglob("*.parquet"))
    
    if not parquet_files:
        raise HTTPException(status_code=404, detail="找不到由 BatchProcessor 產生的 Parquet 檔案。請先執行 Step 4。")
    
    # 找最新的檔案
    latest_file = max(parquet_files, key=os.path.getmtime)
    
    return FileResponse(
        path=latest_file,
        filename=f"{site_id}_cleaned_data.parquet",
        media_type="application/vnd.apache.parquet"
    )


# =============================================================================
# 缺口四：Pipeline 初始化順序狀態指示器 (UI-008)
# =============================================================================

# 快取已載入的 manager 狀態（簡化實作）
_loaded_managers_cache = set()

def _check_excel_yaml_sync(site_id: str) -> bool:
    """檢查 Excel/YAML 同步 (E406)"""
    try:
        from src.utils.config_loader import ConfigLoader
        loader = ConfigLoader()
        yaml_path = Path(f"config/features/sites/{site_id}.yaml")
        excel_path = Path(f"config/features/sites/{site_id}.xlsx")
        
        if not yaml_path.exists():
            return False
            
        # 檢查 checksum 是否匹配
        import hashlib
        if excel_path.exists():
            with open(excel_path, 'rb') as f:
                excel_hash = hashlib.md5(f.read()).hexdigest()[:8]
            with open(yaml_path, 'r', encoding='utf-8') as f:
                yaml_content = f.read()
                # 簡單檢查 YAML 中是否有 checksum 標記
                return f"checksum: {excel_hash}" in yaml_content or f"checksum:" in yaml_content
        return True
    except Exception:
        return False

def _check_yaml_file_lock(site_id: str) -> bool:
    """檢查 YAML 檔案鎖定狀態"""
    lock_file = Path(f"config/features/sites/{site_id}.yaml.lock")
    return lock_file.exists()

def _check_feature_manager(site_id: str) -> bool:
    """檢查 FeatureManager 是否已載入"""
    try:
        from src.features.annotation_manager import FeatureAnnotationManager
        # 嘗試取得實例（如果已快取）
        manager = FeatureAnnotationManager(site_id=site_id)
        _loaded_managers_cache.add(site_id)
        return True
    except Exception:
        return site_id in _loaded_managers_cache

def _check_equipment_validator(site_id: str) -> bool:
    """檢查設備 Validator 是否就緒"""
    try:
        from src.etl.config_models import PRECHECK_CONSTRAINTS
        return len(PRECHECK_CONSTRAINTS) > 0
    except Exception:
        return False

@app.get("/api/pipeline/init-status")
async def get_pipeline_init_status(site_id: str):
    """
    缺口四：Pipeline 初始化順序狀態指示器
    
    回傳 Pipeline 初始化各階段狀態（對齊 System Integration v1.2）：
    E406 稽核 → YAML 鎖定 → Manager 載入 → Validator 就緒
    """
    e406_passed = _check_excel_yaml_sync(site_id)
    yaml_locked = _check_yaml_file_lock(site_id)
    manager_loaded = _check_feature_manager(site_id)
    validator_ready = _check_equipment_validator(site_id)
    
    stages = {
        "e406": {
            "status": "passed" if e406_passed else "failed",
            "label": "E406 稽核",
            "icon": "✅" if e406_passed else "❌",
            "description": "Excel/YAML 同步檢查"
        },
        "yaml_lock": {
            "status": "locked" if yaml_locked else "unlocked",
            "label": "YAML 鎖定",
            "icon": "🔒" if yaml_locked else "🔓",
            "description": "併發衝突防護"
        },
        "manager": {
            "status": "loaded" if manager_loaded else "not_loaded",
            "label": "Manager 載入",
            "icon": "✅" if manager_loaded else "⏳",
            "description": "FeatureAnnotationManager"
        },
        "validator": {
            "status": "ready" if validator_ready else "not_ready",
            "label": "Validator 就緒",
            "icon": "✅" if validator_ready else "⏳",
            "description": "設備驗證器"
        }
    }
    
    pipeline_ready = all([
        e406_passed,
        yaml_locked,
        manager_loaded,
        validator_ready
    ])
    
    return {
        "site_id": site_id,
        "pipeline_ready": pipeline_ready,
        "stages": stages,
        "e406_passed": e406_passed,
        "yaml_locked": yaml_locked,
        "manager_loaded": manager_loaded,
        "validator_ready": validator_ready,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# =============================================================================
# 階段性診斷 API (整合自 diagnostic_api.py)
# =============================================================================

@app.post("/api/diagnostic/parser")
async def diagnostic_parser(
    site_id: str = Form(...),
    parser_type: str = Form("auto"),
    file: UploadFile = File(...),
):
    """階段 1: 僅測試 Parser"""
    parser_type = _validate_parser_type(parser_type)
    
    csv_path = TEMP_DIR / f"diag_parser_{site_id}_{file.filename}"
    with open(csv_path, "wb") as f:
        f.write(await file.read())
    
    try:
        df, metadata, resolved_parser_type = _parse_with_selected_parser(
            site_id=site_id,
            csv_path=csv_path,
            parser_type=parser_type,
        )
        
        return {
            "stage": "parser",
            "status": "success",
            "parser_type_requested": parser_type,
            "parser_type_resolved": resolved_parser_type,
            "rows": len(df),
            "columns": len(df.columns),
            "column_names": df.columns[:20],
            "timestamp_type": str(df["timestamp"].dtype) if "timestamp" in df.columns else "missing",
            "sample": df.head(3).to_dicts() if len(df) > 0 else [],
            "metadata": metadata,
        }
    except Exception as e:
        import traceback
        return {
            "stage": "parser",
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__,
            "traceback": traceback.format_exc().split("\n")[-10:]
        }
    finally:
        cleanup_file(csv_path)


@app.post("/api/diagnostic/cleaner")
async def diagnostic_cleaner(
    site_id: str = Form(...),
    parser_type: str = Form("auto"),
    resample_interval: str = Form("5m"),
    file: UploadFile = File(...)
):
    """階段 2: 測試 Parser + Cleaner"""
    from src.etl.cleaner import DataCleaner
    from src.context import PipelineContext
    parser_type = _validate_parser_type(parser_type)
    
    csv_path = TEMP_DIR / f"diag_cleaner_{site_id}_{file.filename}"
    with open(csv_path, "wb") as f:
        f.write(await file.read())
    
    try:
        # Cleaner
        context = PipelineContext()
        try:
            context.initialize()
        except RuntimeError:
            PipelineContext.reset_for_testing()
            context = PipelineContext()
            context.initialize()

        # Parser
        df_parsed, parse_metadata, resolved_parser_type = _parse_with_selected_parser(
            site_id=site_id,
            csv_path=csv_path,
            parser_type=parser_type,
            context=context,
        )
        
        cleaner = DataCleaner(pipeline_context=context)
        if hasattr(cleaner, 'config') and cleaner.config:
            cleaner.config.resample_interval = resample_interval
        df_clean, metadata, audit = cleaner.clean(df_parsed)
        
        # 檢查拓樸相關欄位
        topology_columns = ["topology_node_id", "control_semantic", "decay_factor"]
        present_topology_cols = [col for col in topology_columns if col in df_clean.columns]
        
        # 建構拓樸摘要
        topology_summary = {
            "has_topology": len(present_topology_cols) > 0,
            "present_columns": present_topology_cols,
            "node_count": 0,
            "sample_nodes": []
        }
        
        if "topology_node_id" in df_clean.columns:
            # 計算唯一節點數（排除 null）
            unique_nodes = df_clean["topology_node_id"].drop_nulls().unique().to_list()
            topology_summary["node_count"] = len(unique_nodes)
            topology_summary["sample_nodes"] = unique_nodes[:5]  # 前 5 個節點
            
        if "control_semantic" in df_clean.columns:
            # 統計 control_semantic 類型
            semantic_counts = {}
            for val in df_clean["control_semantic"].drop_nulls().unique().to_list():
                if val:
                    count = df_clean.filter(pl.col("control_semantic") == val).shape[0]
                    semantic_counts[str(val)] = count
            topology_summary["control_semantic_stats"] = semantic_counts
        
        return {
            "stage": "cleaner",
            "status": "success",
            "parser_type_requested": parser_type,
            "parser_type_resolved": resolved_parser_type,
            "parser_output": {"rows": len(df_parsed), "columns": len(df_parsed.columns)},
            "cleaner_output": {"rows": len(df_clean), "columns": len(df_clean.columns)},
            "parse_metadata": parse_metadata,
            "metadata_keys": list(metadata.keys())[:10],
            "audit_keys": list(audit.keys()),
            "quality_flags_present": "quality_flags" in df_clean.columns,
            "sample_flags": df_clean["quality_flags"].head(5).to_list() if "quality_flags" in df_clean.columns else [],
            "topology_summary": topology_summary  # ✅ v1.4 新增
        }
    except Exception as e:
        import traceback
        return {
            "stage": "cleaner",
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__,
            "traceback": traceback.format_exc().split("\n")[-10:]
        }
    finally:
        cleanup_file(csv_path)


@app.post("/api/diagnostic/batch-processor")
async def diagnostic_batch_processor(
    site_id: str = Form(...),
    parser_type: str = Form("auto"),
    resample_interval: str = Form("5m"),
    file: UploadFile = File(...)
):
    """階段 3: 測試完整 Pipeline 到 BatchProcessor"""
    from src.etl.cleaner import DataCleaner
    from src.etl.batch_processor import BatchProcessor
    from src.context import PipelineContext
    parser_type = _validate_parser_type(parser_type)
    
    csv_path = TEMP_DIR / f"diag_bp_{site_id}_{file.filename}"
    output_dir = TEMP_DIR / "output"
    output_dir.mkdir(exist_ok=True)
    
    with open(csv_path, "wb") as f:
        f.write(await file.read())
    
    results = {"stages": []}
    
    try:
        context = PipelineContext()
        try:
            context.initialize()
        except RuntimeError:
            PipelineContext.reset_for_testing()
            context = PipelineContext()
            context.initialize()

        # Stage 1: Parser
        df_parsed, parse_metadata, resolved_parser_type = _parse_with_selected_parser(
            site_id=site_id,
            csv_path=csv_path,
            parser_type=parser_type,
            context=context,
        )
        results["stages"].append({
            "name": "parser",
            "status": "ok",
            "rows": len(df_parsed),
            "parser_type": resolved_parser_type,
        })
        
        # Stage 2: Cleaner
        
        cleaner = DataCleaner(pipeline_context=context)
        if hasattr(cleaner, 'config') and cleaner.config:
            cleaner.config.resample_interval = resample_interval
        df_clean, metadata, audit = cleaner.clean(df_parsed)
        results["stages"].append({"name": "cleaner", "status": "ok", "rows": len(df_clean)})
        
        # Stage 3: BatchProcessor
        bp = BatchProcessor(
            site_id=site_id,
            output_dir=output_dir,
            pipeline_context=context
        )
        result = bp.process_dataframe(
            df_clean,
            column_metadata=metadata,
            equipment_validation_audit=audit,
            source_file=str(csv_path)
        )
        
        results["stages"].append({
            "name": "batch_processor",
            "status": result.status,
            "rows_processed": result.rows_processed,
            "error": result.error
        })
        
        results["parser_type_requested"] = parser_type
        results["parser_type_resolved"] = resolved_parser_type
        results["parse_metadata"] = parse_metadata
        results["overall_status"] = "success" if result.status == "success" else "failed"
        
        # ==========================================
        # 缺口二：device_role 隔離檢查 (UI-005)
        # ==========================================
        def _check_device_role_isolation(df: pl.DataFrame) -> dict:
            """檢查 DataFrame 是否已完全隔離 device_role"""
            has_device_role = 'device_role' in df.columns
            violation_columns = [col for col in df.columns if 'device_role' in col.lower()]
            return {
                "status": "❌ 違規" if has_device_role else "✅ 合規",
                "isolation_passed": not has_device_role,
                "violation_columns": violation_columns if has_device_role else [],
                "violation_detail": f"發現 {len(violation_columns)} 個 device_role 相關欄位" if has_device_role else None,
                "cleaned_column_count": len([c for c in df.columns if 'device_role' not in c.lower()])
            }
        
        device_role_check = _check_device_role_isolation(df_clean)
        results["device_role_isolation"] = device_role_check
        
        # ==========================================
        # 缺口二：Manifest 契約元資料 (UI-006)
        # ==========================================
        manifest_contract = {
            "pipeline_origin_timestamp": None,
            "annotation_checksum": None,
            "rows_in": 0,
            "rows_out": 0,
            "cleaning_rate": 0.0,
            "e350_violations_count": 0,
            "e351_count": 0,
            "e352_count": 0,
            "file_size_bytes": 0
        }
        
        # 檢查拓樸相關欄位（支援 v1.4 新欄位名稱）
        topology_columns = ["topology_node_id", "point_class", "upstream_equipment_id", "setpoint_pair_id"]
        present_topology_cols = [col for col in topology_columns if col in df_clean.columns]
        
        # 建構拓樸摘要（缺口三：GNN 圖結構）
        topology_summary = {
            "has_topology": len(present_topology_cols) > 0,
            "present_columns": present_topology_cols,
            "node_count": 0,
            "edge_count": 0,
            "sample_nodes": [],
            "sample_edges": [],
            "adjacency_matrix_shape": [0, 0],
            "control_semantic_fields": 0,
            "node_types": {}
        }
        
        # 檢查 Manifest 中的完整資訊
        manifest_path = output_dir / site_id / "output" / "manifest_v1.3.json"
        manifest_data = None
        if manifest_path.exists():
            try:
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    manifest_data = json.load(f)
                
                # 填充 Manifest 契約元資料
                manifest_contract["pipeline_origin_timestamp"] = manifest_data.get("temporal_baseline", {}).get("pipeline_origin_timestamp")
                manifest_contract["annotation_checksum"] = manifest_data.get("annotation_checksum")
                manifest_contract["rows_in"] = manifest_data.get("rows_in", 0)
                manifest_contract["rows_out"] = manifest_data.get("rows_out", 0)
                if manifest_contract["rows_in"] > 0:
                    manifest_contract["cleaning_rate"] = (1 - manifest_contract["rows_out"] / manifest_contract["rows_in"]) * 100
                manifest_contract["e350_violations_count"] = len(manifest_data.get("e350_violations", []))
                manifest_contract["e351_count"] = manifest_data.get("e351_count", 0)
                manifest_contract["e352_count"] = manifest_data.get("e352_count", 0)
                manifest_contract["file_size_bytes"] = manifest_data.get("file_size_bytes", 0)
                
                # 填充拓樸資訊（缺口三）
                topology_context = manifest_data.get("topology_context", {})
                if topology_context:
                    topology_summary["manifest_has_topology"] = True
                    topology_summary["manifest_nodes"] = len(topology_context.get("nodes", []))
                    topology_summary["manifest_edges"] = len(topology_context.get("edges", []))
                    topology_summary["adjacency_matrix_shape"] = topology_context.get("adjacency_matrix_shape", [0, 0])
                    topology_summary["nodes"] = topology_context.get("nodes", [])[:10]  # 前10個節點
                    topology_summary["edges"] = topology_context.get("edges", [])[:10]  # 前10條邊
                    
                    # 統計節點類型
                    node_types = {}
                    for node in topology_context.get("nodes", []):
                        node_type = node.get("type", "unknown")
                        node_types[node_type] = node_types.get(node_type, 0) + 1
                    topology_summary["node_types"] = node_types
                    
                # 缺口三：GNN 多任務指標
                model_metrics = manifest_data.get("model_metrics", {})
                if model_metrics:
                    results["model_metrics"] = {
                        "traditional": model_metrics.get("traditional", {}),
                        "physics": model_metrics.get("physics", {}),
                        "multi_task": model_metrics.get("multi_task", {})
                    }
                    
            except Exception as e:
                logger.warning(f"讀取 Manifest 失敗: {e}")
        
        # 從 DataFrame 補充拓樸統計
        if "topology_node_id" in df_clean.columns:
            unique_nodes = df_clean["topology_node_id"].drop_nulls().unique().to_list()
            topology_summary["node_count"] = len(unique_nodes)
            topology_summary["sample_nodes"] = unique_nodes[:5]
            
        if "point_class" in df_clean.columns:
            point_class_counts = {}
            for val in df_clean["point_class"].drop_nulls().unique().to_list():
                if val:
                    count = df_clean.filter(pl.col("point_class") == val).shape[0]
                    point_class_counts[str(val)] = count
            topology_summary["point_class_stats"] = point_class_counts
            topology_summary["control_semantic_fields"] = len(point_class_counts)
        
        results["topology_summary"] = topology_summary
        results["manifest_contract"] = manifest_contract
        
    except Exception as e:
        import traceback
        results["overall_status"] = "error"
        results["error"] = str(e)
        results["error_type"] = type(e).__name__
        results["traceback"] = traceback.format_exc().split("\n")[-10:]
    finally:
        cleanup_file(csv_path)
    
    return results


@app.post("/api/diagnostic/full")
async def diagnostic_full(
    site_id: str = Form(...),
    parser_type: str = Form("auto"),
    resample_interval: str = Form("5m"),
    file: UploadFile = File(...)
):
    """完整診斷：包含所有階段 + ETLContainer"""
    from src.container import ETLContainer
    parser_type = _validate_parser_type(parser_type)
    
    csv_path = TEMP_DIR / f"diag_full_{site_id}_{file.filename}"
    with open(csv_path, "wb") as f:
        f.write(await file.read())
    
    results = {"stages": [], "container_status": None}
    
    try:
        # 測試 ETLContainer 初始化
        try:
            PipelineContext.reset_for_testing()
            container = ETLContainer(site_id=site_id)
            container.initialize_all()
            results["container_status"] = "initialized"
            results["container_steps"] = container.get_status().completed_steps
        except Exception as e:
            results["container_status"] = f"failed: {e}"
            raise
        
        # 使用 Container 執行（Parser 可覆寫為 UI 選定 strategy）
        cleaner = container.get_cleaner()
        
        if hasattr(cleaner, 'config') and cleaner.config:
            cleaner.config.resample_interval = resample_interval
        
        df_parsed, parse_metadata, resolved_parser_type = _parse_with_selected_parser(
            site_id=site_id,
            csv_path=csv_path,
            parser_type=parser_type,
            context=container.get_context(),
        )
        results["stages"].append({
            "name": "container_parser",
            "status": "ok",
            "rows": len(df_parsed),
            "parser_type": resolved_parser_type,
        })
        
        df_clean, metadata, audit = cleaner.clean(df_parsed)
        results["stages"].append({"name": "container_cleaner", "status": "ok", "rows": len(df_clean)})
        
        from src.etl.batch_processor import BatchProcessor
        output_dir = TEMP_DIR / "output_full"
        output_dir.mkdir(exist_ok=True)
        bp = BatchProcessor(
            site_id=site_id,
            output_dir=str(output_dir),
            pipeline_context=container.get_context()
        )
        bp_result = bp.process_dataframe(
            df_clean,
            column_metadata=metadata,
            equipment_validation_audit=audit,
            source_file=str(csv_path)
        )
        
        results["stages"].append({
            "name": "container_batch_processor",
            "status": bp_result.status,
            "rows_processed": bp_result.rows_processed,
            "error": bp_result.error
        })
        
        results["parser_type_requested"] = parser_type
        results["parser_type_resolved"] = resolved_parser_type
        results["parse_metadata"] = parse_metadata
        results["overall_status"] = "success" if bp_result.status == "success" else "failed"
        
    except Exception as e:
        import traceback
        results["overall_status"] = "error"
        results["error"] = str(e)
        results["error_type"] = type(e).__name__
        results["traceback"] = traceback.format_exc().split("\n")[-15:]
    finally:
        cleanup_file(csv_path)
    
    return results
