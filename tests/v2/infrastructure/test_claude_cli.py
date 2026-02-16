"""Tests for ClaudeCliAgentClient adapter."""

from __future__ import annotations

import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from kdd.domain.entities import GraphNode
from kdd.domain.enums import KDDKind, KDDLayer
from kdd.infrastructure.agent.claude_cli import (
    ClaudeCliAgentClient,
    _parse_enrichment_response,
)


@pytest.fixture
def sample_node() -> GraphNode:
    return GraphNode(
        id="Entity:Pedido",
        kind=KDDKind.ENTITY,
        source_file="01-domain/entities/Pedido.md",
        source_hash="abc123",
        layer=KDDLayer.DOMAIN,
    )


@pytest.fixture
def valid_enrichment() -> dict:
    return {
        "summary": "Pedido represents a customer order.",
        "implicit_relations": [
            {"target": "Entity:Cliente", "type": "DEPENDS_ON"},
        ],
        "impact_analysis": {"change_risk": "high", "reason": "Core entity."},
    }


def _make_envelope(enrichment: dict) -> str:
    """Build a Claude CLI JSON envelope."""
    return json.dumps({
        "type": "result",
        "subtype": "success",
        "result": json.dumps(enrichment),
    })


class TestEnrichSuccess:
    def test_enrich_success(self, sample_node, valid_enrichment):
        client = ClaudeCliAgentClient(timeout=30)
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = _make_envelope(valid_enrichment)
        mock_result.stderr = ""

        with patch("kdd.infrastructure.agent.claude_cli.subprocess.run", return_value=mock_result) as mock_run:
            result = client.enrich(sample_node, "some context")

        assert result["summary"] == "Pedido represents a customer order."
        assert len(result["implicit_relations"]) == 1
        assert result["impact_analysis"]["change_risk"] == "high"

        # Verify CLAUDECODE* env vars are filtered
        call_kwargs = mock_run.call_args
        env = call_kwargs.kwargs["env"]
        for key in env:
            assert not key.startswith("CLAUDECODE"), f"CLAUDECODE var leaked: {key}"

    def test_enrich_with_model_override(self, sample_node, valid_enrichment):
        client = ClaudeCliAgentClient(model="sonnet")
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = _make_envelope(valid_enrichment)
        mock_result.stderr = ""

        with patch("kdd.infrastructure.agent.claude_cli.subprocess.run", return_value=mock_result) as mock_run:
            client.enrich(sample_node, "context")

        cmd = mock_run.call_args.args[0]
        assert "--model" in cmd
        assert "sonnet" in cmd


class TestEnrichErrors:
    def test_enrich_timeout(self, sample_node):
        client = ClaudeCliAgentClient(timeout=1)

        with patch(
            "kdd.infrastructure.agent.claude_cli.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="claude", timeout=1),
        ):
            with pytest.raises(RuntimeError, match="timed out"):
                client.enrich(sample_node, "context")

    def test_enrich_cli_not_found(self, sample_node):
        client = ClaudeCliAgentClient()

        with patch(
            "kdd.infrastructure.agent.claude_cli.subprocess.run",
            side_effect=FileNotFoundError,
        ):
            with pytest.raises(RuntimeError, match="not found"):
                client.enrich(sample_node, "context")

    def test_enrich_nonzero_exit(self, sample_node):
        client = ClaudeCliAgentClient()
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "some error"

        with patch("kdd.infrastructure.agent.claude_cli.subprocess.run", return_value=mock_result):
            with pytest.raises(RuntimeError, match="exited with code 1"):
                client.enrich(sample_node, "context")

    def test_enrich_invalid_json_envelope(self, sample_node):
        client = ClaudeCliAgentClient()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "not json at all"
        mock_result.stderr = ""

        with patch("kdd.infrastructure.agent.claude_cli.subprocess.run", return_value=mock_result):
            with pytest.raises(RuntimeError, match="invalid JSON envelope"):
                client.enrich(sample_node, "context")


class TestParseEnrichmentResponse:
    def test_parse_valid_json(self, valid_enrichment):
        result = _parse_enrichment_response(json.dumps(valid_enrichment))
        assert result["summary"] == "Pedido represents a customer order."

    def test_parse_with_markdown_fences(self, valid_enrichment):
        text = "```json\n" + json.dumps(valid_enrichment) + "\n```"
        result = _parse_enrichment_response(text)
        assert result["summary"] == "Pedido represents a customer order."

    def test_parse_with_bare_fences(self, valid_enrichment):
        text = "```\n" + json.dumps(valid_enrichment) + "\n```"
        result = _parse_enrichment_response(text)
        assert result["summary"] == "Pedido represents a customer order."

    def test_parse_missing_keys_defaults(self):
        result = _parse_enrichment_response("{}")
        assert result["summary"] == ""
        assert result["implicit_relations"] == []
        assert result["impact_analysis"]["change_risk"] == "medium"

    def test_parse_invalid_json_raises(self):
        with pytest.raises(RuntimeError, match="invalid JSON"):
            _parse_enrichment_response("this is not json")

    def test_parse_non_object_raises(self):
        with pytest.raises(RuntimeError, match="Expected JSON object"):
            _parse_enrichment_response("[1, 2, 3]")
