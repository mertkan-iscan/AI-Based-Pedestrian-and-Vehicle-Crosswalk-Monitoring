import cv2
import time
import warnings
import os

from livestream import get_container
from inference import run_inference
from tracker import CentroidTracker
from region_edit import region_editing, overlay_regions, load_polygons, get_polygons_for_point, region_polygons

warnings.filterwarnings("ignore", category=FutureWarning)

STREAM_URL = "https://content.tvkur.com/l/c77ibcnbb2nj4i0fr8cg/master.m3u8"
SKIP_FRAMES = 4
MAX_LATENCY = 0.5

# Global tracker instance (or reinitialize per stream if needed)
tracker = CentroidTracker(maxDisappeared=40)

def run_live_stream(container):
    base_pts = None
    frame_count = 0
    prev_detections = []
    start_time = time.time()
    video_stream = container.streams.video[0]

    for frame in container.decode(video=0):
        frame_count += 1
        if base_pts is None:
            base_pts = frame.pts
            print("Base PTS set to:", base_pts)
        relative_pts = frame.pts - base_pts if frame.pts is not None else 0
        frame_time = float(relative_pts * video_stream.time_base)
        current_time = time.time() - start_time
        delay = frame_time - current_time

        processing_allowed = True
        if delay > 0:
            time.sleep(delay)
        else:
            if abs(delay) > MAX_LATENCY:
                print(f"Warning: Video lagging by {abs(delay):.2f} sec. Skipping inference.")
                processing_allowed = False

        img = frame.to_ndarray(format='bgr24')

        # YOLO inference every SKIP_FRAMES frames
        if frame_count % SKIP_FRAMES == 0:
            if processing_allowed:
                detections = run_inference(img)
                prev_detections = detections.copy()
            else:
                detections = prev_detections
        else:
            detections = prev_detections

        # Draw YOLO detections
        for det in detections:
            x1, y1, x2, y2, cls, conf = det
            label = f"{cls} {conf:.2f}"
            if cls == 0:
                color = (0, 255, 0)
            elif cls == 2:
                color = (255, 0, 0)
            elif cls == 3:
                color = (255, 0, 255)
            else:
                color = (0, 255, 255)
            cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
            cv2.putText(img, label, (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        # Update tracker and draw detections & foot points
        objects = tracker.update([det[:5] for det in detections])
        for objectID, (centroid, bbox) in objects.items():
            cv2.putText(img, f"ID {objectID}", (centroid[0] - 10, centroid[1] - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
            cv2.circle(img, (centroid[0], centroid[1]), 4, (0, 0, 255), -1)
            if bbox[4] == 0:  # If person
                footX = int((bbox[0] + bbox[2]) / 2.0)
                footY = bbox[3]
                cv2.circle(img, (footX, footY), 4, (255, 0, 0), -1)
                cv2.putText(img, "Foot", (footX - 20, footY + 15),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)

        # Overlay region polygons (this creates a semi-transparent overlay)
        img = overlay_regions(img)

        # Now, redraw the region intersection text on top of the overlay.
        for objectID, (centroid, bbox) in objects.items():
            if bbox[4] == 0:  # If person
                footX = int((bbox[0] + bbox[2]) / 2.0)
                footY = bbox[3]
                # Check which regions contain the foot point.
                regions = get_polygons_for_point((footX, footY), region_polygons)
                if regions:
                    region_text = "Region: " + ", ".join(regions)
                    # Draw the text at the top-left corner of the bounding box
                    cv2.putText(img, region_text, (bbox[0], bbox[1] - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
        # Overlay region polygons
        img = overlay_regions(img)

        # Display latency info
        latency_text = f"Latency: {abs(delay):.2f} sec"
        cv2.putText(img, latency_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0,255,255), 2)

        # Create a resizable window (maximized size with borders)
        cv2.namedWindow("Live Stream with Recognition", cv2.WINDOW_NORMAL)
        cv2.moveWindow("Live Stream with Recognition", 0, 0)
        cv2.resizeWindow("Live Stream with Recognition", 1920, 1080)
        cv2.imshow("Live Stream with Recognition", img)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            return "quit", None
        elif key == ord('e'):
            frozen_frame = img.copy()
            return "edit", frozen_frame

    return "quit", None

def main():

    # Check if CUDA is enabled
    if cv2.cuda.getCudaEnabledDeviceCount() > 0:
        print("CUDA is enabled. Running on GPU.")
    else:
        print("CUDA is not enabled. Running on CPU.")

    load_polygons()
    while True:
        container = get_container(STREAM_URL)
        ret, frozen = run_live_stream(container)
        container.close()
        if ret == "quit":
            break
        elif ret == "edit":
            cv2.namedWindow("Region Editing", cv2.WINDOW_NORMAL)
            cv2.moveWindow("Region Editing", 0, 0)
            cv2.resizeWindow("Region Editing", 1920, 1080)
            region_editing(frozen)
            print("Resuming live stream...")
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
