"""Real end-to-end test: Hermes adapter wrapping real Hermes-3 weights.

Marked `@pytest.mark.e2e` -- excluded from the default fast suite.

What this exercises (vs the mocked harness in test_integrations.py):
  * test_integrations.py uses a fake HF model + tokenizer.
  * THIS test loads REAL NousResearch/Hermes-3-Llama-3.2-3B weights and a real
    tokenizer, wraps them with GuardedChatModel, and runs real generation:
      - benign prompt   -> real Hermes inference runs, real text returned;
      - injection prompt -> classifier flags it, inference SUPPRESSED.

Because real Hermes-3 needs a GPU + multi-GB weights, the run itself happens
on a RunPod GPU pod, NOT in CI. This test validates the captured result JSON
that the pod produced. The pod script is tests/e2e_results/hermes_pod/
run_hermes_e2e.py; run it on any CUDA box with:
    pip install agent-guard-plugins[modernbert]
    python run_hermes_e2e.py

Prerequisites to run this pytest check:
  * tests/e2e_results/hermes_e2e.json must exist (pulled back from the pod).

Captured evidence: tests/e2e_results/hermes_e2e.json.
"""
from __future__ import annotations

import json
import pathlib

import pytest

HERE = pathlib.Path(__file__).parent
RESULT_JSON = HERE / "e2e_results" / "hermes_e2e.json"


@pytest.mark.e2e
def test_hermes_real_model_result():
    if not RESULT_JSON.exists():
        pytest.skip("hermes_e2e.json not present -- run run_hermes_e2e.py on a GPU")
    result = json.loads(RESULT_JSON.read_text())

    assert result.get("error") is None, result.get("traceback", "")
    assert result["passed"] is True
    assert result["model"] == "NousResearch/Hermes-3-Llama-3.2-3B"

    # Benign -> real inference ran and produced non-empty text.
    benign = result["benign"]
    assert benign["blocked"] is False
    assert isinstance(benign["text"], str) and benign["text"].strip()

    # Injection -> blocked, model inference suppressed.
    inj = result["injection"]
    assert inj["blocked"] is True
    assert inj["refusal_text"] == "I can't help with that request."
    assert inj["owasp"]  # at least one OWASP label fired
