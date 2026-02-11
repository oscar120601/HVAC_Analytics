# HVAC Analytics - Development Setup Guide

## 📋 Prerequisites

- **Python 3.9+**
- **Node.js 18+**
- **npm or yarn**

## 🚀 Quick Start (Windows)

### Option 1: Using the startup script
```bash
# From project root
start_development.bat
```

### Option 2: Manual setup

#### 1. Start the Backend
```bash
cd backend

# Create virtual environment (first time only)
python -m venv .venv

# Activate
.venv\Scripts\activate

# Install dependencies (first time only)
pip install -r requirements.txt

# Start server
python main.py
```

Backend will be available at: http://localhost:8000

#### 2. Start the Frontend
```bash
cd frontend

# Install dependencies (first time only)
npm install

# Start dev server
npm run dev
```

Frontend will be available at: http://localhost:3001

## 🔌 API Documentation

Once backend is running:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 📁 Project Structure

```
HVAC_Analytics/
├── backend/              # FastAPI backend
│   ├── main.py          # API endpoints
│   ├── requirements.txt # Python dependencies
│   └── .venv/           # Virtual environment
│
├── frontend/            # React + Vite frontend
│   ├── src/
│   │   ├── components/  # UI components
│   │   ├── pages/       # Page components
│   │   └── services/    # API clients
│   └── package.json
│
├── src/                 # Python core modules
│   ├── etl/            # Data processing
│   └── models/         # ML models
│
└── data/               # Data files
```

## 🔧 Backend Dependencies

The backend requires:
- **FastAPI** - Web framework
- **Uvicorn** - ASGI server
- **Polars** - Data processing
- **scikit-learn** - Machine learning
- **XGBoost** - Gradient boosting
- **Pydantic** - Data validation

## 🐛 Troubleshooting

### Backend won't start
1. Check if virtual environment is activated
2. Verify all dependencies are installed: `pip list`
3. Check port 8000 is not in use

### Frontend can't connect to backend
1. Verify backend is running on port 8000
2. Check CORS settings in `backend/main.py`
3. Verify `VITE_API_URL` in frontend `.env` file

### Import errors
Make sure the backend is run from the `backend/` directory so it can find the `src/` modules.

## 📊 Available Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check |
| `/api/files` | GET | List CSV files |
| `/api/parse` | POST | Parse & merge files |
| `/api/clean` | POST | Clean data |
| `/api/data/preview` | GET | Data preview |
| `/api/models` | GET | List models |
| `/api/optimize` | POST | Run optimization |

## 🔄 Development Workflow

1. **Make changes** to backend or frontend code
2. **Backend** auto-reloads on save (FastAPI dev mode)
3. **Frontend** hot-reloads on save (Vite dev mode)
4. **Test** API endpoints using Swagger UI
5. **Verify** frontend-backend integration

## 📝 Environment Variables

### Frontend (.env)
```env
VITE_API_URL=http://localhost:8000
```

### Backend
No environment variables required for local development.

## 🎯 Next Steps

1. Install backend dependencies
2. Start both servers
3. Open http://localhost:3001
4. Test the API connection
5. Begin development!

## 🆘 Need Help?

- Check browser console for frontend errors
- Check terminal output for backend errors
- Verify all ports are available
- Ensure Python 3.9+ and Node 18+ are installed
