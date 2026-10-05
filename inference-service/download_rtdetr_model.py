"""Download the official Ultralytics RT-DETR-L COCO checkpoint locally."""

from pathlib import Path
from urllib.request import urlopen


MODEL_URL = "https://github.com/ultralytics/assets/releases/download/v8.4.0/rtdetr-l.pt"
MODEL_PATH = Path(__file__).parent / "models" / "rtdetr-l.pt"


def main() -> None:
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = MODEL_PATH.with_suffix(".pt.download")
    print(f"Downloading official RT-DETR-L checkpoint to {MODEL_PATH}")
    try:
        with urlopen(MODEL_URL, timeout=60) as response, temporary_path.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
        if temporary_path.stat().st_size == 0:
            raise RuntimeError("The downloaded checkpoint is empty.")
        temporary_path.replace(MODEL_PATH)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
    print(f"Saved {MODEL_PATH.stat().st_size:,} bytes.")


if __name__ == "__main__":
    main()
