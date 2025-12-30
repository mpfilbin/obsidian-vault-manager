"""
Validation and error handling utilities.

This module provides common validation functions and error handling
patterns used across all Library commands, including library imports,
API keys, and file path validation.
"""

import os
import sys
from pathlib import Path
from typing import Optional


def require_library(
    module_name: str,
    import_name: Optional[str] = None,
    pip_package: Optional[str] = None,
    purpose: Optional[str] = None
) -> None:
    """
    Check if an optional library is installed and exit with helpful message if not.

    Args:
        module_name: Python module name to import (e.g., 'anthropic')
        import_name: Optional specific import to check (e.g., 'Anthropic')
        pip_package: Optional pip package name if different from module_name
        purpose: Optional description of what the library is used for

    Raises:
        SystemExit: If library is not installed

    Examples:
        >>> require_library('anthropic', 'Anthropic', purpose='AI tag generation')
        >>> require_library('yaml', pip_package='pyyaml', purpose='YAML processing')
    """
    try:
        module = __import__(module_name)
        if import_name:
            getattr(module, import_name)
    except (ImportError, AttributeError):
        pip_name = pip_package or module_name
        print(f"Error: {module_name} library not installed")
        if purpose:
            print(f"This library is required for: {purpose}")
        print(f"\nInstall it with:")
        print(f"  pip install {pip_name}")
        sys.exit(1)


def check_api_key(env_var: str, service_name: str) -> str:
    """
    Check if an API key environment variable is set.

    Args:
        env_var: Environment variable name (e.g., 'ANTHROPIC_API_KEY')
        service_name: Service name for error message (e.g., 'Anthropic')

    Returns:
        API key value

    Raises:
        SystemExit: If environment variable is not set

    Examples:
        >>> api_key = check_api_key('ANTHROPIC_API_KEY', 'Anthropic')
    """
    api_key = os.environ.get(env_var)
    if not api_key:
        print(f"Error: {env_var} environment variable not set")
        print(f"\nSet it with:")
        print(f"  export {env_var}='your-api-key'")
        sys.exit(1)

    return api_key


def validate_file_path(
    file_path_arg: str,
    vault_root: Path,
    must_exist: bool = True,
    must_be_markdown: bool = True
) -> Path:
    """
    Validate and resolve a file path argument.

    Args:
        file_path_arg: File path argument (relative to vault root)
        vault_root: Vault root directory
        must_exist: Whether file must exist (default True)
        must_be_markdown: Whether file must be a markdown file (default True)

    Returns:
        Resolved Path object

    Raises:
        SystemExit: If validation fails

    Examples:
        >>> vault_root = Path('/vault')
        >>> file_path = validate_file_path('notes/test.md', vault_root)
    """
    file_path = vault_root / file_path_arg

    if must_exist:
        if not file_path.exists():
            print(f"Error: File not found: {file_path_arg}")
            print(f"Looking for: {file_path}")
            sys.exit(1)

        if not file_path.is_file():
            print(f"Error: Not a file: {file_path_arg}")
            sys.exit(1)

    if must_be_markdown:
        if not file_path.suffix == '.md':
            print(f"Error: Not a markdown file: {file_path_arg}")
            print(f"File must have .md extension")
            sys.exit(1)

        if file_path.name.endswith('.excalidraw.md'):
            print(f"Error: Excalidraw files not supported: {file_path_arg}")
            sys.exit(1)

    return file_path
