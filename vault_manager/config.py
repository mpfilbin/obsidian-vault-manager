"""
Configuration management for vault-manager.

Handles vault path resolution with multi-tiered precedence:
1. CLI argument (--vault-path)
2. Environment variable (VAULT_PATH)
3. Config file (~/.config/vault-manager/config.yaml)
4. .obsidian marker detection (search up directory tree)
5. Interactive prompt (with option to save)
"""

import os
import sys
from pathlib import Path
from typing import Optional

try:
    import yaml
except ImportError:
    yaml = None


DEFAULT_CONFIG_PATH = Path.home() / ".config" / "vault-manager" / "config.yaml"


def find_vault_by_marker(start_path: Optional[Path] = None) -> Optional[Path]:
    """
    Search for .obsidian marker directory starting from current dir.

    Similar to how git searches for .git directory.

    Args:
        start_path: Starting directory (defaults to current working directory)

    Returns:
        Path to vault root if found, None otherwise
    """
    if start_path is None:
        start_path = Path.cwd()

    current = start_path.resolve()

    # Search up to root
    while current != current.parent:
        obsidian_dir = current / ".obsidian"
        if obsidian_dir.exists() and obsidian_dir.is_dir():
            return current
        current = current.parent

    return None


def load_config(config_path: Optional[Path] = None) -> dict:
    """
    Load configuration from YAML file.

    Args:
        config_path: Path to config file (defaults to ~/.config/vault-manager/config.yaml)

    Returns:
        Configuration dictionary (empty dict if file doesn't exist or can't be loaded)
    """
    if yaml is None:
        return {}

    if config_path is None:
        config_path = DEFAULT_CONFIG_PATH

    if not config_path.exists():
        return {}

    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            return config if config is not None else {}
    except Exception as e:
        print(f"Warning: Failed to load config from {config_path}: {e}", file=sys.stderr)
        return {}


def save_config(vault_path: Path, config_path: Optional[Path] = None) -> None:
    """
    Save vault path to config file.

    Args:
        vault_path: Vault path to save
        config_path: Path to config file (defaults to ~/.config/vault-manager/config.yaml)
    """
    if yaml is None:
        print("Warning: PyYAML not installed. Cannot save config file.", file=sys.stderr)
        print("Install with: pip install pyyaml", file=sys.stderr)
        return

    if config_path is None:
        config_path = DEFAULT_CONFIG_PATH

    # Create config directory if it doesn't exist
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing config and update vault_path
    config = load_config(config_path)
    config['vault_path'] = str(vault_path)

    try:
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        print(f"Saved vault path to {config_path}")
    except Exception as e:
        print(f"Error: Failed to save config to {config_path}: {e}", file=sys.stderr)


def prompt_for_vault_path() -> Optional[Path]:
    """
    Interactively prompt user for vault path.

    Returns:
        Vault path if valid, None otherwise
    """
    print("\nNo vault path found.")
    print("Please enter the path to your Obsidian vault:")

    try:
        vault_path_str = input("> ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled.")
        return None

    if not vault_path_str:
        return None

    vault_path = Path(vault_path_str).expanduser().resolve()

    if not vault_path.exists():
        print(f"Error: Path does not exist: {vault_path}")
        return None

    if not vault_path.is_dir():
        print(f"Error: Path is not a directory: {vault_path}")
        return None

    # Verify it's an Obsidian vault
    if not (vault_path / ".obsidian").exists():
        print(f"Warning: No .obsidian directory found at {vault_path}")
        try:
            response = input("Continue anyway? (y/n) > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.")
            return None

        if response != 'y':
            return None

    # Ask to save to config
    try:
        response = input(f"\nSave this path to config file? (y/n) > ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\nNot saved.")
        return vault_path

    if response == 'y':
        save_config(vault_path)

    return vault_path


def resolve_vault_path(
    cli_arg: Optional[str] = None,
    env_var: str = "VAULT_PATH",
    config_path: Optional[Path] = None,
    allow_interactive: bool = True
) -> Path:
    """
    Resolve vault path using multi-tiered precedence.

    Priority order (first match wins):
    1. CLI argument (highest priority)
    2. Environment variable
    3. Config file
    4. .obsidian marker detection
    5. Interactive prompt (if allowed)

    Args:
        cli_arg: Explicit path from CLI argument (highest priority)
        env_var: Environment variable name to check (default: VAULT_PATH)
        config_path: Path to config file (defaults to ~/.config/vault-manager/config.yaml)
        allow_interactive: Whether to prompt user if no path found (default: True)

    Returns:
        Resolved vault path

    Raises:
        SystemExit: If vault path cannot be resolved
    """
    # 1. CLI argument (highest priority)
    if cli_arg:
        vault_path = Path(cli_arg).expanduser().resolve()
        if not vault_path.exists():
            print(f"Error: Vault path from --vault-path does not exist: {vault_path}")
            sys.exit(1)
        if not vault_path.is_dir():
            print(f"Error: Vault path from --vault-path is not a directory: {vault_path}")
            sys.exit(1)
        return vault_path

    # 2. Environment variable
    env_path = os.environ.get(env_var)
    if env_path:
        vault_path = Path(env_path).expanduser().resolve()
        if not vault_path.exists():
            print(f"Error: Vault path from {env_var} does not exist: {vault_path}")
            print(f"Environment variable value: {env_path}")
            sys.exit(1)
        if not vault_path.is_dir():
            print(f"Error: Vault path from {env_var} is not a directory: {vault_path}")
            sys.exit(1)
        return vault_path

    # 3. Config file
    if yaml is not None:
        config = load_config(config_path)
        if 'vault_path' in config:
            vault_path = Path(config['vault_path']).expanduser().resolve()
            if not vault_path.exists():
                print(f"Error: Vault path from config does not exist: {vault_path}")
                print(f"Config file: {config_path or DEFAULT_CONFIG_PATH}")
                sys.exit(1)
            if not vault_path.is_dir():
                print(f"Error: Vault path from config is not a directory: {vault_path}")
                sys.exit(1)
            return vault_path

    # 4. .obsidian marker detection
    vault_path = find_vault_by_marker()
    if vault_path:
        return vault_path

    # 5. Interactive prompt (if allowed)
    if allow_interactive:
        vault_path = prompt_for_vault_path()
        if vault_path:
            return vault_path

    # Failed to resolve
    print("\nError: Could not determine vault path.")
    print("\nPlease specify vault path using one of:")
    print("  1. CLI argument: --vault-path /path/to/vault")
    print(f"  2. Environment variable: export {env_var}=/path/to/vault")
    print(f"  3. Config file: {config_path or DEFAULT_CONFIG_PATH}")
    print("  4. Run from within an Obsidian vault (contains .obsidian/)")
    if yaml is None:
        print("\nNote: PyYAML not installed. Install with 'pip install pyyaml' for config file support.")
    sys.exit(1)
