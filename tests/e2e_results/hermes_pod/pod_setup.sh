#!/usr/bin/env bash
# Runs on the RunPod pod. Installs agent-guard-plugins, then runs the Hermes e2e.
#
# Installs from the source tree uploaded to /workspace/agp-src (carries the
# transformers-5.x reference_compile fix). Falls back to PyPI if absent.
set -euo pipefail
cd /workspace
echo "=== installing agent-guard-plugins ==="
if [ -d /workspace/agp-src ]; then
  pip install -q --no-input "/workspace/agp-src[modernbert]" 2>&1 | tail -3
else
  pip install -q --no-input "agent-guard-plugins[modernbert]" 2>&1 | tail -3
fi
python3 -c "import agent_guard_plugins, transformers; print('agp', agent_guard_plugins.__version__ if hasattr(agent_guard_plugins,'__version__') else 'src', '| transformers', transformers.__version__)"
echo "=== running Hermes e2e ==="
python3 run_hermes_e2e.py
echo "=== DONE ==="
