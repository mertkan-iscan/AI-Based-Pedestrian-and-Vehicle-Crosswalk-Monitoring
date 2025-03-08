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

def mouse_callback(event, x, y, flags, param):
    """Record points for the current polygon on left-click."""
    global points
    if event == cv2.EVENT_LBUTTONDOWN:
        points.append((x, y))

def region_editing(frozen_frame):
    """
    Provide an editing interface on a frozen frame.
    Key bindings (press in the "Region Editing" window):
      f: finalize polygon (≥3 points)
      c: clear current polygon
      d: delete last polygon
      R: reset all polygons
      1/2/3: change region type
      e: exit editing
    """
    global points, region_polygons, current_region_type

    cv2.namedWindow("Region Editing", cv2.WINDOW_NORMAL)
    cv2.moveWindow("Region Editing", 0, 0)
    cv2.resizeWindow("Region Editing", 1920, 1080)

    cv2.setMouseCallback("Region Editing", mouse_callback)

    while True:
        temp_img = frozen_frame.copy()
        # Draw lines between current points
        if len(points) > 1:
            cv2.polylines(temp_img, [np.array(points, dtype=np.int32)],
                          isClosed=False, color=(0, 255, 0), thickness=2)
        for pt in points:
            cv2.circle(temp_img, pt, 3, (0, 0, 255), -1)

        # Overlay existing polygons
        temp_img = overlay_regions(temp_img, alpha=0.4)

        cv2.putText(temp_img, f"Editing Mode ({current_region_type})", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        cv2.putText(temp_img, "f: finalize, c: clear, d: delete last, R: reset, 1/2/3: type, e: exit",
                    (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        cv2.imshow("Region Editing", temp_img)
        key = cv2.waitKey(50) & 0xFF
        if key == ord('f'):
            if len(points) >= 3:
                region_polygons.append({
                    "type": current_region_type,
                    "points": points.copy()
                })
                points.clear()
                save_polygons()
                print(f"Polygon finalized as '{current_region_type}'.")
            else:
                print("Polygon requires at least 3 points.")
        elif key == ord('c'):
            points.clear()
            print("Cleared current polygon points.")
        elif key == ord('d'):
            if region_polygons:
                removed = region_polygons.pop()
                save_polygons()
                print(f"Deleted last polygon of type '{removed['type']}'.")
            else:
                print("No polygon to delete.")
        elif key == ord('R'):
            region_polygons.clear()
            if region_json_file and os.path.exists(region_json_file):
                os.remove(region_json_file)
            print("Reset all region polygons.")
        elif key == ord('1'):
            current_region_type = "crosswalk"
            print("Region type set to CROSSWALK.")
        elif key == ord('2'):
            current_region_type = "road"
            print("Region type set to ROAD.")
        elif key == ord('3'):
            current_region_type = "sidewalk"
            print("Region type set to SIDEWALK.")
        elif key == ord('e'):
            print("Exiting region editing mode.")
            break

    cv2.destroyWindow("Region Editing")
