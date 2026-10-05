from ultralytics import YOLO

def check_model(path):
    print(f"\n--- Checking {path} ---")
    try:
        model = YOLO(path)
        print("Classes:")
        for idx, name in model.names.items():
            print(f"  {idx}: {name}")
    except Exception as e:
        print(f"Failed: {e}")

check_model(r"C:\Users\aziz4\Desktop\trainF\inference-service\models\keremberke_ppe.pt")
