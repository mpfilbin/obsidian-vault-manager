"""
Relate command - Find related notes based on similarity.

This module implements the relate command which analyzes notes using a hybrid
similarity algorithm and adds related property with wiki-links to similar notes.
"""

import os
import re
import sqlite3
import sys
from argparse import ArgumentParser, Namespace
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from . import Command
from ..common import get_vault_root, extract_frontmatter
from vault_manager.index.common import get_database_path
from vault_manager.core.vault import iter_markdown_files, count_markdown_files


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


class RelateCommand(Command):
    """Command to analyze and add related note links based on similarity."""

    @staticmethod
    def configure_parser(parser: ArgumentParser) -> None:
        """Configure the argument parser for the relate command."""
        parser.add_argument(
            'path',
            help='File or directory to process (relative to vault root, use "." for entire vault)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview changes without modifying files'
        )
        parser.add_argument(
            '--overwrite',
            action='store_true',
            help='Replace existing related properties'
        )
        parser.add_argument(
            '--max-related',
            type=int,
            default=5,
            help='Maximum related notes to add per file (default: 5)'
        )

    def execute(self, args: Namespace) -> None:
        """Execute the relate command to find and add related notes."""
        # Get vault root
        vault_root = get_vault_root()

        # Resolve path (file or directory)
        if args.path == '.':
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
            if not target_path.suffix == '.md' or target_path.name.endswith('.excalidraw.md'):
                print(f"Error: Not a valid markdown file: {args.path}")
                print(f"File must have .md extension and not be an Excalidraw file")
                sys.exit(1)
            target_dir = target_path.parent
        else:
            target_dir = target_path

        # Check for database
        db_path = get_database_path()
        has_database = db_path.exists()

        # Display header
        print("=" * 60)
        print("Find and Add Related Notes")
        print("=" * 60)
        print(f"Vault root: {vault_root}")
        if is_single_file:
            print(f"Target file: {target_path.relative_to(vault_root)}")
        else:
            print(f"Target directory: {target_dir.relative_to(vault_root) if target_dir != vault_root else '.'}")
        print(f"Mode: {'DRY RUN (preview only)' if args.dry_run else 'MODIFY FILES'}")
        print(f"Overwrite: {'Yes' if args.overwrite else 'No (skip files with related)'}")
        print(f"Max related notes: {args.max_related}")
        print(f"Tag database: {'Found - using vault-wide frequencies' if has_database else 'Not found - will compute from scanned notes'}")
        if not is_single_file:
            print(f"Ignored directories: .obsidian, .trash, Excalidraw, Calendar")

        # Scan notes
        notes = self._scan_notes_for_metadata(target_dir, vault_root, target_path if is_single_file else None)

        # Find related notes
        related_map = self._find_related_notes(notes, args.max_related, vault_root)

        # Update files (filter to single file if needed)
        if is_single_file:
            target_file_relative = str(target_path.relative_to(vault_root))
            notes_to_update = {k: v for k, v in notes.items() if k == target_file_relative}
            stats = self._update_files_with_related(notes_to_update, related_map, vault_root, args.dry_run, args.overwrite)
        else:
            stats = self._update_files_with_related(notes, related_map, vault_root, args.dry_run, args.overwrite)

        # Print summary
        self._print_summary(stats, args.dry_run)

        if not args.dry_run and stats['processed'] > 0:
            print(f"\nDone! Updated {stats['processed']} file{'s' if stats['processed'] != 1 else ''}.")
        elif args.dry_run and stats['processed'] > 0:
            print(f"\nDry run complete. {stats['processed']} file{'s' if stats['processed'] != 1 else ''} would be updated.")
        else:
            print("\nNo files updated.")

    def _get_tag_frequencies_from_database(self, vault_root: Path) -> Optional[Dict[str, int]]:
        """
        Query the vault.db database for tag frequencies (3NF: compute file_count).

        Args:
            vault_root: Root directory of the vault

        Returns:
            Dictionary mapping tag names to file counts, or None if database doesn't exist
        """
        db_path = get_database_path()

        # If database doesn't exist, return None
        if not db_path.exists():
            return None

        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # 3NF: Compute file_count from file_tags table
            cursor.execute('''
                SELECT ft.tag, COUNT(*) as file_count
                FROM file_tags ft
                GROUP BY ft.tag
            ''')

            results = cursor.fetchall()
            conn.close()

            return {tag: count for tag, count in results}

        except sqlite3.Error:
            # If there's any database error, return None
            return None

    def _extract_tags_from_frontmatter(self, frontmatter: str) -> Set[str]:
        """Extract tags from YAML frontmatter."""
        tags = set()

        lines = frontmatter.split('\n')
        i = 0

        while i < len(lines):
            line = lines[i]

            if line.strip().startswith('tags:'):
                tags_value = line.split('tags:', 1)[1].strip()

                # Handle inline array format
                if tags_value.startswith('[') and tags_value.endswith(']'):
                    tags_str = tags_value[1:-1]
                    inline_tags = [t.strip().strip('"').strip("'") for t in tags_str.split(',')]
                    tags.update([t for t in inline_tags if t])
                    break

                # Check next lines for list items
                i += 1
                while i < len(lines):
                    next_line = lines[i].strip()

                    if next_line and not next_line.startswith('-') and ':' in next_line and not next_line.startswith(' '):
                        i -= 1
                        break

                    if next_line.startswith('-'):
                        tag = next_line[1:].strip().strip('"').strip("'")
                        if tag:
                            tags.add(tag)
                    elif not next_line:
                        pass
                    elif next_line.startswith(' '):
                        pass
                    else:
                        i -= 1
                        break

                    i += 1
                break

            i += 1

        return tags

    def _extract_wiki_links(self, content: str) -> Set[str]:
        """Extract wiki-links from markdown content."""
        links = set()

        # Pattern for wiki-links: [[link]] or [[link|display]]
        pattern = r'\[\[([^\]|]+)(?:\|[^\]]*)?\]\]'

        for match in re.finditer(pattern, content):
            link = match.group(1).strip()
            # Normalize link
            if link.endswith('.md'):
                link = link[:-3]
            links.add(link)

        return links

    def _extract_title_words(self, title: str) -> Set[str]:
        """Extract meaningful words from a title."""
        if title.endswith('.md'):
            title = title[:-3]

        words = set()
        for word in re.split(r'[\s\-_]+', title.lower()):
            if len(word) >= 3 and word not in {'the', 'and', 'for', 'with', 'from', 'into'}:
                words.add(word)

        return words

    def _check_has_related_property(self, frontmatter: str) -> bool:
        """Check if frontmatter has a 'related' property."""
        return bool(re.search(r'^related:', frontmatter, re.MULTILINE))

    def _scan_notes_for_metadata(self, directory: Path, vault_root: Path, single_file: Optional[Path] = None) -> Dict[str, NoteMetadata]:
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

        for file_path in iter_markdown_files(directory, vault_root, additional_ignores={'Excalidraw', 'Calendar'}, exclude_excalidraw=True):
            relative_path = str(file_path.relative_to(vault_root))

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                frontmatter, body = extract_frontmatter(content)

                if frontmatter is None:
                    continue

                note = NoteMetadata(file_path, relative_path)
                note.tags = self._extract_tags_from_frontmatter(frontmatter)
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

    def _calculate_tag_similarity(self, note1: NoteMetadata, note2: NoteMetadata,
                                  tag_frequencies: Dict[str, int]) -> float:
        """Calculate tag similarity score with IDF-like weighting for rare tags."""
        if not note1.tags or not note2.tags:
            return 0.0

        common_tags = note1.tags & note2.tags
        all_tags = note1.tags | note2.tags

        if not common_tags:
            return 0.0

        # Weight common tags by inverse frequency
        total_notes = sum(tag_frequencies.values())
        weighted_common = sum(1.0 / tag_frequencies.get(tag, 1) for tag in common_tags)
        weighted_all = sum(1.0 / tag_frequencies.get(tag, 1) for tag in all_tags)

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

        folder1_parts = note1.folder.split(os.sep) if note1.folder != '.' else []
        folder2_parts = note2.folder.split(os.sep) if note2.folder != '.' else []

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

    def _calculate_similarity_score(self, note1: NoteMetadata, note2: NoteMetadata,
                                    tag_frequencies: Dict[str, int]) -> float:
        """
        Calculate overall similarity score using weighted components.

        Weights: Tag (40%), Link (30%), Folder (15%), Title (15%)
        """
        tag_score = self._calculate_tag_similarity(note1, note2, tag_frequencies)
        link_score = self._calculate_link_similarity(note1, note2)
        folder_score = self._calculate_folder_similarity(note1, note2)
        title_score = self._calculate_title_similarity(note1, note2)

        return (
            tag_score * 0.40 +
            link_score * 0.30 +
            folder_score * 0.15 +
            title_score * 0.15
        )

    def _find_related_notes(self, notes: Dict[str, NoteMetadata], max_related: int = 5, vault_root: Optional[Path] = None) -> Dict[str, List[Tuple[str, float]]]:
        """Find related notes for each note in the collection."""
        print("\n2. Calculating tag frequencies...")

        # Try to get tag frequencies from database first
        tag_frequencies_dict = None
        if vault_root:
            tag_frequencies_dict = self._get_tag_frequencies_from_database(vault_root)

        if tag_frequencies_dict:
            # Use database frequencies
            print(f"   Using vault-wide tag frequencies from database")
            print(f"   Found {len(tag_frequencies_dict)} unique tags")
            # Convert to Counter for compatibility
            tag_frequencies = Counter(tag_frequencies_dict)
        else:
            # Fallback to computing frequencies from scanned notes
            print(f"   Computing tag frequencies from scanned notes")
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

    def _add_related_to_frontmatter(self, frontmatter: str, related_notes: List[str], overwrite: bool = False) -> str:
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
                if 'related' in frontmatter_dict:
                    del frontmatter_dict['related']
                # Convert back to YAML
                frontmatter = yaml.dump(frontmatter_dict, default_flow_style=False, allow_unicode=True, sort_keys=False)
                frontmatter = frontmatter.rstrip('\n')
            except yaml.YAMLError:
                # If YAML parsing fails, fall back to simple append
                pass

        related_yaml = "related:\n" + "\n".join(f"  - \"[[{note}]]\"" for note in related_notes)
        return f'{frontmatter}\n{related_yaml}'

    def _update_file_with_related(self, file_path: Path, related_paths: List[str],
                                  vault_root: Path, dry_run: bool = False, overwrite: bool = False) -> bool:
        """Update a file with related notes in its frontmatter."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
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

            updated_frontmatter = self._add_related_to_frontmatter(frontmatter, related_notes, overwrite)
            updated_content = f"---\n{updated_frontmatter}\n---\n{body}"

            if not dry_run:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(updated_content)

            return True

        except Exception as e:
            print(f"  Error updating {file_path}: {e}")
            return False

    def _update_files_with_related(self, notes: Dict[str, NoteMetadata],
                                   related_map: Dict[str, List[Tuple[str, float]]],
                                   vault_root: Path, dry_run: bool, overwrite: bool) -> Dict:
        """Update files with related notes."""
        stats = {
            'total_notes': len(notes),
            'notes_with_relations': len(related_map),
            'processed': 0,
            'skipped_has_related': 0,
            'skipped_no_relations': 0,
            'failed': 0
        }

        print(f"\n4. {'Would update' if dry_run else 'Updating'} files with related notes...")

        for path, note in notes.items():
            if path not in related_map:
                stats['skipped_no_relations'] += 1
                continue

            if note.has_related and not overwrite:
                print(f"  Skipping (has related): {path}")
                stats['skipped_has_related'] += 1
                continue

            related_paths = [r[0] for r in related_map[path]]

            if self._update_file_with_related(note.path, related_paths, vault_root, dry_run, overwrite):
                stats['processed'] += 1
                mode = "Would add" if dry_run else "Added"
                print(f"  {mode} related to: {path}")
                for rel_path, score in related_map[path]:
                    print(f"    - {rel_path} (score: {score:.3f})")
            else:
                stats['failed'] += 1

        return stats

    def _print_summary(self, stats: Dict, dry_run: bool = False) -> None:
        """Print summary of processing results."""
        print("\n" + "=" * 60)
        print(f"{'DRY RUN ' if dry_run else ''}SUMMARY")
        print("=" * 60)
        print(f"Total notes scanned: {stats['total_notes']}")
        print(f"Notes with relations found: {stats['notes_with_relations']}")
        print(f"Files updated: {stats['processed']}")
        print(f"Skipped (has related): {stats['skipped_has_related']}")
        print(f"Skipped (no relations): {stats['skipped_no_relations']}")
        print(f"Failed: {stats['failed']}")

        if dry_run and stats['processed'] > 0:
            print("\n" + "=" * 60)
            print("This was a DRY RUN - no files were actually modified.")
            print("Run without --dry-run to apply changes.")
            print("=" * 60)
