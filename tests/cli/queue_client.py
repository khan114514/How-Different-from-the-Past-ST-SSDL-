"""Bounded data transport. No network, host paths or host credentials."""
import base64
import json
import os
import stat
import time
import uuid
from pathlib import Path

QUEUE = Path('/run/forecastcli/queue')
LIMIT = 2*1024*1024

def read_regular(path, limit=LIMIT):
    descriptor = os.open(path, os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise ValueError('Invalid bounded queue frame')
        content = os.read(descriptor, limit+1)
        if len(content) > limit:
            raise ValueError('Frame limit exceeded')
        return content
    finally:
        os.close(descriptor)

def request(operation, payload, timeout=360):
    nonce = uuid.uuid4().hex
    value = {'id':nonce,'operation':operation,'payload':payload}
    encoded = json.dumps(value,separators=(',',':')).encode()
    if len(encoded) > LIMIT:
        raise ValueError('Request limit exceeded')
    pending = QUEUE/(nonce+'.pending')
    fd = os.open(pending,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as handle:
        handle.write(encoded)
    pending.replace(QUEUE/(nonce+'.req'))
    deadline = time.monotonic()+timeout
    sequence = 0
    while time.monotonic() < deadline:
        path = QUEUE/(nonce+'.'+str(sequence)+'.res')
        try:
            frame = json.loads(read_regular(path))
        except FileNotFoundError:
            time.sleep(0.025)
            continue
        path.unlink()
        if frame.get('id') != nonce or frame.get('sequence') != sequence:
            raise ValueError('Response lineage mismatch')
        yield frame
        sequence += 1
        if frame.get('kind') == 'end':
            return
    raise TimeoutError('Trusted bridge response timed out')

def request_json(operation,payload,timeout=900):
    body = bytearray()
    status = None
    for frame in request(operation,payload,timeout):
        if frame['kind'] == 'header':
            status = frame['status']
        if frame['kind'] == 'chunk':
            body.extend(base64.b64decode(frame['data'],validate=True))
            if len(body) > LIMIT:
                raise ValueError('JSON result limit exceeded')
    if status != 200:
        raise RuntimeError('Trusted evaluator rejected the request: '+body.decode(errors='replace')[:500])
    return json.loads(body)
