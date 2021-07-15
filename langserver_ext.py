import logging
import subprocess
import threading

from tornado import ioloop, process, web, websocket

from pyls_jsonrpc import streams

try:
    import ujson as json
except Exception:  # pylint: disable=broad-except
    import json

log = logging.getLogger(__name__)

import time
from datetime import datetime


def timer(func):
    def log_print(*arg):
        print(datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"), *arg, flush=True)

    def wrapper(*arg, **kw):
        t0 = time.time()
        log_print(func.__name__ + ' start ...')
        result = func(*arg, **kw)
        t1 = time.time()
        log_print(func.__name__ + ' finished, spent time: ' + str(round(t1 - t0, 2)) + 's.')
        return result

    return wrapper

class LanguageServerWebSocketHandler(websocket.WebSocketHandler):
    """Setup tornado websocket handler to host an external language server."""

    writer = None

    @timer
    def open(self, *args, **kwargs):
        log.info("Spawning pyls subprocess")

        # Create an instance of the language server
        proc = process.Subprocess(
            ['pyls', '-v'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE
        )

        # Create a writer that formats json messages with the correct LSP headers
        self.writer = streams.JsonRpcStreamWriter(proc.stdin)

        # Create a reader for consuming stdout of the language server. We need to
        # consume this in another thread
        @timer
        def consume():
            # Start a tornado IOLoop for reading/writing to the process in this thread
            ioloop.IOLoop()
            reader = streams.JsonRpcStreamReader(proc.stdout)
            reader.listen(lambda msg: self.write_message(json.dumps(msg)))

        thread = threading.Thread(target=consume)
        thread.daemon = True
        thread.start()

    @timer
    def on_message(self, message):
        """Forward client->server messages to the endpoint."""
        data = json.loads(message)
        self.writer.write(data)

    @timer
    def check_origin(self, origin):
        return True


if __name__ == "__main__":
    app = web.Application([
        (r"/python", LanguageServerWebSocketHandler),
    ])
    app.listen(3000, address='127.0.0.1')
    ioloop.IOLoop.current().start()