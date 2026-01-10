"""
Visualize command - Generate Obsidian Canvas of tag hierarchy.

This module implements the visualize command which generates an Obsidian Canvas
showing the hierarchical structure of tags with interactive node layout.
"""

import json
import random
import sqlite3
import sys
from argparse import ArgumentParser, Namespace
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Tuple

from . import Command
from ..common import get_vault_root
from vault_manager.index.common import get_database_path


class VisualizeCommand(Command):
    """Command to visualize tag hierarchy as an Obsidian Canvas."""

    @staticmethod
    def configure_parser(parser: ArgumentParser) -> None:
        """Configure the argument parser for the visualize command."""
        parser.add_argument(
            '--output',
            type=str,
            default='tag-hierarchy.canvas',
            help='Output filename (default: tag-hierarchy.canvas)'
        )
        parser.add_argument(
            '--min-count',
            type=int,
            default=2,
            help='Minimum files per tag to include (default: 2)'
        )

    def execute(self, args: Namespace) -> None:
        """Execute the visualize command."""
        vault_root = get_vault_root()
        db_path = get_database_path()

        # Check if database exists
        if not db_path.exists():
            print(f"Error: Database not found: {db_path}")
            print("\nGenerate it first with:")
            print("  vault tags update")
            sys.exit(1)

        # Query tag data
        tag_data = self._query_tag_data(db_path, args.min_count)

        if not tag_data:
            print("No tags found in database")
            sys.exit(1)

        # Analyze tag hierarchy
        hierarchy = self._analyze_hierarchy(tag_data)

        # Generate Canvas JSON
        canvas_data = self._generate_canvas(hierarchy, tag_data)

        # Write output file
        output_path = vault_root / args.output
        self._write_output(output_path, canvas_data)

        print(f"\nTag hierarchy canvas generated: {args.output}")
        print(f"Total tags: {len(tag_data)}")
        print(f"Top-level tags: {len(hierarchy['top_level'])}")
        print(f"Nested tags: {len(hierarchy['nested_tags'])}")
        print(f"Total nodes: {len(canvas_data['nodes'])}")
        print(f"Total edges: {len(canvas_data['edges'])}")

    def _query_tag_data(self, db_path: Path, min_count: int) -> Dict[str, int]:
        """
        Query tag data from database.

        Args:
            db_path: Path to vault.db
            min_count: Minimum file count threshold

        Returns:
            Dictionary mapping tag names to file counts
        """
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT ft.tag, COUNT(*) as file_count
                FROM file_tags ft
                GROUP BY ft.tag
                HAVING file_count >= ?
                ORDER BY ft.tag
            ''', (min_count,))

            tag_data = {tag: count for tag, count in cursor.fetchall()}

        return tag_data

    def _analyze_hierarchy(self, tag_data: Dict[str, int]) -> Dict[str, any]:
        """
        Analyze tag hierarchy structure.

        Args:
            tag_data: Dictionary of tags and their counts

        Returns:
            Dictionary containing hierarchy information
        """
        top_level = set()
        nested = {}  # parent -> set of children
        nested_tags = set()  # all nested tags
        depths = {}
        tag_to_parent = {}  # tag -> parent tag

        for tag in tag_data.keys():
            if '/' in tag:
                # This is a nested tag
                parts = tag.split('/')
                depth = len(parts) - 1
                depths[tag] = depth
                nested_tags.add(tag)

                # Track relationships
                for i in range(len(parts)):
                    if i == 0:
                        # Only add to top_level if it exists in tag_data
                        if parts[0] in tag_data:
                            top_level.add(parts[0])
                    else:
                        parent = '/'.join(parts[:i])
                        child = '/'.join(parts[:i+1])

                        # Only track relationships for tags that exist in tag_data
                        if child in tag_data:
                            if parent not in nested:
                                nested[parent] = set()
                            nested[parent].add(child)
                            tag_to_parent[child] = parent
            else:
                # Top-level tag
                top_level.add(tag)
                depths[tag] = 0

        return {
            'top_level': top_level,
            'nested': nested,
            'nested_tags': nested_tags,
            'depths': depths,
            'tag_to_parent': tag_to_parent
        }

    def _generate_node_id(self) -> str:
        """Generate a random 16-character hex ID for a node."""
        return ''.join(random.choices('0123456789abcdef', k=16))

    def _get_node_color(self, count: int, max_count: int) -> str:
        """
        Get node color based on usage count.

        Args:
            count: File count for this tag
            max_count: Maximum file count across all tags

        Returns:
            Color code (1-6)
        """
        if max_count == 0:
            return "1"

        ratio = count / max_count
        if ratio >= 0.8:
            return "5"  # Red/pink for most used
        elif ratio >= 0.6:
            return "4"  # Orange
        elif ratio >= 0.4:
            return "3"  # Yellow
        elif ratio >= 0.2:
            return "2"  # Green
        else:
            return "1"  # Blue/default

    def _calculate_subtree_width(self, tag: str, hierarchy: Dict[str, any],
                                 tag_data: Dict[str, int], node_width: int,
                                 h_spacing: int, widths_cache: Dict[str, int]) -> int:
        """
        Calculate the total width needed for a tag and all its descendants.

        Args:
            tag: Tag to calculate width for
            hierarchy: Tag hierarchy structure
            tag_data: Tag counts
            node_width: Width of a single node
            h_spacing: Horizontal spacing between nodes
            widths_cache: Cache to store calculated widths

        Returns:
            Total width needed for this subtree
        """
        if tag in widths_cache:
            return widths_cache[tag]

        # If no children, width is just this node
        if tag not in hierarchy['nested']:
            widths_cache[tag] = node_width
            return node_width

        # Get children that exist in tag_data
        children = [c for c in hierarchy['nested'][tag] if c in tag_data]

        if not children:
            widths_cache[tag] = node_width
            return node_width

        # Calculate total width of all children's subtrees
        children_total_width = sum(
            self._calculate_subtree_width(child, hierarchy, tag_data, node_width, h_spacing, widths_cache)
            for child in children
        )

        # Add spacing between children
        children_total_width += (len(children) - 1) * h_spacing

        # Width is the maximum of node width and children width
        subtree_width = max(node_width, children_total_width)
        widths_cache[tag] = subtree_width

        return subtree_width

    def _calculate_layout(self, hierarchy: Dict[str, any], tag_data: Dict[str, int]) -> Dict[str, Tuple[int, int]]:
        """
        Calculate node positions using a hierarchical tree layout with no overlaps.

        Args:
            hierarchy: Tag hierarchy structure
            tag_data: Tag counts

        Returns:
            Dictionary mapping tags to (x, y) positions
        """
        positions = {}

        # Layout parameters
        NODE_WIDTH = 250
        NODE_HEIGHT = 100
        HORIZONTAL_SPACING = 100  # Increased spacing
        VERTICAL_SPACING = 200

        # Root node position
        ROOT_X = 0
        ROOT_Y = 0

        positions['ROOT'] = (ROOT_X, ROOT_Y)

        # Sort top-level tags by file count (descending) for better visual balance
        sorted_top_level = sorted(
            [t for t in hierarchy['top_level'] if t in tag_data],
            key=lambda t: tag_data[t],
            reverse=True
        )

        if not sorted_top_level:
            return positions

        # Calculate width needed for each top-level tag's subtree
        widths_cache = {}
        subtree_widths = []
        for tag in sorted_top_level:
            width = self._calculate_subtree_width(tag, hierarchy, tag_data,
                                                 NODE_WIDTH, HORIZONTAL_SPACING, widths_cache)
            subtree_widths.append(width)

        # Calculate total width needed
        total_width = sum(subtree_widths) + (len(sorted_top_level) - 1) * HORIZONTAL_SPACING

        # Start x position (centered)
        current_x = ROOT_X - total_width / 2
        level_y = ROOT_Y + VERTICAL_SPACING

        # Position each top-level tag and its subtree
        for tag, subtree_width in zip(sorted_top_level, subtree_widths):
            # Center the tag within its allocated subtree width
            tag_x = current_x + subtree_width / 2
            positions[tag] = (int(tag_x), level_y)

            # Recursively position children within this subtree's allocated space
            self._position_subtree(tag, positions, hierarchy, tag_data,
                                 current_x, subtree_width, level_y,
                                 NODE_WIDTH, NODE_HEIGHT, HORIZONTAL_SPACING,
                                 VERTICAL_SPACING, widths_cache)

            # Move to next subtree position
            current_x += subtree_width + HORIZONTAL_SPACING

        return positions

    def _position_subtree(self, parent: str, positions: Dict[str, Tuple[int, int]],
                         hierarchy: Dict[str, any], tag_data: Dict[str, int],
                         subtree_left: float, subtree_width: float, parent_y: int,
                         node_width: int, node_height: int,
                         h_spacing: int, v_spacing: int,
                         widths_cache: Dict[str, int]) -> None:
        """
        Position children nodes within the allocated subtree space.

        Args:
            parent: Parent tag
            positions: Dictionary to store positions
            hierarchy: Tag hierarchy structure
            tag_data: Tag counts
            subtree_left: Left edge of allocated space for this subtree
            subtree_width: Total width allocated for this subtree
            parent_y: Y position of parent
            node_width: Width of a single node
            node_height: Height of a single node
            h_spacing: Horizontal spacing
            v_spacing: Vertical spacing
            widths_cache: Cache of calculated subtree widths
        """
        if parent not in hierarchy['nested']:
            return

        # Get children that exist in tag_data
        children = sorted([c for c in hierarchy['nested'][parent] if c in tag_data],
                         key=lambda c: tag_data[c], reverse=True)

        if not children:
            return

        # Calculate child positions
        child_y = parent_y + node_height + v_spacing
        current_x = subtree_left

        for child in children:
            child_width = widths_cache.get(child, node_width)

            # Center the child within its allocated width
            child_x = current_x + child_width / 2
            positions[child] = (int(child_x), child_y)

            # Recursively position this child's subtree
            self._position_subtree(child, positions, hierarchy, tag_data,
                                 current_x, child_width, child_y,
                                 node_width, node_height, h_spacing, v_spacing,
                                 widths_cache)

            # Move to next child position
            current_x += child_width + h_spacing

    def _generate_canvas(self, hierarchy: Dict[str, any], tag_data: Dict[str, int]) -> Dict:
        """
        Generate Obsidian Canvas JSON.

        Args:
            hierarchy: Tag hierarchy structure
            tag_data: Tag counts

        Returns:
            Canvas JSON structure
        """
        nodes = []
        edges = []
        node_ids = {}  # tag -> node_id

        # Calculate layout
        positions = self._calculate_layout(hierarchy, tag_data)

        # Find max count for color scaling
        max_count = max(tag_data.values()) if tag_data else 1

        # Create root node
        root_id = self._generate_node_id()
        node_ids['ROOT'] = root_id
        root_x, root_y = positions.get('ROOT', (0, 0))

        nodes.append({
            "id": root_id,
            "type": "text",
            "text": "# Tag Hierarchy\n\n**Total Tags:** " + str(len(tag_data)),
            "x": root_x - 125,  # Center the root node
            "y": root_y - 60,
            "width": 250,
            "height": 120,
            "color": "6",
            "styleAttributes": {
                "textAlign": "center"
            }
        })

        # Create nodes for all tags
        for tag, count in tag_data.items():
            # Skip tags that weren't positioned (shouldn't happen, but safety check)
            if tag not in positions:
                continue

            node_id = self._generate_node_id()
            node_ids[tag] = node_id

            # Get position
            x, y = positions[tag]

            # Get display name (just the last part for nested tags)
            display_name = tag.split('/')[-1] if '/' in tag else tag

            # Node text
            node_text = f"**{display_name}**\n\n{count} files"
            if '/' in tag:
                node_text = f"{display_name}\n\n{count} files"

            # Node color based on usage
            color = self._get_node_color(count, max_count)

            nodes.append({
                "id": node_id,
                "type": "text",
                "text": node_text,
                "x": x - 125,  # Center nodes on their position
                "y": y - 50,
                "width": 250,
                "height": 100,
                "color": color,
                "styleAttributes": {
                    "textAlign": "center"
                }
            })

        # Create edges
        # Connect root to top-level tags
        for tag in hierarchy['top_level']:
            if tag in tag_data and tag in node_ids:
                edge_id = self._generate_node_id()
                edges.append({
                    "id": edge_id,
                    "fromNode": root_id,
                    "fromSide": "bottom",
                    "toNode": node_ids[tag],
                    "toSide": "top"
                })

        # Connect parent tags to children
        # Only create edges if both parent and child exist in tag_data
        for parent, children in hierarchy['nested'].items():
            if parent in tag_data and parent in node_ids:
                for child in children:
                    if child in tag_data and child in node_ids:
                        edge_id = self._generate_node_id()
                        edges.append({
                            "id": edge_id,
                            "fromNode": node_ids[parent],
                            "fromSide": "bottom",
                            "toNode": node_ids[child],
                            "toSide": "top"
                        })

        return {
            "nodes": nodes,
            "edges": edges
        }

    def _write_output(self, output_path: Path, canvas_data: Dict) -> None:
        """
        Write the Canvas JSON file.

        Args:
            output_path: Path to output file
            canvas_data: Canvas JSON data
        """
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(canvas_data, f, indent=2)
