import json
import os
import tkinter as tk
from tkinter import simpledialog, messagebox

CONFIG_FILE = "config/locations.json"

def load_locations():
    """
    Load the list of locations from CONFIG_FILE.
    If CONFIG_FILE does not exist, create it with an empty list.
    """
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as f:
            json.dump([], f, indent=4)
        print(f"{CONFIG_FILE} not found. Created a new one.")
        return []
    with open(CONFIG_FILE, "r") as f:
        locations = json.load(f)
    return locations

def add_location(location):
    """
    Add a new location to the JSON file.
    'location' should be a dict with keys:
        - name
        - camera_name
        - stream_url
        - polygons_file
    """
    locations = load_locations()
    locations.append(location)
    with open(CONFIG_FILE, "w") as f:
        json.dump(locations, f, indent=4)
    print(f"Added location: {location['name']}")

def add_location_gui():
    """
    Opens a GUI window to add a new location.
    Returns the newly created location as a dict, or None if canceled.
    """
    root = tk.Tk()
    root.withdraw()  # Hide the root window

    name = simpledialog.askstring("Add Location", "Enter location name:")
    if not name:
        messagebox.showerror("Error", "Location name is required.")
        root.destroy()
        return None

    camera_name = simpledialog.askstring("Add Location", "Enter camera name (optional):")
    stream_url = simpledialog.askstring("Add Location", "Enter stream URL:")
    if not stream_url:
        messagebox.showerror("Error", "Stream URL is required.")
        root.destroy()
        return None

    polygons_file = simpledialog.askstring("Add Location", "Enter polygons file (e.g., polygons_location1.json):")
    if not polygons_file:
        messagebox.showerror("Error", "Polygons file is required.")
        root.destroy()
        return None

    root.destroy()

    new_location = {
        "name": name,
        "camera_name": camera_name or "",
        "stream_url": stream_url,
        "polygons_file": polygons_file
    }
    add_location(new_location)
    return new_location

def select_location():
    """
    If there are no locations, immediately open the Add Location window.
    Otherwise, offer the user a chance to add a new location or select an existing one.
    Returns the chosen location as a dict, or None if canceled/invalid.
    """
    locations = load_locations()

    # Case 1: No locations at all, force adding a new one
    if not locations:
        print("No locations configured. Opening window to add a location.")
        new_location = add_location_gui()
        return new_location  # Could be None if user canceled

    # Case 2: Some locations already exist; ask user if they want to add more
    add_new_answer = input("Do you want to add a new location? (y/n): ").strip().lower()
    if add_new_answer == 'y':
        new_location = add_location_gui()
        if new_location:
            # Reload locations after adding a new one
            locations = load_locations()

    # Now let the user select from the (updated) list
    if not locations:
        # If user added a location then canceled, the list might still be empty
        print("No locations configured after user action.")
        return None

    print("\nConfigured locations:")
    for idx, loc in enumerate(locations):
        print(f"{idx+1}: {loc['name']} ({loc.get('camera_name', 'No camera name')})")
    choice = input("Select a location number: ")
    try:
        index = int(choice) - 1
        if 0 <= index < len(locations):
            return locations[index]
        else:
            print("Invalid selection.")
            return None
    except ValueError:
        print("Invalid input. Please enter a number.")
        return None
