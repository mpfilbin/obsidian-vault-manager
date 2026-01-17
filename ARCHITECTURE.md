# Architecture Documentation

## Overview

Obsidian Vault Manager is a domain-driven CLI tool for managing Obsidian vaults. The architecture follows modular design principles with clear separation of concerns between infrastructure, domain logic, and command execution.

**Core Design Principles:**
- Domain delegation pattern for CLI organization
- Command pattern for operation dispatch
- Database-driven canonical source of truth
- Global vault root management
- Dry-run support across all modification commands
- Extensible command registration

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     CLI Entry Point                         │
│                  (vault_manager/cli.py)                     │
│  - Parse global options (--vault-path, --no-interactive)    │
│  - Resolve vault path via config system                     │
│  - Set global vault root                                    │
│  - Delegate to domain CLI                                   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
       ┌────────────────────┴───────────────────┐
       │                                        │
┌──────▼────────┐  ┌──────────────┐  ┌────────▼────────┐
│  Domain CLI   │  │  Domain CLI  │  │   Domain CLI    │
│  (tags/cli)   │  │ (images/cli) │  │(properties/cli) │
│               │  │              │  │                 │
│ - Subcommand  │  │ - Subcommand │  │  - Subcommand   │
│   parsing     │  │   parsing    │  │    parsing      │
│ - Command     │  │ - Command    │  │  - Command      │
│   dispatch    │  │   dispatch   │  │    dispatch     │
└───────┬───────┘  └──────┬───────┘  └────────┬────────┘
        │                 │                    │
        ▼                 ▼                    ▼
┌───────────────────────────────────────────────────────┐
│              Command Implementations                  │
│         (vault_manager/{domain}/commands/)            │
│                                                       │
│  Each command inherits from Command base class       │
│  - configure_parser(parser)                          │
│  - execute(args)                                     │
└───────┬───────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────┐
│                  Core Services                        │
│            (vault_manager/core/)                      │
│                                                       │
│  - vault.py: Vault operations & global root          │
│  - database.py: SQLite database utilities            │
│  - frontmatter_manager.py: YAML frontmatter ops      │
│  - file_ops.py: Safe file read/write                 │
│  - dry_run.py: Dry-run context & tracking            │
│  - validation.py: Input validation                   │
└───────┬───────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────┐
│              Data Layer (vault.db)                    │
│                                                       │
│  - files: File metadata & frontmatter flags          │
│  - tags: Tag names & counts                          │
│  - file_tags: Tag-to-file relationships              │
│  - links: Wiki-links & resolution status             │
│  - metadata: Build timestamp & stats                 │
└───────────────────────────────────────────────────────┘
```

## Directory Structure

```
obsidian-vault-manager/
├── vault_manager/               # Main package
│   ├── cli.py                   # Top-level CLI entry point
│   ├── __main__.py              # Alternative entry point (python -m)
│   ├── config.py                # Multi-tiered vault path resolution
│   │
│   ├── core/                    # Shared core utilities
│   │   ├── command.py           # Abstract Command base class
│   │   ├── vault.py             # Vault operations & global root
│   │   ├── database.py          # Database utilities
│   │   ├── frontmatter_manager.py  # Frontmatter operations
│   │   ├── file_ops.py          # Safe file operations
│   │   ├── dry_run.py           # Dry-run infrastructure
│   │   └── validation.py        # Input validation
│   │
│   ├── tags/                    # Tag management domain
│   │   ├── cli.py               # Domain CLI
│   │   ├── common.py            # Domain-specific utilities
│   │   └── commands/            # Command implementations
│   │       ├── missing.py       # Find untagged notes
│   │       ├── add.py           # AI tag generation
│   │       ├── clean.py         # Remove invalid tags
│   │       ├── purge.py         # Remove specific tags
│   │       ├── rename.py        # Rename tags
│   │       ├── query.py         # Query tag database
│   │       ├── similar.py       # Find similar tags
│   │       ├── visualize.py     # Generate tag hierarchy
│   │       └── reorganize.py    # Suggest tag organization
│   │
│   ├── images/                  # Image management domain
│   │   ├── cli.py
│   │   └── commands/
│   │       ├── find.py          # Find orphaned images
│   │       ├── broken.py        # Find broken image links
│   │       ├── cleanup.py       # Remove orphaned images
│   │       └── remove_alt.py    # Remove alt text
│   │
│   ├── properties/              # Properties management domain
│   │   ├── cli.py
│   │   └── commands/
│   │       ├── enrich.py        # AI enrichment (summaries, related)
│   │       ├── clean.py         # Clean/normalize properties
│   │       ├── validate.py      # Validate frontmatter
│   │       ├── repair.py        # Auto-repair validation issues
│   │       ├── set.py           # Bulk set properties
│   │       └── audit.py         # Property usage report
│   │
│   └── index/                   # Vault indexing domain
│       ├── cli.py
│       └── commands/
│           ├── build.py         # Build/rebuild vault.db
│           ├── broken_links.py  # Find broken wiki-links
│           ├── duplicates.py    # Find duplicate files
│           └── rename.py        # Find/fix mangled filenames
│
├── tests/                       # Test suite
│   ├── unit/                    # Traditional unit tests
│   ├── features/                # BDD feature files (Gherkin)
│   ├── step_defs/               # BDD step definitions
│   ├── fixtures/                # Test data & fixtures
│   └── conftest.py              # Shared pytest fixtures
│
├── pyproject.toml               # Package metadata & dependencies
├── CLAUDE.md                    # Development guidance for Claude Code
├── ARCHITECTURE.md              # This file
└── README.md                    # User-facing documentation
```

## Architectural Patterns

### 1. Domain Delegation Pattern

The top-level CLI delegates to domain-specific CLIs by manipulating `sys.argv`:

**Flow:**
1. **Top-level CLI** (`vault_manager/cli.py`):
   - Parses `--vault-path` and `--no-interactive` global options
   - Resolves vault path using configuration system
   - Sets global vault root via `vault.set_vault_root()`
   - Identifies target domain (tags, images, properties, index)
   - Imports domain CLI module dynamically
   - Manipulates `sys.argv` to simulate direct invocation
   - Delegates to domain CLI's `main()` function

2. **Domain CLI** (e.g., `vault_manager/tags/cli.py`):
   - Creates domain-specific argument parser with subcommands
   - Parses remaining command-line arguments
   - Maps command name to command class
   - Instantiates and executes command

**Benefits:**
- Clean separation between domains
- Each domain can evolve independently
- No monolithic command registry
- Domain CLIs can be tested in isolation

### 2. Command Pattern

Every command inherits from the abstract `Command` base class:

```python
from abc import ABC, abstractmethod
from argparse import ArgumentParser, Namespace

class Command(ABC):
    @abstractmethod
    def execute(self, args: Namespace) -> None:
        """Execute the command with parsed arguments."""
        pass

    @staticmethod
    @abstractmethod
    def configure_parser(parser: ArgumentParser) -> None:
        """Configure the argument parser for this command."""
        pass
```

**Implementation Example:**

```python
class MissingCommand(Command):
    @staticmethod
    def configure_parser(parser: ArgumentParser) -> None:
        # Add command-specific arguments
        parser.add_argument('--format', choices=['md', 'json'])

    def execute(self, args: Namespace) -> None:
        # Command logic
        vault_root = get_vault_root()
        # ... implementation
```

**Benefits:**
- Consistent interface across all commands
- Self-contained command modules
- Easy to add new commands
- Testable in isolation

### 3. Global Vault Root Management

Vault root is set once at startup and accessed globally:

```python
# Set at CLI startup (vault_manager/cli.py)
from vault_manager.core.vault import set_vault_root
set_vault_root(vault_path)

# Access anywhere in command execution
from vault_manager.core.vault import get_vault_root
vault_root = get_vault_root()
```

**Benefits:**
- Avoids passing vault_root through function chains
- Single source of truth for vault location
- Simplifies command implementations
- Prevents vault path inconsistencies

### 4. Database-Driven Architecture

SQLite database (`vault.db`) serves as canonical source of truth:

**Schema:**

```sql
-- File metadata
CREATE TABLE files (
    path TEXT PRIMARY KEY,
    size INTEGER,
    extension TEXT,
    has_frontmatter BOOLEAN,
    is_sensitive BOOLEAN,
    hash TEXT  -- For duplicate detection
);

-- Tags
CREATE TABLE tags (
    tag TEXT PRIMARY KEY,
    count INTEGER
);

-- Tag-to-file relationships
CREATE TABLE file_tags (
    file_path TEXT,
    tag TEXT,
    FOREIGN KEY (file_path) REFERENCES files(path),
    FOREIGN KEY (tag) REFERENCES tags(tag)
);

-- Wiki-links
CREATE TABLE links (
    source_path TEXT,
    target_link TEXT,
    resolved_path TEXT,
    is_broken BOOLEAN,
    FOREIGN KEY (source_path) REFERENCES files(path)
);

-- Metadata
CREATE TABLE metadata (
    key TEXT PRIMARY KEY,
    value TEXT
);
```

**Database Utilities:**
- `rebuild_vault_database()` - Rebuild entire database
- `require_database()` - Check database exists before command
- `database_exists()` - Check if vault.db exists
- `get_database_stats()` - Query database statistics
- `rebuild_if_needed()` - Conditional rebuild with skip support
- `@auto_rebuild_after` - Decorator for automatic rebuild

**Rebuild Pattern:**

Many commands automatically rebuild the database after making changes:

```python
from vault_manager.core.database import auto_rebuild_after

class PurgeCommand(Command):
    @auto_rebuild_after()
    def execute(self, args):
        # Remove tags from files
        # ...
        # Database will be rebuilt automatically unless --no-rebuild flag is set
```

## Configuration System

Multi-tiered vault path resolution (implemented in `vault_manager/config.py`):

**Priority Order (first match wins):**

1. **CLI Argument** (`--vault-path`): Highest priority
2. **Environment Variable** (`VAULT_PATH`): Second priority
3. **Config File** (`~/.config/vault-manager/config.yaml`): Third priority
4. **Auto-Detection**: Search for `.obsidian/` directory up tree (like git)
5. **Interactive Prompt**: Ask user and optionally save to config

**Functions:**

```python
resolve_vault_path(
    cli_arg=None,
    env_var="VAULT_PATH",
    config_path=None,
    allow_interactive=True
) -> Path
```

**Benefits:**
- Flexible vault specification
- Developer-friendly auto-detection
- CI/CD-friendly (environment variables)
- User-friendly (config file, interactive prompt)

## Core Services

### Vault Operations (`vault_manager/core/vault.py`)

**Key Functions:**

- `set_vault_root(path)` - Set global vault root (called once at startup)
- `get_vault_root()` - Access global vault root
- `is_ignored_path(path, vault_root, additional_ignores)` - Check ignore rules
- `validate_directory(dir_arg, vault_root)` - Validate directory paths
- `get_markdown_files(directory, vault_root)` - Recursively find `.md` files
- `iter_markdown_files(directory, vault_root)` - Memory-efficient iteration
- `count_markdown_files(directory, vault_root)` - Count files for progress

**Default Ignore Patterns:**
- `.obsidian/` - Obsidian configuration
- `.trash/` - Deleted files
- `.backup/` - Backup files
- Domain-specific ignores (e.g., `Excalidraw/` for images)

### Frontmatter Operations (`vault_manager/core/frontmatter_manager.py`)

**Key Functions:**

- `extract_frontmatter(content)` - Parse YAML frontmatter
- `extract_tags_from_frontmatter(content)` - Get tags from frontmatter
- `is_valid_obsidian_tag(tag)` - Validate against Obsidian rules
- `is_sensitive_note(content)` - Check for `sensitive: true` flag

**Tag Validation Rules (Obsidian):**
- Only: letters, numbers, `_`, `-`, `/` (for nested tags)
- Must contain at least one letter or underscore
- Cannot be all numeric (e.g., `2024` is invalid, `y2024` is valid)

### File Operations (`vault_manager/core/file_ops.py`)

**Safe file read/write with error handling:**

- `safe_read(file_path)` - Read file with encoding detection
- `safe_write(file_path, content)` - Write file with backup
- Line ending normalization (`\r\n` and `\r` → `\n`)

### Dry-Run Infrastructure (`vault_manager/core/dry_run.py`)

**OperationStats Class:**

Tracks operation statistics:

```python
stats = OperationStats()
stats.increment('files_processed')
stats.increment('tags_added', 5)
stats.to_dict()  # {'files_processed': 1, 'tags_added': 5, ...}
```

**DryRunContext Class:**

Context manager for dry-run operations:

```python
with DryRunContext(dry_run=args.dry_run) as ctx:
    for file in files:
        if should_modify:
            ctx.record_change(file, "Added tags", tags=['foo', 'bar'])
            if ctx.would_modify(file):
                # Actually modify file
                pass
            ctx.stats.increment('files_modified')

print_dry_run_summary(ctx)
```

**Benefits:**
- Consistent dry-run behavior across all commands
- Centralized change tracking
- Standardized summary output
- Preview mode for all modifications

## Data Flow

### Command Execution Flow

```
1. User invokes CLI
   $ vault --vault-path ~/vault tags add Personal

2. Top-level CLI (vault_manager/cli.py)
   - Parses global options: vault_path="~/vault"
   - Resolves vault path: resolve_vault_path(cli_arg="~/vault")
   - Sets global vault root: set_vault_root(Path("~/vault"))
   - Identifies domain: "tags"
   - Imports: vault_manager.tags.cli
   - Manipulates sys.argv: ['vault tags', 'add', 'Personal']
   - Delegates: tags.cli.main()

3. Domain CLI (vault_manager/tags/cli.py)
   - Creates parser with subcommands
   - Parses args: command='add', directory='Personal'
   - Maps command: 'add' → AddCommand
   - Instantiates: cmd = AddCommand()
   - Executes: cmd.execute(args)

4. Command (vault_manager/tags/commands/add.py)
   - Gets vault root: vault_root = get_vault_root()
   - Validates directory: target_dir = validate_directory(args.directory, vault_root)
   - Finds markdown files: md_files = get_markdown_files(target_dir, vault_root)
   - Processes files: Add tags using AI
   - Rebuilds database: rebuild_vault_database() (if not --no-rebuild)
```

### Database Rebuild Flow

```
1. Command modifies files (e.g., tag purge, rename, normalize)

2. Command calls rebuild_vault_database()
   OR
   Command decorated with @auto_rebuild_after

3. Database rebuild (vault_manager/index/commands/build.py)
   - Scans all markdown files
   - Extracts metadata (size, extension, frontmatter flags)
   - Extracts tags from frontmatter
   - Extracts wiki-links from content
   - Computes file hashes (for duplicate detection)
   - Writes to vault.db SQLite database

4. Database available for queries
   - Tag queries: vault tags query --stats
   - Link queries: vault index broken-links
   - Duplicate detection: vault index duplicates find
```

## Extension Points

### Adding a New Command

1. **Create Command Class** (`vault_manager/{domain}/commands/my_command.py`):

```python
from argparse import ArgumentParser, Namespace
from vault_manager.core.command import Command
from vault_manager.core.vault import get_vault_root

class MyCommand(Command):
    @staticmethod
    def configure_parser(parser: ArgumentParser) -> None:
        parser.add_argument('--option', help='An option')
        parser.add_argument('--dry-run', action='store_true')

    def execute(self, args: Namespace) -> None:
        vault_root = get_vault_root()
        # Command logic here
```

2. **Register in Domain CLI** (`vault_manager/{domain}/cli.py`):

```python
from .commands.my_command import MyCommand

def create_parser():
    # ...
    my_parser = subparsers.add_parser('my-command', help='My command')
    MyCommand.configure_parser(my_parser)
    # ...

def main():
    # ...
    command_map = {
        'my-command': MyCommand,
        # ...
    }
    # ...
```

3. **Import in Domain Commands** (`vault_manager/{domain}/commands/__init__.py`):

```python
from .my_command import MyCommand

__all__ = ['MyCommand', ...]
```

### Adding a New Domain

1. **Create Domain Directory Structure:**

```
vault_manager/
└── my_domain/
    ├── __init__.py
    ├── cli.py
    ├── common.py (optional)
    └── commands/
        ├── __init__.py
        └── my_command.py
```

2. **Implement Domain CLI** (`vault_manager/my_domain/cli.py`):

Follow the pattern from existing domains (tags, images, properties, index).

3. **Register in Top-Level CLI** (`vault_manager/cli.py`):

```python
# Add to create_parser()
subparsers.add_parser('my-domain', help='My domain', add_help=False)

# Add to domain_map in main()
domain_map = {
    'my-domain': 'vault_manager.my_domain.cli',
    # ...
}
```

## Key Design Decisions

### Why Domain Delegation?

**Alternative:** Monolithic CLI with all commands in one registry

**Decision:** Domain delegation pattern

**Rationale:**
- Better code organization (domains can evolve independently)
- Clear ownership boundaries
- Easier testing (test each domain in isolation)
- Scalable (adding new domains doesn't affect existing ones)
- Domain-specific help text and documentation

### Why Global Vault Root?

**Alternative:** Pass vault_root as argument through function chains

**Decision:** Global vault root set once at startup

**Rationale:**
- Reduces function signature complexity
- Vault root is truly global (doesn't change during execution)
- Simplifies command implementations
- Single source of truth
- Easier refactoring (no need to thread vault_root everywhere)

### Why SQLite Database?

**Alternative:** Scan files on every query

**Decision:** Maintain vault.db SQLite database as canonical source

**Rationale:**
- Fast queries (no need to scan thousands of files)
- Complex queries possible (SQL)
- Relationship tracking (tags, links, files)
- Duplicate detection (hashes)
- Historical metadata (build timestamps)
- Trade-off: Must rebuild after modifications (automated with `@auto_rebuild_after`)

### Why Command Pattern?

**Alternative:** Function-based commands

**Decision:** Class-based Command pattern with abstract base class

**Rationale:**
- Enforces consistent interface (`execute`, `configure_parser`)
- Better encapsulation (command state, helper methods)
- Easier testing (can mock/stub specific commands)
- Clear contract for command implementations
- Extensible (decorators like `@auto_rebuild_after`)

### Why Multi-Tiered Configuration?

**Alternative:** Single configuration source (e.g., CLI arg only)

**Decision:** 5-tier resolution (CLI → env → config → auto-detect → prompt)

**Rationale:**
- Flexibility (different workflows: CI/CD, development, user)
- Developer-friendly (auto-detection like git)
- User-friendly (config file, interactive prompt)
- Override capability (CLI arg always wins)
- No surprise behavior (clear precedence order)

## Testing Architecture

### Test Organization

```
tests/
├── unit/                    # Traditional unit tests
│   ├── test_config.py
│   ├── test_vault.py
│   └── test_commands.py
│
├── features/                # BDD feature files (Gherkin)
│   ├── tags.feature
│   ├── images.feature
│   └── properties.feature
│
├── step_defs/               # BDD step definitions
│   ├── test_tag_steps.py
│   └── test_image_steps.py
│
├── fixtures/                # Test data
│   ├── sample_vault/
│   └── test_files/
│
└── conftest.py              # Shared pytest fixtures
```

### Common Fixtures

**Vault Fixtures:**
- `temp_vault` - Temporary vault directory
- `vault_with_notes` - Vault with sample markdown notes
- `mock_vault_root` - Mocks `get_vault_root()`

**Database Fixtures:**
- `vault_database` - Empty vault.db database
- `populated_database` - Database with sample data

### Test Markers

Categorize tests with pytest markers:

```python
@pytest.mark.unit           # Unit tests
@pytest.mark.bdd            # BDD tests
@pytest.mark.tags           # Tag management tests
@pytest.mark.images         # Image management tests
@pytest.mark.properties     # Properties tests
@pytest.mark.index          # Index management tests
@pytest.mark.slow           # Slow tests
@pytest.mark.requires_vault # Needs real vault
@pytest.mark.requires_ai    # Needs AI API key
```

**Run specific test categories:**

```bash
pytest -m unit              # Unit tests only
pytest -m bdd               # BDD tests only
pytest -m "not slow"        # Skip slow tests
```

## Performance Considerations

### Memory Efficiency

**Problem:** Large vaults with thousands of files can consume significant memory

**Solutions:**
1. **Iterator-based file processing:**
   - `iter_markdown_files()` yields files one at a time
   - `count_markdown_files()` counts without loading into memory

2. **Streaming database writes:**
   - Build command processes files in batches
   - Commits to database periodically

3. **Lazy loading:**
   - Only read file contents when needed
   - Skip ignored directories early (prune walk tree)

### Database Performance

**Optimizations:**
1. **Indexes on frequently queried columns:**
   - `files.path` (PRIMARY KEY)
   - `tags.tag` (PRIMARY KEY)
   - `file_tags.file_path`, `file_tags.tag` (FOREIGN KEYS)

2. **Batch inserts:**
   - Build command uses batched inserts
   - Reduced transaction overhead

3. **Query optimization:**
   - Use SQL for complex queries instead of Python filtering
   - Leverage database indexes

## Security Considerations

### Privacy Protection

**Sensitive Notes:**
- Notes with `sensitive: true` in frontmatter are skipped by AI commands
- `is_sensitive_note()` checks frontmatter before AI processing

**Benefits:**
- Prevents sensitive information from being sent to external APIs
- User control over what gets processed

### File System Safety

**Safe File Operations:**
- `safe_write()` creates backups before overwriting
- `safe_read()` handles encoding errors gracefully
- Dry-run mode previews all modifications

**Ignore Patterns:**
- `.obsidian/` protected from modifications
- `.trash/` and `.backup/` excluded from processing

### Input Validation

**Path Validation:**
- `validate_directory()` ensures paths are within vault
- Prevents directory traversal attacks
- Resolves symlinks carefully

**Tag Validation:**
- `is_valid_obsidian_tag()` enforces Obsidian rules
- Prevents malformed tag injection

## Future Architecture Considerations

### Plugin System

**Potential Extension:**
- Command plugins loaded from `~/.config/vault-manager/plugins/`
- Register custom commands without modifying core code

### Event System

**Potential Extension:**
- Pre/post hooks for command execution
- Event subscribers for file modifications
- Audit logging

### Parallel Processing

**Potential Optimization:**
- Process markdown files in parallel (thread/process pool)
- Parallel tag extraction and link resolution
- Trade-off: Complexity vs speed for large vaults

### Remote Vault Support

**Potential Feature:**
- Support for remote vaults (SSH, cloud storage)
- Abstracted file system layer
- Caching strategies for remote access

## Conclusion

The Obsidian Vault Manager architecture is designed for:
- **Modularity:** Domain delegation and command pattern
- **Maintainability:** Clear separation of concerns, consistent interfaces
- **Extensibility:** Easy to add new commands and domains
- **Performance:** Database-driven queries, memory-efficient iteration
- **User Experience:** Dry-run support, flexible configuration, helpful error messages
- **Developer Experience:** Well-organized codebase, comprehensive testing, clear patterns

The architecture balances simplicity with flexibility, making it easy to understand, extend, and maintain while handling the complexity of managing large Obsidian vaults.
