from redis import Redis
from redis.lock import Lock
from contextlib import contextmanager
import logging

from .settings import CELERY_BROKER_URL

logger = logging.getLogger(__name__)
redis_client: Redis = Redis.from_url(CELERY_BROKER_URL, decode_responses=True)


@contextmanager
def acquire_user_lock(
    user_id: int | str,
    task_name: str,                # name of the task being locked
    timeout: int = 3600,           # lock TTL — should cover longest realistic step
    blocking_timeout: int = 5,     # how long caller waits to acquire (seconds)
    renew_interval: float = 10.0,  # auto-renew thread interval (if needed)
):
    """
    Acquire a distributed lock for a specific user and task name.
    Raises RuntimeError if lock cannot be acquired within blocking_timeout.
    """
    lock_key = f"lock:celery:user:{user_id}:task:{task_name}"
    lock = Lock(
        redis_client,
        name=lock_key,
        timeout=timeout,                    # auto-expire if holder crashes
        blocking_timeout=blocking_timeout,  # how long to wait before giving up
        thread_local=True,                  # default — safe for Celery workers
    )

    acquired = lock.acquire(blocking=True)
    if not acquired:
        raise RuntimeError(f"User {user_id} already has an active task_name {task_name} (lock held).")

    try:
        logger.info(f"Lock acquired for user {user_id} and task {task_name} (key={lock_key})")
        yield lock
    except Exception:
        logger.exception(f"Error inside user lock for {user_id} and task {task_name}")
        raise
    finally:
        try:
            lock.release()
            logger.debug(f"Lock released for user {user_id} and task {task_name}")
        except Exception:
            logger.warning(f"Failed to release lock for user {user_id} and task {task_name} — may have expired naturally")