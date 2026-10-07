"""Root verifier; method fitting and checkpoint loading run only as UID1000."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import stat
import shutil
import subprocess
import sys
import time
import uuid

import numpy as np

ASSETS=Path('/opt/verifier-assets')
PUBLIC=Path('/workspace/public_assets')
SEEDS=[17,29,43]
TEMPORARY_DIRS=[]

class SourceFormatError(Exception):pass

def cleanup_owned_temporaries():
    # Each entry is an exact verifier-created nonce; never sweep other tasks.
    def reclaim(path):
        info=path.lstat()
        if not stat.S_ISDIR(info.st_mode):return
        os.chown(path,0,0,follow_symlinks=False)
        path.chmod(0o700)
        for child in path.iterdir():
            if stat.S_ISDIR(child.lstat().st_mode):reclaim(child)
    for directory in TEMPORARY_DIRS:
        if directory.exists():
            reclaim(directory)
            shutil.rmtree(directory)


def identity():
    os.setgroups([])
    os.setgid(1000)
    os.setuid(1000)
    resource.setrlimit(resource.RLIMIT_AS,(3*1024**3,3*1024**3))
    resource.setrlimit(resource.RLIMIT_CPU,(180,180))
    resource.setrlimit(resource.RLIMIT_FSIZE,(64*1024**2,64*1024**2))
    resource.setrlimit(resource.RLIMIT_NOFILE,(128,128))
    import ctypes
    if ctypes.CDLL(None).prctl(38,1,0,0,0)!=0:
        raise RuntimeError('Could not enforce no-new-privileges')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_hash(solution):
    files=[]
    for path in Path(solution).rglob('*'):
        if path.is_symlink():raise ValueError('Source symlinks are forbidden')
        if path.is_file() and path.suffix=='.py':
            if path.stat().st_size>1024**2:raise SourceFormatError('Source exceeds file limit')
            files.append((str(path.relative_to(solution)),digest(path)))
    if not files or len(files)>16 or sum(p.stat().st_size for p in Path(solution).rglob('*.py'))>1536*1024:
        raise SourceFormatError('Invalid executable source bundle')
    return hashlib.sha256(json.dumps(sorted(files)).encode()).hexdigest()


def metrics(prediction,targets):
    if prediction.shape!=targets.shape or not np.isfinite(prediction).all():
        raise ValueError('Prediction shape or finite-value quality gate failed')
    mask=np.isfinite(targets)&(targets>0)
    if not mask.any():raise RuntimeError('No valid scoring targets')
    error=prediction.astype(np.float64)-targets
    return dict(mae=float(np.abs(error[mask]).mean()),
                rmse=float(np.sqrt(np.square(error[mask]).mean())),
                mae_per_horizon=[float(np.abs(error[:,h,:][mask[:,h,:]]).mean()) for h in range(targets.shape[1])],
                valid_values=int(mask.sum()))


def run(solution,output,raw_only=False,retain_models=True,hidden_assets=None):
    if os.geteuid()!=0:raise RuntimeError('Trusted verifier requires root; actors use the public evaluation interface')
    started=time.time()
    output=Path(output)
    output.mkdir(parents=True,exist_ok=False,mode=0o700)
    os.chmod(output,0o700)
    method_hash=source_hash(solution)
    assets=Path(hidden_assets) if hidden_assets else ASSETS
    public=PUBLIC
    if hidden_assets:
        public=Path('/tmp')/('forecast-eval-data-'+uuid.uuid4().hex)
        public.mkdir(mode=0o755)
        TEMPORARY_DIRS.append(public)
        for name in ['train_features.npz','train_targets.npz','graph.npz','manifest.json']:
            shutil.copyfile(PUBLIC/name,public/name)
        shutil.copyfile(assets/'dev_features.npz',public/'dev_features.npz')
        for path in public.iterdir():path.chmod(0o444)
        public.chmod(0o555)
    protocol=json.loads((assets/'protocol.json').read_text())
    if protocol['seeds']!=SEEDS:raise RuntimeError('Seed contract changed')
    launcher=Path(solution)/'solve.sh'
    if launcher.exists() and (launcher.is_symlink() or digest(launcher)!=protocol['solve_sha256']):
        raise ValueError('Frozen solve.sh entry point was altered')
    results=[]
    for seed in SEEDS:
        folder=output/f'seed_{seed}'
        folder.mkdir(mode=0o755)
        candidate=Path('/tmp')/('forecast-worker-'+uuid.uuid4().hex)
        candidate.mkdir(mode=0o700)
        TEMPORARY_DIRS.append(candidate)
        os.chown(candidate,1000,1000)
        argv=['/usr/bin/bwrap','--unshare-user','--unshare-pid','--unshare-net','--unshare-ipc',
              '--unshare-uts','--new-session','--die-with-parent',
              '--ro-bind','/usr','/usr','--ro-bind','/lib','/lib','--ro-bind-try','/lib64','/lib64',
              '--ro-bind','/etc','/etc','--proc','/proc','--dev','/dev','--tmpfs','/tmp',
              '--dir','/workspace','--ro-bind',str(solution),'/workspace/solution',
              '--ro-bind',str(public),'/workspace/public_assets',
              '--dir','/opt','--dir','/opt/forecast-engine',
              '--ro-bind','/opt/forecast-engine/actor_worker.py','/opt/forecast-engine/actor_worker.py',
              '--bind',str(candidate),'/output','--chdir','/workspace/solution',
              sys.executable,'-I','/opt/forecast-engine/actor_worker.py','--solution','/workspace/solution',
              '--data','/workspace/public_assets','--output','/output','--seed',str(seed)]
        environment={k:v for k,v in os.environ.items() if k in {'PATH','LANG'}}
        environment.update(HOME='/output',TMPDIR='/output',PYTHONPATH='',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
        before=time.time()
        with (folder/'run.log').open('w') as log:
            fit=subprocess.run(argv,env=environment,cwd=solution,stdout=log,stderr=subprocess.STDOUT,
                               preexec_fn=identity,timeout=180,start_new_session=True)
        if fit.returncode:raise RuntimeError(f'Candidate seed {seed} fit failed, exit {fit.returncode}; preserve run.log')
        # Reclaim only this nonce directory after its isolated candidate exits.
        # Root has no DAC override; ownership makes the artifact handoff explicit.
        os.chown(candidate,0,0)
        if source_hash(solution)!=method_hash:raise ValueError('Candidate altered its frozen scoring source')
        checkpoint=candidate/'model.pkl'
        if checkpoint.is_symlink() or not checkpoint.is_file() or checkpoint.stat().st_size>64*1024**2:
            raise ValueError('Checkpoint quality gate failed')
        os.chown(checkpoint,0,0,follow_symlinks=False)
        checkpoint.chmod(0o444)
        fitted_checkpoint_sha=digest(checkpoint)
        os.chown(candidate,1000,1000)
        with (folder/'reload.log').open('w') as log:
            reloaded=subprocess.run(argv+['--reload'],env=environment,cwd=solution,stdout=log,stderr=subprocess.STDOUT,
                                    preexec_fn=identity,timeout=60,start_new_session=True)
        if reloaded.returncode:raise RuntimeError(f'Candidate seed {seed} independent checkpoint reload failed')
        os.chown(candidate,0,0)
        if digest(checkpoint)!=fitted_checkpoint_sha:raise ValueError('Checkpoint changed during independent reload')
        for filename in ['prediction.npy','reload_prediction.npy']:
            artifact=candidate/filename
            information=artifact.lstat()
            if not stat.S_ISREG(information.st_mode) or information.st_size>32*1024**2:
                raise ValueError('Invalid prediction artifact type or size')
            os.chown(artifact,0,0,follow_symlinks=False)
            artifact.chmod(0o444)
        predicted=np.load(candidate/'prediction.npy',allow_pickle=False,mmap_mode='r')
        repeated=np.load(candidate/'reload_prediction.npy',allow_pickle=False,mmap_mode='r')
        if list(predicted.shape)!=protocol['prediction_shape'] or list(repeated.shape)!=protocol['prediction_shape']:
            raise ValueError('Prediction shape gate failed before scoring')
        # Development labels are read only after candidate processes have exited.
        targets=np.load(assets/'dev_targets.npz',allow_pickle=False)['target']
        if not np.allclose(predicted,repeated,rtol=0,atol=1e-4):
            raise ValueError('Checkpoint reload predictions differ')
        observed=metrics(predicted,targets)
        result=dict(status='ok',seed=seed,method_sha256=method_hash,
                    protocol_sha256=digest(assets/'protocol.json'),
                    shared_backbone_sha256=protocol['shared_backbone_sha256'],
                    fit_started_epoch=before,completed_epoch=time.time(),fit_exit_code=fit.returncode,
                    fit_command=argv,reload_command=argv+['--reload'],reload_exit_code=reloaded.returncode,metrics=observed,
                    checkpoint=dict(path=f'seed_{seed}/model/model.pkl',sha256=digest(checkpoint),
                                    size_bytes=checkpoint.stat().st_size,format='Python pickle; never deserialized by root',
                                    reload_prediction_max_abs_difference=float(np.max(np.abs(predicted-repeated)))),
                    method_fitting='fresh fit from the same declared public calibration corpus',
                    independent_neural_training=False,quality_gates_pass=True)
        (folder/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        if retain_models:
            saved=folder/'model'
            saved.mkdir(mode=0o700)
            shutil.copyfile(checkpoint,saved/'model.pkl',follow_symlinks=False)
            os.chmod(saved/'model.pkl',0o600)
            shutil.copyfile(folder/'reload.log',saved/'reload.log')
            (saved/'artifact.json').write_text(json.dumps(result['checkpoint'],indent=2)+'\n')
        else:
            result['checkpoint']['retained']=False
            result['checkpoint']['retention_reason']='Candidate iteration only; independent reload was observed. Formal Baseline/Reference and clean final proofs retain actual checkpoints.'
            (folder/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        del predicted,repeated
        shutil.rmtree(candidate)
        results.append(result)
    mean=float(np.mean([r['metrics']['mae'] for r in results]))
    score=None
    if not raw_only:
        baseline,upper=protocol['baseline_mae'],protocol['estimated_attainable_mae']
        if baseline is None or upper is None or not 0<upper<baseline:
            raise RuntimeError('Frozen valid calibration anchors are required')
        score=(baseline-mean)/(baseline-upper)
    summary=dict(status='ok',raw_metric='mae',raw_direction='minimize',raw_mean=mean,
                 normalized_score=score,seeds=SEEDS,method_sha256=method_hash,
                 paired_results=results,quality_gates_pass=True,
                 started_epoch=started,completed_epoch=time.time(),
                 shared_backbone_sha256=protocol['shared_backbone_sha256'])
    summary['evaluation_split']='externally_injected_hidden' if hidden_assets else 'dev'
    (output/'result.json').write_text(json.dumps(summary,indent=2)+'\n')
    if hidden_assets:
        public.chmod(0o755)
        shutil.rmtree(public)
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--solution',default='/workspace/solution')
    parser.add_argument('--output',default='/logs/verifier/evaluation')
    parser.add_argument('--raw-only',action='store_true')
    parser.add_argument('--discard-candidate-models',action='store_true')
    parser.add_argument('--hidden-assets')
    args=parser.parse_args()
    try:
        value=run(args.solution,args.output,args.raw_only,not args.discard_candidate_models,args.hidden_assets)
        if not args.raw_only:
            rewards=Path('/logs/verifier')
            rewards.mkdir(parents=True,exist_ok=True)
            temporary=rewards/'reward.pending.txt'
            temporary.write_text(str(value['normalized_score'])+'\n')
            temporary.replace(rewards/'reward.txt')
        print(json.dumps({k:v for k,v in value.items() if k!='paired_results'}),flush=True)
    except BaseException as error:
        failure={'status':'format_error' if isinstance(error,SourceFormatError) else
                          'timeout' if isinstance(error,subprocess.TimeoutExpired) else
                          'hard_gate' if isinstance(error,ValueError) else 'execution_error',
                 'error_type':type(error).__name__,'message':str(error),
                 'raw_mean':None,'normalized_score':None,'completed_epoch':time.time()}
        Path(args.output).mkdir(parents=True,exist_ok=True)
        (Path(args.output)/'failure.json').write_text(json.dumps(failure,indent=2)+'\n')
        if isinstance(error,ValueError) and not args.raw_only:
            failure['normalized_score']=-1.0
            (Path(args.output)/'failure.json').write_text(json.dumps(failure,indent=2)+'\n')
            rewards=Path('/logs/verifier')
            rewards.mkdir(parents=True,exist_ok=True)
            (rewards/'reward.txt').write_text('-1.0\n')
            print(json.dumps(failure),flush=True)
            sys.exit(0)
        print(json.dumps(failure),flush=True)
        raise
    finally:
        cleanup_owned_temporaries()
