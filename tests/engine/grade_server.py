"""Protected local public scorer. It exposes one bounded source evaluation API."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import uuid

ROOT=Path('/logs/score-evidence')
ROOT.mkdir(mode=0o700,parents=True,exist_ok=True)
os.chmod(ROOT,0o700)
LOCK=threading.Lock()


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass

    def reply(self,status,value):
        raw=json.dumps(value).encode()
        self.send_response(status)
        self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self):
        if self.path!='/evaluate':return self.reply(404,{'status':'invalid_operation'})
        if not LOCK.acquire(blocking=False):return self.reply(409,{'status':'busy','message':'Your own evaluation is already running'})
        source=None
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=1536*1024:raise ValueError('Bounded method source required')
            payload=json.loads(self.rfile.read(length))
            if not isinstance(payload,dict) or set(payload)!={'files'}:raise ValueError('Only source files may be submitted')
            files=payload['files']
            if not isinstance(files,dict) or 'method.py' not in files or not 1<=len(files)<=16:
                raise ValueError('Invalid method source bundle')
            identifier=uuid.uuid4().hex
            source=Path('/tmp')/('forecast-source-'+identifier)
            source.mkdir(mode=0o755)
            for name,value in files.items():
                relative=Path(name)
                if relative.is_absolute() or '..' in relative.parts or relative.suffix!='.py' or not isinstance(value,str) or len(value.encode())>1024**2:
                    raise ValueError('Invalid source path or size')
                path=source/relative
                path.parent.mkdir(mode=0o755,parents=True,exist_ok=True)
                path.write_text(value)
                path.chmod(0o444)
            for path in source.rglob('*'):
                if path.is_dir():path.chmod(0o555)
            source.chmod(0o555)
            folder=ROOT/identifier
            process=subprocess.Popen([sys.executable,'-I','/opt/forecast-engine/grader.py',
                    '--solution',str(source),'--output',str(folder),'--discard-candidate-models'],stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,text=True,start_new_session=True)
            try:
                raw,_=process.communicate(timeout=1200)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL)
                raw,_=process.communicate()
            (ROOT/(identifier+'.log')).write_text(raw)
            result=folder/('result.json' if (folder/'result.json').exists() else 'failure.json')
            value=json.loads(result.read_text()) if result.exists() else {'status':'execution_error'}
            visible={key:value.get(key) for key in ['status','raw_metric','raw_direction','raw_mean',
                'normalized_score','seeds','quality_gates_pass','method_sha256']}
            visible['evaluation_id']=identifier
            if value['status']!='ok':visible['message']='Candidate execution or quality gate failed; repair your method and retry.'
            self.reply(200,visible)
        except BaseException as error:
            self.reply(422,{'status':'format_error','message':str(error)[:300]})
        finally:
            if source:
                import shutil
                for directory in source.rglob('*'):
                    if directory.is_dir():directory.chmod(0o755)
                source.chmod(0o755)
                shutil.rmtree(source,ignore_errors=True)
            LOCK.release()


if __name__=='__main__':
    if os.geteuid()!=0:raise RuntimeError('Protected score service requires trusted startup')
    ThreadingHTTPServer(('127.0.0.1',8766),Handler).serve_forever()
