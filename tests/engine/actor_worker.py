"""Candidate code runs here as UID1000, without any development targets."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import pickle
import random
import sys

import numpy as np

parser=argparse.ArgumentParser()
parser.add_argument('--solution',required=True)
parser.add_argument('--data',required=True)
parser.add_argument('--output',required=True)
parser.add_argument('--seed',required=True,type=int)
parser.add_argument('--reload',action='store_true')
args=parser.parse_args()
if os.geteuid()!=1000:
    raise RuntimeError('Candidate worker requires the unprivileged actor identity')
solution=Path(args.solution)
sys.path.insert(0,str(solution))
spec=importlib.util.spec_from_file_location('method',solution/'method.py')
module=importlib.util.module_from_spec(spec)
sys.modules['method']=module
spec.loader.exec_module(module)
def read(name):
    with np.load(Path(args.data)/name,allow_pickle=False) as file:
        values={key:file[key] for key in file.files}
    for array in values.values():array.flags.writeable=False
    return values
random.seed(args.seed)
np.random.seed(args.seed)
directory=Path(args.output)
if args.reload:
    with (directory/'model.pkl').open('rb') as stream:
        state=pickle.load(stream)
else:
    features=read('train_features.npz')
    targets=read('train_targets.npz')['target']
    state=module.fit(features,targets,args.seed)
    with (directory/'model.pkl').open('wb') as stream:
        pickle.dump(state,stream,protocol=5)
prediction=np.asarray(module.predict(state,read('dev_features.npz')))
if prediction.dtype.kind not in 'fiu' or not np.isfinite(prediction).all():
    raise ValueError('Prediction must be a finite numeric array')
np.save(directory/('reload_prediction.npy' if args.reload else 'prediction.npy'),prediction.astype(np.float32),allow_pickle=False)
print(json.dumps({'worker_uid':os.geteuid(),'seed':args.seed,'reload':args.reload,'shape':list(prediction.shape),'checkpoint_bytes':(directory/'model.pkl').stat().st_size}),flush=True)
