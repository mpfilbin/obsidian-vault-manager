# Installation Guide

## Prerequisites

- Python 3.8 or higher
- pip (Python package installer)
- Git (for development installation)

Check your Python version:

```bash
python3 --version
```

## Installation Methods

### Method 1: From PyPI (Recommended - when published)

```bash
# Standard installation
pip install obsidian-vault-manager

# With AI features (tag generation, summaries)
pip install obsidian-vault-manager[ai]

# With testing dependencies
pip install obsidian-vault-manager[test]

# With all development dependencies
pip install obsidian-vault-manager[dev]
```

### Method 2: From Source (Development)

```bash
# Clone the repository
git clone https://github.com/mfilbin/obsidian-vault-manager.git
cd obsidian-vault-manager

# Install in development mode
pip install -e .

# Or with AI features
pip install -e ".[ai]"

# Or with all development dependencies
pip install -e ".[dev]"
```

Development mode (`-e` flag) allows you to modify the code and see changes immediately without reinstalling.

### Method 3: From Local Directory

```bash
cd /path/to/vault-manager
pip install .
```

## Verifying Installation

After installation, verify the `vault` command is available:

```bash
vault --help
```

You should see the help message with available commands.

## Post-Installation Setup

### 1. Configure Vault Path

Choose one of these methods:

**Option A: Environment Variable**
```bash
export VAULT_PATH=~/Documents/MyVault
echo 'export VAULT_PATH=~/Documents/MyVault' >> ~/.bashrc
```

**Option B: Config File**
```bash
mkdir -p ~/.config/vault-manager
echo "vault_path: ~/Documents/MyVault" > ~/.config/vault-manager/config.yaml
```

**Option C: Use Auto-Detection**

Just run vault commands from within your vault directory.

### 2. (Optional) Configure AI Features

If you installed with AI features:

```bash
export ANTHROPIC_API_KEY='your-api-key-here'
echo 'export ANTHROPIC_API_KEY=your-key' >> ~/.bashrc
```

Get an API key from: https://console.anthropic.com/

### 3. Test the Installation

```bash
# Test basic commands
vault tags --help
vault images --help

# Build vault index
vault index build

# Find notes without tags
vault tags missing
```

## Upgrading

### From PyPI

```bash
pip install --upgrade obsidian-vault-manager
```

### From Source

```bash
cd vault-manager
git pull origin main
pip install -e ".[dev]"
```

## Uninstalling

```bash
pip uninstall obsidian-vault-manager
```

Remove configuration files (optional):

```bash
rm -rf ~/.config/vault-manager
```

## Troubleshooting

### "command not found: vault"

The installation directory may not be in your PATH. Find where pip installed it:

```bash
pip show obsidian-vault-manager
```

Add the scripts directory to your PATH:

```bash
export PATH="$PATH:$HOME/.local/bin"
echo 'export PATH="$PATH:$HOME/.local/bin"' >> ~/.bashrc
```

### "No module named 'vault_manager'"

The package wasn't installed correctly. Try:

```bash
pip uninstall obsidian-vault-manager
pip install obsidian-vault-manager
```

### "ImportError: No module named 'anthropic'"

AI features require the anthropic package:

```bash
pip install anthropic
# Or reinstall with AI features
pip install obsidian-vault-manager[ai]
```

### "ImportError: No module named 'yaml'"

Config file support requires PyYAML:

```bash
pip install pyyaml
```

### Permission Errors

If you get permission errors during installation:

```bash
# Install for current user only
pip install --user obsidian-vault-manager

# Or use a virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate
pip install obsidian-vault-manager
```

## Virtual Environment (Recommended)

Using a virtual environment isolates dependencies:

```bash
# Create virtual environment
python3 -m venv ~/venv/vault-manager
source ~/venv/vault-manager/bin/activate

# Install vault-manager
pip install obsidian-vault-manager[ai]

# Use vault commands
vault tags missing

# Deactivate when done
deactivate
```

Add to your shell profile for convenience:

```bash
echo 'alias vault-activate="source ~/venv/vault-manager/bin/activate"' >> ~/.bashrc
```

## Platform-Specific Notes

### Linux

Standard installation should work on all distributions.

### macOS

```bash
# Install Python 3 if not already installed
brew install python3

# Install vault-manager
pip3 install obsidian-vault-manager
```

### Windows (WSL)

vault-manager works in Windows Subsystem for Linux:

```bash
# Install Python if needed
sudo apt update
sudo apt install python3 python3-pip

# Install vault-manager
pip3 install obsidian-vault-manager

# Configure vault path (Windows path example)
export VAULT_PATH=/mnt/c/Users/YourName/Documents/MyVault
```

### Windows (Native)

Native Windows support may have path-related issues. WSL is recommended.

## Development Setup

For contributing to vault-manager:

```bash
# Clone repository
git clone https://github.com/mfilbin/obsidian-vault-manager.git
cd obsidian-vault-manager

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode with all dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=vault_manager

# Format code
black vault_manager tests

# Lint code
ruff check vault_manager tests
```

## See Also

- [Configuration Guide](configuration.md)
- [Main README](../README.md)
- [Command Reference](README.md)
