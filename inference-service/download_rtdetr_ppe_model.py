"""Download the pretrained RT-DETR PPE model (gloves/masks) from Hugging Face.

Model: qubvel-hf/rtdetr-r50-cppe5-finetune
RT-DETR R50 fine-tuned on the CPPE-5 medical PPE dataset
(Coverall, Face_Shield, Gloves, Goggles, Mask). Not trained by this project.
"""

from pathlib import Path

from huggingface_hub import snapshot_download


MODEL_ID = "qubvel-hf/rtdetr-r50-cppe5-finetune"
MODEL_DIR = Path(__file__).parent / "models" / "rtdetr-cppe5"


def main() -> None:
    print(f"Downloading {MODEL_ID} to {MODEL_DIR}")
    snapshot_download(
        repo_id=MODEL_ID,
        local_dir=MODEL_DIR,
        allow_patterns=["*.json", "*.safetensors"],
    )
    print("Done.")


if __name__ == "__main__":
    main()
