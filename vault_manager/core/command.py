"""
Base command class for all Library commands.

This module provides the abstract base class that all command
implementations must inherit from, enforcing a consistent interface
across all Library modules (tags, images, properties, index).
"""

from abc import ABC, abstractmethod
from argparse import ArgumentParser, Namespace


class Command(ABC):
    """
    Abstract base class for all vault maintenance commands.

    All command classes in Library modules must inherit from this class
    and implement the execute() and configure_parser() methods.

    Examples:
        >>> class MyCommand(Command):
        ...     @staticmethod
        ...     def configure_parser(parser):
        ...         parser.add_argument('--option', help='An option')
        ...     def execute(self, args):
        ...         print(f"Executing with option: {args.option}")
    """

    @abstractmethod
    def execute(self, args: Namespace) -> None:
        """
        Execute the command with parsed arguments.

        Args:
            args: Parsed command-line arguments from ArgumentParser

        Raises:
            NotImplementedError: If subclass doesn't implement this method
        """
        pass

    @staticmethod
    @abstractmethod
    def configure_parser(parser: ArgumentParser) -> None:
        """
        Configure the argument parser for this command.

        Subclasses should add command-specific arguments to the parser.

        Args:
            parser: ArgumentParser or subparser to configure

        Raises:
            NotImplementedError: If subclass doesn't implement this method
        """
        pass
