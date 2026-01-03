#!/usr/bin/env python3
"""
Script to fix common Django template syntax errors.
Run this script to automatically fix:
1. Missing spaces around == operators
2. Split template variables across lines
"""

import os
import re
from pathlib import Path


def fix_operator_spacing(content):
    """Fix missing spaces around == operators in template conditions."""
    # Pattern: word=='value' -> word == 'value'
    content = re.sub(r"(\w+)=='", r"\1 == '", content)
    content = re.sub(r"(\w+)==\"", r'\1 == "', content)
    return content


def fix_split_template_variables(content):
    """Fix template variables split across lines."""
    # Fix {{ at end of line followed by }} on next line
    # This handles cases like:
    # {{ variable
    #    |filter }}
    lines = content.split('\n')
    fixed_lines = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Check if line ends with {{ and doesn't have closing }}
        if '{{' in line and '}}' not in line:
            # Find the closing }} in subsequent lines
            combined = line
            j = i + 1
            while j < len(lines):
                combined += ' ' + lines[j].strip()
                if '}}' in lines[j]:
                    break
                j += 1

            # Clean up extra spaces
            combined = re.sub(r'\s+', ' ', combined)
            fixed_lines.append(combined)
            i = j + 1
        # Check if line starts with content that should be on previous line
        elif line.strip().startswith('}}') and i > 0 and '{{' in fixed_lines[-1] and '}}' not in fixed_lines[-1]:
            # Merge with previous line
            fixed_lines[-1] = fixed_lines[-1].rstrip() + ' ' + line.strip()
            fixed_lines[-1] = re.sub(r'\s+', ' ', fixed_lines[-1])
            i += 1
        else:
            fixed_lines.append(line)
            i += 1

    return '\n'.join(fixed_lines)


def fix_split_template_tags(content):
    """Fix template tags split across lines."""
    # Fix {% at end of line followed by %} on next line
    lines = content.split('\n')
    fixed_lines = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Check if line has {% but not %} (incomplete tag)
        if '{%' in line and '%}' not in line:
            # Find the closing %} in subsequent lines
            combined = line
            j = i + 1
            while j < len(lines) and '%}' not in combined:
                if j < len(lines):
                    combined += ' ' + lines[j].strip()
                    if '%}' in lines[j]:
                        break
                j += 1

            # Clean up extra spaces but preserve structure
            combined = re.sub(r'\s+', ' ', combined)
            fixed_lines.append(combined)
            i = j + 1
        # Check if line starts with %} (continuation from previous)
        elif line.strip().startswith('%}') and i > 0:
            # This should have been caught above, but handle edge case
            fixed_lines[-1] = fixed_lines[-1].rstrip() + ' ' + line.strip()
            fixed_lines[-1] = re.sub(r'\s+', ' ', fixed_lines[-1])
            i += 1
        else:
            fixed_lines.append(line)
            i += 1

    return '\n'.join(fixed_lines)


def fix_template_file(filepath):
    """Fix all template syntax errors in a single file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        original = content

        # Apply fixes
        content = fix_operator_spacing(content)
        content = fix_split_template_variables(content)
        content = fix_split_template_tags(content)

        # Only write if changes were made
        if content != original:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        return False
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return False


def main():
    """Find and fix all template files."""
    templates_dir = Path(__file__).parent / 'templates'

    if not templates_dir.exists():
        print(f"Templates directory not found: {templates_dir}")
        return

    fixed_count = 0
    total_count = 0

    print("Scanning for template files...")

    # Find all .html files recursively
    for filepath in templates_dir.rglob('*.html'):
        total_count += 1
        if fix_template_file(filepath):
            fixed_count += 1
            print(f"Fixed: {filepath.relative_to(templates_dir)}")

    print(f"\n{'='*50}")
    print(f"Scanned: {total_count} files")
    print(f"Fixed: {fixed_count} files")
    print(f"{'='*50}")


if __name__ == '__main__':
    main()
