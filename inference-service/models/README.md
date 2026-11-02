# Model weights

The active YOLO detector uses these local files when present:

- `khawla_v6.pt` — PPE/gloves and hairnet detector (default PPE model)
- `khawla_mask_vest.pt` — optional mask model loaded alongside the PPE model
- `yolov8n.pt` — optional person detector, restricted to COCO class 0

The RT-DETR option loads a separate model through `RTDETRDetector`:

- `rtdetr-cppe5/` (default) — pretrained Hugging Face model [qubvel-hf/rtdetr-r50-cppe5-finetune](https://huggingface.co/qubvel-hf/rtdetr-r50-cppe5-finetune), fine-tuned on CPPE-5 (Coverall, Face_Shield, Gloves, Goggles, Mask). Download with `python inference-service/download_rtdetr_ppe_model.py`. It detects worn gloves and masks only, with no hairnet or violation classes. It was not trained by this project.
- `rtdetr-l.pt` (optional) — COCO-pretrained Ultralytics RT-DETR-L, downloaded with `python inference-service/download_rtdetr_model.py`. Its classes are general objects, not kitchen PPE.

A folder path is loaded with Hugging Face Transformers; a `.pt` path is loaded with Ultralytics. Both are excluded from Git.

Model weights are intentionally excluded from Git because they are binary and may be large. Obtain them from their original sources or provide them locally, and check each model's license and redistribution terms before sharing. If any active file is absent, the related detection branch is unavailable.

