"""
Command base classes for vault indexing.

This module now re-exports the Command class from vault_manager.core for backward compatibility.
All vault indexing commands inherit from this base class.
"""

# Re-export core Command class for backward compatibility
from vault_manager.core.command import Command

__all__ = ['Command']
