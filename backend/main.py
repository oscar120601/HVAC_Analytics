"""
HVAC Analytics Backend API
FastAPI server for HVAC data processing and optimization
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import json

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
import uvicorn

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Define base project directory
BASE_DIR = Path(__file__).parent.parent

# Try to import ETL modules
try:
    from etl.parser import ReportParser
    from etl.cleaner import DataCleaner
    ETL_AVAILABLE = True
except ImportError:
    ETL_AVAILABLE = False

# Try to import ML modules
try:
    from models.energy_model import ChillerEnergyModel
    from optimization.optimizer import ChillerOptimizer
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False

# Create FastAPI app
app = FastAPI(
    title="HVAC Analytics API",
    description="Backend API for HVAC data processing and optimization",
    version="3.0.0"
)

# CORS middleware - allow React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class ParseRequest(BaseModel):
    files: List[str]
    data_dir: str = "data"
    subfolder: str = ""

class ParseResponse(BaseModel):
    success: bool
    row_count: int
    column_count: int
    columns: List[str]
    preview: List[Dict[str, Any]]
    message: str

class CleanRequest(BaseModel):
    resample_interval: str = "5m"
    detect_frozen: bool = True
    apply_steady_state: bool = False
    apply_heat_balance: bool = False
    apply_affinity: bool = False
    filter_invalid: bool = False

class CleanResponse(BaseModel):
    success: bool
    original_rows: int
    cleaned_rows: int
    retention_rate: float
    message: str

class ModelInfo(BaseModel):
    name: str
    mape: Optional[float] = None
    r2: Optional[float] = None
    feature_count: int
    created_at: Optional[str] = None

class OptimizationRequest(BaseModel):
    model_name: str
    input_data: Dict[str, float]

class OptimizationResponse(BaseModel):
    success: bool
    predicted_power: float
    recommendations: List[Dict[str, Any]]

# Global state (in production, use Redis or database)
app_state = {
    "current_df": None,
    "cleaned_df": None,
    "models": {}
}

@app.get("/")
def root():
    return {
        "message": "HVAC Analytics API",
        "version": "3.0.0",
        "etl_available": ETL_AVAILABLE,
        "ml_available": ML_AVAILABLE
    }

@app.get("/api/health")
def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

# File Management Endpoints
@app.get("/api/files")
def list_files(data_dir: str = "data", subfolder: str = None):
    """List available CSV files and subfolders"""
    try:
        # Use absolute path relative to project root
        base_path = BASE_DIR / data_dir
        
        if not base_path.exists():
            return {"files": [], "folders": [], "count": 0, "error": "Directory not found"}
        
        # If subfolder is specified, list files in that subfolder
        if subfolder:
            target_path = base_path / subfolder
            if not target_path.exists():
                return {"files": [], "folders": [], "count": 0, "error": f"Subfolder {subfolder} not found"}
            
            csv_files = sorted([f.name for f in target_path.glob("*.csv")])
            return {
                "files": csv_files,
                "folders": [],
                "count": len(csv_files),
                "directory": str(target_path.absolute()),
                "base_dir": str(base_path.absolute()),
                "current_folder": subfolder
            }
        
        # Otherwise, list subfolders in data_dir
        subfolders = sorted([d.name for d in base_path.iterdir() if d.is_dir()])
        
        # Also count total CSV files across all subfolders
        total_files = 0
        folder_counts = {}
        for folder in subfolders:
            folder_path = base_path / folder
            count = len(list(folder_path.glob("*.csv")))
            folder_counts[folder] = count
            total_files += count
        
        return {
            "files": [],
            "folders": subfolders,
            "folder_counts": folder_counts,
            "total_files": total_files,
            "count": 0,
            "directory": str(base_path.absolute()),
            "base_dir": str(base_path.absolute())
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Data Processing Endpoints
@app.post("/api/parse", response_model=ParseResponse)
def parse_files(request: ParseRequest):
    """Parse and merge CSV files"""
    if not ETL_AVAILABLE:
        raise HTTPException(status_code=503, detail="ETL module not available")
    
    try:
        # Use absolute path relative to project root
        base_dir = BASE_DIR / request.data_dir
        # If subfolder is provided, use it as the target directory
        if request.subfolder:
            data_dir = base_dir / request.subfolder
        else:
            data_dir = base_dir
        
        file_paths = [str(data_dir / f) for f in request.files]
        
        parser = ReportParser()
        
        # Parse each file
        dfs = []
        columns_set = set()
        
        for fp in file_paths:
            df = parser.parse_file(fp)
            if df is not None and len(df) > 0:
                dfs.append(df)
                columns_set.update(df.columns)
        
        if len(dfs) == 0:
            raise HTTPException(status_code=400, detail="No valid data found in selected files")
        
        # Merge with schema normalization
        import polars as pl
        if len(dfs) == 1:
            merged_df = dfs[0]
        else:
            # Get all unique columns across all dataframes
            all_columns = sorted(list(columns_set))
            
            # Normalize each dataframe: add missing columns, cast all to String for compatibility
            normalized_dfs = []
            for df in dfs:
                # Cast all columns to String to avoid type conflicts
                df = df.with_columns([pl.col(c).cast(pl.Utf8) for c in df.columns])
                
                # Add missing columns with null values
                missing_cols = [col for col in all_columns if col not in df.columns]
                if missing_cols:
                    df = df.with_columns([pl.lit(None).cast(pl.Utf8).alias(col) for col in missing_cols])
                
                # Reorder columns to match
                df = df.select(all_columns)
                normalized_dfs.append(df)
            
            # Merge vertically
            merged_df = pl.concat(normalized_dfs, how='vertical_relaxed')
        
        # Store in state
        app_state["current_df"] = merged_df
        
        # Convert preview to dict (handle serialization)
        preview = []
        for row in merged_df.head(10).to_dicts():
            clean_row = {}
            for k, v in row.items():
                if v is None:
                    clean_row[k] = None
                elif hasattr(v, 'item'):  # numpy scalar
                    clean_row[k] = v.item()
                else:
                    clean_row[k] = str(v) if not isinstance(v, (int, float, bool)) else v
            preview.append(clean_row)
        
        return ParseResponse(
            success=True,
            row_count=len(merged_df),
            column_count=len(merged_df.columns),
            columns=list(merged_df.columns),
            preview=preview,
            message=f"Successfully parsed {len(request.files)} files"
        )
    except Exception as e:
        import traceback
        error_detail = f"{str(e)}\n{traceback.format_exc()}"
        print(error_detail)  # Log to console
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/clean", response_model=CleanResponse)
def clean_data(request: CleanRequest):
    """Clean and validate data"""
    if not ETL_AVAILABLE:
        raise HTTPException(status_code=503, detail="ETL module not available")
    
    if app_state["current_df"] is None:
        raise HTTPException(status_code=400, detail="No data to clean. Parse files first.")
    
    try:
        df = app_state["current_df"]
        original_rows = len(df)
        
        cleaner = DataCleaner(resample_interval=request.resample_interval)
        cleaned_df = cleaner.clean_data(
            df,
            apply_steady_state=request.apply_steady_state,
            apply_heat_balance=request.apply_heat_balance,
            apply_affinity_laws=request.apply_affinity,
            filter_invalid=request.filter_invalid
        )
        
        app_state["cleaned_df"] = cleaned_df
        cleaned_rows = len(cleaned_df)
        retention_rate = (cleaned_rows / original_rows * 100) if original_rows > 0 else 0
        
        return CleanResponse(
            success=True,
            original_rows=original_rows,
            cleaned_rows=cleaned_rows,
            retention_rate=round(retention_rate, 2),
            message="Data cleaned successfully"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/data/preview")
def get_data_preview(rows: int = 50):
    """Get data preview"""
    from datetime import datetime, date
    df = app_state.get("cleaned_df") or app_state.get("current_df")
    if df is None:
        raise HTTPException(status_code=400, detail="No data available")
    
    try:
        # Get preview data
        preview_df = df.head(rows)
        columns = list(preview_df.columns)
        
        # Convert to dicts and handle serialization
        preview = []
        for row in preview_df.to_dicts():
            clean_row = {}
            for k, v in row.items():
                if v is None:
                    clean_row[k] = None
                elif isinstance(v, (datetime, date)):
                    clean_row[k] = v.isoformat()
                elif hasattr(v, 'item'):  # numpy scalar
                    clean_row[k] = v.item()
                elif isinstance(v, (int, float, bool)):
                    clean_row[k] = v
                else:
                    clean_row[k] = str(v)
            preview.append(clean_row)
        
        return {
            "preview": preview,
            "total_rows": len(df),
            "columns": columns
        }
    except Exception as e:
        import traceback
        print(f"Preview error: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/data/stats")
def get_data_stats(column: str):
    """Get statistics for a column"""
    import polars as pl
    df = app_state.get("cleaned_df") or app_state.get("current_df")
    if df is None:
        raise HTTPException(status_code=400, detail="No data available")
    
    if column not in df.columns:
        raise HTTPException(status_code=404, detail=f"Column {column} not found")
    
    try:
        col_data = df[column]
        
        # Filter out nulls and string 'None' values
        if col_data.dtype == pl.Utf8:
            # For string columns, filter out 'None' and empty strings
            col_data = col_data.filter((col_data != "None") & (col_data != "") & (col_data.is_not_null()))
            # Try to cast to numeric
            try:
                col_data = col_data.cast(pl.Float64)
            except:
                pass
        else:
            col_data = col_data.drop_nulls()
        
        # Try to calculate statistics
        try:
            if col_data.dtype in [pl.Float64, pl.Float32, pl.Int64, pl.Int32]:
                return {
                    "column": column,
                    "mean": round(float(col_data.mean()), 4) if col_data.mean() is not None else None,
                    "median": round(float(col_data.median()), 4) if col_data.median() is not None else None,
                    "min": round(float(col_data.min()), 4) if col_data.min() is not None else None,
                    "max": round(float(col_data.max()), 4) if col_data.max() is not None else None,
                    "std": round(float(col_data.std()), 4) if col_data.std() is not None else None,
                    "count": len(col_data)
                }
        except:
            pass
        
        # For non-numeric columns, return count only
        return {
            "column": column,
            "mean": None,
            "median": None,
            "min": None,
            "max": None,
            "std": None,
            "count": len(col_data)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Model Management Endpoints
@app.get("/api/models")
def list_models(subfolder: str = None):
    """List available trained models and subfolders"""
    try:
        import os
        print(f"DEBUG: BASE_DIR = {BASE_DIR}")
        print(f"DEBUG: Current dir = {os.getcwd()}")
        base_dir = BASE_DIR / "models"
        print(f"DEBUG: model_dir = {base_dir}")
        print(f"DEBUG: exists = {base_dir.exists()}")
        
        if not base_dir.exists():
            return {"folders": [], "models": [], "total_models": 0}
        
        # If subfolder is specified, list models in that subfolder
        if subfolder:
            target_dir = base_dir / subfolder
            if not target_dir.exists():
                return {"folders": [], "models": [], "total_models": 0, "error": f"Subfolder {subfolder} not found"}
            
            models = []
            for model_file in target_dir.glob("*.joblib"):
                try:
                    model = ChillerEnergyModel.load_model(str(model_file))
                    models.append(ModelInfo(
                        name=model_file.name,
                        mape=model.training_metrics.get('mape') if model.training_metrics else None,
                        r2=model.training_metrics.get('r2') if model.training_metrics else None,
                        feature_count=len(model.feature_names) if model.feature_names else 0,
                        created_at=datetime.fromtimestamp(model_file.stat().st_mtime).isoformat()
                    ))
                except:
                    models.append(ModelInfo(
                        name=model_file.name,
                        feature_count=0
                    ))
            
            return {
                "folders": [],
                "models": models,
                "total_models": len(models),
                "current_folder": subfolder
            }
        
        # Otherwise, list subfolders and count models in each
        subfolders = sorted([d.name for d in base_dir.iterdir() if d.is_dir()])
        
        # Also include .joblib files directly in models/ root
        root_models = []
        for model_file in base_dir.glob("*.joblib"):
            try:
                model = ChillerEnergyModel.load_model(str(model_file))
                root_models.append(ModelInfo(
                    name=model_file.name,
                    mape=model.training_metrics.get('mape') if model.training_metrics else None,
                    r2=model.training_metrics.get('r2') if model.training_metrics else None,
                    feature_count=len(model.feature_names) if model.feature_names else 0,
                    created_at=datetime.fromtimestamp(model_file.stat().st_mtime).isoformat()
                ))
            except:
                root_models.append(ModelInfo(
                    name=model_file.name,
                    feature_count=0
                ))
        
        # Count models in each subfolder
        folder_counts = {}
        total_models = len(root_models)
        for folder in subfolders:
            folder_path = base_dir / folder
            count = len(list(folder_path.glob("*.joblib")))
            folder_counts[folder] = count
            total_models += count
        
        return {
            "folders": subfolders,
            "models": root_models,
            "folder_counts": folder_counts,
            "total_models": total_models,
            "directory": str(base_dir.absolute())
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/models/train")
def train_model(
    model_name: str,
    feature_mapping: Dict[str, Any],
    background_tasks: BackgroundTasks
):
    """Train a new model"""
    if not ML_AVAILABLE:
        raise HTTPException(status_code=503, detail="ML module not available")
    
    # This would be a long-running task
    # For now, return a placeholder
    return {
        "message": "Training started",
        "model_name": model_name,
        "status": "training"
    }

@app.post("/api/optimize", response_model=OptimizationResponse)
def optimize(request: OptimizationRequest):
    """Run optimization with a trained model"""
    if not ML_AVAILABLE:
        raise HTTPException(status_code=503, detail="ML module not available")
    
    try:
        model_path = Path("models") / request.model_name
        if not model_path.exists():
            raise HTTPException(status_code=404, detail="Model not found")
        
        model = ChillerEnergyModel.load_model(str(model_path))
        
        # Make prediction
        # This is a simplified version
        prediction = 100.0  # Placeholder
        
        return OptimizationResponse(
            success=True,
            predicted_power=prediction,
            recommendations=[
                {"parameter": "CHW_Pump_Freq", "value": 45.0, "savings": "5%"},
                {"parameter": "CWP_Pump_Freq", "value": 42.0, "savings": "3%"}
            ]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
