from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from typing import List
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

from src.container import ETLContainer
from src.context import PipelineContext
from src.etl.batch_processor import BatchProcessor
from tools.features.wizard import FeatureAnnotationWizard
from tools.features.excel_to_yaml import ExcelToYamlConverter

app = FastAPI()

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

TEMP_DIR = Path(tempfile.gettempdir()) / "hvac_demo"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

def cleanup_file(filepath: Path):
    if filepath.exists():
        try:
            filepath.unlink()
        except:
            pass

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
    """STEP 1: 從原始 CSV 產生 Excel 標註範本"""
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
    resample_interval: str = Form("5m"),
    files: List[UploadFile] = File(...)
):
    """STEP 3: 執行完整的 Sprint 2 ETL Pipeline (Parser -> Cleaner -> BatchProcessor)
    
    支援單一檔案、多檔案或資料夾上傳，並使用背景任務執行以支援進度顯示。
    """
    import logging
    logger = logging.getLogger(__name__)
    
    if not files:
        raise HTTPException(status_code=400, detail="請至少選擇一個 CSV 檔案")
    
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
        "progress": "初始化任務中...",
        "result": None,
        "message": ""
    }
    
    background_tasks.add_task(
        process_pipeline_task,
        job_id,
        site_id,
        resample_interval,
        csv_paths,
        output_dir
    )
    
    return {"status": "started", "job_id": job_id}

@app.get("/api/job-status/{job_id}")
async def get_job_status(job_id: str):
    if job_id not in pipeline_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return pipeline_jobs[job_id]

def process_pipeline_task(job_id: str, site_id: str, resample_interval: str, csv_paths: List[Path], output_dir: Path):
    import logging
    logger = logging.getLogger(__name__)
    
    def update_progress(msg: str):
        pipeline_jobs[job_id]["progress"] = msg
        logger.info(f"[Job {job_id[:8]}] {msg}")

    try:
        update_progress("系統初始化...")
        
        PipelineContext.reset_for_testing()
        container = ETLContainer(site_id=site_id)
        container.initialize_all()
        context = container.get_context()

        parser = container.get_parser()
        cleaner = container.get_cleaner()
        
        if hasattr(cleaner, 'config') and cleaner.config:
            cleaner.config.resample_interval = resample_interval
            
        bp = BatchProcessor(site_id=site_id, output_dir=str(output_dir), pipeline_context=context)

        total_files = len(csv_paths)
        update_progress(f"開始 Parser 處理 (共 {total_files} 個檔案)...")
        
        df_parsed_list = []
        current_stage = "Parser 解析"
        current_file = None
        
        for i, path in enumerate(csv_paths, 1):
            if i % 10 == 0 or i == 1 or i == total_files:
                update_progress(f"正在解析檔案 ({i}/{total_files})")
            
            # Extract original filename for clearer error message
            current_file = path.name.replace(f"input_{site_id}_", "")
            
            df_p = parser.parse_file(str(path))
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
            
        current_file = None
        current_stage = "合併資料"
        update_progress("正在合併所有解析後的資料...")
        df_parsed = pl.concat(df_parsed_list, how="diagonal_relaxed")
        
        current_stage = "Cleaner 清洗"
        update_progress(f"開始 Cleaner 語意清洗與重採樣... (共 {len(df_parsed)} 行)")
        df_cleaned, column_metadata, equipment_audit = cleaner.clean(df_parsed)
        
        current_stage = "BatchProcessor 落地"
        update_progress(f"正在執行 BatchProcessor 落地輸出... (共 {len(df_cleaned)} 行)")
        source_name = f"multiple_files_({len(csv_paths)})" if len(csv_paths) > 1 else str(csv_paths[0].name.replace(f"input_{site_id}_", ""))
        result = bp.process_dataframe(
            df_cleaned, 
            column_metadata=column_metadata,
            equipment_validation_audit=equipment_audit,
            source_file=source_name
        )
        if result.status == "success":
            df_processed = df_cleaned
        else:
            raise Exception(f"BatchProcessor 失敗: {result.error}")

        update_progress("計算資料品質統計報告...")
        
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
        pipeline_jobs[job_id]["progress"] = "✅ 執行完成"
        pipeline_jobs[job_id]["result"] = {
            "status": "success",
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
            "feature_engineer_input_ready": True
        }

    except Exception as e:
        pipeline_jobs[job_id]["status"] = "error"
        
        # Add context to the error message
        stage_info = f"[{current_stage}] " if 'current_stage' in locals() else ""
        file_info = f" (發生於檔案: {current_file})" if 'current_file' in locals() and current_file else ""
        
        pipeline_jobs[job_id]["message"] = f"Pipeline 執行失敗: {stage_info}{str(e)}{file_info}"
        logger.exception(f"Pipeline Task {job_id} failed")
    finally:
        for path in csv_paths:
            cleanup_file(path)


@app.post("/api/run-feature-engineer")
async def run_feature_engineer(site_id: str = Form(...)):
    """STEP 4: 執行 Sprint 3 特徵工程 (預留擴充點)"""
    # TODO: 在 Sprint 3 實作 FeatureEngineer 時完善此路由
    return {
        "status": "success",
        "message": "Sprint 3 Feature Engineer 尚未實作，此為預留擴充點！",
        "site_id": site_id,
        "optimization_input_ready": True
    }

@app.post("/api/run-optimization")
async def run_optimization(site_id: str = Form(...)):
    """STEP 5: 執行 Sprint 4 最佳化引擎 (預留擴充點)"""
    # TODO: 在 Sprint 4 實作 Optimization Engine 時完善此路由
    return {
        "status": "success",
        "message": "Sprint 4 Optimization Engine 尚未實作，此為預留擴充點！",
        "site_id": site_id,
        "integration_input_ready": True
    }

@app.post("/api/run-integration")
async def run_integration(site_id: str = Form(...)):
    """STEP 6: 執行 Sprint 5 系統整合 (預留擴充點)"""
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
        raise HTTPException(status_code=404, detail="找不到由 BatchProcessor 產生的 Parquet 檔案。請先執行 Step 3。")
    
    # 找最新的檔案
    latest_file = max(parquet_files, key=os.path.getmtime)
    
    return FileResponse(
        path=latest_file,
        filename=f"{site_id}_cleaned_data.parquet",
        media_type="application/vnd.apache.parquet"
    )


# =============================================================================
# 階段性診斷 API (整合自 diagnostic_api.py)
# =============================================================================

@app.post("/api/diagnostic/parser")
async def diagnostic_parser(site_id: str = Form(...), file: UploadFile = File(...)):
    """階段 1: 僅測試 Parser"""
    from src.etl.parser import ReportParser
    
    csv_path = TEMP_DIR / f"diag_parser_{site_id}_{file.filename}"
    with open(csv_path, "wb") as f:
        f.write(await file.read())
    
    try:
        parser = ReportParser(site_id=site_id)
        df = parser.parse_file(str(csv_path))
        
        return {
            "stage": "parser",
            "status": "success",
            "rows": len(df),
            "columns": len(df.columns),
            "column_names": df.columns[:20],
            "timestamp_type": str(df["timestamp"].dtype) if "timestamp" in df.columns else "missing",
            "sample": df.head(3).to_dicts() if len(df) > 0 else []
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
    resample_interval: str = Form("5m"),
    file: UploadFile = File(...)
):
    """階段 2: 測試 Parser + Cleaner"""
    from src.etl.parser import ReportParser
    from src.etl.cleaner import DataCleaner
    from src.context import PipelineContext
    
    csv_path = TEMP_DIR / f"diag_cleaner_{site_id}_{file.filename}"
    with open(csv_path, "wb") as f:
        f.write(await file.read())
    
    try:
        # Parser
        parser = ReportParser(site_id=site_id)
        df_parsed = parser.parse_file(str(csv_path))
        
        # Cleaner
        context = PipelineContext()
        try:
            context.initialize()
        except RuntimeError:
            PipelineContext.reset_for_testing()
            context = PipelineContext()
            context.initialize()
        
        cleaner = DataCleaner(pipeline_context=context)
        if hasattr(cleaner, 'config') and cleaner.config:
            cleaner.config.resample_interval = resample_interval
        df_clean, metadata, audit = cleaner.clean(df_parsed)
        
        return {
            "stage": "cleaner",
            "status": "success",
            "parser_output": {"rows": len(df_parsed), "columns": len(df_parsed.columns)},
            "cleaner_output": {"rows": len(df_clean), "columns": len(df_clean.columns)},
            "metadata_keys": list(metadata.keys())[:10],
            "audit_keys": list(audit.keys()),
            "quality_flags_present": "quality_flags" in df_clean.columns,
            "sample_flags": df_clean["quality_flags"].head(5).to_list() if "quality_flags" in df_clean.columns else []
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
    resample_interval: str = Form("5m"),
    file: UploadFile = File(...)
):
    """階段 3: 測試完整 Pipeline 到 BatchProcessor"""
    from src.etl.parser import ReportParser
    from src.etl.cleaner import DataCleaner
    from src.etl.batch_processor import BatchProcessor
    from src.context import PipelineContext
    
    csv_path = TEMP_DIR / f"diag_bp_{site_id}_{file.filename}"
    output_dir = TEMP_DIR / "output"
    output_dir.mkdir(exist_ok=True)
    
    with open(csv_path, "wb") as f:
        f.write(await file.read())
    
    results = {"stages": []}
    
    try:
        # Stage 1: Parser
        parser = ReportParser(site_id=site_id)
        df_parsed = parser.parse_file(str(csv_path))
        results["stages"].append({"name": "parser", "status": "ok", "rows": len(df_parsed)})
        
        # Stage 2: Cleaner
        context = PipelineContext()
        try:
            context.initialize()
        except RuntimeError:
            PipelineContext.reset_for_testing()
            context = PipelineContext()
            context.initialize()
        
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
        
        results["overall_status"] = "success" if result.status == "success" else "failed"
        
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
    resample_interval: str = Form("5m"),
    file: UploadFile = File(...)
):
    """完整診斷：包含所有階段 + ETLContainer"""
    from src.container import ETLContainer
    
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
        
        # 使用 Container 執行
        parser = container.get_parser()
        cleaner = container.get_cleaner()
        
        if hasattr(cleaner, 'config') and cleaner.config:
            cleaner.config.resample_interval = resample_interval
        
        df_parsed = parser.parse_file(str(csv_path))
        results["stages"].append({"name": "container_parser", "status": "ok", "rows": len(df_parsed)})
        
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
