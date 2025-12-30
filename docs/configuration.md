# Configuration Guide

## Overview

vault-manager uses a flexible multi-tiered configuration system to locate your Obsidian vault.

## Configuration Methods (Priority Order)

### 1. CLI Argument (Highest Priority)

Specify vault path directly on the command line:

```bash
vault --vault-path ~/Documents/MyVault tags missing
vault -v ~/Documents/MyVault tags query --stats
```

**Pros**: Maximum flexibility, works for one-off commands or scripts
**Cons**: Verbose, must specify every time

### 2. Environment Variable

Set the `VAULT_PATH` environment variable:

```bash
# Temporary (current session)
export VAULT_PATH=~/Documents/MyVault
vault tags missing

# Permanent (add to ~/.bashrc or ~/.zshrc)
echo 'export VAULT_PATH=~/Documents/MyVault' >> ~/.bashrc
source ~/.bashrc
```

**Pros**: Simple, works across all terminals
**Cons**: Global setting, harder to manage multiple vaults

### 3. Config File

Create a YAML configuration file at `~/.config/vault-manager/config.yaml`:

```yaml
vault_path: /home/user/Documents/MyVault
```

Setup:

```bash
mkdir -p ~/.config/vault-manager
echo "vault_path: ~/Documents/MyVault" > ~/.config/vault-manager/config.yaml
```

**Pros**: Persistent, clean, supports future configuration options
**Cons**: Requires PyYAML package

### 4. Auto-Detection

Run commands from within your vault directory:

```bash
cd ~/Documents/MyVault
vault tags missing
```

vault-manager will search for `.obsidian/` directory in the current and parent directories (similar to how git works).

**Pros**: Zero configuration if working from vault
**Cons**: Only works when in vault directory tree

### 5. Interactive Prompt

If no vault path is found, vault-manager will prompt you:

```
No vault path found.
Please enter the path to your Obsidian vault:
> ~/Documents/MyVault

Save this path to config file? (y/n) > y
Saved vault path to /home/user/.config/vault-manager/config.yaml
```

**Pros**: User-friendly, one-time setup
**Cons**: Not suitable for non-interactive scripts

## Disabling Interactive Prompts

For scripts or CI/CD environments, use `--no-interactive`:

```bash
vault --no-interactive tags missing
```

This will exit with an error if no vault path can be determined automatically.

## Multiple Vaults

To work with multiple vaults:

### Option 1: Use CLI argument

```bash
vault --vault-path ~/Vaults/Personal tags missing
vault --vault-path ~/Vaults/Work tags missing
```

### Option 2: Use different environment variables

```bash
# In your shell profile
alias vault-personal="VAULT_PATH=~/Vaults/Personal vault"
alias vault-work="VAULT_PATH=~/Vaults/Work vault"

vault-personal tags missing
vault-work tags missing
```

### Option 3: Use directory-based auto-detection

```bash
cd ~/Vaults/Personal && vault tags missing
cd ~/Vaults/Work && vault tags missing
```

## Troubleshooting

### "Error: Could not determine vault path"

Make sure you've configured the vault path using one of the methods above.

Verify configuration:

```bash
# Check environment variable
echo $VAULT_PATH

# Check config file
cat ~/.config/vault-manager/config.yaml

# Try with explicit path
vault --vault-path ~/Documents/MyVault tags --help
```

### "Warning: PyYAML not installed"

Config file support requires PyYAML:

```bash
pip install pyyaml
```

Or install with all dependencies:

```bash
pip install obsidian-vault-manager[dev]
```

### "Error: Vault path from config does not exist"

The configured path no longer exists. Update it:

```bash
# Edit config file
nano ~/.config/vault-manager/config.yaml

# Or set environment variable
export VAULT_PATH=~/Documents/NewVault
```

## Advanced Configuration

### Custom Config File Location

While not currently supported, you can use environment variables to achieve similar results:

```bash
export VAULT_PATH=$(grep vault_path ~/my-custom-config.yaml | cut -d: -f2 | xargs)
vault tags missing
```

### Scripting Best Practices

For reliable scripts:

```bash
#!/bin/bash
set -e  # Exit on error

# Explicit configuration
export VAULT_PATH=~/Documents/MyVault

# Or use CLI argument
VAULT_PATH=~/Documents/MyVault

# Disable interactive prompts
vault --no-interactive --vault-path "$VAULT_PATH" tags missing
```

## See Also

- [Installation Guide](installation.md)
- [Main README](../README.md)
- [Command Reference](README.md)
