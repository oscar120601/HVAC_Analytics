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
    data_dir: str = "data/CGMH-TY"

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
def list_files(data_dir: str = "data/CGMH-TY"):
    """List available CSV files"""
    try:
        path = Path(data_dir)
        if not path.exists():
            return {"files": [], "count": 0, "error": "Directory not found"}
        
        csv_files = sorted([f.name for f in path.glob("*.csv")])
        return {
            "files": csv_files,
            "count": len(csv_files),
            "directory": str(path.absolute())
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
        data_dir = Path(request.data_dir)
        file_paths = [str(data_dir / f) for f in request.files]
        
        parser = ReportParser()
        
        # Parse each file
        dfs = []
        for fp in file_paths:
            df = parser.parse_file(fp)
            dfs.append(df)
        
        # Merge
        import polars as pl
        if len(dfs) == 1:
            merged_df = dfs[0]
        else:
            merged_df = pl.concat(dfs, how='vertical_relaxed')
        
        # Store in state
        app_state["current_df"] = merged_df
        
        # Convert preview to dict
        preview = merged_df.head(10).to_pandas().to_dict('records')
        
        return ParseResponse(
            success=True,
            row_count=len(merged_df),
            column_count=len(merged_df.columns),
            columns=list(merged_df.columns),
            preview=preview,
            message=f"Successfully parsed {len(request.files)} files"
        )
    except Exception as e:
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
    df = app_state.get("cleaned_df") or app_state.get("current_df")
    if df is None:
        raise HTTPException(status_code=400, detail="No data available")
    
    try:
        preview = df.head(rows).to_pandas().to_dict('records')
        return {
            "preview": preview,
            "total_rows": len(df),
            "columns": list(df.columns)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/data/stats")
def get_data_stats(column: str):
    """Get statistics for a column"""
    df = app_state.get("cleaned_df") or app_state.get("current_df")
    if df is None:
        raise HTTPException(status_code=400, detail="No data available")
    
    if column not in df.columns:
        raise HTTPException(status_code=404, detail=f"Column {column} not found")
    
    try:
        col_data = df[column].drop_nulls()
        return {
            "column": column,
            "mean": round(col_data.mean(), 4),
            "median": round(col_data.median(), 4),
            "min": round(col_data.min(), 4),
            "max": round(col_data.max(), 4),
            "std": round(col_data.std(), 4),
            "count": len(col_data)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Model Management Endpoints
@app.get("/api/models", response_model=List[ModelInfo])
def list_models():
    """List available trained models"""
    try:
        model_dir = Path("models")
        if not model_dir.exists():
            return []
        
        models = []
        for model_file in model_dir.glob("*.joblib"):
            # Try to load model info
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
        
        return models
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
