import json
import os
import uuid
import tkinter as tk
from tkinter import simpledialog, messagebox

CONFIG_FILE = "config/locations.json"

def load_locations():
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as f:
            json.dump([], f, indent=4)
        print(f"{CONFIG_FILE} not found. Created a new one.")
        return []
    with open(CONFIG_FILE, "r") as f:
        locations = json.load(f)
    return locations

def add_location(location):
    locations = load_locations()
    locations.append(location)
    with open(CONFIG_FILE, "w") as f:
        json.dump(locations, f, indent=4)
    print(f"Added location: {location['name']}")

def delete_location(location):
    """
    Delete a location from the locations file.
    Also remove the associated polygons file if it exists.
    """
    locations = load_locations()
    # Filter out the location to delete. Here, we assume the location is uniquely identified by its dictionary.
    updated_locations = [loc for loc in locations if loc != location]
    with open(CONFIG_FILE, "w") as f:
        json.dump(updated_locations, f, indent=4)
    print(f"Deleted location: {location['name']}")
    # Remove the associated polygons file if it exists.
    polygons_file = location.get("polygons_file")
    if polygons_file and os.path.exists(polygons_file):
        os.remove(polygons_file)
        print(f"Deleted polygons file: {polygons_file}")