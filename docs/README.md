---
tags:
- scripts
- automation
- vault-management
---
# Library - Unified Vault Management Tools

This directory contains Python scripts for maintaining the Obsidian vault through a unified `vault` command-line interface.

## Installation

Install the Library package to enable the standalone `vault` command:

```bash
# From vault root directory
cd /mnt/c/Users/micha/Documents/Brain/Brain

# Install in development mode (recommended)
pip install -e .

# Install with AI features (for AI-powered tag generation and summaries)
pip install -e ".[ai]"
```

After installation, the `vault` command will be available system-wide.

## Testing

The Library includes comprehensive tests using pytest and pytest-bdd (Behavior-Driven Development).

### Install Test Dependencies

```bash
# Install with test dependencies only
pip install -e ".[test]"

# Install with all development dependencies (includes AI features and tests)
pip install -e ".[dev]"
```

### Run Tests

```bash
# Run all tests with coverage
pytest

# Run specific test types
pytest -m unit              # Unit tests only
pytest -m bdd               # BDD tests only
pytest -m tags              # Tag management tests
pytest -m images            # Image management tests

# Run with verbose output
pytest -v

# Generate HTML coverage report
pytest --cov=Library --cov-report=html
```

### Test Structure

```
Library/tests/
├── conftest.py              # Shared fixtures
├── features/                # BDD feature files (Gherkin)
├── step_defs/              # BDD step definitions
├── unit/                   # Traditional unit tests
└── README.md               # Detailed testing documentation
```

See `Library/tests/README.md` for comprehensive testing documentation, including:
- Writing BDD tests with Gherkin syntax
- Writing unit tests
- Using test fixtures
- Best practices and examples

## Usage

All vault management commands follow the pattern: `vault <domain> <command> [args]`

**Domains:**
- `vault tags` - Tag management and validation
- `vault images` - Image organization and cleanup
- `vault properties` - Frontmatter properties management
- `vault index` - Vault indexing and link resolution

**Examples:**
```bash
vault tags missing              # Find notes without tags
vault tags update               # Update vault index
vault images find               # Find orphaned images
vault properties validate       # Validate frontmatter
vault index build               # Build vault index
vault index broken-links        # Find broken wiki-links

# View help for any domain
vault tags --help
vault images --help
vault properties --help
vault index --help
```

## Package Structure

The Library package consists of four main domains:

```
Library/
├── __init__.py              # Package version metadata
├── __main__.py              # Entry point for python -m Library
├── cli.py                   # Unified CLI dispatcher
├── core/                    # Shared utilities
│   ├── database.py          # Database rebuild and query utilities
│   ├── frontmatter.py       # YAML frontmatter parsing
│   ├── vault.py             # Vault path resolution and file scanning
│   └── file_scanner.py      # File scanning utilities
├── tags/                    # Tag management
├── images/                  # Image management
├── properties/              # Frontmatter properties
└── index/                   # Vault indexing
```

## Scripts

### Tag Management Package (`Library/tags/`)

A modular tag management system using the command pattern and argparse for CLI argument parsing.

**Architecture:**
- **Command Pattern:** Each command (missing, update, add, clean, query) is implemented as a separate module
- **Modular Structure:** Code organized into focused, maintainable modules
- **Argparse CLI:** Professional command-line interface with subcommands and help text
- **Unified CLI:** Accessed through `vault tags <command>` via the main vault dispatcher

**Package Structure:**
```
Library/tags/
├── __init__.py           # Package metadata
├── cli.py                # CLI dispatcher with argparse
├── common.py             # Shared utilities
└── commands/
    ├── __init__.py       # Command base class
    ├── missing.py        # Missing tags command (was: tagless)
    ├── tags_inventory.py # Tags update command (updates vault.db)
    ├── query.py          # Query database command
    ├── add.py            # AI tag generation command
    ├── clean.py          # Clean command dispatcher
    ├── clean_invalid.py  # Remove invalid tags subcommand
    ├── clean_normalize.py # Normalize tag casing subcommand
    ├── purge.py          # Purge tags command
    ├── rename.py         # Rename tags command
    ├── similar.py        # Find similar tags command
    └── visualize.py      # Visualize tag hierarchy command
```

**Usage:**
All commands are run from the vault root directory using `vault tags`:

```bash
# View help
vault tags --help

# View command-specific help
vault tags missing --help
vault tags update --help
vault tags query --help
vault tags add --help
vault tags clean --help
vault tags purge --help
vault tags rename --help
vault tags similar --help
vault tags visualize --help
```

#### Command: missing

Generate markdown report of files without tags.

```bash
vault tags missing
```

**Features:**
- Scans all `.md` files in the vault
- Ignores `.obsidian` and `Excalidraw/Scripts` directories
- Checks for `tags:` field in YAML frontmatter only
- Generates markdown report with:
  - YAML frontmatter (`vault-management`, `tagless` tags)
  - Statistics section (total files, files with/without tags)
  - Wiki-links to all files without tags (clickable in Obsidian)
  - Timestamp and vault path

**Output:** `tagless-notes.md` in vault root (markdown format with wiki-links)

**Example Output:**
```markdown
---
tags:
  - vault-management
  - tagless
---

# Notes Without Tags

**Generated:** 2025-12-25 12:00:00
**Vault:** `/path/to/vault`

## Statistics

- Total markdown files: 100
- Files with tags: 95
- Files without tags: 5

## Files Without Tags

- [[Personal/Note1]]
- [[Personal/Note2]]
```

#### Command: update

Update the vault tag index in the SQLite database.

```bash
vault tags update
```

**Features:**
- Internally calls `vault index build` to scan all vault files
- Extracts tags from YAML frontmatter in `.md` files
- Updates `vault.db` SQLite database with all tag data
- Provides queryable tag data for automation and reporting

**Database Schema:**
- **metadata** table - Generation timestamp, vault path, statistics
- **tags** table - Tag names and file counts
- **file_tags** table - Tag-to-file relationships
- **files** table - File paths, sizes, extensions, and metadata
- Indexes for fast querying

**Output:**
- `vault.db` in vault root (SQLite database, source of truth)

**Note:** The SQLite database is the canonical source for all tag data. Use the `query` command to explore and analyze tags.

#### Command: add

AI-powered tag generation using Claude API.

```bash
# Preview changes
vault tags add <directory> --dry-run

# Apply changes
vault tags add <directory>

# Overwrite existing tags
vault tags add <directory> --overwrite
```

**Requirements:**
- `ANTHROPIC_API_KEY` environment variable must be set
- `anthropic` Python package (`pip install anthropic`)

**Features:**
- Uses Claude API to generate 3-4 appropriate tags
- Automatically validates tags against Obsidian's rules
- Filters out invalid tags (e.g., all-numeric tags like "2024", tags with special characters)
- Reports which tags were filtered during processing
- Recursively processes all `.md` files in specified directory (max depth: 5)
- Adds `tags:` field to YAML frontmatter
- Skips files without frontmatter
- By default, skips files that already have tags
- **Privacy:** Automatically skips notes with `sensitive: true` in frontmatter to prevent sending sensitive content to external APIs
- Ignores `.obsidian`, `.trash`, and `Excalidraw` directories
- Progress tracking with detailed statistics

**Arguments:**
- `directory` (required) - Directory path relative to vault root (use `.` for entire vault)
- `--dry-run` (optional) - Preview changes without modifying files
- `--overwrite` (optional) - Replace existing tags instead of skipping

**Examples:**
```bash
# Set API key first
export ANTHROPIC_API_KEY='your-api-key'

# Preview tag generation for Personal directory
vault tags add Personal --dry-run

# Generate tags for specific subdirectory
vault tags add "Personal/Software Development"

# Regenerate all tags in Personal directory
vault tags add Personal --overwrite
```

**Tag Validation:**
The `add` command automatically validates all AI-generated tags against Obsidian's rules before adding them to files:
- Valid tags are added to the frontmatter
- Invalid tags are filtered out and reported
- Summary shows how many tags were filtered and from which files
- This ensures all generated tags comply with Obsidian's requirements

For example, if the AI suggests tags like `software-development, 2024, design-principles`, the command will:
- Add: `software-development`, `design-principles` (valid)
- Filter: `2024` (invalid - all numeric)
- Report: "Filtered (invalid): 2024"

#### Command: clean

Clean and normalize tags. The `clean` command includes two subcommands: `invalid` (remove invalid tags) and `normalize` (normalize tag casing to lowercase).

```bash
# Remove invalid tags
vault tags clean invalid <directory> [--dry-run]

# Normalize tag casing to lowercase
vault tags clean normalize <directory> [--dry-run]
```

### Subcommand: clean invalid

Remove tags that don't conform to Obsidian's tag validation rules.

**Features:**
- Validates all tags against Obsidian's tag rules
- Removes invalid tags from YAML frontmatter
- Reports which tags were removed and from which files
- Provides statistics on invalid tags found
- Recursively processes all `.md` files in specified directory
- Ignores `.obsidian`, `.trash`, `.backup`, `Excalidraw`, and `Calendar` directories

**Obsidian Tag Rules:**
Tags must meet these requirements:
1. **Allowed characters only:** Letters (a-z, A-Z), numbers (0-9), underscore (_), hyphen (-), forward slash (/) for nested tags
2. **Must contain at least one non-numerical character:** At least one letter or underscore required

**Examples:**
- ❌ Invalid: `#1984`, `#2024`, `#123` (all numeric - no letters or underscores)
- ✅ Valid: `#y1984`, `#_test`, `#software-development`, `#2024-goals` (contain letters/underscores)

**Arguments:**
- `directory` (required) - Directory path relative to vault root (use `.` for entire vault)
- `--dry-run` (optional) - Preview changes without modifying files

**Usage Examples:**
```bash
# Preview cleaning for entire vault
vault tags clean invalid . --dry-run

# Clean invalid tags from Personal directory
vault tags clean invalid Personal

# Clean specific subdirectory
vault tags clean invalid "Personal/Software Development"
```

**Output:**
- Lists each file with invalid tags
- Shows which tags were removed
- Summary statistics (files scanned, files modified, total tags removed)
- Top invalid tags by occurrence count

**Note:** Year tags like `2023`, `2024`, `2025` are technically invalid according to Obsidian's rules (all numeric). If you use year tags for temporal tracking, consider prefixing them with a letter (e.g., `y2023`, `y2024`) or using an alternative tagging strategy.

### Subcommand: clean normalize

Normalize all tag casing to lowercase for consistency across the vault.

**Features:**
- Converts all tags to lowercase
- Shows preview of case changes before applying
- Confirmation prompt in live mode
- By default, automatically rebuilds vault.db after changes
- Recursively processes all `.md` files in specified directory
- Ignores `.obsidian` and `Excalidraw/Scripts` directories

**Arguments:**
- `directory` (required) - Directory path relative to vault root (use `.` for entire vault)
- `--dry-run` (optional) - Preview changes without modifying files or database
- `--no-rebuild` (optional) - Skip automatic database rebuild (rebuild manually with `vault index build`)

**Usage Examples:**
```bash
# Preview normalization for entire vault
vault tags clean normalize . --dry-run

# Normalize tags in Personal directory
vault tags clean normalize Personal

# Normalize entire vault
vault tags clean normalize .

# Normalize without rebuilding database (faster for bulk operations)
vault tags clean normalize . --no-rebuild
```

**Output:**
- Case changes summary showing old tag → new tag
- Statistics (files scanned, files modified, total tags normalized)
- Most common case changes
- Confirmation prompt before applying changes (in live mode)

**Example Case Changes:**
- `Software-Development` → `software-development`
- `OWASP` → `owasp`
- `AWS-Lambda` → `aws-lambda`

#### Command: query

Query the tag database with SQL or predefined queries.

```bash
# Database statistics
vault tags query --stats

# Top N most used tags
vault tags query --most-used 10

# Bottom N least used tags
vault tags query --least-used 10

# Files tagged with ALL specified tags
vault tags query --files-with software-architecture design-principles

# Files tagged with ANY of the specified tags
vault tags query --files-with-any aws cloud databases

# Detailed information about a specific tag
vault tags query --tag-info software-development

# Custom SQL query
vault tags query --sql "SELECT tag FROM tags WHERE tag LIKE '%aws%'"
```

**Requirements:**
- Database must exist: Run `vault tags update` first to generate `vault.db`

**Features:**
- Query tag data for automation and custom reporting
- Predefined queries for common use cases
- Custom SQL support for advanced queries
- Results formatted with wiki-links for easy navigation in Obsidian
- Fast queries using indexed database

**Predefined Queries:**
- `--stats` - Show database statistics (total files, tags, averages, distribution)
- `--most-used N` - Show top N tags by file count
- `--least-used N` - Show bottom N tags by file count (useful for finding consolidation candidates)
- `--files-with TAG1 TAG2 ...` - Show files tagged with ALL specified tags (INTERSECT)
- `--files-with-any TAG1 TAG2 ...` - Show files tagged with ANY of the specified tags (UNION)
- `--tag-info TAG` - Show detailed information about a specific tag (count + all files)

**Custom SQL Queries:**
- `--sql "QUERY"` - Execute custom SQL query against the database
- Access to all tables: `metadata`, `tags`, `tag_files`, `files`
- Returns results in table format with column headers

**Database Tables:**
```sql
-- Metadata (key-value pairs)
metadata (key TEXT PRIMARY KEY, value TEXT)

-- Tags with counts
tags (tag TEXT PRIMARY KEY, file_count INTEGER)

-- Tag-to-file relationships
tag_files (tag TEXT, file_path TEXT, PRIMARY KEY (tag, file_path))

-- Files with tag counts
files (file_path TEXT PRIMARY KEY, tag_count INTEGER)
```

**Example Queries:**
```bash
# Find all AWS-related tags
vault tags query --sql "SELECT tag, file_count FROM tags WHERE tag LIKE '%aws%' ORDER BY file_count DESC"

# Find files with most tags
vault tags query --sql "SELECT file_path, tag_count FROM files ORDER BY tag_count DESC LIMIT 10"

# Find tags used in exactly 1 file (consolidation candidates)
vault tags query --sql "SELECT tag FROM tags WHERE file_count = 1 ORDER BY tag"

# Count files tagged with both 'security' and 'owasp'
vault tags query --sql "SELECT COUNT(DISTINCT file_path) FROM tag_files WHERE tag IN ('security', 'owasp')"

# Find all files in a specific directory with specific tag
vault tags query --sql "SELECT file_path FROM tag_files WHERE tag = 'software-architecture' AND file_path LIKE 'Personal/Software%'"
```

**Use Cases:**
- Build custom automation based on tag data
- Generate custom visualizations and reports
- Find underutilized tags for consolidation
- Identify files needing better tagging
- Analyze tag distribution and patterns
- Create tag-based queries for Obsidian integration

#### Command: purge

Remove one or more specified tags from all markdown files and database.

```bash
# Preview purging tags
vault tags purge tag1 tag2 tag3 --dry-run

# Purge tags from vault
vault tags purge deprecated-tag old-tag

# Purge without rebuilding database (faster for bulk operations)
vault tags purge deprecated-tag old-tag --no-rebuild
```

**Features:**
- Removes specified tags from all files in the vault
- Supports multiple tags in a single operation
- Keeps empty tags list in frontmatter (doesn't remove tags property)
- By default, automatically rebuilds vault.db after successful purge
- Shows statistics and requires confirmation before purging (in live mode)
- Ignores `.obsidian`, `.trash`, `.backup`, `Excalidraw`, and `Calendar` directories

**Arguments:**
- `tags` (required) - One or more tags to purge (space-separated, case-sensitive)
- `--dry-run` (optional) - Preview changes without modifying files or database
- `--no-rebuild` (optional) - Skip automatic database rebuild (rebuild manually with `vault index build`)

**Usage Examples:**
```bash
# Preview purging a single tag
vault tags purge deprecated-tag --dry-run

# Purge multiple tags
vault tags purge old-tag unused-tag temporary-tag

# Purge year tags
vault tags purge 2023 2024
```

**Output:**
- Shows which tags will be removed from which files
- Statistics (files scanned, files modified, total tags removed)
- Tag removal counts by tag
- Confirmation prompt before applying changes (in live mode)

**Workflow:**
1. Scan vault for specified tags
2. Show preview of changes and statistics
3. Prompt for confirmation (in live mode)
4. Remove tags from frontmatter
5. Rebuild vault.db automatically (unless `--no-rebuild` specified)

**Note:** Tags are matched case-sensitively. If you have both `Tag` and `tag`, you must purge them separately.

#### Command: rename

Rename a tag across all markdown files and database.

```bash
# Preview tag rename
vault tags rename old-tag new-tag --dry-run

# Rename tag
vault tags rename old-tag new-tag

# Rename without rebuilding database (faster for bulk operations)
vault tags rename old-tag new-tag --no-rebuild
```

**Features:**
- Renames tag across entire vault
- Validates new tag name against Obsidian's rules
- Detects and handles conflicts (when new tag already exists)
- By default, automatically rebuilds vault.db after successful rename
- Shows statistics and requires confirmation before renaming (in live mode)
- Ignores `.obsidian`, `.trash`, `.backup`, `Excalidraw`, and `Calendar` directories

**Arguments:**
- `old_tag` (required) - Tag to rename (case-sensitive)
- `new_tag` (required) - New tag name (case-sensitive)
- `--dry-run` (optional) - Preview changes without modifying files or database
- `--no-rebuild` (optional) - Skip automatic database rebuild (rebuild manually with `vault index build`)

**Tag Validation:**
The new tag must conform to Obsidian's tag rules:
- Only letters, numbers, underscore (_), hyphen (-), slash (/) for nested tags
- Must contain at least one letter or underscore
- Examples: `software-development`, `y2024`, `nested/tag`

**Conflict Handling:**
If a file already has the new tag, the old tag is removed to avoid duplicates. Files with conflicts are tracked and reported.

**Usage Examples:**
```bash
# Preview renaming a tag
vault tags rename software-dev software-development --dry-run

# Rename tag
vault tags rename database databases

# Rename to nested tag
vault tags rename aws cloud/aws
```

**Output:**
- Shows which files will be modified
- Reports conflicts (files already containing new tag)
- Statistics (files scanned, files modified, total tags renamed)
- Confirmation prompt before applying changes (in live mode)

**Workflow:**
1. Validate new tag name
2. Scan vault for old tag
3. Check for conflicts
4. Show preview and statistics
5. Prompt for confirmation (in live mode)
6. Rename tags in frontmatter
7. Rebuild vault.db automatically (unless `--no-rebuild` specified)

#### Command: similar

Find similar tags that might be typos, plurals, or consolidation candidates.

```bash
# Find similar tags with default threshold (0.85)
vault tags similar

# Find similar tags with custom threshold
vault tags similar --threshold 0.90

# Include less common tags (default minimum: 2 files)
vault tags similar --min-count 1

# Generate report with custom filename
vault tags similar --output my-similarity-report.md
```

**Features:**
- Analyzes tags using Levenshtein distance (string similarity)
- Categorizes findings for easy identification
- Generates markdown report with actionable suggestions
- Suggests specific commands for consolidation
- Ignores very rare tags by default (minimum 2 files)
- Uses vault.db for fast analysis

**Categories:**
1. **Case Only** - Tags differing only in case (e.g., `AWS` vs `aws`)
2. **Likely Typos** - Very similar tags (>90% similarity), probable typos
3. **Singular/Plural** - Tags likely to be singular/plural forms
4. **Similar Tags** - Tags with high similarity (>threshold) that might be candidates for consolidation

**Arguments:**
- `--threshold` (optional) - Similarity threshold (0.0-1.0, default: 0.85)
- `--min-count` (optional) - Minimum files per tag to include (default: 2)
- `--output` (optional) - Output filename (default: tag-similarity-report.md)

**Usage Examples:**
```bash
# Find similar tags with default settings
vault tags similar

# Be more strict (only very similar tags)
vault tags similar --threshold 0.95

# Include single-file tags
vault tags similar --min-count 1

# Custom output file
vault tags similar --output similarity-analysis.md
```

**Report Format:**
```markdown
# Tag Similarity Report

## Summary
- Total similar pairs: 15
- Case differences: 3
- Likely typos: 5
- Singular/plural: 4
- Similar tags: 3

## Likely Typos
| Tag 1 | Files | Tag 2 | Files | Similarity | Suggested Action |
|-------|-------|-------|-------|------------|------------------|
| `databse` | 2 | `database` | 25 | 95.65% | `vault tags rename databse database` |

## Similar Tags
| Tag 1 | Files | Tag 2 | Files | Similarity | Suggested Action |
|-------|-------|-------|-------|------------|------------------|
| `development` | 30 | `ui-development` | 5 | 88.00% | Review: merge or keep separate |
```

**Use Cases:**
- Find and fix typos in tags
- Identify inconsistent tag usage (case differences)
- Discover singular/plural variations for normalization
- Find opportunities for tag consolidation
- Maintain consistent tagging across vault

**Workflow:**
1. Query vault.db for all tags and their file counts
2. Calculate similarity between all tag pairs
3. Categorize similar tag pairs
4. Generate markdown report with suggestions
5. Review report and use suggested commands to consolidate

**Requirements:**
- Database must exist: Run `vault tags update` first to generate `vault.db`

#### Command: visualize

Generate an interactive Obsidian Canvas visualization of tag hierarchy.

```bash
# Generate visualization with default settings
vault tags visualize

# Generate with custom output filename
vault tags visualize --output my-tags.canvas

# Only include tags used in 5+ files
vault tags visualize --min-count 5
```

**Features:**
- Generates interactive Obsidian Canvas showing hierarchical tag structure
- Displays nested tags (tags with `/` separator) as parent-child relationships
- Shows file count for each tag node
- Color-codes nodes by usage (blue=low, green/yellow/orange=medium, red=high)
- Intelligent hierarchical layout algorithm
- Fully interactive: zoom, pan, drag nodes
- Uses vault.db for fast analysis

**Arguments:**
- `--output` (optional) - Output filename (default: tag-hierarchy.canvas)
- `--min-count` (optional) - Minimum files per tag to include (default: 2)

**Usage Examples:**
```bash
# Generate visualization with default settings (min-count: 2)
vault tags visualize

# Custom output filename
vault tags visualize --output my-tags.canvas

# Show all tags (including single-use tags)
vault tags visualize --min-count 1

# Only show frequently-used tags (10+ files)
vault tags visualize --min-count 10
```

**Canvas Features:**
1. **Interactive Visualization** - Obsidian Canvas with:
   - Root node displaying total tag count
   - All tags as individual nodes with file counts
   - Hierarchical layout (parent tags above children)
   - Grid layout for top-level tags
   - Edges connecting parents to children

2. **Color Coding** - Node colors indicate usage:
   - **Blue** (1): Low usage (0-20% of max)
   - **Green** (2): Medium-low (20-40%)
   - **Yellow** (3): Medium (40-60%)
   - **Orange** (4): Medium-high (60-80%)
   - **Red/Pink** (5): High usage (80-100%)
   - **Purple** (6): Root node

3. **Layout Algorithm** - Intelligent positioning:
   - Grid layout for top-level tags (sorted by usage)
   - Child tags positioned below parents
   - Automatic spacing and alignment
   - Scales to any number of tags

4. **Canvas Interactions** - Full Obsidian Canvas features:
   - Zoom in/out with scroll wheel
   - Pan by dragging canvas
   - Select and move individual nodes
   - Rearrange layout manually
   - Add notes, links, or groups

**Example Output:**
Opens as an interactive canvas in Obsidian with:
- 1 root node ("Tag Hierarchy")
- N tag nodes (filtered by min-count)
- N+1 edges connecting hierarchy
- Color-coded by usage frequency
- Hierarchical tree layout

**Use Cases:**
- Understand tag taxonomy at a glance
- Identify tag hierarchies and relationships
- Visualize tag organization interactively
- Find opportunities to create nested tag structures
- Share vault organization with collaborators
- Audit tag usage patterns visually
- Explore tag connections by zooming and panning
- Manually adjust layout for presentations

**Workflow:**
1. Query vault.db for all tags and their file counts
2. Analyze tag hierarchy (detect nested tags with `/`)
3. Build hierarchical structure mapping parent tags to children
4. Calculate node positions using layout algorithm
5. Generate Canvas JSON with nodes and edges
6. Apply color coding based on usage frequency
7. Write Canvas file to vault

**Requirements:**
- Database must exist: Run `vault tags update` first to generate `vault.db`

**Note:** The generated Canvas opens directly in Obsidian and provides a fully interactive, zoomable, pannable visualization of your tag taxonomy. You can manually rearrange nodes, add annotations, or export the canvas.

#### Command: reorganize

Analyze tag taxonomy and suggest hierarchical reorganization using semantic analysis.

```bash
# Generate reorganization suggestions (rule-based)
vault tags reorganize

# Use AI for semantic analysis
vault tags reorganize --use-ai

# Customize analysis
vault tags reorganize --min-count 5 --max-suggestions 30

# Custom output file
vault tags reorganize --output my-reorganization-plan.md
```

**Features:**
- Analyzes flat tags and suggests hierarchical organization using parent/child relationships
- Two analysis modes: rule-based (default) and AI-powered (requires ANTHROPIC_API_KEY)
- Considers existing hierarchical structure and domain patterns
- Provides confidence scores and reasoning for each suggestion
- Generates actionable markdown report with commands to apply suggestions
- Supports filtering by minimum tag usage count
- Uses vault.db for fast analysis

**Analysis Methods:**

1. **Rule-based (default):**
   - Matches tags with existing parent tags based on keyword overlap
   - Applies domain knowledge patterns (e.g., algorithms → computer-science)
   - Detects semantic relationships using word matching
   - Fast and doesn't require API access

2. **AI-powered (--use-ai):**
   - Uses Claude API for advanced semantic analysis
   - Understands complex relationships and domain context
   - Provides detailed reasoning for each suggestion
   - Requires ANTHROPIC_API_KEY environment variable

**Arguments:**
- `--min-count N` (optional) - Minimum tag usage count to consider (default: 2)
- `--output FILE` (optional) - Output markdown filename (default: tag-reorganization-report.md)
- `--use-ai` (optional) - Enable AI analysis using Claude API
- `--max-suggestions N` (optional) - Maximum number of suggestions (default: 50)

**Usage Examples:**
```bash
# Basic analysis with rule-based suggestions
vault tags reorganize

# AI-powered analysis (requires API key)
export ANTHROPIC_API_KEY='your-api-key'
vault tags reorganize --use-ai

# Focus on frequently-used tags only
vault tags reorganize --min-count 10

# Generate detailed report with many suggestions
vault tags reorganize --max-suggestions 100 --output full-reorganization.md
```

**Report Format:**
```markdown
# Tag Reorganization Report

## Summary
- Total reorganization suggestions: 16
- Existing hierarchical tags: 5
- Existing parent tags: 4

## Current Tag Hierarchy
### design
- design/patterns
- design/principles

## Reorganization Suggestions
| Tag | Files | Suggested Path | Confidence | Reason | Command |
|-----|-------|----------------|------------|--------|---------|
| algorithms | 52 | computer-science/algorithms | 80% | domain pattern match | vault tags rename ... |
```

**Use Cases:**
- Organize flat tag taxonomy into logical hierarchies
- Discover semantic relationships between tags
- Create consistent tag structure across vault
- Plan tag reorganization before applying changes
- Identify opportunities to group related tags
- Maintain clean, organized tag taxonomy

**Workflow:**
1. Run analysis: `vault tags reorganize`
2. Review generated report with suggestions
3. Preview individual changes: `vault tags rename tag new-path --dry-run`
4. Apply approved reorganizations: `vault tags rename tag new-path`
5. Rebuild database: `vault index build`

**Example Suggestions:**
- `algorithms` → `computer-science/algorithms`
- `microservices` → `architecture/microservices`
- `owasp` → `security/owasp`
- `solid` → `design/solid`
- `scalability` → `architecture/scalability`

**Requirements:**
- Database must exist: Run `vault tags update` first to generate `vault.db`
- For AI analysis: `ANTHROPIC_API_KEY` environment variable and `anthropic` package

**Note:** Always preview changes with `--dry-run` before applying tag reorganizations. The command generates suggestions only - you review and approve each change before applying.

---

### Image Management Package (`Library/images/`)

A modular image management system using the command pattern and argparse for CLI argument parsing.

**Architecture:**
- **Command Pattern:** Each command (find, cleanup, remove-alt) is implemented as a separate module
- **Modular Structure:** Code organized into focused, maintainable modules
- **Argparse CLI:** Professional command-line interface with subcommands and help text

**Package Structure:**
```
Library/images/
├── __init__.py           # Package metadata
├── __main__.py           # Module entry point
├── cli.py                # CLI dispatcher with argparse
├── common.py             # Shared utilities
└── commands/
    ├── __init__.py       # Command base class
    ├── find.py           # Find orphaned images command
    ├── cleanup.py        # Cleanup command
    └── remove_alt.py     # Remove alt text command
```

**Usage:**
All commands are run from the vault root directory using `vault images`:

```bash
# View help
vault images --help

# View command-specific help
vault images find --help
vault images cleanup --help
vault images remove-alt --help
```

#### Command: find

Find images not referenced in any markdown file.

```bash
vault images find
```

**Features:**
- Scans for image files (`.png`, `.jpg`, `.jpeg`, `.gif`, `.svg`, `.webp`, `.bmp`, `.ico`)
- Scans all `.md` files for image references in multiple formats:
  - Markdown syntax: `![alt](path/to/image.png)`
  - Obsidian wiki-links: `![[image.png]]`
  - HTML img tags: `<img src="path">`
- Ignores `.obsidian`, `.trash`, and `Excalidraw` directories
- Resolves relative paths and Obsidian-style filename references
- Generates hierarchical report organized by directory structure
- Uses markdown checkboxes and wiki-links for easy navigation

**Output:** `orphaned-images.md` in vault root

#### Command: broken

Find notes with missing local image references.

```bash
vault images broken [--output <filename>]
```

**Features:**
- Scans all `.md` files for **local vault image references only**:
  - Obsidian wiki-links: `![[image.png]]` or `![[image.png|alt text]]`
  - Local markdown paths: `![alt](path/to/image.png)`
- **Ignores external URLs** (http://, https://, ftp://, etc.)
- Checks if referenced local images exist in the vault
- Resolves both filename-only references (Obsidian style) and relative paths
- Reports line numbers and reference format for each broken reference
- Useful for identifying:
  - Deleted or moved vault images
  - Typos in image filenames
  - Path resolution issues
  - Images referenced with incorrect paths
- Ignores `.obsidian`, `.trash`, and `Excalidraw` directories
- Generates detailed report with wiki-links to notes

**Arguments:**
- `--output` (optional) - Output filename (default: `broken-image-refs.md`)

**Output:** `broken-image-refs.md` in vault root (or custom filename)

**Report Format:**
```markdown
### [[Note Name]]

**File:** `path/to/note.md`
**Missing images:** 2

- `![[missing-image.png]]` (line 42, format: wiki-link)
- `![alt](path/to/missing.jpg)` (line 58, format: markdown)
```

**Note:** External URLs like `![](https://example.com/image.jpg)` are ignored and not reported.

**Examples:**
```bash
# Generate report with default name
vault images broken

# Custom output filename
vault images broken --output my-broken-images.md
```

#### Command: cleanup

Move checked-off orphaned images to .trash directory.

```bash
vault images cleanup
```

**Features:**
- Reads `orphaned-images.md` for checked items (`- [x]`)
- Extracts file paths from wiki-links
- Moves checked files to `.trash` directory
- Preserves directory structure in `.trash`
- Removes empty directories after moving files
- Updates `orphaned-images.md` to remove processed items
- Generates summary report of moved and failed files

**Input:** `orphaned-images.md` in vault root
**Output:** Files moved to `.trash/` directory

#### Command: remove-alt

Remove alt text from wiki-link image embeds.

```bash
# Preview changes
vault images remove-alt <directory> --dry-run

# Apply changes
vault images remove-alt <directory>
```

**Features:**
- Recursively processes all `.md` files in specified directory
- Converts `![[file.ext|alt text]]` to `![[file.ext]]`
- Supports all common image formats
- Ignores `.obsidian`, `.trash`, and `Excalidraw` directories
- Dry-run mode to preview changes before applying

**Arguments:**
- `directory` (required) - Directory path relative to vault root (use `.` for entire vault)
- `--dry-run` (optional) - Preview changes without modifying files

**Examples:**
```bash
# Process entire vault (dry run)
vault images remove-alt . --dry-run

# Process specific directory
vault images remove-alt Personal/Software\ Development

# Process with spaces in path
vault images remove-alt "Personal/Software Development"
```

---

### Property Management Package (`Library/properties/`)

A modular property management system for frontmatter operations using the command pattern and argparse.

**Architecture:**
- **Command Pattern:** Each command (enrich, clean, validate, repair) is implemented as a separate module
- **Modular Structure:** Code organized into focused, maintainable modules
- **Argparse CLI:** Professional command-line interface with subcommands and help text

**Package Structure:**
```
Library/properties/
├── __init__.py           # Package metadata
├── __main__.py           # Module entry point
├── cli.py                # CLI dispatcher with argparse
├── common.py             # Shared utilities
└── commands/
    ├── __init__.py       # Command base class
    ├── enrich.py         # Enrich command (summaries, related)
    ├── clean.py          # Clean command (normalize, deduplicate, remove)
    ├── validate.py       # Validate frontmatter command
    ├── repair.py         # Repair frontmatter command
    ├── set.py            # Set property value command
    ├── audit.py          # Audit properties command
    ├── summarize.py      # AI summaries subcommand
    ├── relate.py         # Related notes subcommand
    ├── normalize.py      # Normalize frontmatter subcommand
    ├── deduplicate.py    # Deduplicate properties subcommand
    └── remove.py         # Remove property subcommand
```

**Usage:**
All commands are run from the vault root directory using `vault properties`:

```bash
# View help
vault properties --help

# View command-specific help
vault properties enrich --help
vault properties clean --help
vault properties validate --help
vault properties repair --help
vault properties set --help
vault properties audit --help
```

#### Command: enrich

Enrich notes with AI-generated content and metadata. The `enrich` command consolidates two content enhancement operations: summaries and related notes.

```bash
# Summaries - AI-generated summaries
vault properties enrich summaries <directory> [--dry-run] [--overwrite]

# Related - Find related notes based on similarity
vault properties enrich related <path> [--dry-run] [--overwrite] [--max-related=N]
```

### Subcommand: summaries

AI-powered summary generation using Claude API.

**Requirements:**
- `ANTHROPIC_API_KEY` environment variable must be set
- `anthropic` Python package (`pip install anthropic`)

**Features:**
- Uses Claude API to generate concise 2-4 sentence summaries in plain text (no markdown formatting)
- Recursively processes all `.md` files in specified directory (max depth: 5)
- Adds `summary:` field to YAML frontmatter
- Skips files without frontmatter
- By default, skips files that already have summaries
- **Privacy:** Automatically skips notes with `sensitive: true` in frontmatter to prevent sending sensitive content to external APIs
- Ignores `.obsidian`, `.trash`, `.backup`, `Excalidraw`, and `Calendar` directories

**Arguments:**
- `directory` (required) - Directory path relative to vault root (use `.` for entire vault)
- `--dry-run` (optional) - Preview changes without modifying files
- `--overwrite` (optional) - Replace existing summaries

**Examples:**
```bash
# Set API key first
export ANTHROPIC_API_KEY='your-api-key'

# Preview summary generation
vault properties enrich summaries Personal --dry-run

# Generate summaries for specific subdirectory
vault properties enrich summaries "Personal/Software Development"

# Regenerate all summaries
vault properties enrich summaries Personal --overwrite
```

### Subcommand: related

Find related notes using hybrid similarity algorithm.

**Features:**
- Analyzes notes using hybrid similarity algorithm
- Adds `related:` property with wiki-links to similar notes
- Accepts either a file path or directory path
- Wiki-links use just the filename (e.g., `[[Note Name]]`) instead of full paths
- Algorithm weights:
  - Tag similarity: 40% (weighted by tag rarity using IDF-like scoring)
  - Link proximity: 30% (direct links + shared link targets)
  - Folder proximity: 15% (same/parent/child/sibling folders)
  - Title keywords: 15% (shared meaningful words)
- When processing a single file, scans the entire vault to find the best related notes
- Ignores `.obsidian`, `.trash`, `.backup`, `Excalidraw`, and `Calendar` directories

**Arguments:**
- `path` (required) - File or directory path relative to vault root (use `.` for entire vault)
- `--dry-run` (optional) - Preview changes without modifying files
- `--overwrite` (optional) - Replace existing related properties
- `--max-related=N` (optional) - Maximum related notes per file (default: 5)

**Examples:**
```bash
# Find related notes for a directory (dry run)
vault properties enrich related Personal --dry-run

# Find related notes for a single file
vault properties enrich related "Personal/Software Development/SOLID Principles.md"

# Find top 3 related notes
vault properties enrich related Personal --max-related=3

# Regenerate all related links for entire vault
vault properties enrich related . --overwrite
```

#### Command: clean

Clean and standardize frontmatter properties. The `clean` command consolidates three cleanup operations: normalize, deduplicate, and remove.

```bash
# Normalize - standardize properties
vault properties clean normalize <directory> [--dry-run]

# Deduplicate - remove duplicate properties
vault properties clean deduplicate <directory> [--dry-run]

# Remove - remove a specific property
vault properties clean remove <property_name> <directory> [--dry-run]
```

### Subcommand: normalize

Standardize frontmatter properties across notes.

**Normalization Rules:**
- **Keep:** `tags`, `summary`, `related`, `source` (and any other properties not explicitly removed)
- **Remove:** `author`, `title`, `description`, `created`, `published`
- **Rename:** `url` → `source`
- **Reorder:** Properties ordered as: tags, summary, related, source, then others alphabetically

**Features:**
- Standardizes frontmatter properties using YAML library
- Provides detailed reporting of changes (removed, renamed properties)
- Aggregated change counts in summary
- Ignores `.obsidian`, `.trash`, `.backup`, `Excalidraw`, and `Calendar` directories

**Arguments:**
- `directory` (required) - Directory path relative to vault root (use `.` for entire vault)
- `--dry-run` (optional) - Preview changes without modifying files

**Examples:**
```bash
# Preview normalization
vault properties clean normalize Personal --dry-run

# Normalize entire vault
vault properties clean normalize .

# Normalize specific directory
vault properties clean normalize "Personal/Software Development"
```

### Subcommand: deduplicate

Remove duplicate frontmatter properties from notes.

**Features:**
- Detects duplicate keys in YAML frontmatter
- Keeps the last occurrence of each duplicate property
- Preserves property order
- Reports which properties were deduplicated
- Provides statistics on most common duplicate properties
- Ignores `.obsidian`, `.trash`, `.backup`, `Excalidraw`, and `Calendar` directories

**Use Cases:**
- Fix broken frontmatter with duplicate properties
- Clean up after buggy script runs (e.g., relate command with --overwrite)
- Ensure YAML frontmatter is valid
- Restore file readability in Obsidian

**Strategy:**
The command parses YAML frontmatter and identifies duplicate keys. When duplicates are found, it keeps only the last occurrence of each property (matching YAML behavior). The deduplicated frontmatter is then written back to the file.

**Arguments:**
- `directory` (required) - Directory path relative to vault root (use `.` for entire vault)
- `--dry-run` (optional) - Preview changes without modifying files

**Examples:**
```bash
# Preview deduplication for entire vault
vault properties clean deduplicate . --dry-run

# Fix duplicate properties in Personal directory
vault properties clean deduplicate Personal

# Fix all notes in vault
vault properties clean deduplicate .
```

**Output:**
- Lists each file with duplicates found
- Shows which specific properties were deduplicated
- Summary with most common duplicate properties
- Statistics (total files scanned, files modified, total duplicates removed)

**Common Scenario:**
If the `relate` command was run with `--overwrite` and created duplicate `related` properties, this command will fix all affected files by removing the duplicate entries.

### Subcommand: remove

Remove a specific property from frontmatter across all notes.

**Features:**
- Removes specified property from YAML frontmatter
- If removal leaves frontmatter empty, removes entire frontmatter block
- Preserves all other properties
- Provides detailed reporting
- Ignores `.obsidian`, `.trash`, `.backup`, `Excalidraw`, and `Calendar` directories

**Use Cases:**
- Remove deprecated or unwanted properties
- Clean up after data migration or import
- Remove properties that are no longer needed

**Arguments:**
- `property_name` (required) - Name of the property to remove
- `directory` (required) - Directory path relative to vault root (use `.` for entire vault)
- `--dry-run` (optional) - Preview changes without modifying files

**Examples:**
```bash
# Preview removal without modifying files
vault properties clean remove author Personal --dry-run

# Remove 'created' property from entire vault
vault properties clean remove created .

# Remove 'description' from specific directory
vault properties clean remove description "Personal/Software Development"
```

**Output:**
- Shows each file where the property was found and removed
- Reports files that failed to process
- Summary statistics (total files, files with property, files modified, files failed)

#### Command: validate

Validate YAML frontmatter structure and content against Obsidian's property rules.

```bash
# Validate entire vault
vault properties validate

# Validate specific directory
vault properties validate Personal
```

**Features:**
- Detects files without YAML frontmatter
- Detects frontmatter without tags property
- Warns when tags property exists but is empty
- Validates YAML syntax and structure
- Checks for unique property names
- Detects deprecated singular properties (`tag`, `alias`, `cssclass`)
- Validates tag format (no hashtags in YAML)
- Warns about unquoted wiki-links
- Detects unsupported Markdown in property values
- Ensures frontmatter is at the top of the file
- Generates markdown report with checkboxes for tracking fixes

**Validation Checks:**
- **Missing Frontmatter**: Detects files without YAML frontmatter
- **Missing Tags**: Detects frontmatter without tags property
- **Empty Tags**: Warns when tags property exists but is empty
- **YAML Syntax**: Valid YAML structure and formatting
- **Property Names**: Unique property names, detects deprecated singular forms
- **Tag Format**: Tags must not contain hashtags (#) in YAML
- **Wiki-Links**: Warns about unquoted wiki-links that may cause parsing issues
- **Markdown Content**: Detects unsupported Markdown syntax in property values
- **Position**: Ensures frontmatter is at the very top of the file

**Arguments:**
- `directory` (optional) - Directory to validate (defaults to entire vault if omitted)

**Output:** `invalid-frontmatter.md` in vault root with checkboxes for each issue

#### Command: repair

Automatically repair checked frontmatter issues from the validation report.

```bash
# Simulate repairs (preview only)
vault properties repair --dry-run

# Repair with backup
vault properties repair --backup

# Repair without backup
vault properties repair
```

**Features:**
- Reads `invalid-frontmatter.md` validation report
- Repairs only checked items (marked with `- [x]`)
- Supports automatic repair for common fixable issues
- Optional backup to `.backup/repair_TIMESTAMP/` directory
- Dry-run mode for safe testing
- Detailed reporting of repairs applied

**Repairable Issues:**
- **Missing frontmatter**: Creates new frontmatter block with empty tags property
- **Missing tags**: Adds empty tags property to existing frontmatter
- **Deprecated properties**: Renames singular forms to plural (`tag` → `tags`, `alias` → `aliases`, `cssclass` → `cssclasses`)
- **Invalid tag format**: Removes hashtag (#) prefixes from tags in YAML frontmatter
- **Duplicate properties**: Removes duplicate property keys (keeps last occurrence)
- **Empty frontmatter**: Removes empty frontmatter blocks
- **Unquoted wiki-links**: Ensures wiki-links are properly quoted in YAML
- **Markdown in properties**: Strips markdown formatting (bold, italic, code, links, etc.) from property values

**Issues Requiring Manual Intervention:**
- **Empty tags**: Tags property exists but is empty (requires manual tag input)
- **YAML syntax errors**: Invalid YAML that cannot be parsed
- **Invalid YAML structure**: Malformed YAML structure
- **File read errors**: Files that cannot be read or written

**Workflow:**
1. Run `vault properties validate` to generate the report
2. Review `invalid-frontmatter.md` and check items you want to fix (change `- [ ]` to `- [x]`)
3. Run `vault properties repair --backup` to apply fixes with backup
4. Run validation again to verify remaining issues

**Arguments:**
- `--backup` (optional) - Backup files to `.backup` directory before repairing
- `--dry-run` (optional) - Simulate repairs without modifying files

**Examples:**
```bash
# Preview what would be repaired
vault properties repair --dry-run

# Repair with backup (recommended)
vault properties repair --backup

# Repair without backup (use with caution)
vault properties repair
```

**Output:**
- Progress messages for each file processed
- Indication of which repairs were applied
- Summary statistics (repaired, skipped, failed, backed up)
- Recommendations for next steps

#### Command: set

Bulk set or update a property value across multiple markdown files.

```bash
# Preview changes
vault properties set <property_name> <value> <directory> --dry-run

# Set property
vault properties set status draft Personal

# Set property with tag filtering
vault properties set category architecture Personal --files-with software-architecture

# Overwrite existing values
vault properties set priority high Personal/Projects --overwrite
```

**Features:**
- Bulk set or update properties across multiple files
- Tag filtering support (only process files with specific tags)
- Skips files that already have the property (unless --overwrite)
- Dry-run mode for previewing changes
- Detailed progress reporting
- Ignores `.obsidian`, `.trash`, `.backup`, `Excalidraw`, and `Calendar` directories

**Arguments:**
- `property_name` (required) - Name of the property to set
- `value` (required) - Value to assign to the property
- `directory` (required) - Directory path relative to vault root (use `.` for entire vault)
- `--dry-run` (optional) - Preview changes without modifying files
- `--overwrite` (optional) - Replace existing property values (default: skip files that already have the property)
- `--files-with TAG1 TAG2 ...` (optional) - Only process files that have ALL of the specified tags

**Use Cases:**
- Add a property to multiple files at once
- Update an existing property value across files
- Add properties to files matching specific tags
- Bulk categorization or classification of notes
- Add metadata for workflow management (status, priority, etc.)

**Usage Examples:**
```bash
# Preview adding a property to all files in a directory
vault properties set status draft Personal --dry-run

# Add property to files with specific tags
vault properties set category architecture Personal --files-with software-architecture design-principles

# Update property and overwrite existing values
vault properties set priority high Personal/Projects --overwrite

# Set property across entire vault
vault properties set type note .

# Add status to all security notes
vault properties set reviewed true Personal/SecOps --files-with security owasp
```

**Output:**
- Lists each file being processed
- Shows whether property was added or skipped
- Summary statistics (total files scanned, files modified, files skipped)
- Clear dry-run mode indication

**Example Output:**
```
Processing files in Personal...

Added 'status: draft' to Personal/Note1.md
Added 'status: draft' to Personal/Note2.md
Skipped Personal/Note3.md (property already exists)

Summary:
  Total files scanned: 50
  Files modified: 35
  Files skipped: 15
```

#### Command: audit

Analyze all frontmatter properties across the vault and generate a comprehensive report.

```bash
# Generate audit report
vault properties audit

# Generate report with custom filename
vault properties audit --output my-audit-report.md
```

**Features:**
- Analyzes all frontmatter properties across the entire vault
- Generates comprehensive markdown report with statistics
- Shows property usage, data types, and value distributions
- Includes example files with wiki-links for each property
- Identifies properties with mixed data types
- Reports most common values for each property
- Uses vault.db for fast analysis

**Report Includes:**
1. **Property Overview Table**: All properties with usage counts, data types, and sample values
2. **Detailed Analysis**: For each property:
   - Data type distribution (string, list, boolean, number, null, etc.)
   - Most common values with occurrence counts
   - Example files with wiki-links showing usage
3. **Statistics**: Total files scanned, files with frontmatter, unique properties found

**Arguments:**
- `--output FILENAME` (optional) - Output filename (default: property-audit.md)

**Usage Examples:**
```bash
# Generate report in default location
vault properties audit

# Generate report with custom filename
vault properties audit --output property-analysis.md

# Generate report and review in Obsidian
vault properties audit && echo "Report generated: property-audit.md"
```

**Use Cases:**
- Understand what properties are used across the vault
- Identify inconsistent property usage (mixed data types)
- Find properties with inconsistent naming (singular vs plural)
- Plan property normalization or cleanup
- Document vault schema for team collaboration
- Discover underutilized or deprecated properties
- Audit property values for standardization

**Sample Report Output:**
```markdown
# Frontmatter Property Audit

Generated: 2025-12-28 18:00:00
Vault: /path/to/vault

## Statistics

- Total files scanned: 150
- Files with frontmatter: 145
- Unique properties: 12

## Property Overview

| Property | Files | Data Types | Sample Values |
|----------|-------|------------|---------------|
| tags | 145 | list(100%) | software-architecture, security, ... |
| summary | 42 | string(100%) | This note describes... |
| source | 38 | string(100%) | https://example.com |
| status | 25 | string(100%) | draft, published, review |
| priority | 15 | string(80%), number(20%) | high, low, 1, 2, 3 |

## Detailed Analysis

### Property: tags
- **Files**: 145 (96.67% of files with frontmatter)
- **Data Types**:
  - list: 145 files (100.00%)

**Most Common Values**:
- software-architecture: 45 files
- security: 32 files
- design-principles: 28 files
- ...

**Example Files**:
- [[Personal/Software Development/SOLID Principles]]
- [[Personal/Software Architecture/Microservices]]
- ...

### Property: priority
- **Files**: 15 (10.00% of files with frontmatter)
- **Data Types**:
  - string: 12 files (80.00%)
  - number: 3 files (20.00%)

**Most Common Values**:
- high: 8 files
- low: 4 files
- 1: 2 files
- 2: 1 file

**Example Files**:
- [[Personal/Projects/Website Redesign]]
- [[Personal/Tasks/Bug Fixes]]
```

**Note:** Properties with mixed data types (like `priority` above with both string and number values) may indicate inconsistent usage that could benefit from normalization.

---

### Index Management Package (`Library/index/`)

A comprehensive vault indexing system that tracks files, links, tags, and duplicates in a SQLite database.

**Package Structure:**
```
Library/index/
├── __init__.py           # Package metadata
├── __main__.py           # Module entry point
├── cli.py                # CLI dispatcher with argparse
├── common.py             # Shared utilities
└── commands/
    ├── __init__.py       # Command base class
    ├── build.py          # Build vault index database
    ├── duplicates.py     # Find and cleanup duplicate files
    ├── rename.py         # Fix mangled filenames
    └── broken_links.py   # Find broken wiki-links
```

**Usage:**
All commands are run from the vault root directory using `vault index`:

```bash
# Build vault index
vault index build

# Find broken wiki-links
vault index broken-links

# Find duplicate files
vault index duplicates find

# Fix mangled filenames
vault index rename find
```

#### Command: broken-links

Find and report broken wiki-links in markdown files.

```bash
vault index broken-links
```

**Features:**
- Queries `vault.db` for unresolved links (is_resolved = 0)
- Groups broken links by source file
- Generates markdown report with wiki-links to source files
- Includes line numbers for each broken link
- Shows both wiki-links (`[[...]]`) and markdown links (`[...](...)`

**Output:**
- `broken-links.md` in vault root
- Frontmatter tags: `vault-management`, `broken-links`
- Statistics: total broken links, affected files
- Grouped by source file with clickable wiki-links

**Report Format:**
```markdown
### [[Source File Name]]

**File:** `path/to/file.md`
**Broken links:** 5

- `[[Broken Link 1]]` (line 42)
- `[[Broken Link 2]]` (line 58)
```

**Note:** Run `vault index build` first to create/update the database.

---

### Deprecated Scripts (superseded by modular packages)

The following individual script files have been replaced by modular packages:

- `find_orphaned_images.py` → Use `vault images find`
- `cleanup_orphaned_images.py` → Use `vault images cleanup`
- `remove_image_alt_text.py` → Use `vault images remove-alt`
- `add_summaries.py`

Finds image files that are not referenced in any markdown files and generates a report with hierarchical checkbox list.

**Usage:**
```bash
/usr/bin/python3 Library/find_orphaned_images.py
```

**Features:**
- Scans for image files (`.png`, `.jpg`, `.jpeg`, `.gif`, `.svg`, `.webp`, `.bmp`, `.ico`)
- Scans all `.md` files for image references in multiple formats:
  - Markdown syntax: `![alt](path/to/image.png)`
  - Obsidian wiki-links: `![[image.png]]`
  - HTML img tags: `<img src="path">`
- Ignores `.obsidian`, `.trash`, and `Excalidraw` directories
- Resolves relative paths and Obsidian-style filename references
- Generates hierarchical report organized by directory structure
- Uses markdown checkboxes and wiki-links for easy navigation and cleanup tracking

**Output:** `orphaned-images.md` in vault root

---

### cleanup_orphaned_images.py

Processes the `orphaned-images.md` file and moves checked-off images to the `.trash` directory.

**Usage:**
```bash
/usr/bin/python3 Library/cleanup_orphaned_images.py
```

**Features:**
- Reads `orphaned-images.md` for checked items (`- [x]`)
- Extracts file paths from wiki-links
- Moves checked files to `.trash` directory
- Preserves directory structure in `.trash`
- Removes empty directories after moving files
- Updates `orphaned-images.md` to remove processed items
- Generates summary report of moved and failed files

**Input:** `orphaned-images.md` in vault root
**Output:** Files moved to `.trash/` directory

---

### remove_image_alt_text.py

Removes alt text from wiki-link image embeds in markdown files.

**Usage:**
```bash
/usr/bin/python3 Library/remove_image_alt_text.py <directory>
/usr/bin/python3 Library/remove_image_alt_text.py <directory> --dry-run
```

**Features:**
- Recursively processes all `.md` files in specified directory
- Converts `![[file.ext|alt text]]` to `![[file.ext]]`
- Supports all common image formats (`.png`, `.jpg`, `.jpeg`, `.gif`, `.svg`, `.webp`, `.bmp`, `.ico`)
- Ignores `.obsidian`, `.trash`, and `Excalidraw` directories
- Dry-run mode to preview changes before applying
- Generates summary report of modified files

**Arguments:**
- `<directory>` - Directory path relative to vault root (use `.` for entire vault)
- `--dry-run` - Preview changes without modifying files

**Examples:**
```bash
# Process entire vault (dry run)
/usr/bin/python3 Library/remove_image_alt_text.py . --dry-run

# Process specific directory
/usr/bin/python3 Library/remove_image_alt_text.py Personal/Software\ Development

# Process with spaces in path
/usr/bin/python3 Library/remove_image_alt_text.py "Personal/Software Development"
```

---

### add_summaries.py

Automatically generates AI-powered summaries for markdown files and adds them to the frontmatter.

**Usage:**
```bash
/usr/bin/python3 Library/add_summaries.py <directory>
/usr/bin/python3 Library/add_summaries.py <directory> --dry-run
/usr/bin/python3 Library/add_summaries.py <directory> --overwrite
```

**Features:**
- Uses Claude API to generate concise 2-4 sentence summaries in plain text (no markdown formatting)
- Recursively processes all `.md` files in specified directory
- Adds `summary:` field to YAML frontmatter
- Skips files without frontmatter
- By default, skips files that already have summaries
- Ignores `.obsidian`, `.trash`, and `Excalidraw` directories
- Dry-run mode to preview changes before applying
- Progress tracking with detailed statistics

**Requirements:**
- `ANTHROPIC_API_KEY` environment variable must be set
- `anthropic` Python package (`pip install anthropic`)

**Arguments:**
- `<directory>` - Directory path relative to vault root
- `--dry-run` - Preview changes without modifying files
- `--overwrite` - Replace existing summaries (default: skip files with summaries)

**Examples:**
```bash
# Set API key first
export ANTHROPIC_API_KEY='your-api-key'

# Process Personal directory (dry run)
/usr/bin/python3 Library/add_summaries.py Personal --dry-run

# Process specific subdirectory
/usr/bin/python3 Library/add_summaries.py "Personal/Software Development"

# Process and overwrite existing summaries
/usr/bin/python3 Library/add_summaries.py Personal --overwrite
```

**Summary Characteristics:**
- 2-4 sentences long
- Captures main concepts and key takeaways
- Mentions specific technical details when relevant
- Informative enough to understand content at a glance
- Professional, clear language
- Plain text only (no markdown formatting)

---

## Common Restrictions

All scripts follow these rules:
- **Ignored directories:**
  - Tag scripts: `.obsidian`, `Excalidraw/Scripts`
  - Image script: `.obsidian`, `.trash`, `Excalidraw`
- **Excalidraw files:** Inline tags are ignored, only YAML frontmatter tags are processed
- **Tag location:** Only YAML frontmatter tags are processed, inline tags (e.g., `#tag`) are ignored

## Requirements

- Python 3.x (tested with Python 3.13)
- Most scripts use standard library only (no external dependencies)
- `add_summaries.py` requires:
  - `anthropic` Python package (`pip install anthropic`)
  - `ANTHROPIC_API_KEY` environment variable
