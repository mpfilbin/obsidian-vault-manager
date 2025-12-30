#!/usr/bin/env python3
"""
Library - Main entry point for 'python -m Library' invocation.

This module serves as the top-level entry point when the Library package
is invoked as a module. It delegates to the unified CLI dispatcher.
"""

from .cli import main

if __name__ == '__main__':
    main()
