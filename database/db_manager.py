import os
import sqlite3
import json
from datetime import datetime

class DBManager:

    def __init__(self, db_file=None):
        if db_file is None:
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
          - foot_path (text, storing a JSON-encoded list of [x, y] pairs)
        """
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS foot_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                object_id INTEGER,
                foot_path TEXT
            )
        ''')
        self.conn.commit()


    def insert_log(self, object_id, foot_path, timestamp=None):
        """
        Inserts a single record.
        :param object_id: the ID of the tracked object
        :param foot_path: a list of [x, y] pairs, e.g. [[320, 480], [322, 482]]
        :param timestamp: optional custom timestamp; if None, use current time
        """
        if timestamp is None:
            timestamp = datetime.now().isoformat(timespec='seconds')


        # Convert the list of foot coordinates to JSON for storage
        foot_path_json = json.dumps(foot_path)
        self.cursor.execute('''
            INSERT INTO foot_logs (timestamp, object_id, foot_path)
            VALUES (?, ?, ?)
        ''', (timestamp, object_id, foot_path_json))
        self.conn.commit()


    def fetch_logs(self):
        """
        Returns all rows from foot_logs.
        Each row has (id, timestamp, object_id, foot_path).
        You can json.loads(foot_path) to get the list of coordinates back.
        """
        self.cursor.execute('SELECT * FROM foot_logs')
        return self.cursor.fetchall()


    def close(self):
        self.conn.close()

#test
if __name__ == '__main__':

    db = DBManager()

    path_data = [[320, 480], [322, 482], [330, 485]]
    db.insert_log(object_id=1, foot_path=path_data)

    for row in db.fetch_logs():

        record_id, record_ts, record_obj_id, record_foot_path = row
        coords_list = json.loads(record_foot_path)
        print(f"ID={record_id}, time={record_ts}, obj={record_obj_id}, coords={coords_list}")

    db.close()
