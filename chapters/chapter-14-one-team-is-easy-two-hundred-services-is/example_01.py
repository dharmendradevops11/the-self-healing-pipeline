import redis
import time
import uuid

class RedisDistributedRateLimiter:
    # Admission and bookkeeping have to happen together, or a rejected
    # request still occupies a slot in the window. Redis runs this script
    # atomically, so concurrent callers cannot interleave.
    _ACQUIRE_LUA = """
        local key    = KEYS[1]
        local now    = tonumber(ARGV[1])
        local window = tonumber(ARGV[2])
        local limit  = tonumber(ARGV[3])
        local member = ARGV[4]

        redis.call('ZREMRANGEBYSCORE', key, 0, now - window)
        local count = redis.call('ZCARD', key)
        if count >= limit then
            return 0
        end
        redis.call('ZADD', key, now, member)
        redis.call('EXPIRE', key, window)
        return 1
    """

    def __init__(self, redis_client, key="rate_limit:bedrock", limit=180, period=60):
        self.redis = redis_client
        self.key = key
        self.limit = limit
        self.period = period
        self._acquire = redis_client.register_script(self._ACQUIRE_LUA)

    def acquire(self) -> bool:
        """
        Redis sliding-window log for distributed rate limiting.
        Returns True if the request is allowed, False if rate limited.
        """
        now = time.time()
        # A unique member per call; timestamps alone collide under concurrency
        # and a ZADD with a duplicate member silently overwrites the old entry.
        member = f"{now}:{uuid.uuid4().hex}"
        return bool(self._acquire(keys=[self.key],
                                  args=[now, self.period, self.limit, member]))
