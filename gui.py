# gui.py
import tkinter as tk
from tkinter import messagebox
import threading
import cv2
import time

# Import your separate modules
import location_manager  # Handles loading/adding location configs
import region_edit  # Contains region editing functions
from livestream import get_container
from inference import run_inference
from tracker import CentroidTracker

# Global variable for the streaming thread
stream_thread = None


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Pedestrian Cross Monitoring GUI")
        self.geometry("600x400")
        self.selected_location = None
        self.locations = location_manager.load_locations()
        self.create_widgets()

    def create_widgets(self):
        # Listbox to display available locations
        self.location_listbox = tk.Listbox(self, height=10)
        self.location_listbox.pack(fill=tk.BOTH, padx=10, pady=10)
        self.refresh_location_listbox()

        # Button frame
        button_frame = tk.Frame(self)
        button_frame.pack(pady=10)

        tk.Button(button_frame, text="Add Location", command=self.open_add_location_window).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Select Location", command=self.select_location).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Edit Polygons", command=self.edit_polygons).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Run Stream", command=self.run_stream).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Quit", command=self.quit_app).pack(side=tk.LEFT, padx=5)

    def refresh_location_listbox(self):
        self.location_listbox.delete(0, tk.END)
        for loc in self.locations:
            display_text = f"{loc['name']} - {loc.get('camera_name', '')}"
            self.location_listbox.insert(tk.END, display_text)

    def open_add_location_window(self):
        # Open a new window to add a location (see separate AddLocationWindow class below)
        AddLocationWindow(self)

    def select_location(self):
        try:
            index = self.location_listbox.curselection()[0]
            self.selected_location = self.locations[index]
            messagebox.showinfo("Location Selected", f"Selected: {self.selected_location['name']}")
        except IndexError:
            messagebox.showerror("Error", "No location selected.")

    def edit_polygons(self):
        if not self.selected_location:
            messagebox.showerror("Error", "Please select a location first.")
            return

        # Set the polygons file for the region editor from the selected location
        region_edit.region_json_file = self.selected_location["polygons_file"]
        region_edit.load_polygons()

        # Capture a single frame from the live stream to use for region editing
        frame = get_single_frame(self.selected_location["stream_url"])
        if frame is None:
            messagebox.showerror("Error", "Could not retrieve a frame from the stream.")
            return

        region_edit.region_editing(frame)

    def run_stream(self):
        if not self.selected_location:
            messagebox.showerror("Error", "Please select a location first.")
            return

        # Set the correct polygon file for the stream
        region_edit.region_json_file = self.selected_location["polygons_file"]
        region_edit.load_polygons()

        # Launch the live stream in a new thread so the GUI remains responsive
        global stream_thread
        if stream_thread is None or not stream_thread.is_alive():
            stream_thread = threading.Thread(target=run_live_stream, args=(self.selected_location["stream_url"],))
            stream_thread.start()
        else:
            messagebox.showinfo("Info", "Stream is already running.")

    def quit_app(self):
        self.destroy()


class AddLocationWindow(tk.Toplevel):
    """
    A separate window for adding a new location.
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Add Location")
        self.geometry("300x250")
        self.parent = parent

        tk.Label(self, text="Location Name:").pack(pady=5)
        self.name_entry = tk.Entry(self)
        self.name_entry.pack(pady=5)

        tk.Label(self, text="Camera Name (optional):").pack(pady=5)
        self.camera_entry = tk.Entry(self)
        self.camera_entry.pack(pady=5)

        tk.Label(self, text="Stream URL:").pack(pady=5)
        self.stream_entry = tk.Entry(self)
        self.stream_entry.pack(pady=5)

        tk.Label(self, text="Polygons File:").pack(pady=5)
        self.poly_entry = tk.Entry(self)
        self.poly_entry.pack(pady=5)

        tk.Button(self, text="Add", command=self.add_location).pack(pady=10)
        tk.Button(self, text="Cancel", command=self.destroy).pack()

    def add_location(self):
        name = self.name_entry.get().strip()
        camera_name = self.camera_entry.get().strip()
        stream_url = self.stream_entry.get().strip()
        polygons_file = self.poly_entry.get().strip()

        if not name or not stream_url or not polygons_file:
            messagebox.showerror("Error", "Name, Stream URL, and Polygons File are required.")
            return

        new_loc = {
            "name": name,
            "camera_name": camera_name,
            "stream_url": stream_url,
            "polygons_file": polygons_file
        }
        location_manager.add_location(new_loc)
        self.parent.locations = location_manager.load_locations()
        self.parent.refresh_location_listbox()
        self.destroy()


def get_single_frame(stream_url):
    """
    Grab a single frame from the live stream (using get_container from livestream.py).
    """
    try:
        container = get_container(stream_url)
        for frame in container.decode(video=0):
            img = frame.to_ndarray(format='bgr24')
            container.close()
            return img
    except Exception as e:
        print("Error capturing frame:", e)
    return None


def run_live_stream(stream_url):
    """
    Run the live stream with YOLO inference, object tracking, and region overlays.
    This function replicates the logic in your original main.py.
    Press 'q' in the OpenCV window to exit the stream.
    """
    SKIP_FRAMES = 4
    MAX_LATENCY = 0.5
    tracker = CentroidTracker(maxDisappeared=40)

    try:
        container = get_container(stream_url)
    except Exception as e:
        print("Error opening stream:", e)
        return

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

        # YOLO inference on every SKIP_FRAMES frame
        if frame_count % SKIP_FRAMES == 0:
            if processing_allowed:
                detections = run_inference(img)
                prev_detections = detections.copy()
            else:
                detections = prev_detections
        else:
            detections = prev_detections

        # Draw detections
        for det in detections:
            x1, y1, x2, y2, cls, conf = det
            label = f"{cls} {conf:.2f}"
            color = (0, 255, 0) if cls == 0 else (255, 0, 0) if cls == 2 else (255, 0, 255) if cls == 3 else (
            0, 255, 255)
            cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
            cv2.putText(img, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        # Update tracker and draw IDs/foot points
        rects_for_tracker = [det[:5] for det in detections]
        objects = tracker.update(rects_for_tracker)

        for objectID, (centroid, bbox) in objects.items():
            cv2.putText(img, f"ID {objectID}", (centroid[0] - 10, centroid[1] - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
            cv2.circle(img, (centroid[0], centroid[1]), 4, (0, 0, 255), -1)
            # If person detected (cls == 0), draw foot point
            if bbox[4] == 0:
                footX = int((bbox[0] + bbox[2]) / 2.0)
                footY = bbox[3]
                cv2.circle(img, (footX, footY), 4, (255, 0, 0), -1)
                cv2.putText(img, "Foot", (footX - 20, footY + 15),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)

        # Overlay region polygons and region names
        img = region_edit.overlay_regions(img)
        for objectID, (centroid, bbox) in objects.items():
            if bbox[4] == 0:
                footX = int((bbox[0] + bbox[2]) / 2.0)
                footY = bbox[3]
                regions = region_edit.get_polygons_for_point((footX, footY), region_edit.region_polygons)
                if regions:
                    region_text = "Region: " + ", ".join(regions)
                    cv2.putText(img, region_text, (bbox[0], bbox[1] - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
        img = region_edit.overlay_regions(img)
        latency_text = f"Latency: {abs(delay):.2f} sec"
        cv2.putText(img, latency_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)

        cv2.namedWindow("Live Stream", cv2.WINDOW_NORMAL)
        cv2.moveWindow("Live Stream", 0, 0)
        cv2.resizeWindow("Live Stream", 1280, 720)
        cv2.imshow("Live Stream", img)
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break

    container.close()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    app = App()
    app.mainloop()
