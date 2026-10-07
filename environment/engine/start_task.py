"""Start the fixed public scorer, then drop privileges before actor execution."""
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

if os.geteuid()!=0:raise RuntimeError('Trusted task startup requires root')
log=Path('/logs/service')
log.mkdir(mode=0o700,parents=True,exist_ok=True)
os.chmod(log,0o700)
stream=(log/'score-service.log').open('a')
subprocess.Popen([sys.executable,'-I','/opt/forecast-engine/grade_server.py'],
                 stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT)
for attempt in range(100):
    try:
        with socket.create_connection(('127.0.0.1',8766),timeout=.1):break
    except OSError:time.sleep(.05)
else:raise RuntimeError('Protected public scorer did not start')
os.setgroups([])
os.setgid(1000)
os.setuid(1000)
os.execv(sys.executable,[sys.executable,'/opt/forecastcli/entrypoint.py',*sys.argv[1:]])
