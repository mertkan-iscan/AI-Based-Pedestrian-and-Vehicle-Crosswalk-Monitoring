# gui.py
import os
import json
import uuid
import time
import cv2
import numpy as np

from PyQt5 import QtCore, QtGui, QtWidgets

# Import logic functions from live_stream.py instead of duplicating them
from stream.live_stream import get_single_frame, stream_generator
from region import region_edit, location_manager

# ---------------------------
# QThread for live stream
# ---------------------------
class VideoStreamThread(QtCore.QThread):
    frame_ready = QtCore.pyqtSignal(QtGui.QImage)
    error_signal = QtCore.pyqtSignal(str)

    def __init__(self, stream_url, polygons_file, parent=None):
        super().__init__(parent)
        self.stream_url = stream_url
        self.polygons_file = polygons_file
        self._is_running = True

    def run(self):
        try:
            # Iterate over frames provided by the stream_generator
            for img in stream_generator(self.stream_url, self.polygons_file):
                if not self._is_running:
                    break
                # Convert BGR image to RGB QImage and apply .copy() for safety
                rgb_image = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                height, width, channel = rgb_image.shape
                bytes_per_line = 3 * width
                q_img = QtGui.QImage(rgb_image.data, width, height, bytes_per_line,
                                     QtGui.QImage.Format_RGB888).copy()
                self.frame_ready.emit(q_img)
        except Exception as e:
            self.error_signal.emit(str(e))

    def stop(self):
        self._is_running = False
        self.wait()

# ---------------------------
# Video Player Window
# ---------------------------
class VideoPlayerWindow(QtWidgets.QMainWindow):
    def __init__(self, location, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Live Stream - {location['name']}")
        self.resize(800, 600)
        self.location = location
        self.initUI()
        self.start_stream()

    def initUI(self):
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        layout = QtWidgets.QVBoxLayout(central_widget)

        self.video_label = QtWidgets.QLabel()
        self.video_label.setAlignment(QtCore.Qt.AlignCenter)
        self.video_label.setScaledContents(True)
        layout.addWidget(self.video_label)

        stop_btn = QtWidgets.QPushButton("Stop Stream")
        stop_btn.clicked.connect(self.stop_stream)
        layout.addWidget(stop_btn)

    def start_stream(self):
        self.stream_thread = VideoStreamThread(self.location["stream_url"], self.location["polygons_file"])
        self.stream_thread.frame_ready.connect(self.update_frame)
        self.stream_thread.error_signal.connect(self.handle_error)
        self.stream_thread.start()

    def update_frame(self, q_img):
        self.video_label.setPixmap(QtGui.QPixmap.fromImage(q_img))

    def handle_error(self, error_msg):
        QtWidgets.QMessageBox.critical(self, "Stream Error", error_msg)
        self.stop_stream()

    def stop_stream(self):
        if hasattr(self, "stream_thread") and self.stream_thread is not None:
            self.stream_thread.stop()
            self.stream_thread = None
        self.close()

    def closeEvent(self, event):
        self.stop_stream()
        event.accept()

# ---------------------------
# Main Application Window and AddLocationDialog remain unchanged
# ---------------------------
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pedestrian Cross Monitoring GUI")
        self.resize(800, 600)
        self.locations = location_manager.load_locations()
        self.selected_location = None
        self.initUI()

    def initUI(self):
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        layout = QtWidgets.QVBoxLayout(central_widget)

        # List of locations
        self.location_list = QtWidgets.QListWidget()
        self.refresh_location_list()
        self.location_list.itemSelectionChanged.connect(self.on_location_selected)
        layout.addWidget(self.location_list)

        # Buttons panel
        btn_layout = QtWidgets.QHBoxLayout()
        add_btn = QtWidgets.QPushButton("Add Location")
        add_btn.clicked.connect(self.open_add_location_dialog)
        btn_layout.addWidget(add_btn)

        edit_btn = QtWidgets.QPushButton("Edit Polygons")
        edit_btn.clicked.connect(self.edit_polygons)
        btn_layout.addWidget(edit_btn)

        run_btn = QtWidgets.QPushButton("Run Stream")
        run_btn.clicked.connect(self.run_stream)
        btn_layout.addWidget(run_btn)

        delete_btn = QtWidgets.QPushButton("Delete Location")
        delete_btn.clicked.connect(self.delete_location)
        btn_layout.addWidget(delete_btn)

        quit_btn = QtWidgets.QPushButton("Quit")
        quit_btn.clicked.connect(self.close)
        btn_layout.addWidget(quit_btn)

        layout.addLayout(btn_layout)

    def refresh_location_list(self):
        self.location_list.clear()
        self.locations = location_manager.load_locations()
        for loc in self.locations:
            self.location_list.addItem(loc["name"])

    def on_location_selected(self):
        selected_items = self.location_list.selectedItems()
        if selected_items:
            selected_name = selected_items[0].text()
            for loc in self.locations:
                if loc["name"] == selected_name:
                    self.selected_location = loc
                    break

    def open_add_location_dialog(self):
        dialog = AddLocationDialog(self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            self.refresh_location_list()

    def edit_polygons(self):
        if not self.selected_location:
            QtWidgets.QMessageBox.critical(self, "Error", "Please select a location first.")
            return

        from stream.live_stream import get_single_frame
        region_edit.region_json_file = self.selected_location["polygons_file"]
        region_edit.load_polygons()
        frame = get_single_frame(self.selected_location["stream_url"])
        if frame is None:
            QtWidgets.QMessageBox.critical(self, "Error", "Could not retrieve a frame from the stream.")
            return
        region_edit.region_editing(frame)

    def run_stream(self):
        if not self.selected_location:
            QtWidgets.QMessageBox.critical(self, "Error", "Please select a location first.")
            return
        self.video_window = VideoPlayerWindow(self.selected_location)
        self.video_window.show()

    def delete_location(self):
        if not self.selected_location:
            QtWidgets.QMessageBox.critical(self, "Error", "Please select a location first.")
            return

        reply = QtWidgets.QMessageBox.question(
            self,
            "Delete Location",
            f"Are you sure you want to delete '{self.selected_location['name']}'?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        if reply == QtWidgets.QMessageBox.Yes:
            location_manager.delete_location(self.selected_location)
            self.selected_location = None
            self.refresh_location_list()

class AddLocationDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Location")
        self.resize(300, 200)
        self.setupUI()

    def setupUI(self):
        layout = QtWidgets.QVBoxLayout(self)
        name_label = QtWidgets.QLabel("Location Name:")
        self.name_edit = QtWidgets.QLineEdit()
        layout.addWidget(name_label)
        layout.addWidget(self.name_edit)

        stream_label = QtWidgets.QLabel("Stream URL:")
        self.stream_edit = QtWidgets.QLineEdit()
        layout.addWidget(stream_label)
        layout.addWidget(self.stream_edit)

        btn_layout = QtWidgets.QHBoxLayout()
        add_btn = QtWidgets.QPushButton("Add")
        add_btn.clicked.connect(self.add_location)
        btn_layout.addWidget(add_btn)

        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def add_location(self):
        name = self.name_edit.text().strip()
        stream_url = self.stream_edit.text().strip()

        if not name or not stream_url:
            QtWidgets.QMessageBox.critical(self, "Error", "Name and Stream URL are required.")
            return

        import uuid
        import os
        polygons_file = os.path.join("config", "location_regions", f"polygons_{uuid.uuid4().hex}.json")
        new_loc = {
            "name": name,
            "stream_url": stream_url,
            "polygons_file": polygons_file
        }
        location_manager.add_location(new_loc)

        if not os.path.exists(polygons_file):
            with open(polygons_file, "w") as f:
                import json
                json.dump([], f, indent=4)
            print(f"Created new polygons file: {polygons_file}")

        self.accept()
