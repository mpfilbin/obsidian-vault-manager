# Obsidian Vault Manager

A standalone CLI tool for managing Obsidian vaults with comprehensive features for tags, images, properties, and indexing.

## Features

- **Tag Management**: AI-powered tagging, validation, querying, visualization, and hierarchical reorganization
- **Image Management**: Find orphaned images, detect broken references, cleanup, alt text removal
- **Properties Management**: Frontmatter validation, enrichment, normalization, and bulk operations
- **Vault Indexing**: Build searchable index, find broken links, detect duplicates, fix mangled filenames

## Installation

```bash
# Standard installation (when published to PyPI)
pip install obsidian-vault-manager

# With AI features (for tag generation and summaries)
pip install obsidian-vault-manager[ai]

# For development
git clone https://github.com/mfilbin/obsidian-vault-manager.git
cd obsidian-vault-manager
pip install -e ".[dev]"
```

## Quick Start

```bash
# Configure your vault path (one-time setup)
export VAULT_PATH=~/Documents/MyVault

# Or create a config file
mkdir -p ~/.config/vault-manager
echo "vault_path: ~/Documents/MyVault" > ~/.config/vault-manager/config.yaml

# Or specify on each command
vault --vault-path ~/Documents/MyVault tags missing

# Find notes without tags
vault tags missing

# Generate AI-powered tags (requires Anthropic API key)
export ANTHROPIC_API_KEY='your-key'
vault tags add Personal --dry-run

# Find orphaned images
vault images find

# Validate frontmatter
vault properties validate

# Build vault index
vault index build
```

## Configuration

The tool uses a multi-tiered configuration system (in order of precedence):

1. **CLI argument**: `--vault-path /path/to/vault`
2. **Environment variable**: `VAULT_PATH=/path/to/vault`
3. **Config file**: `~/.config/vault-manager/config.yaml`
4. **Auto-detection**: Searches for `.obsidian/` directory in current/parent directories
5. **Interactive prompt**: Asks for path if not found

### Configuration File Example

```yaml
# ~/.config/vault-manager/config.yaml
vault_path: /home/user/Documents/MyVault
```

## Usage

### Tag Management

```bash
# Find notes without tags
vault tags missing

# Update tag index (rebuild vault.db)
vault tags update

# AI-generate tags for notes
vault tags add Personal --dry-run        # Preview
vault tags add Personal                  # Apply
vault tags add Personal --overwrite      # Regenerate existing tags

# Clean and normalize tags
vault tags clean invalid .               # Remove invalid tags
vault tags clean normalize .             # Normalize to lowercase

# Query tag database
vault tags query --stats                 # Database statistics
vault tags query --most-used 10          # Top 10 tags
vault tags query --files-with tag1 tag2  # Files with ALL tags
vault tags query --tag-info software     # Detailed tag info

# Manage tags
vault tags rename old-tag new-tag        # Rename tag
vault tags purge deprecated-tag          # Remove tag from all files
vault tags similar                       # Find similar/duplicate tags

# Visualize and organize
vault tags visualize                     # Generate interactive Canvas
vault tags reorganize                    # Suggest hierarchical structure
```

### Image Management

```bash
# Find orphaned images
vault images find

# Find notes with broken image references
vault images broken

# Clean up checked orphaned images
vault images cleanup

# Remove alt text from image embeds
vault images remove-alt Personal --dry-run
```

### Properties Management

```bash
# Validate frontmatter
vault properties validate

# Auto-repair frontmatter issues
vault properties repair --backup

# Enrich with AI-generated content
vault properties enrich summaries Personal
vault properties enrich related Personal

# Clean and normalize
vault properties clean normalize .
vault properties clean deduplicate .
vault properties clean remove author .

# Bulk set properties
vault properties set status draft Personal
vault properties set priority high Projects --files-with urgent

# Audit properties
vault properties audit
```

### Vault Indexing

```bash
# Build/rebuild vault index
vault index build
vault index build --force                # Force full rebuild

# Find broken wiki-links
vault index broken-links

# Find duplicate files
vault index duplicates find

# Fix mangled filenames
vault index rename find
vault index rename apply
```

## Documentation

- **Configuration Guide**: See `docs/configuration.md` for detailed configuration options
- **Installation Guide**: See `docs/installation.md` for installation instructions
- **Testing Guide**: See `tests/README.md` for testing documentation and best practices
- **Development**: See `docs/development.md` for contributing guidelines

## Requirements

- Python 3.8 or higher
- PyYAML (for config file support)
- Optional: `anthropic` package for AI-powered features

## Privacy & Security

AI-powered commands (`vault tags add`, `vault properties enrich summaries`) automatically skip notes with `sensitive: true` in frontmatter:

```yaml
---
sensitive: true
tags:
  - your-tags
---
```

## License

MIT License - see LICENSE file for details

## Contributing

Contributions are welcome! Please see `docs/development.md` for guidelines.

## Support

- Report issues: [GitHub Issues](https://github.com/mfilbin/obsidian-vault-manager/issues)
- Documentation: [Project Docs](https://github.com/mfilbin/obsidian-vault-manager/tree/main/docs)
