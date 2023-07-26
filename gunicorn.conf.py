import time
import sys
import traceback

from ocr_service.utils.utils import sync_port_mapping

sys.path.append(".")

counter = 0

def pre_fork(server, worker):
    global counter

    time.sleep(1 + counter)
    counter += 1

def post_fork(server, worker):
    try:
        sync_port_mapping(worker_id=(counter - 1), worker_pid=worker.pid)
        time.sleep(1)
    except Exception:
        print(traceback.print_exc())
    