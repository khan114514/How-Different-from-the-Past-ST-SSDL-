# How Different from the Past? — ST-SSDL (Harbor task package)

This repository contains the **Harbor task package** for the optimization surface built on top of the
paper *“How Different from the Past? Spatio-Temporal Time Series Forecasting with Self-Supervised
Deviation Learning”* (**ST-SSDL**).

- Paper: arXiv [2510.04908](https://arxiv.org/abs/2510.04908)
- Official source: [Jimmy-7664/ST-SSDL](https://github.com/Jimmy-7664/ST-SSDL) (snapshot `a98331d`)

## Optimization surface

A single, **fully trained and frozen** traffic predictor (PEMS08, trained once with the official
hyper-parameters: seed 17, max 200 epochs / patience 20, early-stopped at epoch 63 with the best
validation checkpoint) is kept fixed. On top of it, candidates implement an **executable forecast
correction** with two entry points:

```python
def fit(features, targets, seed):      # -> serializable state
def predict(state, features):          # -> corrected forecast
```

The state must be independently reloadable. Candidates may change the fitting target / method
structure, the conditional spatio-temporal representation, and the forecast combination; the data
boundaries, seeds (17/29/43), scoring and resource budget are fixed. The objective is masked MAE
(minimize), with shape / finite / reload (≤ 1e-4) quality gates.

## Repository layout

| Path | Purpose |
|---|---|
| `instruction.md` | The eight-part task instruction given to the agent. |
| `task.toml` | Harbor task configuration (agent / verifier / environment). |
| `environment/` | Actor image build context: engine, CLI helpers, public assets. |
| `tests/` | Self-contained **separate-verifier** build context (engine, public assets, verifier assets, `test.sh`). |
| `solution/` | Starter solution — the deterministic identity corrector (returns the base forecast unchanged). |

## Data and verifier assets

- `*/public_assets/` hold the public features, graph and training targets.
- `*/verifier_assets/` hold the **public development set** labels (`dev_targets.npz`) and the scoring
  `protocol.json` (B/U anchors and grading details).
- The **hidden held-out set is intentionally not included**. It is injected into the verifier at
  evaluation time only, and never enters the actor image or build context.

## Runtime binaries

The agent execution environment normally vendors third-party CLI binaries under
`environment/cli/` (`codex`, `codex-code-mode-host`, `rg`). They are **not committed** here due to
file size and upstream licensing; they are provided by the execution/runtime environment.

## Attribution

All model architecture and the original implementation belong to the ST-SSDL authors; this package
only packages the Harbor task definition and the frozen-predictor correction surface.
