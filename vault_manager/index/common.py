"""
Common utilities for vault indexing.

This module now re-exports common utilities from vault_manager.core for backward compatibility.
Module-specific utilities for file indexing remain here.
New code should import common functions directly from vault_manager.core when possible.
"""

import hashlib
from pathlib import Path
from typing import Optional

# Re-export core utilities
from vault_manager.core import (
    get_vault_root,
    is_ignored_path as core_is_ignored_path,
)


def get_database_path() -> Path:
    """Get the path to the vault.db database file."""
    return get_vault_root() / 'vault.db'


def is_ignored_path(file_path: Path, vault_root: Path) -> bool:
    """
    Check if a file path should be ignored during vault indexing.

    This is a module-specific wrapper around core's is_ignored_path
    with additional ignore rules for the index module.

    Args:
        file_path: Path to check
        vault_root: Vault root directory

    Returns:
        True if path should be ignored, False otherwise

    Ignores:
        - .obsidian directory
        - .trash directory
        - .backup directory
        - Excalidraw directory
    """
    # Use core function with additional Excalidraw ignore
    additional_ignores = {'Excalidraw'}
    return core_is_ignored_path(file_path, vault_root, additional_ignores)


def is_ignored_file(file_path: Path, vault_root: Path) -> bool:
    """
    Check if a specific file should be ignored during vault indexing.

    This checks individual files (not directories) for exclusion patterns.

    Args:
        file_path: Path to file to check
        vault_root: Vault root directory

    Returns:
        True if file should be ignored, False otherwise

    Note:
        This is called after is_ignored_path() directory checks
    """
    filename = file_path.name
    relative_path = file_path.relative_to(vault_root)

    # Ignore SQLite databases in vault root
    if len(relative_path.parts) == 1 and filename.endswith('.db'):
        return True

    # Ignore specific database files anywhere in vault
    ignored_files = {
        'vault.db',
        'tags.db',
    }
    if filename in ignored_files:
        return True

    # Ignore Python cache files
    if filename.endswith('.pyc') or filename.endswith('.pyo'):
        return True

    # Ignore OS-specific files
    if filename in {'.DS_Store', 'Thumbs.db', 'desktop.ini'}:
        return True

    return False


def compute_file_hash(file_path: Path, max_size_mb: int = 100) -> Optional[str]:
    """
    Compute SHA-256 hash of file content.

    Args:
        file_path: Path to file to hash
        max_size_mb: Maximum file size to hash in MB (default: 100)

    Returns:
        64-character hex string SHA-256 hash, or None if file is too large or cannot be read

    Examples:
        >> compute_file_hash(Path('small.txt'))
        'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
        >> compute_file_hash(Path('large_video.mp4'), max_size_mb=10)
        None
    """
    try:
        file_size = file_path.stat().st_size
        max_bytes = max_size_mb * 1024 * 1024

        # Skip files larger than max_size_mb
        if file_size > max_bytes:
            return None

        sha256 = hashlib.sha256()

        # Read file in chunks for memory efficiency
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                sha256.update(chunk)

        return sha256.hexdigest()

    except (OSError, PermissionError, FileNotFoundError):
        return None


def get_file_extension_category(ext: str) -> str:
    """
    Categorize file extension into broad types.

    Args:
        ext: File extension (including dot, e.g., '.md')

    Returns:
        Category: 'markdown', 'image', 'document', 'code', 'data', 'archive', 'other'

    Examples:
        >> get_file_extension_category('.md')
        'markdown'
        >> get_file_extension_category('.png')
        'image'
        >> get_file_extension_category('.pdf')
        'document'
    """
    ext = ext.lower()

    if ext in {'.md', '.markdown'}:
        return 'markdown'

    if ext in {'.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.bmp', '.ico', '.tiff', '.heic'}:
        return 'image'

    if ext in {'.pdf', '.doc', '.docx', '.txt', '.rtf', '.odt'}:
        return 'document'

    if ext in {'.py', '.js', '.ts', '.java', '.c', '.cpp', '.h', '.cs', '.go', '.rs', '.rb', '.php', '.swift', '.kt'}:
        return 'code'

    if ext in {'.json', '.yaml', '.yml', '.xml', '.csv', '.toml', '.ini', '.conf'}:
        return 'data'

    if ext in {'.zip', '.tar', '.gz', '.7z', '.rar', '.bz2'}:
        return 'archive'

    if ext in {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.mp3', '.wav', '.flac'}:
        return 'media'

    if ext in {'.excalidraw', '.excalidraw.md'}:
        return 'drawing'

    return 'other'


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in bytes to human-readable string.

    Args:
        size_bytes: File size in bytes

    Returns:
        Formatted string like '1.5 MB', '500 KB', '2 GB'

    Examples:
        >> format_file_size(1024)
        '1.0 KB'
        >> format_file_size(1536)
        '1.5 KB'
        >> format_file_size(1048576)
        '1.0 MB'
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


def is_text_file(file_path: Path) -> bool:
    """
    Check if a file is likely a text file that can be safely read as UTF-8.

    Args:
        file_path: Path to file

    Returns:
        True if file is likely text, False otherwise

    Note:
        Uses extension-based heuristic for performance
    """
    ext = file_path.suffix.lower()

    text_extensions = {
        '.md', '.markdown', '.txt', '.rtf',
        '.py', '.js', '.ts', '.java', '.c', '.cpp', '.h', '.cs', '.go', '.rs', '.rb', '.php', '.swift', '.kt',
        '.json', '.yaml', '.yml', '.xml', '.csv', '.toml', '.ini', '.conf',
        '.html', '.htm', '.css', '.scss', '.sass', '.less',
        '.sh', '.bash', '.zsh', '.fish',
        '.sql', '.r', '.m', '.mm',
        '.log', '.config', '.gitignore', '.dockerignore',
        '.excalidraw.md'
    }

    return ext in text_extensions


def format_timestamp(timestamp: float) -> str:
    """
    Format Unix timestamp to ISO 8601 string.

    Args:
        timestamp: Unix timestamp (seconds since epoch)

    Returns:
        ISO 8601 formatted string (YYYY-MM-DD HH:MM:SS)

    Examples:
        >> format_timestamp(1640000000.0)
        '2021-12-20 13:33:20'
    """
    from datetime import datetime
    return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
