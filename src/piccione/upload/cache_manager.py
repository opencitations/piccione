# SPDX-FileCopyrightText: 2025 Arcangelo Massari <arcangelo.massari@unibo.it>
#
# SPDX-License-Identifier: ISC

from typing import cast

import redis
from redis.exceptions import ConnectionError as RedisConnectionError


class CacheManager:
    REDIS_KEY = "processed_files"

    def __init__(
        self,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        redis_db: int = 4,
    ):
        self.processed_files: set[str] = set()
        try:
            self._redis = redis.Redis(
                host=redis_host,
                port=redis_port,
                db=redis_db,
                decode_responses=True,
            )
            self._redis.ping()
        except RedisConnectionError:
            raise RuntimeError("Redis is not available. Cache requires Redis.")
        self.processed_files.update(cast(set[str], self._redis.smembers(self.REDIS_KEY)))

    def add(self, filename: str) -> None:
        self.processed_files.add(filename)
        self._redis.sadd(self.REDIS_KEY, filename)

    def __contains__(self, filename: str) -> bool:
        return filename in self.processed_files

    def get_all(self) -> set[str]:
        self.processed_files.update(cast(set[str], self._redis.smembers(self.REDIS_KEY)))
        return self.processed_files
