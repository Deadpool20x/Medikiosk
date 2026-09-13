# MediKiosk Installation & Setup Guide

This guide provides step-by-step instructions for running MediKiosk on a clean machine from the committed repository.

---

## 1. System Requirements

| Component | Minimum | Recommended |
| :--- | :--- | :--- |
| **OS** | Windows 10/11, macOS 13+, or Ubuntu 22.04+ | Windows 11 / Ubuntu 22.04 LTS |
| **Python** | Python 3.11 or 3.12 | Python 3.12 |
| **Node.js** | Node.js 18.18+ or 20+ | Node.js 20 LTS |
| **RAM** | 4 GB | 8 GB+ |
| **Disk** | 2 GB free disk space | 5 GB SSD |

---

## 2. Clone the Repository

```bash
git clone https://github.com/Deadpool20x/Medikiosk.git
cd Medikiosk
```

---

## 3. Configure Environment Variables

Copy the provided example environment template:

```bash
# On Linux / macOS / PowerShell
cp .env.example .env
```

Open `.env` in your editor. At least **one** LLM provider API key should be configured to support the clinical interview:

```env
# AI Providers (At least one required for dynamic interview extraction)
GROQ_API_KEY=gsk_...
GROQ_MODEL=openai/gpt-oss-20b

# Optional Providers
GEMINI_API_KEY=AIza...
CEREBRAS_API_KEY=csk-...
CEREBRAS_MODEL=llama-3.3-70b
NVIDIA_NIM_API_KEY=nvapi-...
# OpenRouter is excluded from the production LLM chain (dead credentials)
OPENROUTER_API_KEY=sk-or-...

# Ports & Connectivity
BACKEND_PORT=8000
DATABASE_URL=sqlite:///./backend/data/medikiosk.db
NEXT_PUBLIC_API_URL=http://localhost:8000

# Doctor Access (Optional)
# Set to require the 'X-Doctor-Token' header in production; defaults to loopback clients (localhost).
# DOCTOR_SECRET_TOKEN=my_secure_kiosk_token
```

---

## 4. Backend Setup (FastAPI)

From the project root:

### 4.1 Create & Activate Virtual Environment

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 4.2 Install Python Dependencies

```bash
pip install -r backend/requirements.txt
```

### 4.3 Initialize the Database

The database is initialized automatically on startup, but you can seed demo data immediately:

```bash
python scripts/seed_demo.py
```

### 4.4 Start the Backend Server

```bash
python -m uvicorn backend.main:app --port 8000 --reload
```

Verify backend health at: [http://localhost:8000/health](http://localhost:8000/health). You should see:
```json
{"status":"ok","database":"connected"}
```

---

## 5. Frontend Setup (Next.js 16 / React 19)

In a new terminal window:

```bash
cd frontend
npm ci
npm run build
npm start
```

For live development with hot reload:
```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## 6. Verification & Health Checks

Verify your installation using the built-in test suites:

```bash
# Run the complete automated backend test suite (179 tests)
pytest backend/tests -v

# Run the 9-point state invariant audit
python -m backend.audit
```

---

## 7. Common Troubleshooting

### `ModuleNotFoundError: No module named 'backend'`
Ensure you run python commands from the repository root directory or set `PYTHONPATH`:
```bash
# Windows PowerShell
$env:PYTHONPATH="."
# Linux / macOS
export PYTHONPATH="."
```

### `403 Forbidden` on Doctor Workspace
The doctor API protects endpoints by allowing only loopback (`127.0.0.1`, `localhost`) traffic in demo mode. If accessing from another machine on your LAN, either set `DOCTOR_SECRET_TOKEN` and supply `X-Doctor-Token`, or configure your proxy host appropriately.

### Port Conflicts
If port 8000 or 3000 is occupied:
- Change backend port: `python -m uvicorn backend.main:app --port 8080`
- Update `NEXT_PUBLIC_API_URL=http://localhost:8080` in `.env`
