# Model weights

The active YOLO detector uses these local files when present:

- `khawla_v6.pt` — PPE/gloves and hairnet detector (default PPE model)
- `khawla_mask_vest.pt` — optional mask model loaded alongside the PPE model
- `yolov8n.pt` — optional person detector, restricted to COCO class 0

The RT-DETR option loads a separate, genuine Ultralytics RT-DETR-L checkpoint:

- `rtdetr-l.pt` — COCO-pretrained RT-DETR-L model, loaded by `RTDETRDetector`

Download this checkpoint with `python inference-service/download_rtdetr_model.py` from the repository root. The checkpoint is large and excluded from Git. It is pretrained on COCO, so its default classes are general objects rather than kitchen PPE. Fine-tune an RT-DETR model on the project's PPE dataset before evaluating it as a PPE detector or claiming a meaningful PPE model comparison.

Model weights are intentionally excluded from Git because they are binary and may be large. Obtain them from their original sources or provide them locally, and check each model's license and redistribution terms before sharing. If any active file is absent, the related detection branch is unavailable.

`unused/` contains other weight files found in this workspace. They are retained for reference and are not referenced by the current default detector configuration.
