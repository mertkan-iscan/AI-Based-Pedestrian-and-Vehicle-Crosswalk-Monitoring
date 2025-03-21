import queue
import threading
import concurrent.futures
from database.db_manager import DBManager  # Adjust the import path as needed

# Thread-safe queue to hold tasks.
# Each task is a tuple: (task_type, object_id, data)
# 'update' tasks accumulate the new foot coordinate.
# 'disappear' tasks trigger a DB write for an object that has disappeared.
task_queue = queue.Queue()

# Global dictionary to store accumulated paths per object.
global_paths = {}
global_paths_lock = threading.Lock()

def process_task(task, db_manager):
    """
    Processes a single task.
    :param task: A tuple (task_type, object_id, data)
    :param db_manager: An instance of DBManager used for writing to the database.
    """
    task_type, object_id, data = task

    if task_type == 'update':

        with global_paths_lock:
            if object_id not in global_paths:
                global_paths[object_id] = []
            global_paths[object_id].append(data)

            #print(f"Path updated {object_id}")



    elif task_type == 'disappear':

        with global_paths_lock:

            final_path = global_paths.pop(object_id, [])

            print(f"[Task Processor] Removing object {object_id} from global_paths. Final path: {final_path}")

        if final_path:

            db_manager.insert_log(object_id=object_id, object_type="person", foot_path=final_path)

            print(f"[DB Writer] Object {object_id} disappeared. Final path written to DB: {final_path}")

        else:

            print(f"[DB Writer] Object {object_id} disappeared. No path recorded (empty path).")


def dynamic_task_processor(db_manager, pool_size=4):
    """
    Processes tasks from the task_queue using a dynamic thread pool.
    Runs until a sentinel value (None) is encountered.
    :param db_manager: An instance of DBManager.
    :param pool_size: Number of worker threads.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=pool_size) as executor:
        while True:
            task = task_queue.get()
            if task is None:
                task_queue.task_done()
                break  # Sentinel encountered: exit the loop.
            executor.submit(process_task, task, db_manager)
            task_queue.task_done()
