# Hybrid Secret Scanner

A full-stack application designed to detect hardcoded API keys and secrets using an advanced machine learning model.

This project is separated into two components:
- `backend/`: Contains the Machine Learning model, inferencing pipelines, and core Python scripts.
- `frontend/`: Contains the Next.js web application providing a high-performance web editor and UI.

## Quick Start

### Frontend
Navigate to the `frontend/` directory, install dependencies, and run via `portless`:
```bash
cd frontend
npm install
npm run dev
```

### Backend
Navigate to the `backend/` directory and install the required Python dependencies:
```bash
cd backend
pip install -r requirements.txt
python main.py
```
