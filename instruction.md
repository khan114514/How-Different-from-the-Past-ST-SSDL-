# Conditional traffic forecasting

## Goal
Given immutable forecasts and observed historical features for a sensor network, implement a forecasting method that lowers masked mean absolute error. A valid submission fits from the provided calibration corpus and returns one finite forecast for each requested sample, horizon and node.

## Task Setting
All forecasts share the same fixed, sufficiently trained upstream predictor. The initial method returns its forecasts unchanged. Calibration examples and their targets are public; development features are public, and their targets are available only to the protected scorer. Held-out data are externally supplied and are absent from your environment. Each evaluation starts a fresh fit for each declared seed and independently reloads the resulting state.

## Objective and Metrics
Raw MAE averages absolute error over finite targets greater than zero, over all samples, horizons and sensors. The three fresh fits use seeds 17, 29 and 43; their complete MAE mean is the raw metric to minimize. Score is (B-MAE)/(B-U), continuously and without clipping. Frozen B and U are recorded by the trusted scorer and summarized by the public evaluation response. RMSE and per-horizon MAE are diagnostics. Finite output, exact shape and reproducible checkpoint reload are required. Scores from self-written result files are ignored. A valid improvement requires all quality gates to pass and a strictly positive reduction in complete mean MAE under these same fixed seeds; there is no additional percentage threshold.

## Allowed Scope
Implement executable methods in solution/method.py and at most 15 supporting Python source files under solution/. Interface: fit(features, targets, seed) returns serializable method state; predict(state, features) returns a numeric array of shape [sample, horizon, node]. Public features contain base forecasts, twelve observed history steps, training-only historical anchors and known future time-of-day coordinates. Their exact axes and hashes are in public_assets/manifest.json. numpy, scipy and scikit-learn are available. Arbitrary method structures may be implemented; scalar configuration search alone does not establish a method improvement.

## Hard Boundaries
Only solution/ is writable for submissions. Do not modify solve.sh, frozen assets, task files or the scorer. No Internet or host access is available. Never use development targets to fit your method, access held-out data, tamper with metrics, fabricate scores or create idle filler. The scorer runs your code as an unprivileged user without development labels. Source is limited to 16 Python files and 1.5 MiB total, method state to 64 MiB, fitting to 180 CPU/wall seconds per seed, reload to 60 wall seconds, and total scoring to 1800 seconds. There are two CPU cores and 4 GiB memory per evaluation. Prediction shape and finiteness are enforced; checkpoints must reload within absolute tolerance 1e-4. Invalid submissions and infrastructure failures are reported separately.

## Submission Instructions
Submit method.py and any permitted supporting Python files. The trusted scorer snapshots these sources, calls fit for each seed with calibration features/targets, serializes the returned state, executes a separate unprivileged reload process, calls predict on development features, and computes the score itself. Do not submit trained neural-backbone checkpoints or a self-reported score. Keep solution/solve.sh as the fixed public evaluation entry point.

## Workflow & Iteration
This is an anytime method optimization task. Read the contract and initial method, run ./solve.sh, implement a method change, evaluate on the same development protocol, and retain or revert based on its actual raw MAE. Record the method, observed result and your next decision in your research journal. The public command sends only your bounded source to the protected local scorer in your isolated environment; no other trajectory or reference is available. Continue developing structural methods while retaining a runnable best submission. End by rerunning your best method.

## Completion Criteria
The method interface works, all complete seed fits and independent reloads pass, output is finite and has the required shape, an actual trusted score is produced, protected files are unchanged, and neither reference nor held-out material was accessed.
