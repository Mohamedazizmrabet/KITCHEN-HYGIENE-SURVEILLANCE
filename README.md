# KitchenWatch — Intelligent Kitchen Hygiene Surveillance System

Real-time PPE compliance monitoring prototype with independent YOLO and RT-DETR-L inference paths.

```
┌──────────────────────────────────────────────────────────┐
│                     React Frontend                        │
│         Dashboard | Live Monitor | Violations | Settings  │
└──────────────────┬───────────────────────────────────────┘
                   │  HTTP/JSON (Axios)
                   ▼
┌──────────────────────────────────────────────────────────┐
│                   Laravel Backend :8000                   │
│         Sessions · Violations · Settings · SQLite        │
└──────────────────┬───────────────────────────────────────┘
                   │  Guzzle HTTP
                   ▼
┌──────────────────────────────────────────────────────────┐
│          Python Inference Service :8001                   │
│  YOLO / RT-DETR-L → BoT-SORT → MJPEG Stream             │
└──────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
trainF/
├── inference-service/       Python FastAPI — detection, tracking, streaming
├── laravel-backend/         PHP Laravel — sessions, violations, settings
└── frontend/                React Vite — dashboard UI
```

---

## Quick Start

### Prerequisites

| Tool | Version |
|---|---|
| Python | ≥ 3.10 |
| pip | latest |
| PHP | ≥ 8.2 |
| Composer | ≥ 2 |
| Node.js | ≥ 18 |
| npm | ≥ 9 |
| CUDA (optional) | ≥ 11.8 for GPU |

---

## Step 1 — Python Inference Service

### 1.1 Create virtual environment

```bash
cd inference-service
python -m venv venv

# Windows
venv\Scripts\activate

# Linux / macOS
source venv/bin/activate
```

### 1.2 Install dependencies

```bash
pip install -r requirements.txt
```

> For CUDA GPU acceleration, install PyTorch with CUDA first:
> ```bash
> pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
> pip install onnxruntime-gpu   # instead of onnxruntime
> ```

### 1.3 Configure environment

Edit `inference-service/.env` if needed:

```env
DEFAULT_MODEL=YOLO           # YOLO | RTDETR | BOTH
CONFIDENCE_THRESHOLD=0.5
DEVICE=auto                  # auto | cuda | cpu
```

### 1.4 Place model weights

```
inference-service/models/
├── khawla_v6.pt             ← default PPE model for YOLO
├── khawla_mask_vest.pt      ← optional YOLO mask model
├── yolov8n.pt               ← optional YOLO person model
└── rtdetr-l.pt              ← separate Ultralytics RT-DETR-L weights
```

To download the official COCO-pretrained RT-DETR-L checkpoint, run
`python inference-service/download_rtdetr_model.py` from the repository root.
It is a genuine RT-DETR model, but it is not PPE-trained; fine-tune it on a
PPE dataset before comparing PPE detection quality against the YOLO models.

### 1.5 Configure class mapping

Edit `inference-service/config.py` — `CLASS_MAPPING` dict:

```python
CLASS_MAPPING = {
    0: "gloves",
    1: "hairnet",
    2: "mask",
    3: "no_gloves",
    4: "no_hairnet",
    5: "no_mask",
    6: "incorrect_mask",
}
```

Map integer indices to match your model's training class order.

### 1.6 Start the service

```bash
python app.py
# or
uvicorn app:app --host 0.0.0.0 --port 8001 --reload
```

Service available at: `http://localhost:8001`
API docs at: `http://localhost:8001/docs`

---

## Step 2 — Laravel Backend

### 2.1 Install PHP dependencies

```bash
cd laravel-backend
composer install
```

### 2.2 Configure environment

```bash
copy .env.example .env      # Windows
# cp .env.example .env      # Linux/macOS

php artisan key:generate
```

Edit `.env`:
```env
APP_URL=http://localhost:8000
DB_CONNECTION=sqlite
DB_DATABASE=database/database.sqlite
INFERENCE_SERVICE_URL=http://localhost:8001
```

### 2.3 Create database and run migrations

```bash
# Create the SQLite file
type nul > database\database.sqlite   # Windows
# touch database/database.sqlite      # Linux/macOS

php artisan migrate
php artisan db:seed
```

### 2.4 Start the server

```bash
php artisan serve --port=8000
```

Laravel API available at: `http://localhost:8000/api`

---

## Step 3 — React Frontend

### 3.1 Install dependencies

```bash
cd frontend
npm install
```

### 3.2 Start development server

```bash
npm run dev
```

Frontend available at: `http://localhost:3000`

---

## Full Startup (all 3 services)

Open **three terminal windows**:

```bash
# Terminal 1 — Python Inference Service
cd inference-service
venv\Scripts\activate
python app.py

# Terminal 2 — Laravel Backend
cd laravel-backend
php artisan serve --port=8000

# Terminal 3 — React Frontend
cd frontend
npm run dev
```

Then open: **http://localhost:3000**

---

## API Reference

### Python Inference Service (`:8001`)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Service liveness + model status |
| `POST` | `/session/start` | Start a new inference session |
| `POST` | `/session/stop` | Stop a running session |
| `GET` | `/stream/{id}` | MJPEG stream for a session |
| `POST` | `/model/select` | Switch active model |
| `GET` | `/metrics` | Live FPS / latency / detections |
| `POST` | `/benchmark/start` | Start dual-model comparison |
| `POST` | `/benchmark/stop` | Stop benchmark |
| `GET` | `/benchmark/stream` | Benchmark MJPEG stream |

### Laravel Backend (`:8000/api`)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/sessions` | List all sessions |
| `POST` | `/api/sessions` | Create a session |
| `GET` | `/api/violations` | List violations (filter: `?type=`, `?session_id=`) |
| `POST` | `/api/violations` | Record a violation |
| `GET` | `/api/settings` | Get current settings |
| `PUT` | `/api/settings` | Update settings |

---

## Adding Real Model Weights

When your model weights are ready:

1. Place the YOLO PPE weights at `inference-service/models/khawla_v6.pt`.
2. Place the RT-DETR checkpoint at `inference-service/models/rtdetr-l.pt` or set `RTDETR_MODEL_PATH` in `inference-service/.env`.
3. Train/fine-tune RT-DETR on the PPE classes before using it to assess PPE compliance.
4. Restart the inference service with `cd inference-service` followed by `python app.py`.

No other code changes required.

---

## Benchmark Mode

To compare YOLO vs RT-DETR-L side-by-side:

1. Go to **Model Settings** → select **Compare Both**
2. Go to **Live Monitoring** → Start Session
3. The stream shows both models' bounding boxes and a dual HUD
4. Results are saved to `inference-service/logs/benchmark.csv`

CSV columns: `timestamp, model, frame, fps, latency_ms, detections`

---

## Verification Tests

```bash
# 1. Python service health
curl http://localhost:8001/health

# 2. Laravel health
curl http://localhost:8000/api/health

# 3. Laravel settings (should return defaults)
curl http://localhost:8000/api/settings

# 4. Select YOLO model
curl -X POST http://localhost:8001/model/select \
  -H "Content-Type: application/json" \
  -d "{\"model\": \"YOLO\"}"

# 5. Start a webcam session
curl -X POST http://localhost:8001/session/start \
  -H "Content-Type: application/json" \
  -d "{\"source\": \"0\"}"

# 6. Open MJPEG stream in browser
# → http://localhost:8001/stream/{session_id_from_above}
```

---

## Detection Classes

Configure in `inference-service/config.py`:

```python
CLASS_MAPPING = {
    0: "gloves",
    1: "hairnet",
    2: "mask",
    3: "no_gloves",
    4: "no_hairnet",
    5: "no_mask",
    6: "incorrect_mask",
}

VIOLATION_CLASSES = {"no_gloves", "no_hairnet", "no_mask", "incorrect_mask"}
COMPLIANCE_CLASSES = {"gloves", "hairnet", "mask"}
```

---

## Tracking Output

```
Person ID: 5   Status: COMPLIANT
  ✓ gloves
  ✓ hairnet

Person ID: 8   Status: VIOLATION
  ✗ gloves  ← missing
  ✓ hairnet
```

Compliance is determined by checking which `COMPLIANCE_CLASSES`
appear near each tracked person's bounding box in the current frame.

---

## Technology Stack

| Layer | Technology |
|---|---|
| Detection | Ultralytics YOLO and RT-DETR |
| Tracking | BoT-SORT via Ultralytics |
| Streaming | OpenCV → MJPEG → FastAPI StreamingResponse |
| API | FastAPI + Uvicorn |
| Backend | Laravel 13 + SQLite |
| Frontend | React 19 + Vite + Axios |

---

## Troubleshooting

**"Model file not found"**
→ Place weight files in `inference-service/models/` and restart.

**MJPEG stream not showing**
→ Ensure the inference service is running on port 8001 and a session is active.

**Composer permission errors on Windows**
→ Run your terminal as Administrator, or set `COMPOSER_HOME` to a writable directory.

**CORS errors from React**
→ The Vite dev server proxies `/api` to Laravel. Direct API calls go through `localhost:8001` for streams.
