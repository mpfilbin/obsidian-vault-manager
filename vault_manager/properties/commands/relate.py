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


class RelateCommand(Command):
    """Command to analyze and add related note links based on similarity."""

    @staticmethod
    def configure_parser(parser: ArgumentParser) -> None:
        """Configure the argument parser for the relate command."""
        parser.add_argument(
            "path",
            help='File or directory to process (relative to vault root, use "." for entire vault)',
        )
        parser.add_argument(
            "--dry-run", action="store_true", help="Preview changes without modifying files"
        )
        parser.add_argument(
            "--overwrite", action="store_true", help="Replace existing related properties"
        )
        parser.add_argument(
            "--max-related",
            type=int,
            default=5,
            help="Maximum related notes to add per file (default: 5)",
        )

    def execute(self, args: Namespace) -> None:
        """Execute the relate command to find and add related notes."""
        # Get vault database instance
        db = VaultDatabase()
        vault_root = db.vault_root

        # Resolve path (file or directory)
        if args.path == ".":
            target_path = vault_root
        else:
            target_path = vault_root / args.path

        # Validate path exists
        if not target_path.exists():
            print(f"Error: Path not found: {args.path}")
            print(f"Looking for: {target_path}")
            sys.exit(1)

        # Determine if it's a file or directory
        is_single_file = target_path.is_file()

        if is_single_file:
            # Validate it's a markdown file
            if not target_path.suffix == ".md" or target_path.name.endswith(".excalidraw.md"):
                print(f"Error: Not a valid markdown file: {args.path}")
                print("File must have .md extension and not be an Excalidraw file")
                sys.exit(1)
            target_dir = target_path.parent
        else:
            target_dir = target_path

        # Check for database
        has_database = db.exists()

        # Display header
        print("=" * 60)
        print("Find and Add Related Notes")
        print("=" * 60)
        print(f"Vault root: {vault_root}")
        if is_single_file:
            print(f"Target file: {target_path.relative_to(vault_root)}")
        else:
            print(
                f"Target directory: {target_dir.relative_to(vault_root) if target_dir != vault_root else '.'}"
            )
        print(f"Mode: {'DRY RUN (preview only)' if args.dry_run else 'MODIFY FILES'}")
        print(f"Overwrite: {'Yes' if args.overwrite else 'No (skip files with related)'}")
        print(f"Max related notes: {args.max_related}")
        print(
            f"Tag database: {'Found - using vault-wide frequencies' if has_database else 'Not found - will compute from scanned notes'}"
        )
        if not is_single_file:
            print("Ignored directories: .obsidian, .trash, Excalidraw, Calendar")

        # Scan notes
        notes = self._scan_notes_for_metadata(
            target_dir, vault_root, target_path if is_single_file else None
        )

        # Find related notes
        related_map = self._find_related_notes(notes, args.max_related, db)

        # Update files (filter to single file if needed)
        with DryRunContext(args.dry_run) as ctx:
            ctx.stats.custom_stats["total_notes"] = len(notes)
            ctx.stats.custom_stats["notes_with_relations"] = len(related_map)

            if is_single_file:
                target_file_relative = str(target_path.relative_to(vault_root))
                notes_to_update = {k: v for k, v in notes.items() if k == target_file_relative}
                self._update_files_with_related(
                    notes_to_update, related_map, vault_root, ctx, args.overwrite
                )
            else:
                self._update_files_with_related(notes, related_map, vault_root, ctx, args.overwrite)

            # Print summary
            self._print_custom_summary(ctx)
            print_dry_run_summary(ctx)

            if not args.dry_run and ctx.stats.files_processed > 0:
                print(
                    f"\nDone! Updated {ctx.stats.files_processed} file{'s' if ctx.stats.files_processed != 1 else ''}."
                )
            elif args.dry_run and ctx.stats.files_processed > 0:
                print(
                    f"\nDry run complete. {ctx.stats.files_processed} file{'s' if ctx.stats.files_processed != 1 else ''} would be updated."
                )
            else:
                print("\nNo files updated.")

    def _get_tag_frequencies_from_database(self, db: VaultDatabase) -> Optional[Dict[str, int]]:
        """
        Query the vault.db database for tag frequencies (3NF: compute file_count).

        Args:
            db: VaultDatabase instance

        Returns:
            Dictionary mapping tag names to file counts, or None if database doesn't exist
        """
        # If database doesn't exist, return None
        if not db.exists():
            return None

        try:
            # 3NF: Compute file_count from file_tags table
            with db:
                results = db.query("""
                    SELECT ft.tag, COUNT(*) as file_count
                    FROM file_tags ft
                    GROUP BY ft.tag
                """)

            return {tag: count for tag, count in results}

        except Exception:
            # If there's any database error, return None
            return None

    def _extract_wiki_links(self, content: str) -> Set[str]:
        """Extract wiki-links from markdown content."""
        links = set()

        # Pattern for wiki-links: [[link]] or [[link|display]]
        pattern = r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]"

        for match in re.finditer(pattern, content):
            link = match.group(1).strip()
            # Normalize link
            if link.endswith(".md"):
                link = link[:-3]
            links.add(link)

        return links

    def _extract_title_words(self, title: str) -> Set[str]:
        """Extract meaningful words from a title."""
        if title.endswith(".md"):
            title = title[:-3]

        words = set()
        for word in re.split(r"[\s\-_]+", title.lower()):
            if len(word) >= 3 and word not in {"the", "and", "for", "with", "from", "into"}:
                words.add(word)

        return words

    def _check_has_related_property(self, frontmatter: str) -> bool:
        """Check if frontmatter has a 'related' property."""
        return bool(re.search(r"^related:", frontmatter, re.MULTILINE))

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

    def _scan_notes_for_metadata(
        self, directory: Path, vault_root: Path, single_file: Optional[Path] = None
    ) -> Dict[str, NoteMetadata]:
        """
        Scan all notes and extract metadata for similarity analysis.

        Args:
            directory: Directory to scan
            vault_root: Root of the vault
            single_file: If provided, indicates we're processing a single file (but still scan all notes for relationships)
        """
        notes = {}

        if single_file:
            print("\n1. Scanning vault for potential related notes...")
        else:
            print("\n1. Scanning notes and extracting metadata...")

        for file_path in iter_markdown_files(
            directory,
            vault_root,
            additional_ignores={"Excalidraw", "Calendar"},
            exclude_excalidraw=True,
        ):
            relative_path = str(file_path.relative_to(vault_root))

            try:
                with open(file_path, encoding="utf-8") as f:
                    content = f.read()

                frontmatter, body = extract_frontmatter(content)

                if frontmatter is None:
                    continue

                note = NoteMetadata(file_path, relative_path)
                note.tags = set(FrontmatterManager.extract_tags_from_frontmatter(content))
                note.links = self._extract_wiki_links(body)
                note.title = file_path.name
                note.title_words = self._extract_title_words(file_path.name)
                note.folder = str(file_path.parent.relative_to(vault_root))
                note.has_related = self._check_has_related_property(frontmatter)

                notes[relative_path] = note

            except Exception as e:
                print(f"  Warning: Could not read {relative_path}: {e}")

        print(f"   Found {len(notes)} notes with frontmatter")
        return notes

    def _calculate_tag_similarity(
        self, note1: NoteMetadata, note2: NoteMetadata, tag_frequencies: Dict[str, int]
    ) -> float:
        """Calculate tag similarity score with IDF weighting for rare tags.

        Uses proper IDF (Inverse Document Frequency) formula:
        IDF(tag) = log(total_notes / notes_with_tag)

        Rare tags (low frequency) receive higher weight than common tags.
        """
        if not note1.tags or not note2.tags:
            return 0.0

        common_tags = note1.tags & note2.tags
        all_tags = note1.tags | note2.tags

        if not common_tags:
            return 0.0

        # Weight tags by IDF: log(total_notes / tag_frequency)
        total_notes = sum(tag_frequencies.values())

        if total_notes == 0:
            return 0.0

        weighted_common = sum(
            math.log(total_notes / tag_frequencies.get(tag, 1)) for tag in common_tags
        )
        weighted_all = sum(math.log(total_notes / tag_frequencies.get(tag, 1)) for tag in all_tags)

        return weighted_common / weighted_all if weighted_all > 0 else 0.0

    def _calculate_link_similarity(self, note1: NoteMetadata, note2: NoteMetadata) -> float:
        """Calculate link proximity score (direct links and shared targets)."""
        score = 0.0

        # Direct link bonus
        note1_name = Path(note1.relative_path).stem
        note2_name = Path(note2.relative_path).stem

        if note2_name in note1.links or note1_name in note2.links:
            score += 0.5

        # Shared link targets
        if note1.links and note2.links:
            common_links = note1.links & note2.links
            all_links = note1.links | note2.links
            if common_links:
                score += 0.5 * (len(common_links) / len(all_links))

        return min(score, 1.0)

    def _calculate_folder_similarity(self, note1: NoteMetadata, note2: NoteMetadata) -> float:
        """Calculate folder proximity score."""
        if note1.folder == note2.folder:
            return 1.0

        folder1_parts = note1.folder.split(os.sep) if note1.folder != "." else []
        folder2_parts = note2.folder.split(os.sep) if note2.folder != "." else []

        if folder1_parts and folder2_parts:
            min_len = min(len(folder1_parts), len(folder2_parts))
            if folder1_parts[:min_len] == folder2_parts[:min_len]:
                depth_diff = abs(len(folder1_parts) - len(folder2_parts))
                if depth_diff == 1:
                    return 0.5  # Direct parent/child
                elif depth_diff == 2:
                    return 0.3  # Grandparent/grandchild

        return 0.0

    def _calculate_title_similarity(self, note1: NoteMetadata, note2: NoteMetadata) -> float:
        """Calculate title similarity based on shared meaningful words."""
        if not note1.title_words or not note2.title_words:
            return 0.0

        common_words = note1.title_words & note2.title_words
        all_words = note1.title_words | note2.title_words

        if not common_words:
            return 0.0

        return len(common_words) / len(all_words)

    def _calculate_similarity_score(
        self, note1: NoteMetadata, note2: NoteMetadata, tag_frequencies: Dict[str, int]
    ) -> float:
        """
        Calculate overall similarity score using weighted components.

        Weights: Tag (40%), Link (30%), Folder (15%), Title (15%)
        """
        tag_score = self._calculate_tag_similarity(note1, note2, tag_frequencies)
        link_score = self._calculate_link_similarity(note1, note2)
        folder_score = self._calculate_folder_similarity(note1, note2)
        title_score = self._calculate_title_similarity(note1, note2)

        return tag_score * 0.40 + link_score * 0.30 + folder_score * 0.15 + title_score * 0.15

    def _find_related_notes(
        self,
        notes: Dict[str, NoteMetadata],
        max_related: int = 5,
        db: Optional[VaultDatabase] = None,
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

        related_notes = {}
        note_list = list(notes.items())
        total_comparisons = len(note_list) * (len(note_list) - 1) // 2
        comparisons_done = 0

        for i, (path1, note1) in enumerate(note_list):
            scores = []

            for j in range(i + 1, len(note_list)):
                path2, note2 = note_list[j]

                score = self._calculate_similarity_score(note1, note2, tag_frequencies)

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

    def _add_related_to_frontmatter(
        self, frontmatter: str, related_notes: List[str], overwrite: bool = False
    ) -> str:
        """
        Add related field to YAML frontmatter.

        Args:
            frontmatter: Existing YAML frontmatter text
            related_notes: List of related note names to add
            overwrite: If True, remove existing 'related' property first

        Returns:
            Updated frontmatter with related notes
        """
        import yaml

        # If overwrite, parse YAML and remove existing 'related' field
        if overwrite:
            try:
                frontmatter_dict = yaml.safe_load(frontmatter) or {}
                # Remove existing 'related' field if present
                if "related" in frontmatter_dict:
                    del frontmatter_dict["related"]
                # Convert back to YAML
                frontmatter = yaml.dump(
                    frontmatter_dict, default_flow_style=False, allow_unicode=True, sort_keys=False
                )
                frontmatter = frontmatter.rstrip("\n")
            except yaml.YAMLError:
                # If YAML parsing fails, fall back to simple append
                pass

        related_yaml = "related:\n" + "\n".join(f'  - "[[{note}]]"' for note in related_notes)
        return f"{frontmatter}\n{related_yaml}"

    def _update_file_with_related(
        self,
        file_path: Path,
        related_paths: List[str],
        vault_root: Path,
        dry_run: bool = False,
        overwrite: bool = False,
    ) -> bool:
        """Update a file with related notes in its frontmatter."""
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            frontmatter, body = extract_frontmatter(content)

            if frontmatter is None:
                return False

            # Convert paths to note names (using just filename, not full path)
            related_notes = []
            for path in related_paths:
                note_path = Path(path)
                note_name = note_path.stem  # Just the filename without extension
                related_notes.append(note_name)

            updated_frontmatter = self._add_related_to_frontmatter(
                frontmatter, related_notes, overwrite
            )
            updated_content = f"---\n{updated_frontmatter}\n---\n{body}"

            if not dry_run:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(updated_content)

            return True

        except Exception as e:
            print(f"  Error updating {file_path}: {e}")
            return False

    def _update_files_with_related(
        self,
        notes: Dict[str, NoteMetadata],
        related_map: Dict[str, List[Tuple[str, float]]],
        vault_root: Path,
        ctx: DryRunContext,
        overwrite: bool,
    ) -> None:
        """Update files with related notes."""
        print(f"\n4. {'Would update' if ctx.dry_run else 'Updating'} files with related notes...")

        for path, note in notes.items():
            if path not in related_map:
                ctx.stats.increment("skipped_no_relations")
                continue

            if note.has_related and not overwrite:
                print(f"  Skipping (has related): {path}")
                ctx.stats.increment("skipped_has_related")
                continue

            related_paths = [r[0] for r in related_map[path]]

            if self._update_file_with_related(
                note.path, related_paths, vault_root, ctx.dry_run, overwrite
            ):
                ctx.stats.increment("files_processed")
                ctx.record_change(
                    note.path,
                    f"Added {len(related_paths)} related note(s)",
                    related_notes=related_paths,
                )
                mode = "Would add" if ctx.dry_run else "Added"
                print(f"  {mode} related to: {path}")
                for rel_path, score in related_map[path]:
                    print(f"    - {rel_path} (score: {score:.3f})")
            else:
                ctx.stats.increment("files_failed")

    def _print_custom_summary(self, ctx: DryRunContext) -> None:
        """Print custom summary of processing results."""
        print("\n" + "=" * 60)
        print("Related Notes Details")
        print("=" * 60)
        print(f"Total notes scanned: {ctx.stats.custom_stats.get('total_notes', 0)}")
        print(
            f"Notes with relations found: {ctx.stats.custom_stats.get('notes_with_relations', 0)}"
        )
        print(f"Skipped (has related): {ctx.stats.custom_stats.get('skipped_has_related', 0)}")
        print(f"Skipped (no relations): {ctx.stats.custom_stats.get('skipped_no_relations', 0)}")
