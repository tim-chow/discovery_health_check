[main]
threads = 5
implement_class = discovery_health_check:RedisRegistry
sleep_time = 1000

[redis]
redis_password = timchow
redis_port = 6380
identifier = This_Should_Be_IP
default_check_path = /
default_check_timeout = 2000
user_agent = Mozilla/5.0 (Linux 2.6) Discovery/1.0.0
black_list_prefix = BLACK_LIST:
max_fails = 3
check_interval = 1000
disable_time = 100000

