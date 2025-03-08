import tkinter as tk
from tkinter import messagebox
import threading
import os
import json

from region import location_manager, region_edit
from stream.stream_processor import get_single_frame, run_live_stream

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
        self.location_listbox.bind('<<ListboxSelect>>', self.on_location_selected)
        self.refresh_location_listbox()

        # Button frame
        button_frame = tk.Frame(self)
        button_frame.pack(pady=10)

        tk.Button(button_frame, text="Add Location", command=self.open_add_location_window).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Edit Polygons", command=self.edit_polygons).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Run Stream", command=self.run_stream).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Delete Location", command=self.delete_location).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Quit", command=self.quit_app).pack(side=tk.LEFT, padx=5)

    def refresh_location_listbox(self):
        self.location_listbox.delete(0, tk.END)
        for loc in self.locations:
            display_text = f"{loc['name']}"
            self.location_listbox.insert(tk.END, display_text)

    def open_add_location_window(self):
        AddLocationWindow(self)

    def on_location_selected(self, event):
        try:
            index = self.location_listbox.curselection()[0]
            self.selected_location = self.locations[index]
            print(f"Selected: {self.selected_location['name']}")
        except IndexError:
            self.selected_location = None

    def edit_polygons(self):
        if not self.selected_location:
            messagebox.showerror("Error", "Please select a location first.")
            return

        # Set the polygon file for the region editor from the selected location
        region_edit.region_json_file = self.selected_location["polygons_file"]
        region_edit.load_polygons()

        # Grab a single frame from the live stream to use for region editing
        frame = get_single_frame(self.selected_location["stream_url"])
        if frame is None:
            messagebox.showerror("Error", "Could not retrieve a frame from the stream.")
            return

        region_edit.region_editing(frame)

    def run_stream(self):
        if not self.selected_location:
            messagebox.showerror("Error", "Please select a location first.")
            return

        # Set the polygon file for the stream
        region_edit.region_json_file = self.selected_location["polygons_file"]
        region_edit.load_polygons()

        # Launch the live stream in a new thread so the GUI remains responsive
        stream_thread = threading.Thread(target=run_live_stream, args=(self.selected_location["stream_url"],))
        stream_thread.start()

    def delete_location(self):
        if not self.selected_location:
            messagebox.showerror("Error", "Please select a location first.")
            return

        # Confirm deletion
        confirm = messagebox.askyesno("Delete Location", f"Are you sure you want to delete '{self.selected_location['name']}'?")
        if not confirm:
            return

        # Call the delete function from location_manager
        location_manager.delete_location(self.selected_location)
        # Refresh the locations list
        self.locations = location_manager.load_locations()
        self.refresh_location_listbox()
        self.selected_location = None

    def quit_app(self):
        self.destroy()


class AddLocationWindow(tk.Toplevel):
    """
    A separate window for adding a new location.
    """
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Add Location")
        self.geometry("300x200")
        self.parent = parent

        tk.Label(self, text="Location Name:").pack(pady=5)
        self.name_entry = tk.Entry(self)
        self.name_entry.pack(pady=5)

        tk.Label(self, text="Stream URL:").pack(pady=5)
        self.stream_entry = tk.Entry(self)
        self.stream_entry.pack(pady=5)

        tk.Button(self, text="Add", command=self.add_location).pack(pady=10)
        tk.Button(self, text="Cancel", command=self.destroy).pack()

    def add_location(self):
        name = self.name_entry.get().strip()
        stream_url = self.stream_entry.get().strip()

        if not name or not stream_url:
            messagebox.showerror("Error", "Name and Stream URL are required.")
            return

        # Generate a random polygons file name.
        import uuid
        polygons_file = os.path.join("config", "location_regions", f"polygons_{uuid.uuid4().hex}.json")

        new_loc = {
            "name": name,
            "stream_url": stream_url,
            "polygons_file": polygons_file
        }
        location_manager.add_location(new_loc)

        # Create the polygons file if it doesn't exist.
        if not os.path.exists(polygons_file):
            with open(polygons_file, "w") as f:
                json.dump([], f, indent=4)
            print(f"Created new polygons file: {polygons_file}")

        self.parent.locations = location_manager.load_locations()
        self.parent.refresh_location_listbox()
        self.destroy()