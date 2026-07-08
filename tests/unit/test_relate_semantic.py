"""
Unit tests for semantic (embedding-based) relatedness in the relate command.

Covers markdown stripping/truncation for embedding text, content hashing
for cache invalidation, the embedding cache itself, rebalanced scoring
weights, and the end-to-end acceptance case where two notes with no
structural overlap are still related via semantic similarity.
"""

from collections import Counter
from unittest.mock import patch

import pytest

from vault_manager.core.database import VaultDatabase
from vault_manager.core.embeddings import EmbeddingError, pack_vector
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

    def test_strips_mixed_wiki_link_and_markdown_link_without_corruption(self):
        cmd = RelateCommand()
        text = "See [[Wiki|display]] and then a [link](url) after."

        result = cmd._strip_markdown_for_embedding(text)

        assert result == "See display and then a link after."


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
        assert rows == [
            ("a.md", "openai/text-embedding-3-small"),
            ("b.md", "openai/text-embedding-3-small"),
        ]

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
                (
                    "a.md",
                    content_hash,
                    "openai/text-embedding-3-small",
                    pack_vector([9.0, 9.0]),
                    "2026-01-01T00:00:00",
                ),
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
                (
                    "a.md",
                    "stale-hash",
                    "openai/text-embedding-3-small",
                    pack_vector([9.0, 9.0]),
                    "2026-01-01T00:00:00",
                ),
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

    def _notes_with_folder_overlap_only(self, tmp_path):
        # Parent/child folders give folder_score = 0.5 via _calculate_folder_similarity.
        # Tags/links/title are empty/disjoint so those components are 0.
        note1 = NoteMetadata(tmp_path / "a.md", "a.md")
        note1.folder = "Parent"

        note2 = NoteMetadata(tmp_path / "b.md", "b.md")
        note2.folder = "Parent/Child"

        return note1, note2

    def test_rebalanced_folder_weight_with_semantic_score(self, tmp_path):
        cmd = RelateCommand()
        note1, note2 = self._notes_with_folder_overlap_only(tmp_path)

        score = cmd._calculate_similarity_score(note1, note2, Counter(), semantic_score=0.5)

        # semantic 0.5*0.40 + folder 0.5*0.075 (tag/link/title all 0)
        assert score == pytest.approx(0.5 * 0.40 + 0.5 * 0.075, abs=1e-6)

    def test_rebalanced_folder_weight_without_semantic_score(self, tmp_path):
        cmd = RelateCommand()
        note1, note2 = self._notes_with_folder_overlap_only(tmp_path)

        score = cmd._calculate_similarity_score(note1, note2, Counter(), semantic_score=None)

        # folder 0.5*0.15 (tag/link/title all 0, no semantic term at all)
        assert score == pytest.approx(0.5 * 0.15, abs=1e-6)
