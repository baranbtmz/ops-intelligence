"""Shared OpenAI JSON requests with explicit budgets and output validation."""
import json
import os
from openai import OpenAI


def create_json_response(*, model, system, user, max_output_tokens=6000, client=None):
    client = client or OpenAI(timeout=float(os.getenv("OPENAI_TIMEOUT_SECONDS", "75")), max_retries=1)
    kwargs = {
        "model": model,
        "input": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "text": {"format": {"type": "json_object"}},
        "max_output_tokens": max_output_tokens,
        "store": False,
    }
    if model.startswith(("gpt-6", "gpt-5", "o3", "o4")):
        kwargs["reasoning"] = {"effort": os.getenv("OPENAI_REASONING_EFFORT", "low")}
    response = client.responses.create(**kwargs)
    if response.status != "completed":
        raise ValueError("AI response did not complete within its output budget")
    parsed = json.loads(response.output_text)
    if not isinstance(parsed, dict):
        raise ValueError("AI response must be a JSON object")
    return parsed, response
