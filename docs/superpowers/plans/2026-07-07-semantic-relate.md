# Semantic Relatedness for `vault properties relate` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add embedding-based semantic similarity to `vault properties relate` (invoked as `vault properties enrich related`) so notes are associated by meaning, not just tag/link/folder/title overlap.

**Architecture:** A new `vault_manager/core/embeddings.py` module calls OpenRouter's OpenAI-compatible embeddings endpoint. `relate.py` caches embeddings in a new `note_embeddings` table in `vault.db` (keyed by content hash so unchanged notes aren't re-embedded), computes pairwise cosine similarity via numpy, and blends it into the existing weighted similarity score as a new component.

**Tech Stack:** Python stdlib `urllib.request` (HTTP), `numpy` (cosine similarity), SQLite (`vault.db` via existing `VaultDatabase`), pytest + `unittest.mock`.

## Global Constraints

- Embeddings come from OpenRouter (`POST https://openrouter.ai/api/v1/embeddings`), OpenAI-compatible request/response shape.
- Default model: `openai/text-embedding-3-small`. Configurable via `OPENROUTER_EMBEDDING_MODEL` env var.
- Feature auto-enables when `OPENROUTER_API_KEY` env var is set — no new CLI flag.
- Rebalanced weights when semantic score is available: semantic 40%, tag 25%, link 20%, folder 7.5%, title 7.5%. Without a semantic score (no key, no numpy, or a specific note's embedding failed): original weights (tag 40%, link 30%, folder 15%, title 15%) apply for that comparison.
- Sensitive notes (`sensitive: true` in frontmatter) are never embedded, consistent with `summarize.py`/`enrich.py`.
- No new HTTP client dependency — use stdlib `urllib.request` only. `numpy` is the one new dependency, added to the `ai` optional-dependency group.
- Embedding text: stripped-markdown note body, truncated to 6000 characters.
- Per-note/per-batch failure fallback: an embedding failure never aborts the run; affected notes just score without a semantic component for that run.
- Full design detail: `docs/superpowers/specs/2026-07-07-semantic-relate-design.md`.

---

### Task 1: Add numpy dependency

**Files:**
- Modify: `pyproject.toml:40-42` (ai extra), `pyproject.toml:49-56` (dev extra)

**Interfaces:**
- Produces: `numpy` importable in the dev/ai environment for later tasks.

- [ ] **Step 1: Add numpy to the `ai` and `dev` optional-dependency groups**

In `pyproject.toml`, change:

```toml
ai = [
    "anthropic>=0.18.0",
]
```

to:

```toml
ai = [
    "anthropic>=0.18.0",
    "numpy>=1.24.0",
]
```

And change the `dev` group from:

```toml
dev = [
    "anthropic>=0.18.0",
    "pytest>=7.4.0",
    "pytest-bdd>=6.1.0",
    "pytest-cov>=4.1.0",
    "pytest-mock>=3.12.0",
    "black>=23.0.0",
    "ruff>=0.1.0",
]
```

to:

```toml
dev = [
    "anthropic>=0.18.0",
    "numpy>=1.24.0",
    "pytest>=7.4.0",
    "pytest-bdd>=6.1.0",
    "pytest-cov>=4.1.0",
    "pytest-mock>=3.12.0",
    "black>=23.0.0",
    "ruff>=0.1.0",
]
```

- [ ] **Step 2: Reinstall the dev environment and verify numpy is importable**

Run: `pip install -e ".[dev]" && python -c "import numpy; print(numpy.__version__)"`
Expected: prints a version number (e.g. `1.26.4`), no `ModuleNotFoundError`.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "build: add numpy dependency for semantic similarity"
```

---

### Task 2: OpenRouter embeddings client

**Files:**
- Create: `vault_manager/core/embeddings.py`
- Test: `tests/unit/test_embeddings.py`

**Interfaces:**
- Produces:
  - `class EmbeddingError(Exception)`
  - `embed_texts(texts: List[str], model: str, api_key: str) -> List[List[float]]`
  - `pack_vector(values: List[float]) -> bytes`
  - `unpack_vector(blob: bytes) -> List[float]`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_embeddings.py`:

```python
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


class TestPackUnpackVector:
    def test_roundtrip_preserves_values(self):
        values = [0.1, -0.2, 3.5, 0.0]

        packed = pack_vector(values)
        result = unpack_vector(packed)

        assert result == pytest.approx(values, abs=1e-6)

    def test_packed_value_is_bytes(self):
        packed = pack_vector([1.0, 2.0])

        assert isinstance(packed, bytes)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_embeddings.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'vault_manager.core.embeddings'`

- [ ] **Step 3: Implement the embeddings client**

Create `vault_manager/core/embeddings.py`:

```python
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
        except (urllib.error.URLError, KeyError, ValueError) as e:
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_embeddings.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add vault_manager/core/embeddings.py tests/unit/test_embeddings.py
git commit -m "feat: add OpenRouter embeddings client"
```

---

### Task 3: Markdown stripping and content-hash helpers in relate.py

**Files:**
- Modify: `vault_manager/properties/commands/relate.py:1-23` (imports), `:26-37` (`NoteMetadata`)
- Test: `tests/unit/test_relate_semantic.py`

**Interfaces:**
- Consumes: none new.
- Produces:
  - `NoteMetadata.is_sensitive: bool` (default `False`)
  - `NoteMetadata.embedding_text: str` (default `""`)
  - `RelateCommand._strip_markdown_for_embedding(self, text: str) -> str`
  - `RelateCommand._prepare_embedding_text(self, body: str) -> str`
  - `RelateCommand._compute_content_hash(self, text: str) -> str`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_relate_semantic.py`:

```python
"""
Unit tests for semantic (embedding-based) relatedness in the relate command.

Covers markdown stripping/truncation for embedding text, content hashing
for cache invalidation, the embedding cache itself, rebalanced scoring
weights, and the end-to-end acceptance case where two notes with no
structural overlap are still related via semantic similarity.
"""

from vault_manager.properties.commands.relate import NoteMetadata, RelateCommand


class TestPrepareEmbeddingText:
    def test_strips_bold_italic_and_links(self):
        cmd = RelateCommand()
        text = "This is **bold**, *italic*, and a [link](http://example.com)."

        result = cmd._strip_markdown_for_embedding(text)

        assert "**" not in result
        assert "[link]" not in result
        assert "bold" in result
        assert "italic" in result
        assert "link" in result

    def test_strips_wiki_links_keeping_display_text(self):
        cmd = RelateCommand()
        text = "See [[Other Note|this note]] for details."

        result = cmd._strip_markdown_for_embedding(text)

        assert "[[" not in result
        assert "this note" in result

    def test_truncates_to_6000_characters(self):
        cmd = RelateCommand()
        long_body = "word " * 2000  # far more than 6000 chars

        result = cmd._prepare_embedding_text(long_body)

        assert len(result) <= 6000

    def test_short_body_is_unchanged_in_length(self):
        cmd = RelateCommand()
        body = "A short note body."

        result = cmd._prepare_embedding_text(body)

        assert result.strip() == "A short note body."


class TestComputeContentHash:
    def test_same_text_same_hash(self):
        cmd = RelateCommand()

        assert cmd._compute_content_hash("hello") == cmd._compute_content_hash("hello")

    def test_different_text_different_hash(self):
        cmd = RelateCommand()

        assert cmd._compute_content_hash("hello") != cmd._compute_content_hash("goodbye")


class TestNoteMetadataDefaults:
    def test_new_fields_default_correctly(self, tmp_path):
        note = NoteMetadata(tmp_path / "note.md", "note.md")

        assert note.is_sensitive is False
        assert note.embedding_text == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_relate_semantic.py -v`
Expected: FAIL with `AttributeError: 'RelateCommand' object has no attribute '_strip_markdown_for_embedding'`

- [ ] **Step 3: Add imports and NoteMetadata fields**

In `vault_manager/properties/commands/relate.py`, replace the import block (lines 1-23):

```python
"""
Relate command - Find related notes based on similarity.

This module implements the relate command which analyzes notes using a hybrid
similarity algorithm and adds related property with wiki-links to similar notes.
"""

import hashlib
import math
import os
import re
import sys
from argparse import ArgumentParser, Namespace
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from vault_manager.core.database import VaultDatabase
from vault_manager.core.dry_run import DryRunContext, print_dry_run_summary
from vault_manager.core.embeddings import EmbeddingError, embed_texts, pack_vector, unpack_vector
from vault_manager.core.frontmatter_manager import FrontmatterManager
from vault_manager.core.vault import iter_markdown_files

from ..common import extract_frontmatter
from . import Command

try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    np = None
    HAS_NUMPY = False

DEFAULT_EMBEDDING_MODEL = "openai/text-embedding-3-small"
```

Replace the `NoteMetadata` class (lines 26-37):

```python
class NoteMetadata:
    """Holds metadata about a note for similarity calculation."""

    def __init__(self, path: Path, relative_path: str):
        self.path = path
        self.relative_path = relative_path
        self.tags: Set[str] = set()
        self.links: Set[str] = set()
        self.title: str = ""
        self.title_words: Set[str] = set()
        self.folder: str = ""
        self.has_related: bool = False
        self.is_sensitive: bool = False
        self.embedding_text: str = ""
```

- [ ] **Step 4: Add the markdown-stripping, truncation, and hashing methods**

Add these methods to `RelateCommand` (place after `_check_has_related_property`, before `_scan_notes_for_metadata`):

```python
    def _strip_markdown_for_embedding(self, text: str) -> str:
        """Remove markdown formatting from text before embedding."""
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
        text = re.sub(r"__(.+?)__", r"\1", text)
        text = re.sub(r"\*(.+?)\*", r"\1", text)
        text = re.sub(r"_(.+?)_", r"\1", text)
        text = re.sub(r"`(.+?)`", r"\1", text)
        text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)
        text = re.sub(
            r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", lambda m: m.group(2) or m.group(1), text
        )
        text = re.sub(r"~~(.+?)~~", r"\1", text)
        text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
        return text

    def _prepare_embedding_text(self, body: str) -> str:
        """Strip markdown formatting and truncate body text for embedding."""
        stripped = self._strip_markdown_for_embedding(body)
        return stripped[:6000]

    def _compute_content_hash(self, text: str) -> str:
        """Compute a stable hash of embedding text for cache invalidation."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/unit/test_relate_semantic.py -v`
Expected: PASS (6 tests)

- [ ] **Step 6: Commit**

```bash
git add vault_manager/properties/commands/relate.py tests/unit/test_relate_semantic.py
git commit -m "feat: add embedding text prep and content hashing to relate command"
```

---

### Task 4: Embedding cache table and semantic embedding computation

**Files:**
- Modify: `vault_manager/properties/commands/relate.py` (add methods after `_get_tag_frequencies_from_database`)
- Modify: `tests/conftest.py:277-286` (`reset_environment` fixture)
- Test: `tests/unit/test_relate_semantic.py` (append)

**Interfaces:**
- Consumes: `embed_texts`, `EmbeddingError`, `pack_vector`, `unpack_vector` (Task 2); `NoteMetadata.is_sensitive`/`embedding_text` (Task 3).
- Produces:
  - `RelateCommand._get_openrouter_api_key(self) -> Optional[str]`
  - `RelateCommand._get_embedding_model(self) -> str`
  - `RelateCommand._compute_semantic_embeddings(self, notes: Dict[str, NoteMetadata], db: VaultDatabase, api_key: str, model: str) -> Dict[str, List[float]]`

- [ ] **Step 1: Prevent real API calls leaking into tests**

In `tests/conftest.py`, change the `reset_environment` fixture:

```python
@pytest.fixture(autouse=True)
def reset_environment(monkeypatch):
    """
    Reset environment variables for each test.

    This fixture runs automatically before each test.
    """
    # Remove API keys to prevent accidental API calls in tests
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_EMBEDDING_MODEL", raising=False)
```

- [ ] **Step 2: Write the failing tests**

Append to `tests/unit/test_relate_semantic.py`:

```python
from unittest.mock import patch

import pytest

from vault_manager.core.database import VaultDatabase
from vault_manager.core.embeddings import EmbeddingError, pack_vector


def _make_note(tmp_path, name, embedding_text, is_sensitive=False):
    path = tmp_path / name
    path.write_text(f"---\ntags: []\n---\n{embedding_text}\n", encoding="utf-8")
    note = NoteMetadata(path, name)
    note.embedding_text = embedding_text
    note.is_sensitive = is_sensitive
    return note


class TestApiKeyAndModelConfig:
    def test_no_key_returns_none(self, monkeypatch):
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        cmd = RelateCommand()

        assert cmd._get_openrouter_api_key() is None

    def test_key_is_read_from_env(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-123")
        cmd = RelateCommand()

        assert cmd._get_openrouter_api_key() == "sk-test-123"

    def test_default_model(self, monkeypatch):
        monkeypatch.delenv("OPENROUTER_EMBEDDING_MODEL", raising=False)
        cmd = RelateCommand()

        assert cmd._get_embedding_model() == "openai/text-embedding-3-small"

    def test_model_override_from_env(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_EMBEDDING_MODEL", "openai/text-embedding-3-large")
        cmd = RelateCommand()

        assert cmd._get_embedding_model() == "openai/text-embedding-3-large"


class TestComputeSemanticEmbeddings:
    def test_embeds_new_notes_and_caches_them(self, vault_database, tmp_path):
        db = VaultDatabase(vault_root=tmp_path)
        notes = {
            "a.md": _make_note(tmp_path, "a.md", "content about cats"),
            "b.md": _make_note(tmp_path, "b.md", "content about dogs"),
        }
        cmd = RelateCommand()

        with patch(
            "vault_manager.properties.commands.relate.embed_texts",
            return_value=[[1.0, 0.0], [0.0, 1.0]],
        ) as mock_embed:
            vectors = cmd._compute_semantic_embeddings(
                notes, db, "test-key", "openai/text-embedding-3-small"
            )

        assert vectors["a.md"] == [1.0, 0.0]
        assert vectors["b.md"] == [0.0, 1.0]
        mock_embed.assert_called_once()

        with db:
            rows = db.query("SELECT file_path, model FROM note_embeddings ORDER BY file_path")
        assert rows == [("a.md", "openai/text-embedding-3-small"), ("b.md", "openai/text-embedding-3-small")]

    def test_reuses_cached_embedding_when_hash_matches(self, vault_database, tmp_path):
        db = VaultDatabase(vault_root=tmp_path)
        note = _make_note(tmp_path, "a.md", "stable content")
        content_hash = RelateCommand()._compute_content_hash("stable content")

        with db:
            db.write(
                """
                CREATE TABLE IF NOT EXISTS note_embeddings (
                    file_path TEXT PRIMARY KEY,
                    content_hash TEXT NOT NULL,
                    model TEXT NOT NULL,
                    vector BLOB NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            db.write(
                "INSERT INTO note_embeddings VALUES (?, ?, ?, ?, ?)",
                ("a.md", content_hash, "openai/text-embedding-3-small", pack_vector([9.0, 9.0]), "2026-01-01T00:00:00"),
            )

        cmd = RelateCommand()
        with patch("vault_manager.properties.commands.relate.embed_texts") as mock_embed:
            vectors = cmd._compute_semantic_embeddings(
                {"a.md": note}, db, "test-key", "openai/text-embedding-3-small"
            )

        assert vectors["a.md"] == [9.0, 9.0]
        mock_embed.assert_not_called()

    def test_re_embeds_when_content_hash_changed(self, vault_database, tmp_path):
        db = VaultDatabase(vault_root=tmp_path)
        note = _make_note(tmp_path, "a.md", "new content")

        with db:
            db.write(
                """
                CREATE TABLE IF NOT EXISTS note_embeddings (
                    file_path TEXT PRIMARY KEY,
                    content_hash TEXT NOT NULL,
                    model TEXT NOT NULL,
                    vector BLOB NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            db.write(
                "INSERT INTO note_embeddings VALUES (?, ?, ?, ?, ?)",
                ("a.md", "stale-hash", "openai/text-embedding-3-small", pack_vector([9.0, 9.0]), "2026-01-01T00:00:00"),
            )

        cmd = RelateCommand()
        with patch(
            "vault_manager.properties.commands.relate.embed_texts",
            return_value=[[1.0, 2.0]],
        ) as mock_embed:
            vectors = cmd._compute_semantic_embeddings(
                {"a.md": note}, db, "test-key", "openai/text-embedding-3-small"
            )

        assert vectors["a.md"] == [1.0, 2.0]
        mock_embed.assert_called_once()

    def test_skips_sensitive_notes(self, vault_database, tmp_path):
        db = VaultDatabase(vault_root=tmp_path)
        note = _make_note(tmp_path, "secret.md", "sensitive content", is_sensitive=True)
        cmd = RelateCommand()

        with patch("vault_manager.properties.commands.relate.embed_texts") as mock_embed:
            vectors = cmd._compute_semantic_embeddings(
                {"secret.md": note}, db, "test-key", "openai/text-embedding-3-small"
            )

        assert "secret.md" not in vectors
        mock_embed.assert_not_called()

    def test_batch_failure_skips_only_that_batch(self, vault_database, tmp_path, capsys):
        db = VaultDatabase(vault_root=tmp_path)
        notes = {"a.md": _make_note(tmp_path, "a.md", "content a")}
        cmd = RelateCommand()

        with patch(
            "vault_manager.properties.commands.relate.embed_texts",
            side_effect=EmbeddingError("rate limited"),
        ):
            vectors = cmd._compute_semantic_embeddings(
                notes, db, "test-key", "openai/text-embedding-3-small"
            )

        assert vectors == {}
        assert "Warning" in capsys.readouterr().out
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/unit/test_relate_semantic.py -v`
Expected: FAIL with `AttributeError: 'RelateCommand' object has no attribute '_get_openrouter_api_key'`

- [ ] **Step 4: Implement the cache and computation methods**

Add these methods to `RelateCommand` (place after `_get_tag_frequencies_from_database`):

```python
    def _get_openrouter_api_key(self) -> Optional[str]:
        """Read the OpenRouter API key from the environment, if set."""
        return os.environ.get("OPENROUTER_API_KEY")

    def _get_embedding_model(self) -> str:
        """Read the configured embedding model, defaulting to text-embedding-3-small."""
        return os.environ.get("OPENROUTER_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)

    def _compute_semantic_embeddings(
        self,
        notes: Dict[str, NoteMetadata],
        db: VaultDatabase,
        api_key: str,
        model: str,
    ) -> Dict[str, List[float]]:
        """
        Compute (or reuse cached) embeddings for all non-sensitive notes.

        Returns:
            Dict mapping file_path -> embedding vector for every note with a
            usable embedding. Sensitive notes, and notes whose embedding
            request failed, are simply absent from the returned dict.
        """
        vectors: Dict[str, List[float]] = {}
        upserts: List[Tuple[str, str, str, bytes, str]] = []

        with db:
            db.write(
                """
                CREATE TABLE IF NOT EXISTS note_embeddings (
                    file_path TEXT PRIMARY KEY,
                    content_hash TEXT NOT NULL,
                    model TEXT NOT NULL,
                    vector BLOB NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

            cached_rows = db.query(
                "SELECT file_path, content_hash, vector FROM note_embeddings WHERE model = ?",
                (model,),
            )
            cached = {
                path: (content_hash, unpack_vector(blob))
                for path, content_hash, blob in cached_rows
            }

            to_embed: List[Tuple[str, str, str]] = []  # (file_path, text, content_hash)

            for path, note in notes.items():
                if note.is_sensitive:
                    continue

                content_hash = self._compute_content_hash(note.embedding_text)
                cached_entry = cached.get(path)

                if cached_entry and cached_entry[0] == content_hash:
                    vectors[path] = cached_entry[1]
                else:
                    to_embed.append((path, note.embedding_text, content_hash))

            batch_size = 50
            for i in range(0, len(to_embed), batch_size):
                batch = to_embed[i : i + batch_size]
                texts = [text for _, text, _ in batch]

                try:
                    embeddings = embed_texts(texts, model, api_key)
                except EmbeddingError as e:
                    print(f"   Warning: Embedding request failed for {len(batch)} note(s): {e}")
                    continue

                timestamp = datetime.now(timezone.utc).isoformat()
                for (path, _, content_hash), vector in zip(batch, embeddings):
                    vectors[path] = vector
                    upserts.append((path, content_hash, model, pack_vector(vector), timestamp))

            if upserts:
                db.write_many(
                    """
                    INSERT INTO note_embeddings (file_path, content_hash, model, vector, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(file_path) DO UPDATE SET
                        content_hash = excluded.content_hash,
                        model = excluded.model,
                        vector = excluded.vector,
                        created_at = excluded.created_at
                    """,
                    upserts,
                )

        return vectors
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/unit/test_relate_semantic.py -v`
Expected: PASS (all tests so far)

- [ ] **Step 6: Commit**

```bash
git add vault_manager/properties/commands/relate.py tests/conftest.py tests/unit/test_relate_semantic.py
git commit -m "feat: cache note embeddings in vault.db keyed by content hash"
```

---

### Task 5: Rebalance the similarity score with an optional semantic component

**Files:**
- Modify: `vault_manager/properties/commands/relate.py:350-363` (`_calculate_similarity_score`)
- Test: `tests/unit/test_relate_semantic.py` (append)

**Interfaces:**
- Consumes: existing `_calculate_tag_similarity`, `_calculate_link_similarity`, `_calculate_folder_similarity`, `_calculate_title_similarity`.
- Produces: `RelateCommand._calculate_similarity_score(self, note1, note2, tag_frequencies, semantic_score: Optional[float] = None) -> float`

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_relate_semantic.py`:

```python
class TestCalculateSimilarityScoreWeights:
    def _notes_with_no_structural_overlap(self, tmp_path):
        note1 = NoteMetadata(tmp_path / "a.md", "a.md")
        note1.tags = {"unique-tag-1"}
        note1.folder = "FolderA"
        note1.title_words = {"alpha"}

        note2 = NoteMetadata(tmp_path / "b.md", "b.md")
        note2.tags = {"unique-tag-2"}
        note2.folder = "FolderB"
        note2.title_words = {"beta"}

        return note1, note2

    def test_without_semantic_score_uses_original_weights(self, tmp_path):
        cmd = RelateCommand()
        note1, note2 = self._notes_with_no_structural_overlap(tmp_path)

        score = cmd._calculate_similarity_score(note1, note2, Counter(), semantic_score=None)

        assert score == 0.0

    def test_semantic_score_of_one_with_no_structural_overlap(self, tmp_path):
        cmd = RelateCommand()
        note1, note2 = self._notes_with_no_structural_overlap(tmp_path)

        score = cmd._calculate_similarity_score(note1, note2, Counter(), semantic_score=1.0)

        assert score == pytest.approx(0.40, abs=1e-6)

    def test_semantic_score_of_zero_matches_structural_only(self, tmp_path):
        cmd = RelateCommand()
        note1, note2 = self._notes_with_no_structural_overlap(tmp_path)

        with_zero_semantic = cmd._calculate_similarity_score(note1, note2, Counter(), semantic_score=0.0)

        assert with_zero_semantic == pytest.approx(0.0, abs=1e-6)
```

Add `from collections import Counter` to the imports at the top of `tests/unit/test_relate_semantic.py` if not already present (it's needed by `Counter()` above).

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_relate_semantic.py::TestCalculateSimilarityScoreWeights -v`
Expected: FAIL with `TypeError: _calculate_similarity_score() got an unexpected keyword argument 'semantic_score'`

- [ ] **Step 3: Rebalance the score calculation**

Replace `_calculate_similarity_score` (lines 350-363):

```python
    def _calculate_similarity_score(
        self,
        note1: NoteMetadata,
        note2: NoteMetadata,
        tag_frequencies: Dict[str, int],
        semantic_score: Optional[float] = None,
    ) -> float:
        """
        Calculate overall similarity score using weighted components.

        With a semantic score: Semantic (40%), Tag (25%), Link (20%), Folder (7.5%), Title (7.5%)
        Without one: Tag (40%), Link (30%), Folder (15%), Title (15%)
        """
        tag_score = self._calculate_tag_similarity(note1, note2, tag_frequencies)
        link_score = self._calculate_link_similarity(note1, note2)
        folder_score = self._calculate_folder_similarity(note1, note2)
        title_score = self._calculate_title_similarity(note1, note2)

        if semantic_score is None:
            return tag_score * 0.40 + link_score * 0.30 + folder_score * 0.15 + title_score * 0.15

        return (
            semantic_score * 0.40
            + tag_score * 0.25
            + link_score * 0.20
            + folder_score * 0.075
            + title_score * 0.075
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_relate_semantic.py -v`
Expected: PASS (all tests so far)

- [ ] **Step 5: Run the full existing relate-adjacent test suite to check for regressions**

Run: `pytest tests/ -k relate -v`
Expected: PASS (no pre-existing relate tests broken; if none exist yet, this reports "no tests ran" — that's fine)

- [ ] **Step 6: Commit**

```bash
git add vault_manager/properties/commands/relate.py tests/unit/test_relate_semantic.py
git commit -m "feat: rebalance relate scoring to include optional semantic component"
```

---

### Task 6: Plumb semantic vectors into `_find_related_notes` via cosine similarity

**Files:**
- Modify: `vault_manager/properties/commands/relate.py:365-432` (`_find_related_notes`)
- Test: `tests/unit/test_relate_semantic.py` (append)

**Interfaces:**
- Consumes: `HAS_NUMPY`, `np` (Task 3 import block); `_calculate_similarity_score(..., semantic_score=...)` (Task 5).
- Produces:
  - `RelateCommand._build_semantic_similarity_lookup(self, semantic_vectors: Optional[Dict[str, List[float]]]) -> Tuple[Dict[str, int], Optional["np.ndarray"]]`
  - `RelateCommand._find_related_notes(self, notes, max_related=5, db=None, semantic_vectors: Optional[Dict[str, List[float]]] = None) -> Dict[str, List[Tuple[str, float]]]` (new `semantic_vectors` parameter)

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_relate_semantic.py`:

```python
class TestFindRelatedNotesWithSemanticVectors:
    def test_semantically_similar_notes_get_related_despite_no_structural_overlap(self, tmp_path):
        cmd = RelateCommand()

        note_a = NoteMetadata(tmp_path / "a.md", "a.md")
        note_a.tags = {"unique-a"}
        note_a.folder = "FolderA"
        note_a.title_words = {"alpha"}

        note_b = NoteMetadata(tmp_path / "b.md", "b.md")
        note_b.tags = {"unique-b"}
        note_b.folder = "FolderB"
        note_b.title_words = {"beta"}

        notes = {"a.md": note_a, "b.md": note_b}
        semantic_vectors = {"a.md": [1.0, 0.0], "b.md": [1.0, 0.0]}  # identical direction

        related = cmd._find_related_notes(notes, max_related=5, semantic_vectors=semantic_vectors)

        assert "b.md" in [path for path, _ in related["a.md"]]
        score = next(score for path, score in related["a.md"] if path == "b.md")
        assert score == pytest.approx(0.40, abs=1e-6)

    def test_note_missing_from_semantic_vectors_falls_back_to_structural_weights(self, tmp_path):
        cmd = RelateCommand()

        note_a = NoteMetadata(tmp_path / "a.md", "a.md")
        note_a.folder = "Parent"

        note_b = NoteMetadata(tmp_path / "b.md", "b.md")
        note_b.folder = "Parent/Child"

        notes = {"a.md": note_a, "b.md": note_b}
        # Only "a.md" has a vector - "b.md" is absent (e.g. embedding failed).
        semantic_vectors = {"a.md": [1.0, 0.0]}

        related = cmd._find_related_notes(notes, max_related=5, semantic_vectors=semantic_vectors)

        # No semantic score is available for this pair (b.md has no vector), so it
        # falls back to the original weights. Tags/links/title are all empty here,
        # so only the folder-proximity component (parent/child = 0.5 similarity,
        # 15% weight) contributes.
        score = next(score for path, score in related["a.md"] if path == "b.md")
        assert score == pytest.approx(0.5 * 0.15, abs=1e-6)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_relate_semantic.py::TestFindRelatedNotesWithSemanticVectors -v`
Expected: FAIL with `TypeError: _find_related_notes() got an unexpected keyword argument 'semantic_vectors'`

- [ ] **Step 3: Implement the cosine similarity lookup and wire it into `_find_related_notes`**

Add this method to `RelateCommand` (place immediately before `_find_related_notes`):

```python
    def _build_semantic_similarity_lookup(
        self, semantic_vectors: Optional[Dict[str, List[float]]]
    ) -> Tuple[Dict[str, int], Optional["np.ndarray"]]:
        """Build a path->index map and a precomputed cosine similarity matrix."""
        if not semantic_vectors or not HAS_NUMPY:
            return {}, None

        paths = list(semantic_vectors.keys())
        matrix = np.array([semantic_vectors[p] for p in paths], dtype=np.float32)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1e-10
        normalized = matrix / norms
        similarity_matrix = normalized @ normalized.T

        path_to_index = {path: i for i, path in enumerate(paths)}
        return path_to_index, similarity_matrix
```

Replace the body of `_find_related_notes` (lines 365-432) with:

```python
    def _find_related_notes(
        self,
        notes: Dict[str, NoteMetadata],
        max_related: int = 5,
        db: Optional[VaultDatabase] = None,
        semantic_vectors: Optional[Dict[str, List[float]]] = None,
    ) -> Dict[str, List[Tuple[str, float]]]:
        """Find related notes for each note in the collection."""
        print("\n2. Calculating tag frequencies...")

        # Try to get tag frequencies from database first
        tag_frequencies_dict = None
        if db:
            tag_frequencies_dict = self._get_tag_frequencies_from_database(db)

        if tag_frequencies_dict:
            # Use database frequencies
            print("   Using vault-wide tag frequencies from database")
            print(f"   Found {len(tag_frequencies_dict)} unique tags")
            # Convert to Counter for compatibility
            tag_frequencies = Counter(tag_frequencies_dict)
        else:
            # Fallback to computing frequencies from scanned notes
            print("   Computing tag frequencies from scanned notes")
            tag_frequencies = Counter()
            for note in notes.values():
                tag_frequencies.update(note.tags)
            print(f"   Found {len(tag_frequencies)} unique tags")

        print("\n3. Computing similarity scores...")

        path_to_index, similarity_matrix = self._build_semantic_similarity_lookup(semantic_vectors)

        related_notes = {}
        note_list = list(notes.items())
        total_comparisons = len(note_list) * (len(note_list) - 1) // 2
        comparisons_done = 0

        for i, (path1, note1) in enumerate(note_list):
            scores = []

            for j in range(i + 1, len(note_list)):
                path2, note2 = note_list[j]

                semantic_score = None
                if path1 in path_to_index and path2 in path_to_index:
                    semantic_score = max(
                        0.0,
                        float(similarity_matrix[path_to_index[path1], path_to_index[path2]]),
                    )

                score = self._calculate_similarity_score(note1, note2, tag_frequencies, semantic_score)

                if score > 0.01:
                    scores.append((path2, score))

                    if path2 not in related_notes:
                        related_notes[path2] = []
                    related_notes[path2].append((path1, score))

                comparisons_done += 1

            if scores:
                scores.sort(key=lambda x: x[1], reverse=True)
                related_notes[path1] = scores[:max_related]

            if (i + 1) % 50 == 0:
                progress = (comparisons_done / total_comparisons) * 100
                print(f"   Progress: {i + 1}/{len(note_list)} notes ({progress:.1f}%)")

        # Sort and trim all related lists
        for path in related_notes:
            related_notes[path].sort(key=lambda x: x[1], reverse=True)
            related_notes[path] = related_notes[path][:max_related]

        print(f"   Completed {comparisons_done:,} comparisons")

        return related_notes
```

(This is a whitespace-equivalent replacement except for the two new lines building `path_to_index`/`similarity_matrix` and the `semantic_score` lookup + pass-through inside the inner loop — the rest of the method is unchanged from today.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_relate_semantic.py -v`
Expected: PASS (all tests so far)

- [ ] **Step 5: Commit**

```bash
git add vault_manager/properties/commands/relate.py tests/unit/test_relate_semantic.py
git commit -m "feat: compute pairwise cosine similarity and thread it into relate scoring"
```

---

### Task 7: Wire semantic embeddings into note scanning

**Files:**
- Modify: `vault_manager/properties/commands/relate.py:215-264` (`_scan_notes_for_metadata`)
- Test: `tests/unit/test_relate_semantic.py` (append)

**Interfaces:**
- Consumes: `NoteMetadata.is_sensitive`/`embedding_text` (Task 3), `_prepare_embedding_text` (Task 3).
- Produces: `_scan_notes_for_metadata` now populates `note.is_sensitive` and `note.embedding_text` for every scanned note.

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_relate_semantic.py`:

```python
class TestScanNotesPopulatesEmbeddingFields:
    def test_embedding_text_and_sensitivity_are_populated(self, tmp_path):
        note_path = tmp_path / "note.md"
        note_path.write_text(
            "---\ntags: [test]\n---\n# Heading\n\nSome **bold** content here.\n",
            encoding="utf-8",
        )
        sensitive_path = tmp_path / "secret.md"
        sensitive_path.write_text(
            "---\ntags: [test]\nsensitive: true\n---\n\nHidden content.\n",
            encoding="utf-8",
        )

        cmd = RelateCommand()
        notes = cmd._scan_notes_for_metadata(tmp_path, tmp_path)

        assert notes["note.md"].is_sensitive is False
        assert "bold" in notes["note.md"].embedding_text
        assert "**" not in notes["note.md"].embedding_text

        assert notes["secret.md"].is_sensitive is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_relate_semantic.py::TestScanNotesPopulatesEmbeddingFields -v`
Expected: FAIL with `AssertionError` (fields are still defaults, since scanning doesn't populate them yet)

- [ ] **Step 3: Populate the new fields during scanning**

In `_scan_notes_for_metadata`, inside the `try` block, after the existing line:

```python
                note.has_related = self._check_has_related_property(frontmatter)
```

add:

```python
                note.is_sensitive = FrontmatterManager.is_sensitive_note(content)
                note.embedding_text = self._prepare_embedding_text(body)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_relate_semantic.py -v`
Expected: PASS (all tests so far)

- [ ] **Step 5: Commit**

```bash
git add vault_manager/properties/commands/relate.py tests/unit/test_relate_semantic.py
git commit -m "feat: populate embedding text and sensitivity during note scanning"
```

---

### Task 8: End-to-end wiring in `execute()` and acceptance test

**Files:**
- Modify: `vault_manager/properties/commands/relate.py:63-152` (`execute`)
- Test: `tests/unit/test_relate_semantic.py` (append)

**Interfaces:**
- Consumes: everything from Tasks 3-7.
- Produces: `vault properties enrich related` auto-detects `OPENROUTER_API_KEY`, computes semantic embeddings, and blends them into scoring end-to-end.

- [ ] **Step 1: Write the failing acceptance test**

Append to `tests/unit/test_relate_semantic.py`:

```python
from argparse import Namespace

from vault_manager.core.database import VaultDatabase


class TestRelateCommandEndToEndSemantic:
    def test_semantically_similar_notes_get_related_with_no_shared_tags_or_links(
        self, tmp_path, monkeypatch
    ):
        vault_path = tmp_path
        (vault_path / "machine_learning.md").write_text(
            "---\ntags: [ml-topic]\n---\n\nDiscussion of neural network training.\n",
            encoding="utf-8",
        )
        (vault_path / "cooking.md").write_text(
            "---\ntags: [recipe-topic]\n---\n\nA recipe for baking bread.\n",
            encoding="utf-8",
        )
        (vault_path / "deep_learning.md").write_text(
            "---\ntags: [dl-topic]\n---\n\nMore on neural network training approaches.\n",
            encoding="utf-8",
        )

        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

        # ml/deep_learning get near-identical vectors; cooking is orthogonal.
        vectors_by_text = {
            "Discussion of neural network training.\n": [1.0, 0.0],
            "A recipe for baking bread.\n": [0.0, 1.0],
            "More on neural network training approaches.\n": [0.99, 0.01],
        }

        def fake_embed_texts(texts, model, api_key):
            return [vectors_by_text[text] for text in texts]

        # execute() calls `db = VaultDatabase()` with no args, which internally
        # resolves the vault root via get_vault_root(). Patching VaultDatabase's
        # constructor to always return a fixed instance is the simplest way to
        # point it at our temp vault.
        with patch(
            "vault_manager.properties.commands.relate.VaultDatabase",
            return_value=VaultDatabase(vault_root=vault_path),
        ), patch(
            "vault_manager.properties.commands.relate.embed_texts",
            side_effect=fake_embed_texts,
        ):
            cmd = RelateCommand()
            args = Namespace(path=".", dry_run=False, overwrite=False, max_related=5)
            cmd.execute(args)

        ml_content = (vault_path / "machine_learning.md").read_text(encoding="utf-8")
        assert "deep_learning" in ml_content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_relate_semantic.py::TestRelateCommandEndToEndSemantic -v`
Expected: FAIL with an assertion error (`"deep_learning" not in ml_content`), since `execute()` doesn't compute semantic embeddings yet.

- [ ] **Step 3: Wire semantic computation into `execute()`**

In `execute()`, after the line:

```python
        # Scan notes
        notes = self._scan_notes_for_metadata(
            target_dir, vault_root, target_path if is_single_file else None
        )
```

add:

```python
        # Compute semantic embeddings if OpenRouter is configured
        api_key = self._get_openrouter_api_key()
        semantic_vectors: Optional[Dict[str, List[float]]] = None
        if api_key and HAS_NUMPY:
            model = self._get_embedding_model()
            print(f"\nSemantic scoring: Enabled (model: {model})")
            semantic_vectors = self._compute_semantic_embeddings(notes, db, api_key, model)
        elif api_key and not HAS_NUMPY:
            print("\nSemantic scoring: Disabled (numpy not installed - run `pip install -e '.[ai]'`)")
        else:
            print("\nSemantic scoring: Disabled (set OPENROUTER_API_KEY to enable)")
```

And update the call to `_find_related_notes`:

```python
        # Find related notes
        related_map = self._find_related_notes(notes, args.max_related, db)
```

to:

```python
        # Find related notes
        related_map = self._find_related_notes(notes, args.max_related, db, semantic_vectors)
```

- [ ] **Step 4: Run the acceptance test again**

Run: `pytest tests/unit/test_relate_semantic.py::TestRelateCommandEndToEndSemantic -v`
Expected: PASS

- [ ] **Step 5: Run the full test suite**

Run: `pytest tests/ -v`
Expected: PASS (all tests, no regressions in other properties/tags/images/index tests)

- [ ] **Step 6: Commit**

```bash
git add vault_manager/properties/commands/relate.py tests/unit/test_relate_semantic.py
git commit -m "feat: enable semantic relatedness end-to-end when OPENROUTER_API_KEY is set"
```

---

## Plan Self-Review Notes

- **Spec coverage:** OpenRouter client (Task 2), model default + env override (Task 4), embedding text prep (Task 3), cache table + invalidation (Task 4), rebalanced weights (Task 5), cosine similarity (Task 6), sensitive-note skip (Task 3/4), per-batch failure fallback (Task 4), auto-enable via env var + header notice (Task 8), numpy dependency (Task 1). All spec sections are covered.
- **Out of scope confirmed:** no new CLI flag, no non-OpenRouter providers, no backfill command — matches the spec's "Out of Scope" section.
