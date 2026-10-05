import urllib.request
from ultralytics import YOLO

url = "https://huggingface.co/Hexmon/vyra-yolo-ppe-detection/resolve/main/best.pt"
print(f"Downloading model from {url}...")
urllib.request.urlretrieve(url, "models/temp_ppe.pt")

model = YOLO("models/temp_ppe.pt")
print("Model classes:")
print(model.names)
