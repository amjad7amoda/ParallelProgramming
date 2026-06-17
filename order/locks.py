import redis
import uuid 

from contextlib import contextmanager
from django.conf import settings


r = redis.Redis.from_url(settings.REDIS_URL)


class DistributedLockError(Exception):
    pass

@contextmanager
def distributed_lock(resource_ids: list[str], timeout: int = 10):
    lock_keys = {f'lock:product:{rid}': str(uuid.uuid4()) for rid in sorted(resource_ids)}

    acquired = []
    try:
        for lock_key, lock_id in lock_keys.items():
            if not r.set(lock_key, lock_id, nx=True, ex=timeout):
                raise DistributedLockError('Product is locked')
            acquired.append((lock_key, lock_id))
        yield
    finally:
        for lock_key, lock_id in acquired:
            lua = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("del", KEYS[1])
            else
                return 0
            end
            """
            r.eval(lua, 1, lock_key, lock_id)