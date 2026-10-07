#!/bin/sh
set -eu
chmod 700 /tests /logs/verifier
rm -f /logs/verifier/reward.txt /logs/verifier/reward.json
if [ -f /tests/hidden_assets/protocol.json ]; then
  python -I /opt/forecast-engine/grader.py --solution /workspace/solution --output /logs/verifier/evaluation --hidden-assets /tests/hidden_assets
else
  python -I /opt/forecast-engine/grader.py --solution /workspace/solution --output /logs/verifier/evaluation
fi
