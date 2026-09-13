# Quick Start Guide for MediKiosk

A simple, step-by-step guide to get MediKiosk running on your machine.

---

## Step 1: Create Your `.env` File

Copy the template below and save it as a new file named `.env` in the root folder (`d:\project\Medikishok\.env`):

```env
# ==========================================
# 1. AI PROVIDERS (Need at least ONE real key)
# ==========================================

# Groq (Recommended for conversational interview - Fast & Free tier available)
# Get a free key at: https://console.groq.com/keys
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=openai/gpt-oss-20b

# Google Gemini (Used for Prescription OCR and vision analysis)
# Get key at: https://aistudio.google.com/app/apikey
GEMINI_API_KEY=your_gemini_api_key_here

# OpenRouter (Fallback LLM provider)
# Get key at: https://openrouter.ai/keys
OPENROUTER_API_KEY=your_openrouter_api_key_here
OPENROUTER_MODEL=meta-llama/llama-3.3-70b-instruct:free
OPENROUTER_REFERER=https://medikiosk.local
OPENROUTER_TITLE=MediKiosk

# NVIDIA NIM (Optional vision fallback)
NVIDIA_NIM_API_KEY=your_nvidia_nim_api_key_here
NVIDIA_NIM_MODEL=meta/llama-3.2-11b-vision-instruct

# ==========================================
# 2. SERVER CONFIGURATION
# ==========================================
BACKEND_PORT=8000
DATABASE_URL=sqlite:///./backend/data/medikiosk.db

# ==========================================
# 3. FRONTEND CONFIGURATION
# ==========================================
NEXT_PUBLIC_API_URL=http://localhost:8000
```

> **Note**: You only need **one** working LLM key to run the interview. Groq (`GROQ_API_KEY`) is recommended.

---

## Step 2: Start the Backend (Terminal 1)

Open PowerShell or Command Prompt in the project folder:

```powershell
# 1. Create a Python virtual environment (only needed the first time)
python -m venv .venv

# 2. Activate the virtual environment
# Windows:
.\.venv\Scripts\Activate.ps1
# Linux/macOS:
# source .venv/bin/activate

# 3. Install required Python packages
pip install -r backend/requirements.txt

# 4. (Optional) Seed demo patients and doctors
python scripts/seed_demo.py

# 5. Start the FastAPI server
python -m uvicorn backend.main:app --port 8000 --reload
```

* Verify backend is running: Open [http://localhost:8000/health](http://localhost:8000/health) in your browser. You should see `{"status":"ok"}`.

---

## Step 3: Start the Frontend (Terminal 2)

Open a **new, separate terminal** in the project folder:

```powershell
# 1. Navigate to the frontend directory
cd frontend

# 2. Install dependencies (only needed the first time)
npm install

# 3. Start the Next.js development server
npm run dev
```

---

## Step 4: Open the Application in Your Browser

Once both terminals are running, open:

| Interface | URL | Description |
| :--- | :--- | :--- |
| **Patient Kiosk** | [http://localhost:3000](http://localhost:3000) | Multilingual touch intake kiosk for patients |
| **Doctor Workspace** | [http://localhost:3000/doctor](http://localhost:3000/doctor) | Real-time queue, clinical summaries, and prescriptions |
| **Backend API Docs** | [http://localhost:8000/docs](http://localhost:8000/docs) | Interactive Swagger API documentation |

---

## Common Troubleshooting

- **Script Execution Error on Windows (`Activate.ps1 cannot be loaded`)**:
  Run this command in PowerShell as Administrator:
  ```powershell
  Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
  ```
  Or activate using Command Prompt instead: `.\.venv\Scripts\activate.bat`

- **Port 8000 or 3000 Already in Use**:
  Close existing Python or Node processes, or change `BACKEND_PORT=8001` in `.env` and `NEXT_PUBLIC_API_URL=http://localhost:8001`.
