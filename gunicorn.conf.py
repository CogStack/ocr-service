import time
import traceback
import os
from ocr_service.settings import settings
from ocr_service.utils.utils import sync_port_mapping, is_file_locked, cleanup_stale_lo_profiles


counter: int = 0

def pre_fork(server, worker):
    global counter

    time.sleep(1 + counter)
    counter += 1
    server.log.debug("pre_fork: initializing worker with PID: " + str(worker.pid))

def post_fork(server, worker):
    try:
        _worker_id = counter - 1
        sync_port_mapping(_worker_id, worker_pid=worker.pid)
        time.sleep(1)
        server.log.debug("WORKER ID: " + str(_worker_id) + " | pid : " + str(worker.pid))
    except Exception:
        server.log.exception(traceback.print_exc())

def on_exit(server):
    try:
        server.log.debug("cleaning up lo artifacts...")
        if os.path.exists(settings.WORKER_PORT_MAP_FILE_PATH):
            while not is_file_locked(settings.WORKER_PORT_MAP_FILE_PATH): 
                os.remove(settings.WORKER_PORT_MAP_FILE_PATH)
                server.log.debug("removed WORKER_PORT_MAP_FILE_PATH")
                break
        cleanup_stale_lo_profiles(settings.TMP_FILE_DIR)
    except Exception:
        server.log.exception(traceback.print_exc())

