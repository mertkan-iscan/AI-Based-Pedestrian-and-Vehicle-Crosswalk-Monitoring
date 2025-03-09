import cv2
import numpy as np
import json
import os

# Globals for region editing
points = []                  # Points for the current polygon
region_polygons = []         # List of dicts, each with "type" and "points"
current_region_type = "crosswalk"  # Default area type

# Instead of a fixed file, set region_json_file dynamically.
region_json_file = None

# Colors for each region type (BGR)
area_colors = {
    "crosswalk": (0, 255, 255),  # Yellow
    "road": (50, 50, 50),        # Dark gray
    "sidewalk": (255, 255, 0)    # Light blue
}

def set_region_file(file_path):
    """Set the polygon file path dynamically."""
    global region_json_file
    region_json_file = file_path
    print(f"Polygon file set to {region_json_file}")

def load_polygons():
    """Load existing polygons from JSON if it exists."""
    global region_polygons, region_json_file
    if not region_json_file:
        print("No polygon file specified.")
        return
    if os.path.exists(region_json_file):
        with open(region_json_file, "r") as f:
            region_polygons = json.load(f)
        print(f"Loaded polygons from {region_json_file}")
    else:
        # Initialize an empty list if file does not exist
        region_polygons.clear()
        print(f"No existing polygon file at {region_json_file}. Starting fresh.")

def save_polygons():
    """Save the current polygons to JSON."""
    global region_json_file
    if not region_json_file:
        print("No polygon file specified. Cannot save.")
        return
    with open(region_json_file, "w") as f:
        json.dump(region_polygons, f, indent=4)
    print(f"Polygon data saved to {region_json_file}")

def overlay_regions(img, alpha=0.4):
    """
    Overlay the saved region polygons on the given image with semi-transparency.
    Also draws polygon edges.
    """
    overlay = img.copy()
    for poly in region_polygons:
        pts = np.array(poly["points"], dtype=np.int32)
        color = area_colors.get(poly["type"], (0, 0, 255))
        # Draw polygon edges
        cv2.polylines(overlay, [pts], isClosed=True, color=color, thickness=2)
        # Fill polygon
        cv2.fillPoly(overlay, [pts], color)
    return cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0)

def get_polygons_for_point(point, polygons):
    """
    Given a point (x,y) and a list of region polygons (each a dict with "type" and "points"),
    return a list of region types that contain the point.
    """
    inside = []
    for poly in polygons:
        pts = np.array(poly["points"], dtype=np.int32)
        # cv2.pointPolygonTest returns a positive value if the point is inside,
        # 0 if on the edge, negative if outside.
        if cv2.pointPolygonTest(pts, point, False) >= 0:
            inside.append(poly["type"])
    return inside
