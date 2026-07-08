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


from argparse import Namespace


class TestRelateCommandEndToEndSemantic:
    def test_semantically_similar_notes_get_related_with_no_shared_tags_folders_or_titles(
        self, tmp_path, monkeypatch
    ):
        # Three sibling folders (not nested in each other) so
        # _calculate_folder_similarity is exactly 0 for every pair.
        vault_path = tmp_path
        (vault_path / "TopicA").mkdir()
        (vault_path / "TopicB").mkdir()
        (vault_path / "TopicC").mkdir()

        # Filenames share no title words across any pair (unlike the previous
        # "machine_learning"/"deep_learning" pairing, which both contain
        # "learning" and would clear the threshold via title similarity alone),
        # so _calculate_title_similarity is also exactly 0 for every pair.
        (vault_path / "TopicA" / "neural_networks.md").write_text(
            "---\ntags: [ml-topic]\n---\n\nDiscussion of neural network training.\n",
            encoding="utf-8",
        )
        (vault_path / "TopicB" / "sourdough_bread.md").write_text(
            "---\ntags: [recipe-topic]\n---\n\nA recipe for baking bread.\n",
            encoding="utf-8",
        )
        (vault_path / "TopicC" / "gradient_descent.md").write_text(
            "---\ntags: [dl-topic]\n---\n\nMore on neural network training approaches.\n",
            encoding="utf-8",
        )

        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

        # neural_networks/gradient_descent get near-identical vectors (cosine
        # similarity ~0.9999); sourdough_bread is orthogonal to neural_networks
        # (cosine similarity exactly 0.0). Tags are distinct, folders are
        # distinct siblings, and title words share nothing across any pair, so
        # with tag/link/folder/title components all pinned at 0.0, the ONLY
        # way a pair can clear the `> 0.01` inclusion threshold in
        # _find_related_notes is via the semantic component - which only
        # exists if execute() actually calls _compute_semantic_embeddings and
        # threads the result into _find_related_notes.
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

        nn_content = (vault_path / "TopicA" / "neural_networks.md").read_text(encoding="utf-8")
        # gradient_descent: semantic cosine ~0.9999 * 0.40 weight ~= 0.40, well above 0.01.
        assert "gradient_descent" in nn_content
        # sourdough_bread: semantic cosine == 0.0 (orthogonal vectors) * 0.40 weight == 0.0,
        # below the 0.01 threshold, and no structural component can push it over
        # since tags/folders/titles share nothing with neural_networks.
        assert "sourdough_bread" not in nn_content
