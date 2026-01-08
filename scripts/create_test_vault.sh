#!/bin/bash
# create_test_vault.sh
# Creates a test vault for validating DryRunContext refactoring

set -e  # Exit on error

# Configuration
DEFAULT_VAULT_PATH="$HOME/Documents/Test Vault"
VAULT_PATH="${1:-$DEFAULT_VAULT_PATH}"

echo "=========================================="
echo "Creating Test Vault for Manual Testing"
echo "=========================================="
echo "Vault path: $VAULT_PATH"
echo ""

# Confirm or exit
read -p "This will create/overwrite the vault at the above path. Continue? (y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
fi

# Clean and create vault directory
rm -rf "$VAULT_PATH"
mkdir -p "$VAULT_PATH"

# Create Obsidian config directory
mkdir -p "$VAULT_PATH/.obsidian"
cat > "$VAULT_PATH/.obsidian/app.json" << 'EOF'
{
  "alwaysUpdateLinks": true,
  "newLinkFormat": "shortest",
  "useMarkdownLinks": false
}
EOF

# Create main directories
mkdir -p "$VAULT_PATH/notes"
mkdir -p "$VAULT_PATH/docs"
mkdir -p "$VAULT_PATH/projects"
mkdir -p "$VAULT_PATH/archive"

# Create nested directory structure for depth testing
mkdir -p "$VAULT_PATH/deep/level1/level2/level3/level4/level5/level6"

echo "✓ Created directory structure"

# ============================================================================
# Test Suite 1: Tags Purge - Files with various tag configurations
# ============================================================================

cat > "$VAULT_PATH/notes/note1.md" << 'EOF'
---
tags: [Foo, bar, test-tag]
created: 2024-01-01
---

# Note 1

This is a test note with mixed-case tags.
It should be affected by purge, rename, and normalize operations.
EOF

cat > "$VAULT_PATH/notes/note2.md" << 'EOF'
---
tags: [FOO, baz, test-tag]
created: 2024-01-02
---

# Note 2

Another test note with uppercase FOO tag.
Links to [[note1]].
EOF

cat > "$VAULT_PATH/notes/note3.md" << 'EOF'
---
tags: [foo, Bar, BAZ]
created: 2024-01-03
---

# Note 3

This note has mixed case tags: foo, Bar, BAZ.
Should be normalized to lowercase.
EOF

# ============================================================================
# Test Suite 2: Tags Rename - Files with tags to rename
# ============================================================================

cat > "$VAULT_PATH/notes/note5.md" << 'EOF'
---
tags: [old-tag, other]
created: 2024-01-05
---

# Note 5

This note has the old-tag that should be renamed.
EOF

cat > "$VAULT_PATH/notes/note6.md" << 'EOF'
---
tags: [old-tag, another]
created: 2024-01-06
---

# Note 6

Another note with old-tag for rename testing.
EOF

# ============================================================================
# Test Suite 3: Tags Add - Files needing AI tag generation
# ============================================================================

cat > "$VAULT_PATH/notes/note4.md" << 'EOF'
---
tags: []
created: 2024-01-04
---

# Note 4 - Python Web Development

This note discusses building web applications with Python and Flask.
It covers routing, templates, database integration, and deployment strategies.
The Flask framework provides a lightweight approach to web development.
EOF

cat > "$VAULT_PATH/notes/no-tags.md" << 'EOF'
---
created: 2024-01-10
---

# Machine Learning Basics

An introduction to machine learning concepts including supervised learning,
unsupervised learning, and neural networks. Covers common algorithms like
linear regression, decision trees, and k-means clustering.
EOF

cat > "$VAULT_PATH/notes/has-tags.md" << 'EOF'
---
tags: [existing, should-skip]
created: 2024-01-11
---

# Note with Existing Tags

This note already has tags and should be skipped unless --overwrite is used.
EOF

# ============================================================================
# Test Suite 4: Sensitive Notes
# ============================================================================

cat > "$VAULT_PATH/notes/sensitive.md" << 'EOF'
---
tags: [personal]
sensitive: true
created: 2024-01-07
---

# Sensitive Note

This note contains private information and should be skipped by AI commands.
It has the sensitive: true flag in frontmatter.
EOF

# ============================================================================
# Test Suite 5: Properties Summarize - Files needing summaries
# ============================================================================

cat > "$VAULT_PATH/docs/doc1.md" << 'EOF'
---
tags: [documentation]
created: 2024-01-08
---

# Documentation Standards

This document outlines the documentation standards for the project.
All code should be well-documented with clear docstrings.
README files should include installation instructions, usage examples,
and contribution guidelines. Use Markdown for all documentation files.
EOF

cat > "$VAULT_PATH/docs/doc2.md" << 'EOF'
---
tags: [documentation]
summary: "This document already has a summary and should be skipped by default."
created: 2024-01-09
---

# Existing Summary Document

This document already has a summary field in its frontmatter.
It should be skipped by the summarize command unless --overwrite is used.
EOF

# ============================================================================
# Test Suite 6: Properties Relate - Files with topical relationships
# ============================================================================

cat > "$VAULT_PATH/projects/python.md" << 'EOF'
---
tags: [python, programming, language]
created: 2024-01-15
---

# Python Programming Language

Python is a high-level, interpreted programming language known for its
readability and simplicity. It supports multiple programming paradigms
including object-oriented, functional, and procedural programming.

Key features:
- Dynamic typing
- Automatic memory management
- Extensive standard library
- Large ecosystem of third-party packages

Related: [[flask]], [[django]]
EOF

cat > "$VAULT_PATH/projects/flask.md" << 'EOF'
---
tags: [python, flask, web, framework]
created: 2024-01-16
---

# Flask Web Framework

Flask is a lightweight WSGI web application framework written in Python.
It's designed to be simple and easy to use, making it perfect for small
to medium web applications.

Features:
- Built-in development server
- RESTful request dispatching
- Jinja2 templating
- Support for unit testing

Based on [[python]]. Compare with [[django]].
EOF

cat > "$VAULT_PATH/projects/django.md" << 'EOF'
---
tags: [python, django, web, framework]
created: 2024-01-17
---

# Django Web Framework

Django is a high-level Python web framework that encourages rapid development
and clean, pragmatic design. It follows the model-template-view (MTV)
architectural pattern.

Features:
- ORM (Object-Relational Mapping)
- Admin interface
- Authentication system
- Template engine

Built on [[python]]. Alternative to [[flask]].
EOF

cat > "$VAULT_PATH/projects/java.md" << 'EOF'
---
tags: [java, programming, language]
created: 2024-01-18
---

# Java Programming Language

Java is a high-level, class-based, object-oriented programming language
designed to have as few implementation dependencies as possible.
It's widely used for enterprise applications.

Key features:
- Write once, run anywhere (WORA)
- Strongly typed
- Automatic garbage collection
- Rich API and libraries

Unrelated to [[python]] - different ecosystem.
EOF

cat > "$VAULT_PATH/projects/react.md" << 'EOF'
---
tags: [javascript, react, web, frontend]
created: 2024-01-19
---

# React JavaScript Library

React is a JavaScript library for building user interfaces.
It lets you create reusable UI components and manage application state
efficiently using a virtual DOM.

Features:
- Component-based architecture
- JSX syntax
- One-way data binding
- Large ecosystem
EOF

# ============================================================================
# Test Suite 7: Files with existing related field
# ============================================================================

cat > "$VAULT_PATH/projects/has-related.md" << 'EOF'
---
tags: [test]
related: [old-relation-1, old-relation-2]
created: 2024-01-20
---

# Note with Existing Relations

This note already has a related field and should be skipped unless --overwrite.
EOF

# ============================================================================
# Test Suite 8: Error Handling - Files with issues
# ============================================================================

cat > "$VAULT_PATH/notes/no-frontmatter.md" << 'EOF'
# Note Without Frontmatter

This note has no YAML frontmatter at all.
It should be skipped by commands that require frontmatter.
EOF

cat > "$VAULT_PATH/notes/invalid-yaml.md" << 'EOF'
---
tags: [foo
invalid yaml here
no closing bracket
---

# Invalid YAML

This note has malformed YAML frontmatter.
It should be caught gracefully with an error message.
EOF

cat > "$VAULT_PATH/notes/empty-frontmatter.md" << 'EOF'
---
---

# Empty Frontmatter

This note has empty frontmatter.
EOF

# ============================================================================
# Test Suite 9: Deep Directory Testing
# ============================================================================

cat > "$VAULT_PATH/deep/level1/note-depth1.md" << 'EOF'
---
tags: [depth-test]
---

# Depth Level 1
EOF

cat > "$VAULT_PATH/deep/level1/level2/note-depth2.md" << 'EOF'
---
tags: [depth-test]
---

# Depth Level 2
EOF

cat > "$VAULT_PATH/deep/level1/level2/level3/note-depth3.md" << 'EOF'
---
tags: [depth-test]
---

# Depth Level 3
EOF

cat > "$VAULT_PATH/deep/level1/level2/level3/level4/note-depth4.md" << 'EOF'
---
tags: [depth-test]
---

# Depth Level 4
EOF

cat > "$VAULT_PATH/deep/level1/level2/level3/level4/level5/note-depth5.md" << 'EOF'
---
tags: [depth-test]
---

# Depth Level 5
EOF

cat > "$VAULT_PATH/deep/level1/level2/level3/level4/level5/level6/note-depth6.md" << 'EOF'
---
tags: [depth-test]
---

# Depth Level 6 - Should be ignored by max_depth=5
EOF

# ============================================================================
# Test Suite 10: Archive with various patterns
# ============================================================================

cat > "$VAULT_PATH/archive/archived-note.md" << 'EOF'
---
tags: [archive, OLD-TAG]
created: 2023-12-01
---

# Archived Note

This is an old note that should still be processed by commands.
EOF

echo "✓ Created test markdown files"

# ============================================================================
# Create .gitignore for test vault
# ============================================================================

cat > "$VAULT_PATH/.gitignore" << 'EOF'
.obsidian/workspace*
.obsidian/cache
.trash/
vault.db
vault.db-*
EOF

# ============================================================================
# Build the vault database
# ============================================================================

echo ""
echo "Building vault database..."
cd "$VAULT_PATH"

# Check if vault command is available
if ! command -v vault &> /dev/null; then
    echo "⚠ Warning: 'vault' command not found."
    echo "   Please install vault-manager and run: vault index build"
    echo "   in the test vault directory."
else
    vault index build
    echo "✓ Built vault database"
fi

# ============================================================================
# Create README for test vault
# ============================================================================

cat > "$VAULT_PATH/README.md" << 'EOF'
# Test Vault for DryRunContext Refactoring

This vault was automatically generated for testing the refactored commands.

## Structure

- `notes/` - Test notes with various tag configurations
  - Mixed-case tags (Foo, BAR, baz)
  - Tags to purge (test-tag)
  - Tags to rename (old-tag)
  - Sensitive notes
  - Invalid YAML
  - No frontmatter

- `docs/` - Documentation notes
  - Some with existing summaries
  - Some needing summaries

- `projects/` - Project notes with topical relationships
  - Python, Flask, Django (related topics)
  - Java (unrelated)
  - React (different domain)

- `archive/` - Archived notes

- `deep/` - Nested directories for depth testing (6 levels)

## Test Data Summary

| File | Tags | Purpose |
|------|------|---------|
| notes/note1.md | Foo, bar, test-tag | Purge, rename, normalize |
| notes/note2.md | FOO, baz, test-tag | Purge, normalize |
| notes/note3.md | foo, Bar, BAZ | Normalize |
| notes/note4.md | [] | AI tag generation |
| notes/note5.md | old-tag, other | Rename |
| notes/note6.md | old-tag, another | Rename |
| notes/sensitive.md | personal | Sensitive flag test |
| notes/no-tags.md | (none) | AI tag generation |
| notes/has-tags.md | existing | Skip/overwrite test |
| notes/no-frontmatter.md | (none) | Error handling |
| notes/invalid-yaml.md | (invalid) | Error handling |
| docs/doc1.md | documentation | AI summary generation |
| docs/doc2.md | documentation | Has summary (skip) |
| projects/python.md | python, programming | Relate test |
| projects/flask.md | python, flask, web | Relate test |
| projects/django.md | python, django, web | Relate test |
| projects/java.md | java, programming | Relate test |
| projects/react.md | javascript, react | Relate test |
| projects/has-related.md | test | Has related (skip) |

## Database

Run `vault index build` to create the initial database.

## Usage

Follow the MANUAL_TEST_PLAN.md in the main repository to test each command.
EOF

# ============================================================================
# Summary and next steps
# ============================================================================

echo ""
echo "=========================================="
echo "✓ Test Vault Created Successfully"
echo "=========================================="
echo "Location: $VAULT_PATH"
echo ""
echo "Files created:"
find "$VAULT_PATH" -name "*.md" | wc -l | xargs echo "  Markdown files:"
echo "  Total directories: $(find "$VAULT_PATH" -type d | wc -l | xargs)"
echo ""
echo "Next steps:"
echo "  1. cd $VAULT_PATH"
echo "  2. Review README.md for vault structure"
echo "  3. Follow MANUAL_TEST_PLAN.md to run tests"
echo ""
echo "Quick test commands:"
echo "  vault tags purge test-tag --dry-run"
echo "  vault tags rename old-tag new-tag --dry-run"
echo "  vault tags clean normalize . --dry-run"
echo "  vault tags add notes --dry-run --max-files 2"
echo "  vault properties enrich related projects --dry-run"
echo "  vault properties enrich summaries docs --dry-run"
echo ""
echo "⚠ Note: AI commands require ANTHROPIC_API_KEY environment variable"
echo "=========================================="
