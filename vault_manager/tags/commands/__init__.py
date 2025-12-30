"""
Command base classes for tag management.

This module now re-exports the Command class from vault_manager.core for backward compatibility.
All tag management commands inherit from this base class.
"""

# Re-export core Command class for backward compatibility
from vault_manager.core.command import Command

__all__ = ['Command']
