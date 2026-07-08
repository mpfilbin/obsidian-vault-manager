"""
OpenRouter embeddings client.

Thin wrapper around OpenRouter's OpenAI-compatible embeddings endpoint,
used to generate semantic embeddings for notes. Uses only the standard
library for HTTP so no new HTTP dependency is required.
"""

import json
import urllib.error
import urllib.request
from array import array
from typing import List

OPENROUTER_EMBEDDINGS_URL = "https://openrouter.ai/api/v1/embeddings"


class EmbeddingError(Exception):
    """Raised when the OpenRouter embeddings API request fails."""


def embed_texts(texts: List[str], model: str, api_key: str) -> List[List[float]]:
    """
    Request embeddings for a batch of texts from OpenRouter.

    Sends a single request containing all texts as an array. Retries once
    (immediate, no backoff) before raising on failure.

    Args:
        texts: Text strings to embed, in order.
        model: OpenRouter embedding model identifier
            (e.g. "openai/text-embedding-3-small").
        api_key: OpenRouter API key.

    Returns:
        One embedding vector per input text, in the same order.

    Raises:
        EmbeddingError: If both the initial attempt and the retry fail.
    """
    payload = json.dumps({"model": model, "input": texts}).encode("utf-8")

    last_error: Exception = EmbeddingError("no attempts made")
    for _ in range(2):
        request = urllib.request.Request(
            OPENROUTER_EMBEDDINGS_URL,
            data=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = json.loads(response.read().decode("utf-8"))
            return [item["embedding"] for item in body["data"]]
        except (OSError, KeyError, ValueError) as e:
            last_error = e

    raise EmbeddingError(f"OpenRouter embeddings request failed: {last_error}")


def pack_vector(values: List[float]) -> bytes:
    """Pack a list of floats into bytes for storage as a SQLite BLOB."""
    return array("f", values).tobytes()


def unpack_vector(blob: bytes) -> List[float]:
    """Unpack a SQLite BLOB back into a list of floats."""
    values = array("f")
    values.frombytes(blob)
    return list(values)
