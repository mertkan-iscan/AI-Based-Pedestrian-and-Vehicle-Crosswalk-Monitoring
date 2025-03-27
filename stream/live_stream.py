import av
import streamlink
import cv2
import time

from region import region_edit

from detection.detected_object import DetectedObject
from detection.inference import run_inference

from detection.tracker import DeepSortTracker
from detection.inference import calculate_foot_location

from detection.path_updater import task_queue

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


def get_region_info(coord):

    loc = (int(coord[0]), int(coord[1]))
    regions = region_edit.get_polygons_for_point(loc, region_edit.region_polygons)

    return regions[0] if regions else "unknown"


def update_tracker_and_draw(img, detections, tracker, persistent_objects):
    font = cv2.FONT_HERSHEY_SIMPLEX
    rects_for_tracker = [det[:5] for det in detections]
    objects = tracker.update(rects_for_tracker)
    detected_objects_list = []

    for objectID, (centroid, bbox) in objects.items():
        if len(bbox) < 5:
            continue

        object_type = DetectedObject.CLASS_NAMES.get(bbox[4], "unknown")
        foot = calculate_foot_location(bbox) if (object_type == "person" and bbox[4] == 0) else None
        location = foot if (object_type == "person" and foot is not None) else centroid
        region = get_region_info(location)

        if objectID in persistent_objects:

            detected_obj = persistent_objects[objectID]

            detected_obj.update_centroid(centroid)
            if object_type == "person" and foot is not None:

                task_queue.put(('update', objectID, foot))
                detected_obj.update_foot(foot)

            detected_obj.region = region

        else:
            detected_obj = DetectedObject(objectID, object_type, centroid, foot, region)
            persistent_objects[objectID] = detected_obj

            if object_type == "person" and foot is not None:
                task_queue.put(('update', objectID, foot))


        cv2.putText(img, f"ID {objectID}", (centroid[0] - 10, centroid[1] - 10),
                    font, 0.5, (0, 0, 255), 2)
        cv2.circle(img, (centroid[0], centroid[1]), 4, (0, 0, 255), -1)

        if foot is not None:
            cv2.circle(img, foot, 4, (255, 0, 0), -1)
            cv2.putText(img, "Foot", (foot[0] - 20, foot[1] + 15),
                        font, 0.5, (255, 0, 0), 2)

        detected_objects_list.append(detected_obj)

    return img, detected_objects_list


def draw_region_info(img, detected_objects):

    for detected_obj in detected_objects:

        if detected_obj.object_type == "person" and detected_obj.foot_coordinate is not None:
            loc = (int(detected_obj.foot_coordinate[0]), int(detected_obj.foot_coordinate[1]))
        else:
            loc = (int(detected_obj.centroid_coordinate[0]), int(detected_obj.centroid_coordinate[1]))

        if detected_obj.region != "unknown":
            cv2.putText(img, "Region: " + detected_obj.region, (loc[0], loc[1] - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)

    return img


def stream_generator(stream_url, polygons_file, skip_frames=2, max_latency=0.5, max_frame_gap=5.0):
    persistent_objects = {}
    region_edit.region_json_file = polygons_file
    region_edit.load_polygons()

    tracker = DeepSortTracker(maxDisappeared=40)

    try:
        container = get_container(stream_url)
    except Exception as e:
        raise Exception(f"Error opening stream: {e}")

    base_pts = None
    frame_count = 0
    prev_detections = []
    start_time = time.time()
    video_stream = container.streams.video[0]

    last_frame_time = time.time()

    try:
        for frame in container.decode(video=0):

            frame_count += 1

            #variable for stream health check
            gap = check_stream_health(last_frame_time, max_frame_gap)
            last_frame_time = time.time()

            if base_pts is None:
                base_pts = frame.pts

            frame_time, current_time, delay = compute_frame_timing(
                frame.pts, base_pts, video_stream, start_time
            )

            processing_allowed = True
            if delay > 0:
                time.sleep(delay)
            else:
                if abs(delay) > max_latency:
                    processing_allowed = False
                    print("Skipping frame, max latency exceeded")

            img = frame.to_ndarray(format='bgr24')

            # Perform detection inference
            detections, prev_detections = process_inference_for_frame(
                img, frame_count, skip_frames, processing_allowed, prev_detections
            )

            # Draw bounding boxes
            img = draw_detections(img, detections)

            # Update tracker and draw tracker info
            img, objects = update_tracker_and_draw(img, detections, tracker, persistent_objects)

            # Overlay regions
            img = region_edit.overlay_regions(img)

            # Draw region info
            img = draw_region_info(img, objects)

            # Draw latency info
            img = draw_latency_info(img, delay)

            # Instead of yielding only `img`, yield both `img` and the list/dict of objects
            yield (img, objects)

    except Exception as e:
        raise Exception(f"Error during streaming: {e}")
    finally:
        container.close()


def check_stream_health(last_frame_time, max_frame_gap):

    current_time = time.time()
    gap = current_time - last_frame_time

    if gap > max_frame_gap:
        print(f"WARNING: No frames received for {gap:.1f}s (exceeds {max_frame_gap}s). Slow or stalled stream?")

    return gap


def draw_latency_info(img, delay):
    latency_text = f"Latency: {abs(delay):.2f} sec"
    cv2.putText(img, latency_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)
    return img