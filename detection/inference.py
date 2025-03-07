import cv2
import torch
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)


device = 'cuda' if torch.cuda.is_available() else 'cpu'
# Load YOLOv5s (you can swap this model with your own)
model = torch.hub.load('ultralytics/yolov5', 'yolov5n', pretrained=True)
# Detect persons (0), cars (2), motorcycles (3)
model.classes = [0, 2, 3]
model.to(device)
model.eval()

def run_inference(img):
    """
    Run YOLOv5 inference on a BGR image.
    Returns a list of detections as tuples: (x1, y1, x2, y2, cls, conf)
    """
    frame_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    with torch.no_grad():
        results = model(frame_rgb)
    boxes = results.xyxy[0].cpu().numpy()
    detections = []
    for box in boxes:
        x1, y1, x2, y2, conf, cls = box
        detections.append((int(x1), int(y1), int(x2), int(y2), int(cls), conf))
    return detections
