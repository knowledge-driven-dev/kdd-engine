"""AgentClient adapter that invokes the Claude CLI (``claude -p``).

Requires the ``claude`` binary available in PATH (Claude Code subscription).
No API key needed — uses the developer's existing Claude CLI auth.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from typing import Any

from kdd.domain.entities import GraphNode

logger = logging.getLogger(__name__)


class ClaudeCliAgentClient:
    """Adapter: AgentClient → ``claude -p`` subprocess."""

    def __init__(
        self,
        timeout: int = 120,
        claude_path: str | None = None,
        model: str | None = None,
    ) -> None:
        self.timeout = timeout
        self.claude_path = claude_path or "claude"
        self.model = model

    def enrich(self, node: GraphNode, context: str) -> dict[str, Any]:
        """Call Claude CLI to enrich a graph node (CMD-003)."""
        prompt = _build_enrichment_prompt(node, context)

        cmd = [self.claude_path, "-p", prompt, "--output-format", "json"]
        if self.model:
            cmd.extend(["--model", self.model])

        # Filter CLAUDECODE* env vars so nested claude invocation works
        env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDECODE")}

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                env=env,
            )
        except FileNotFoundError:
            raise RuntimeError(
                f"Claude CLI not found at '{self.claude_path}'. "
                "Install it from https://docs.anthropic.com/en/docs/claude-code"
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(
                f"Claude CLI timed out after {self.timeout}s enriching {node.id}"
            )

        if result.returncode != 0:
            stderr = result.stderr.strip()[:500] if result.stderr else "(no stderr)"
            raise RuntimeError(
                f"Claude CLI exited with code {result.returncode}: {stderr}"
            )

        # Parse the CLI envelope: {"type":"result","subtype":"success","result":"..."}
        try:
            envelope = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Claude CLI returned invalid JSON envelope: {e}")

        model_text = envelope.get("result", "")
        return _parse_enrichment_response(model_text)


def _build_enrichment_prompt(node: GraphNode, context: str) -> str:
    """Build the enrichment prompt for Claude."""
    return f"""\
You are a KDD (Knowledge-Driven Development) analyst. Given the following \
specification node and its context, produce a JSON object with exactly these keys:

- "summary": A concise 2-3 sentence summary of the specification's purpose and scope.
- "implicit_relations": An array of objects, each with "target" (node ID like "Entity:Pedido") \
and "type" (edge type like "DEPENDS_ON", "TRIGGERS", "VALIDATES").
- "impact_analysis": An object with "change_risk" ("low"|"medium"|"high") and \
"reason" (one sentence explaining why).

Respond ONLY with the JSON object, no markdown fences, no explanation.

---
{context}
"""


def _parse_enrichment_response(text: str) -> dict[str, Any]:
    """Parse the model's response text into a structured dict.

    Handles markdown fences defensively and fills missing keys with defaults.
    """
    cleaned = text.strip()

    # Strip markdown fences if present
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # Remove first line (```json or ```)
        lines = lines[1:]
        # Remove last line if it's closing fence
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Model returned invalid JSON: {e}\nRaw text: {text[:300]}")

    if not isinstance(data, dict):
        raise RuntimeError(f"Expected JSON object, got {type(data).__name__}")

    # Fill missing keys with defaults
    data.setdefault("summary", "")
    data.setdefault("implicit_relations", [])
    data.setdefault("impact_analysis", {"change_risk": "medium", "reason": "unknown"})

    return data
