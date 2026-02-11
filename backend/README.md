# HVAC Analytics Backend

FastAPI backend server for HVAC data processing and optimization.

## 🚀 Quick Start

### Option 1: Using startup script (Windows)
```bash
cd backend
start_server.bat
```

### Option 2: Manual start
```bash
cd backend

# Create virtual environment
python -m venv .venv

# Activate
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Start server
python main.py
```

Server will start at: http://localhost:8000

## 📚 API Documentation

Once server is running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 🔌 API Endpoints

### Health Check
- `GET /api/health` - Server health status

### File Management
- `GET /api/files` - List available CSV files

### Data Processing
- `POST /api/parse` - Parse and merge CSV files
- `POST /api/clean` - Clean and validate data
- `GET /api/data/preview` - Get data preview
- `GET /api/data/stats` - Get column statistics

### Model Management
- `GET /api/models` - List trained models
- `POST /api/models/train` - Train new model

### Optimization
- `POST /api/optimize` - Run optimization

## 🔧 Development

The backend connects to the existing Python modules in `/src`:
- `etl.parser` - ReportParser for CSV parsing
- `etl.cleaner` - DataCleaner for data cleaning
- `models.energy_model` - ChillerEnergyModel for ML

## 📦 Requirements

- Python 3.9+
- FastAPI
- Uvicorn
- Polars (for data processing)
- Scikit-learn (for ML)
- XGBoost (for ML)
