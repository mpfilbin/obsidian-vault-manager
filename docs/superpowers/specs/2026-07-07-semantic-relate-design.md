# Semantic Relatedness for `vault properties relate`

**Date:** 2026-07-07
**Status:** Approved for planning

## Problem

`vault properties relate` (`vault_manager/properties/commands/relate.py`) currently finds related notes using a purely structural/lexical hybrid score:

- Tag similarity (IDF-weighted Jaccard overlap): 40%
- Link proximity (direct + shared wiki-links): 30%
- Folder proximity: 15%
- Title word overlap: 15%

This misses notes that discuss the same ideas but don't share tags, links, folder, or title wording — i.e. it has no understanding of what a note actually *means*. The goal of this feature is to add semantic similarity, based on embeddings of note content, as a first-class signal.

## Approach

Generate text embeddings for note content via OpenRouter's OpenAI-compatible embeddings endpoint, cache them in `vault.db`, and blend cosine similarity between note embeddings into the existing weighted similarity score.

### Why OpenRouter

Anthropic does not offer an embeddings API. OpenRouter exposes an OpenAI-compatible embeddings endpoint (`POST https://openrouter.ai/api/v1/embeddings`) that proxies multiple providers' embedding models (OpenAI, Cohere, Google, Mistral, etc.) behind one API key, and the user already has an OpenRouter account. This avoids introducing a second new provider/dependency beyond what's needed.

### Default model

`openai/text-embedding-3-small` via OpenRouter — cheap (~$0.02/1M tokens), fast, 1536 dimensions, sufficient semantic quality for note-length text. Configurable via `OPENROUTER_EMBEDDING_MODEL` env var if a higher-quality model (e.g. `openai/text-embedding-3-large`) is wanted later.

## Architecture

### New module: `vault_manager/core/embeddings.py`

Thin OpenRouter client using stdlib `urllib.request` (no new HTTP dependency, consistent with the project's minimal-dependency approach):

```python
def embed_texts(texts: list[str], model: str, api_key: str) -> list[list[float]]:
    """Call OpenRouter embeddings endpoint, batching requests. Returns one vector per input text, in order."""
```

- Batches requests (e.g. 50 texts/request) to reduce round trips while respecting the model's context window.
- Retries a failed batch once (simple immediate retry, no backoff) before giving up; raises a dedicated `EmbeddingError` on final failure. Callers decide fallback behavior (see Error Handling).

### New dependency: `numpy`

Added to the `ai` optional-dependency group in `pyproject.toml`. Used for vectorized cosine similarity across all note-pair embeddings — avoids an O(n²) pure-Python inner loop once vaults reach hundreds of notes. `numpy` is only imported when the semantic path is active (API key present); its absence degrades gracefully to structural-only scoring with a printed notice.

### New database table: `note_embeddings`

```sql
CREATE TABLE IF NOT EXISTS note_embeddings (
    file_path TEXT PRIMARY KEY,
    content_hash TEXT NOT NULL,
    model TEXT NOT NULL,
    vector BLOB NOT NULL,
    created_at TEXT NOT NULL
)
```

- `content_hash`: SHA-256 of the stripped-markdown, truncated note body that was actually embedded (distinct from `files.content_hash`, which hashes the whole file for index-freshness purposes).
- `vector`: packed floats (`array('f', values).tobytes()`), decoded back to a numpy array on read.
- Keyed by `file_path` (not a foreign key to `files`, since `relate` can run before `vault index build` has populated `files`).
- Table is created lazily by the `relate` command itself (via `VaultDatabase`) if it doesn't exist yet — it doesn't require `vault index build` to have run first.

## Data Flow

1. `_scan_notes_for_metadata` scans notes as today, and additionally reads/strips the note body (markdown formatting removed, similar to `summarize.py`'s `_strip_markdown`) and truncates it to ~6000 characters (roughly 1500 tokens — comfortably under the model's context window while keeping cost and latency low).
2. **If `OPENROUTER_API_KEY` is set:**
   a. For each non-sensitive note (`sensitive: true` in frontmatter is skipped, consistent with `summarize`/`enrich`), compute `content_hash = sha256(stripped_truncated_body)`.
   b. Look up `note_embeddings` by `file_path`. If `content_hash` and `model` both match the current run's config, reuse the cached vector. Otherwise, queue the note's text for (re-)embedding.
   c. Call `embed_texts` in batches for all queued notes; upsert results into `note_embeddings` with the new `content_hash`, `model`, and `created_at`.
   d. Build an in-memory matrix of all notes' vectors (cached + freshly embedded) and compute pairwise cosine similarity with numpy in one vectorized pass.
3. **If `OPENROUTER_API_KEY` is not set,** or `numpy` is not installed: print a notice, skip the semantic path entirely, and use the original (pre-existing) weights for every note.
4. `_calculate_similarity_score` is rebalanced when semantic scores are available:
   - Semantic: 40%
   - Tag: 25%
   - Link: 20%
   - Folder: 7.5%
   - Title: 7.5%

   Title remains as a minor tiebreaker since it's now largely redundant with semantic similarity, but isn't worth removing entirely (cheap, occasionally catches exact-name matches semantics might not weight highly).
5. **Per-note fallback:** if a specific note's embedding call fails (after batching/retries within `embed_texts`), log a warning, do not cache anything for that note, and score its pairwise comparisons using the *original* weights (tag 40/link 30/folder 15/title 15) instead of the rebalanced ones. This is decided per-note, not globally — one flaky API call doesn't degrade the whole run.
6. Rest of the pipeline (`_find_related_notes`, `_update_files_with_related`, frontmatter writing) is unchanged.

## CLI / Config

- No new flag. `vault properties relate` auto-detects `OPENROUTER_API_KEY` and enables semantic scoring when present, matching the existing pattern where `summarize`/`enrich` auto-detect `ANTHROPIC_API_KEY`.
- New env vars:
  - `OPENROUTER_API_KEY` — required to enable semantic scoring.
  - `OPENROUTER_EMBEDDING_MODEL` — optional, defaults to `openai/text-embedding-3-small`.
- The header block printed at the top of `execute()` gains a line indicating whether semantic scoring is active, matching the existing "Tag database: Found/Not found" line style.

## Error Handling

- **No API key / no numpy:** feature disabled for the run, structural-only scoring, printed notice. Command remains fully functional.
- **API call failure for a batch:** warning logged, affected notes fall back to original per-note weighting (see Data Flow step 5). No partial/corrupt cache entries are written.
- **Cache invalidation:** automatic via content hash — editing a note's body invalidates its cached embedding on the next run; editing only frontmatter/tags does not (since the hash is computed on stripped body text only).

## Testing

- Unit tests for `vault_manager/core/embeddings.py`: request batching, response parsing, error propagation (mocked HTTP, no real API calls in tests).
- Unit tests for cache logic in `relate.py`: hash match → reuse; hash mismatch → re-embed; model change → re-embed; missing entry → embed.
- Unit tests for rebalanced scoring: weights sum correctly with and without semantic component; per-note fallback uses original weights.
- Extend existing `relate` BDD fixtures with a case where two notes share no tags/links/folder/title-words but have similar embeddings (mocked), asserting they still get related.

## Out of Scope

- No UI/interactive model picker — model is env-var configured only.
- No support for non-OpenRouter embedding providers in this iteration.
- No re-embedding backfill command — embeddings are computed lazily as `relate` is run over notes.
