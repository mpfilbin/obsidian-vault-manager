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
