import os
import time
import signal
import sys
from concurrent.futures import ThreadPoolExecutor

from .registry import BaseRegistry
from .util import config_to_dict

class Entry:
    def __init__(self, config_file):
        self._handle_signal()
        self._quit = False
        self._executor = None
        self._command = None
        self._config = config_to_dict(config_file)
        options = self._config["main"]
        self._python_path = options.get("python_path", "")
        self._implement_class = options["implement_class"]
        self._threads = int(options.get("threads", 1))
        self._sleep_time = float(options.get("sleep_time", 100))/1000.
        self._command, self._executor = self._initialize()

    def _on_sig_int(self, sn, fo):
        print "received signal:", sn
        self._quit = True

    def _handle_signal(self):
        signal.signal(signal.SIGINT, self._on_sig_int)
        signal.signal(signal.SIGUSR1, self._on_sig_int)
        signal.signal(signal.SIGUSR2, self._on_sig_int)

    def execute(self):
        self._command.init()

        while not self._quit:
            time.sleep(self._sleep_time)
            if not self._command.on_check_begin():
                continue
            try:
                upstreams = self._command.get_upstreams()
            except Exception as ex:
                print >>sys.stderr, "get_upstreams failed:", str(ex)
            else:
                futures = []
                for upstream in upstreams:
                    futures.append(self._executor.submit(
                        self._command.service, upstream))
                for future in futures:
                    try:
                        future.result()
                    except Exception as ex:
                        print >>sys.stderr, str(ex)
            finally:
                self._command.on_check_end()

    def _destroy(self):
        if self._executor:
            self._executor.shutdown()
        if self._command:
            self._command.destroy()

    def __del__(self):
        self._destroy()

    def _initialize(self):
        sys.path.extend(self._python_path.split(","))

        try:
            module_name, cls_name = self._implement_class.split(":")
            klass = getattr(__import__(module_name), cls_name)
            assert issubclass(klass, BaseRegistry), \
                "implement class must be a subclass of BaseRegistry"
            command = klass(self._config)
        except (ImportError, ValueError,
                AttributeError, TypeError):
            print >>sys.stderr, "Error accurs:"
            raise

        executor = ThreadPoolExecutor(max_workers=self._threads)
        return command, executor

def main():
    if len(sys.argv) < 2:
        print >>sys.stderr, "config file is not found"
        sys.exit(1)
    if not os.access(sys.argv[1], os.R_OK):
        print >>sys.stderr, "permission denied"
        sys.exit(1)
    Entry(sys.argv[1]).execute()

