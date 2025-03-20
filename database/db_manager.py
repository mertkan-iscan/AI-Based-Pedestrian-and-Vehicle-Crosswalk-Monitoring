import os
import sqlite3
import json
from datetime import datetime

class DBManager:
    def __init__(self, db_file=None):
        if db_file is None:
            # Get the base directory and then move up one level to the project root
            base_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.abspath(os.path.join(base_dir, '..'))
            resources_dir = os.path.join(project_root, 'resources')
            if not os.path.exists(resources_dir):
                os.makedirs(resources_dir)
            db_file = os.path.join(resources_dir, 'object_paths.db')

        self.conn = sqlite3.connect(db_file)
        self.cursor = self.conn.cursor()
        self.create_table()

    def create_table(self):
        """
        Creates a table with columns:
          - id (primary key)
          - timestamp (text)
          - object_id (integer)
          - object_type (text)
          - foot_path (text, storing a JSON-encoded list of [x, y] pairs)
        """
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS foot_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                object_id INTEGER,
                object_type TEXT,
                foot_path TEXT
            )
        ''')
        self.conn.commit()

    def insert_log(self, object_id, object_type, foot_path, timestamp=None):
        """
        Inserts a single record.
        :param object_id: the ID of the tracked object.
        :param object_type: type of the object (e.g., "person", "car").
        :param foot_path: a list of [x, y] pairs, e.g. [[320,480], [322,482]].
        :param timestamp: optional custom timestamp; if None, uses current time.
        """
        if timestamp is None:
            timestamp = datetime.now().isoformat(timespec='seconds')
        # Convert the list of foot coordinates to JSON for storage
        foot_path_json = json.dumps(foot_path)
        self.cursor.execute('''
            INSERT INTO foot_logs (timestamp, object_id, object_type, foot_path)
            VALUES (?, ?, ?, ?)
        ''', (timestamp, object_id, object_type, foot_path_json))
        self.conn.commit()

    def fetch_logs(self):
        """
        Returns all rows from foot_logs.
        Each row has (id, timestamp, object_id, object_type, foot_path).
        Use json.loads(foot_path) to convert the JSON string back to a list.
        """
        self.cursor.execute('SELECT * FROM foot_logs')
        return self.cursor.fetchall()

    def fetch_logs_by_timestamp_range(self, start_ts, end_ts):
        """
        Returns rows from foot_logs for records with a timestamp between start_ts (inclusive)
        and end_ts (exclusive).
        :param start_ts: The starting timestamp (ISO 8601 string).
        :param end_ts: The ending timestamp (ISO 8601 string).
        """
        self.cursor.execute('''
            SELECT * FROM foot_logs
            WHERE timestamp >= ? AND timestamp < ?
        ''', (start_ts, end_ts))
        return self.cursor.fetchall()

    def fetch_logs_by_timestamp_and_type(self, start_ts, end_ts, object_type):
        """
        Returns rows from foot_logs for records with a timestamp between start_ts (inclusive)
        and end_ts (exclusive) for a specific object type.
        :param start_ts: The starting timestamp (ISO 8601 string).
        :param end_ts: The ending timestamp (ISO 8601 string).
        :param object_type: The type of the object (e.g., "person", "car").
        """
        self.cursor.execute('''
            SELECT * FROM foot_logs
            WHERE timestamp >= ? AND timestamp < ? 
              AND object_type = ?
        ''', (start_ts, end_ts, object_type))
        return self.cursor.fetchall()

    def close(self):
        self.conn.close()

def convert_to_timestamp(date_str, time_str):
    """
    Converts a date string (YYYY-MM-DD) and a time string (HH:MM:SS)
    into an ISO-formatted timestamp.
    :param date_str: Date as a string, e.g. "2025-03-20".
    :param time_str: Time as a string, e.g. "09:30:00".
    :return: An ISO-formatted timestamp string, e.g. "2025-03-20T09:30:00".
    """
    dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
    return dt.isoformat(timespec='seconds')

# Test usage
if __name__ == '__main__':
    db = DBManager()

    # Insert a sample log with an object type (e.g., "person")
    path_data = [[320, 480], [322, 482], [330, 485]]
    db.insert_log(object_id=1, object_type="person", foot_path=path_data)

    # Fetch and print all logs
    print("All logs:")
    for row in db.fetch_logs():
        record_id, record_ts, record_obj_id, record_obj_type, record_foot_path = row
        coords_list = json.loads(record_foot_path)
        print(f"ID={record_id}, time={record_ts}, obj={record_obj_id}, type={record_obj_type}, coords={coords_list}")

    # Define a timestamp range for filtering
    start_timestamp = convert_to_timestamp("2025-03-20", "00:00:00")
    end_timestamp = convert_to_timestamp("2025-03-21", "00:00:00")

    # Fetch logs for a specific object type within the timestamp range
    print(f"\nLogs between {start_timestamp} and {end_timestamp} for object_type='person':")
    for row in db.fetch_logs_by_timestamp_and_type(start_timestamp, end_timestamp, "person"):
        record_id, record_ts, record_obj_id, record_obj_type, record_foot_path = row
        coords_list = json.loads(record_foot_path)
        print(f"ID={record_id}, time={record_ts}, obj={record_obj_id}, type={record_obj_type}, coords={coords_list}")

    db.close()
