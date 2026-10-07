"""A real bounded Codex turn; a supervisor resumes productive work until 10 hours."""
import os
from pathlib import Path
import signal
import subprocess
import sys

role=os.environ['FORECAST_LANE']
models={'gpt':'gpt-6.1-sol','seed':'doubao-seed-2-1-turbo-260628'}
effort='xhigh' if role=='gpt' else 'high'
prompt=Path(sys.argv[1]).read_text()
seconds=int(sys.argv[2])
process=subprocess.Popen(['codex','exec','--ephemeral','--json','--skip-git-repo-check',
    '--sandbox','workspace-write','-m',models[role],'-c',f'model_reasoning_effort="{effort}"',prompt],
    stdin=subprocess.DEVNULL,start_new_session=True)
try:code=process.wait(timeout=seconds)
except subprocess.TimeoutExpired:
    os.killpg(process.pid,signal.SIGTERM)
    try:code=process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid,signal.SIGKILL)
        code=process.wait()
raise SystemExit(code if code>=0 else 128-code)
