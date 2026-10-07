"""Loopback-only Responses proxy to the lane's physically separate queue."""
import base64
import json
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from queue_client import LIMIT,request

class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    def log_message(self,*args):
        pass
    def do_POST(self):
        if self.path != '/responses':
            self.send_error(404)
            return
        try:
            length = int(self.headers.get('Content-Length','0'))
            if not 0 < length <= LIMIT:
                raise ValueError('Invalid request size')
            body = json.loads(self.rfile.read(length))
            if not isinstance(body,dict):
                raise ValueError('Responses body must be an object')
            started = False
            for frame in request('responses',body,360):
                kind = frame['kind']
                if kind == 'header':
                    self.send_response(frame['status'])
                    self.send_header('Content-Type',frame['content_type'])
                    self.send_header('Connection','close')
                    self.end_headers()
                    started = True
                elif kind == 'chunk':
                    if not started:
                        raise ValueError('Missing HTTP header')
                    self.wfile.write(base64.b64decode(frame['data'],validate=True))
                    self.wfile.flush()
            self.close_connection = True
        except (BrokenPipeError,ConnectionResetError):
            self.close_connection = True
        except Exception:
            if not locals().get('started',False):
                self.send_error(502,'Trusted bridge failed')
            self.close_connection = True

if __name__ == '__main__':
    ThreadingHTTPServer(('127.0.0.1',8765),Handler).serve_forever()
