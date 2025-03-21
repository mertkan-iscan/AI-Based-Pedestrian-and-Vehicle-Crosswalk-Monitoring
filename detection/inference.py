import cv2
import torch
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

device = 'cuda' if torch.cuda.is_available() else 'cpu'

model = torch.hub.load('ultralytics/yolov5', 'yolov5n', pretrained=True)

model.classes = [0, 2, 3]
model.to(device)
model.eval()

def run_inference(img):

    frame_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    with torch.no_grad():
        results = model(frame_rgb)
    boxes = results.xyxy[0].cpu().numpy()
    detections = []
    for box in boxes:

        x1, y1, x2, y2, conf, cls = box
        detections.append((int(x1), int(y1), int(x2), int(y2), int(cls), conf))
    return detections

def calculate_foot_location(bbox):

    if not (isinstance(bbox, (list, tuple)) and len(bbox) >= 4):
        raise ValueError("bbox must be a list or tuple with at least 4 elements: [x1, y1, x2, y2]")

    x1, y1, x2, y2 = bbox[:4]
    foot_x = int((x1 + x2) / 2)
    foot_y = y2

    return foot_x, foot_y