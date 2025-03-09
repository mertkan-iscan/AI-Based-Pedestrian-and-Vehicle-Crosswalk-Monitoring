import av
import streamlink
import cv2
import time
from detection.inference import run_inference
from detection.tracker import CentroidTracker
from region import region_edit

def get_container(url):

    streams = streamlink.streams(url)
    if "best" not in streams:
        raise Exception("No suitable stream found.")
    stream_obj = streams["best"]
    raw_stream = stream_obj.open()

    class StreamWrapper:
        def read(self, size=-1):
            return raw_stream.read(size)
        def readable(self):
            return True

    wrapped = StreamWrapper()
    container = av.open(wrapped)
    return container

def frame_generator(container):

    for frame in container.decode(video=0):
        yield frame.to_ndarray(format='bgr24')

def get_single_frame(stream_url):

    try:
        container = get_container(stream_url)
        for frame in container.decode(video=0):
            img = frame.to_ndarray(format='bgr24')
            container.close()
            return img
    except Exception as e:
        print("Error capturing frame:", e)
    return None

def compute_frame_timing(frame_pts, base_pts, video_stream, start_time):

    relative_pts = frame_pts - base_pts if frame_pts is not None else 0
    frame_time = float(relative_pts * video_stream.time_base)
    current_time = time.time() - start_time
    delay = frame_time - current_time
    return frame_time, current_time, delay

def process_inference_for_frame(img, frame_count, skip_frames, processing_allowed, prev_detections):

    if frame_count % skip_frames == 0:
        if processing_allowed:
            detections = run_inference(img)
            prev_detections = detections.copy()
        else:
            detections = prev_detections
    else:
        detections = prev_detections
    return detections, prev_detections

def draw_detections(img, detections):

    for det in detections:
        x1, y1, x2, y2, cls, conf = det
        label = f"{cls} {conf:.2f}"
        color = (0, 255, 0) if cls == 0 else (255, 0, 0) if cls == 2 else (255, 0, 255) if cls == 3 else (0, 255, 255)
        cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
        cv2.putText(img, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
    return img

def update_tracker_and_draw(img, detections, tracker):

    rects_for_tracker = [det[:5] for det in detections]
    objects = tracker.update(rects_for_tracker)
    for objectID, (centroid, bbox) in objects.items():
        cv2.putText(img, f"ID {objectID}", (centroid[0] - 10, centroid[1] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
        cv2.circle(img, (centroid[0], centroid[1]), 4, (0, 0, 255), -1)
        if bbox[4] == 0:
            footX = int((bbox[0] + bbox[2]) / 2.0)
            footY = bbox[3]
            cv2.circle(img, (footX, footY), 4, (255, 0, 0), -1)
            cv2.putText(img, "Foot", (footX - 20, footY + 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
    return img, objects

def draw_region_info(img, objects):

    for objectID, (centroid, bbox) in objects.items():
        if bbox[4] == 0:
            footX = int((bbox[0] + bbox[2]) / 2.0)
            footY = bbox[3]
            regions = region_edit.get_polygons_for_point((footX, footY), region_edit.region_polygons)
            if regions:
                region_text = "Region: " + ", ".join(regions)
                cv2.putText(img, region_text, (bbox[0], bbox[1] - 25),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
    return img

def draw_latency_info(img, delay):

    latency_text = f"Latency: {abs(delay):.2f} sec"
    cv2.putText(img, latency_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)
    return img

def stream_generator(stream_url, polygons_file, skip_frames=4, max_latency=0.5):

    region_edit.region_json_file = polygons_file
    region_edit.load_polygons()

    tracker = CentroidTracker(maxDisappeared=40)
    try:
        container = get_container(stream_url)
    except Exception as e:
        raise Exception(f"Error opening stream: {e}")

    base_pts = None
    frame_count = 0
    prev_detections = []
    start_time = time.time()
    video_stream = container.streams.video[0]

    try:
        for frame in container.decode(video=0):
            frame_count += 1
            if base_pts is None:
                base_pts = frame.pts

            frame_time, current_time, delay = compute_frame_timing(frame.pts, base_pts, video_stream, start_time)

            processing_allowed = True
            if delay > 0:
                time.sleep(delay)
            else:
                if abs(delay) > max_latency:
                    processing_allowed = False
                    print("Skipping frame, max latency exceeded")

            img = frame.to_ndarray(format='bgr24')

            detections, prev_detections = process_inference_for_frame(img, frame_count, skip_frames, processing_allowed, prev_detections)

            img = draw_detections(img, detections)

            img, objects = update_tracker_and_draw(img, detections, tracker)

            img = region_edit.overlay_regions(img)

            img = draw_region_info(img, objects)

            img = draw_latency_info(img, delay)


            yield img

    except Exception as e:
        raise Exception(f"Error during streaming: {e}")
    finally:
        container.close()