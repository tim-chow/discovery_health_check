import base64
import os
import json
import time

import redis
import requests

class BaseRegistry:
    def __init__(self, config):
        self._config = config

    def on_check_begin(self):
        return True

    def on_check_end(self):
        pass

    def init(self):
        pass

    def destroy(self):
        pass

    def get_upstreams(self, *a, **kw):
        raise NotImplementedError(
            "get_all_upstreams should be implemented by subclass")

    def service(self, *a, **kw):
        raise NotImplementedError(
            "service should be implemented by subclass")

class RedisRegistry(BaseRegistry):
    unlock_lua_script = """
        if redis.call("GET", KEYS[1]) == KEYS[2] then
            redis.call("DEL", KEYS[1])
            return 1
        else
            return 0
        end
    """
    lock_lua_script = """
        if redis.call("SETNX", KEYS[1], KEYS[2]) == 1 then
            if redis.call("EXPIRE", KEYS[1], KEYS[3]) == 1 then
                return 1
            end
        end

        if redis.call("GET", KEYS[1]) == KEYS[2] then
            if redis.call("EXPIRE", KEYS[1], KEYS[3]) == 1 then
                return 1
            end
        end

        return 0
    """

    def init(self):
        print "init() is invoked"

        self._val = None # the value of distribute lock
        options = self._config["redis"]

        self._host = options.get("defualt_host")
        self._user_agent = options["user_agent"]
        self._check_path = options["default_check_path"]
        self._black_list_prefix = options["black_list_prefix"]
        self._node_name = options.get("node_name",
            "NODE_TYPE-default@DATA_CENTER-dc1")
        self._lock_name = options.get("lock_prefix",
            "HEALTH_CHECK_LOCK_PREFIX:") + self._node_name
        self._id = options["identifier"]

        self._lock_expire = int(options.get("lock_expire", 90))
        self._max_fails = int(options["max_fails"])
        self._check_timeout = \
            float(options["default_check_timeout"])/1000.
        self._check_interval = \
            float(options["check_interval"])/1000.
        self._disable_time = int(options["disable_time"])/1000

        self._redis = redis.Redis(
            host=options.get("redis_host", "127.0.0.1"),
            port=int(options.get("redis_port", 6379)),
            password=options.get("redis_password", None),
            db=int(options.get("redis_database", 0)),
            retry_on_timeout=True)
        self._redis.ping()

    def on_check_begin(self):
        print "on_check_begin() is invoked",
        if self._val is None:
            self._val = "%d|%s|%s" % (os.getpid(),
                self._id, self.get_unique_id())
        try:
            status = self._redis.eval(self.lock_lua_script, 3,
                self._lock_name, self._val, self._lock_expire)
        except redis.exceptions.RedisError as ex:
            print "redis.exceptions.RedisError:", str(ex)
            return False
        print "status is:", status
        return status

    def _unlock(self):
        if not hasattr(self, "_redis"):
            return -1
        try:
            return self._redis.eval(self.unlock_lua_script, 2,
                self._lock_name,
                self._val or self.get_unique_id())
        except redis.exceptions.RedisError as ex:
            print "redis.exceptions.RedisError:", str(ex)
            return -2

    def on_check_end(self):
        print "on_check_end() is invoked"
        self._unlock()

    def get_unique_id(self):
        return base64.b64encode(os.urandom(20)).strip("=")

    def destroy(self):
        print "destroy() is invoked"
        self._unlock()

    def get_upstreams(self):
        result = []
        try:
            for k, v in self._redis.hgetall(
                self._node_name).iteritems():
                for ki, vi in self._redis.hgetall(v).iteritems():
                    result.append((ki, vi, v))
        except redis.exceptions.RedisError as ex:
            print "redis.exceptions.RedisError:", str(ex)
        return result

    def _on_ok(self, backend, dc):
        print backend, "of", dc, "is ok"
        self._redis.hdel(self._black_list_prefix+dc, backend)

    def _on_error(self, backend, dc):
        print backend, "of", dc, "is bad"
        self._redis.hset(self._black_list_prefix+dc, backend,
            int(time.time())+self._disable_time)

    def determine_result(self, request_object):
        if request_object.status_code == 200:
            return True
        return False

    def _make_request(self, backend, backend_info, dc):
        url = "http://"+ backend + \
            (backend_info.get("checkpath") or 
                self._check_path)
        timeout = self._check_timeout
        if isinstance(backend_info.get("checktimeout"),
            (int, float, long)):
            timeout = backend_info["checktimeout"]/1000.
        for _ in range(self._max_fails):
            try:
                headers = {"User-Agent": self._user_agent}
                if backend_info.get("hostname"):
                    headers["Host"] = backend_info["hostname"]
                elif self._host:
                    headers["Host"] = self._host
                r = requests.get(url, timeout=timeout, headers=headers)
                if self.default_check_timeout(r):
                    self._on_ok(backend, dc)
                    return
            except requests.exceptions.RequestException as ex:
                print "requests.exceptions.RequestError:", str(ex)
            time.sleep(self._check_interval)
        self._on_error(backend, dc)

    def service(self, upstream):
        backend_info = json.loads(upstream[1])
        if not isinstance(backend_info, dict):
            raise ValueError("backend_info must be a dict")
        self._make_request(upstream[0], backend_info, upstream[2])

