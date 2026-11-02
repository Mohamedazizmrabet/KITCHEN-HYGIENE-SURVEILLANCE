# KitchenWatch — Intelligent Kitchen Hygiene Surveillance System

Real-time PPE compliance monitoring prototype with independent YOLO and RT-DETR inference paths.

```
                ┌────────────────────────────────────────────┐
                │           React Frontend :3000             │
                │ Dashboard | Live Monitor | Violations |    │
                │ Settings                                   │
                └──────┬──────────────────────────┬──────────┘
     sessions, settings,│ (Axios)                  │ start/stop sessions,
     violation history  ▼                          ▼ MJPEG stream, metrics
┌────────────────────────────┐  violations  ┌────────────────────────────┐
│   Laravel Backend :8000    │◄─────────────│ Python Inference :8001     │
│ Sessions · Violations ·    │              │ YOLO / RT-DETR → BoT-SORT  │
│ Settings · SQLite          │              │ → MJPEG stream             │
└────────────────────────────┘              └────────────────────────────┘
```

---

## Project Structure

```
KITCHEN-HYGIENE-SURVEILLANCE/
├── inference-service/       Python FastAPI — detection, tracking, streaming
├── laravel-backend/         PHP Laravel — sessions, violations, settings
├── frontend/                React Vite — dashboard UI
├── imagesToTest/            sample images (local only, not in Git)
└── PROJECT_NOTES.txt        project summary, model choices and limitations
```

---

## Quick Start

### Prerequisites

| Tool | Version |
|---|---|
| Python | 3.11 (≥ 3.10) |
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
python -m venv venv311   # Python 3.11

# Windows
venv311\Scripts\activate

# Linux / macOS
source venv311/bin/activate
```

### 1.2 Install dependencies

```bash
pip install -r requirements.txt
```

> For CUDA GPU acceleration, install PyTorch with CUDA first:
> ```bash
> pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
> ```
>
> `requirements.txt` includes `transformers`, which the RT-DETR model needs.

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
└── rtdetr-cppe5/            ← default RT-DETR model (Hugging Face, gloves + masks)
```

The default RT-DETR model is the pretrained
[qubvel-hf/rtdetr-r50-cppe5-finetune](https://huggingface.co/qubvel-hf/rtdetr-r50-cppe5-finetune),
fine-tuned on the CPPE-5 dataset (Coverall, Face_Shield, Gloves, Goggles, Mask).
Download it with `python inference-service/download_rtdetr_ppe_model.py` from the
repository root. It has no hairnet or violation classes, so it detects worn gloves
and masks only.

To use the COCO-pretrained Ultralytics checkpoint instead, run
`python inference-service/download_rtdetr_model.py` and set
`RTDETR_MODEL_PATH=models/rtdetr-l.pt`. It is not PPE-trained.

### 1.5 Configure class names

Each model uses its own class names. `CLASS_NORMALISE` in
`inference-service/config.py` maps them to the names the app uses:

```python
CLASS_NORMALISE = {
    "Glove":     "gloves",      # khawla_v6
    "Bare Hand": "no_gloves",
    "Hairnet":   "hairnet",
    "Bare Hair": "no_hairnet",
    "Mask":      "mask",        # khawla_mask_vest and rtdetr-cppe5
    "NO-Mask":   "no_mask",
    "Person":    "person",
    "Gloves":    "gloves",      # rtdetr-cppe5
    ...
}
```

If you add a model with different class names, add its names here.

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
venv311\Scripts\activate
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
| `POST` | `/session/start` | Start a session (`source`, `model`: `YOLO` or `RT`, optional `laravel_session_id`) |
| `POST` | `/session/stop` | Stop a running session |
| `GET` | `/stream/{id}` | MJPEG stream for a session |
| `GET` | `/session/{id}/tracks` | Tracked persons and their PPE status |
| `GET` | `/session/{id}/snapshots` | List violation snapshots |
| `GET` | `/session/{id}/snapshots/full` | Snapshots with images |
| `GET` | `/snapshot/{snapshot_id}/download` | Download one snapshot as JPEG |
| `GET` / `POST` | `/config/ppe` | Read or change which PPE items are checked |
| `POST` | `/model/select` | Switch active model (`YOLO`, `RT`, `BOTH`) |
| `GET` | `/metrics` | Live FPS / latency / detections |
| `POST` | `/benchmark/start` | Start dual-model comparison |
| `POST` | `/benchmark/stop` | Stop benchmark |
| `GET` | `/benchmark/stream` | Benchmark MJPEG stream |

### Laravel Backend (`:8000/api`)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Service liveness |
| `GET` | `/api/sessions` | List all sessions with their violations |
| `POST` | `/api/sessions` | Create a session record |
| `GET` | `/api/sessions/{id}` | One session with its violations |
| `DELETE` | `/api/sessions/{id}` | Mark a session as stopped |
| `GET` | `/api/violations` | List violations (filter: `?type=`, `?session_id=`) |
| `POST` | `/api/violations` | Record a violation (sent by the inference service) |
| `GET` | `/api/violations/{id}` | One violation |
| `GET` | `/api/settings` | Get current settings |
| `PUT` | `/api/settings` | Update settings |
| `GET` | `/api/inference/health`, `/api/inference/metrics` | Proxies to the inference service |
| `POST` | `/api/inference/model/select` | Proxy to the inference service |

---

## Adding Real Model Weights

When your model weights are ready:

1. Place the YOLO PPE weights at `inference-service/models/khawla_v6.pt`.
2. Download the RT-DETR model with `python inference-service/download_rtdetr_ppe_model.py`, or set `RTDETR_MODEL_PATH` in `inference-service/.env` to another Hugging Face model folder or Ultralytics `.pt` file.
3. Fine-tune RT-DETR on kitchen PPE classes (including hairnets and violations) for a fair comparison with YOLO.
4. Restart the inference service with `cd inference-service` followed by `python app.py`.

No other code changes required.

---

## Benchmark Mode

To compare YOLO vs RT-DETR side-by-side:

1. Go to **Live Monitoring** → select **Compare Both** (or choose it in **Model Settings**, which pre-selects it)
2. Click **Start Session**
3. The stream shows both models' bounding boxes and a YOLOv8 / RT-DETR metrics panel
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

Configured in `inference-service/config.py`:

```python
COMPLIANCE_CLASSES = {"gloves", "hairnet", "mask"}
VIOLATION_CLASSES = {"no_gloves", "no_hairnet", "no_mask"}
```

| Model | Detects |
|---|---|
| YOLO (khawla_v6 + khawla_mask_vest + yolov8n) | gloves, hairnet, mask, their violations, person |
| RT-DETR (rtdetr-cppe5) + yolov8n for persons | gloves, mask, person — **no hairnet** |

The PPE items to check can also be switched on and off live from the
**Live Monitoring** page.

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
A missing item counts as a violation, except items the active model
cannot detect: in RT-DETR mode hairnet is shown as "—" (not checked).

When a person gets a new violation, the inference service saves a
snapshot and records the violation in Laravel against the current
session, so it appears on the **Violations** page.

---

## Technology Stack

| Layer | Technology |
|---|---|
| Detection | Ultralytics YOLOv8; RT-DETR via Hugging Face Transformers |
| Tracking | BoT-SORT via Ultralytics |
| Streaming | OpenCV → MJPEG → FastAPI StreamingResponse |
| API | FastAPI + Uvicorn |
| Backend | Laravel 13 + SQLite |
| Frontend | React 19 + Vite + Axios |

---

## Running the Tests

```bash
cd inference-service
venv311\Scripts\activate
python -m pytest tests
```

The tests check the detector interface and configuration without needing
the model weights.

---

## Limitations

- This is a prototype; it does not replace human supervision.
- Detection is unreliable when a person is far from the camera (PPE items
  are only a few pixels wide).
- The RT-DETR model was trained on medical PPE images (CPPE-5), not kitchen
  footage, and cannot detect hairnets. A fair YOLO vs RT-DETR comparison
  needs both models trained on the same kitchen dataset.
- The final end-to-end check used a video file; test a webcam or RTSP
  camera before relying on it.

See `PROJECT_NOTES.txt` for more detail.

---

## Credits

- [Ultralytics YOLOv8](https://docs.ultralytics.com/models/yolov8) — `yolov8n.pt` person detector and the YOLO framework
- [qubvel-hf/rtdetr-r50-cppe5-finetune](https://huggingface.co/qubvel-hf/rtdetr-r50-cppe5-finetune) — pretrained RT-DETR model (gloves, masks)
- `khawla_v6.pt` and `khawla_mask_vest.pt` — third-party YOLOv8 PPE weights; see `PROJECT_NOTES.txt` for what is known about their source

Model weights are not included in this repository. Check each model's
license before redistributing it.

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
