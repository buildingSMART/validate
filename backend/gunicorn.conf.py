"""Gunicorn hooks for prometheus_client multiprocess mode.

With multiple workers each process keeps its own counters in
PROMETHEUS_MULTIPROC_DIR; this hook cleans up when a worker dies, otherwise
the directory slowly fills with files of dead pids.
"""
from prometheus_client import multiprocess


def child_exit(server, worker):
    multiprocess.mark_process_dead(worker.pid)
