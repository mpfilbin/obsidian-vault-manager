"""
Unit tests for the OpenRouter embeddings client.

Tests verify request/response handling for embed_texts(), including
retry-then-succeed and give-up-after-two-failures behavior, and the
pack/unpack roundtrip used to store vectors as SQLite BLOBs.
"""

import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from vault_manager.core.embeddings import (
    EmbeddingError,
    embed_texts,
    pack_vector,
    unpack_vector,
)


def _mock_response(vectors):
    body = json.dumps({"data": [{"embedding": v} for v in vectors]}).encode("utf-8")
    mock_resp = MagicMock()
    mock_resp.read.return_value = body
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False
    return mock_resp


class TestEmbedTexts:
    def test_returns_vectors_in_order(self):
        with patch(
            "vault_manager.core.embeddings.urllib.request.urlopen",
            return_value=_mock_response([[0.1, 0.2], [0.3, 0.4]]),
        ) as mock_urlopen:
            result = embed_texts(["a", "b"], "openai/text-embedding-3-small", "test-key")

        assert result == [[0.1, 0.2], [0.3, 0.4]]
        mock_urlopen.assert_called_once()

    def test_sends_bearer_token_and_model(self):
        with patch(
            "vault_manager.core.embeddings.urllib.request.urlopen",
            return_value=_mock_response([[0.1]]),
        ) as mock_urlopen:
            embed_texts(["a"], "openai/text-embedding-3-small", "test-key")

        sent_request = mock_urlopen.call_args[0][0]
        assert sent_request.get_header("Authorization") == "Bearer test-key"
        sent_body = json.loads(sent_request.data.decode("utf-8"))
        assert sent_body == {"model": "openai/text-embedding-3-small", "input": ["a"]}

    def test_retries_once_then_succeeds(self):
        with patch(
            "vault_manager.core.embeddings.urllib.request.urlopen",
            side_effect=[urllib.error.URLError("boom"), _mock_response([[0.1]])],
        ):
            result = embed_texts(["a"], "openai/text-embedding-3-small", "test-key")

        assert result == [[0.1]]

    def test_raises_embedding_error_after_two_failures(self):
        with patch(
            "vault_manager.core.embeddings.urllib.request.urlopen",
            side_effect=urllib.error.URLError("boom"),
        ):
            with pytest.raises(EmbeddingError):
                embed_texts(["a"], "openai/text-embedding-3-small", "test-key")

    def test_converts_read_phase_timeout_to_embedding_error(self):
        with patch(
            "vault_manager.core.embeddings.urllib.request.urlopen",
            side_effect=TimeoutError("read timed out"),
        ):
            with pytest.raises(EmbeddingError):
                embed_texts(["a"], "openai/text-embedding-3-small", "test-key")


class TestPackUnpackVector:
    def test_roundtrip_preserves_values(self):
        values = [0.1, -0.2, 3.5, 0.0]

        packed = pack_vector(values)
        result = unpack_vector(packed)

        assert result == pytest.approx(values, abs=1e-6)

    def test_packed_value_is_bytes(self):
        packed = pack_vector([1.0, 2.0])

        assert isinstance(packed, bytes)
