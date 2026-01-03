#!/usr/bin/env python
"""
Template Validation Script
Checks Django templates for common syntax errors before they cause runtime issues.
"""

import os
import re
import sys
from pathlib import Path


class TemplateValidator:
    def __init__(self, templates_dir="templates"):
        self.templates_dir = Path(templates_dir)
        self.errors = []
        self.warnings = []

    def validate_all(self):
        """Validate all HTML templates in the templates directory."""
        html_files = list(self.templates_dir.rglob("*.html"))

        print(f"🔍 Validating {len(html_files)} template files...\n")

        for filepath in html_files:
            self.validate_file(filepath)

        self.print_results()
        return len(self.errors) == 0

    def validate_file(self, filepath):
        """Validate a single template file."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')

            relative_path = filepath.relative_to(self.templates_dir)

            # Run all validation checks
            self.check_operator_spacing(lines, relative_path)
            self.check_split_tags(lines, relative_path)
            self.check_block_matching(content, relative_path)
            self.check_empty_tag_placement(content, relative_path)

        except Exception as e:
            self.errors.append(f"❌ {filepath}: Error reading file - {str(e)}")

    def check_operator_spacing(self, lines, filepath):
        """Check for operators without proper spacing."""
        # Pattern: variable==value or variable=='value' or variable=="value"
        patterns = [
            (r"(\w+)==['\"]", "Missing space before =="),
            (r"['\"](\w+)==", "Missing space after =="),
            (r"(\w+)!=", "Missing space before !="),
            (r"!=(\w+)", "Missing space after !="),
        ]

        for line_num, line in enumerate(lines, 1):
            # Skip if not a Django template tag
            if '{%' not in line:
                continue

            for pattern, message in patterns:
                if re.search(pattern, line):
                    self.errors.append(
                        f"❌ {filepath}:{line_num} - {message}\n"
                        f"   Line: {line.strip()}\n"
                        f"   Fix: Add spaces around comparison operators (e.g., var == 'value')"
                    )

    def check_split_tags(self, lines, filepath):
        """Check for template tags split across lines."""
        for line_num, line in enumerate(lines, 1):
            # Check for opening tag without closing
            if '{%' in line and '%}' not in line:
                self.errors.append(
                    f"❌ {filepath}:{line_num} - Template tag split across lines\n"
                    f"   Line: {line.strip()}\n"
                    f"   Fix: Keep template tags on a single line"
                )

            # Check for closing without opening
            if '%}' in line and '{%' not in line and '{{' not in line:
                self.errors.append(
                    f"❌ {filepath}:{line_num} - Template tag ending without start\n"
                    f"   Line: {line.strip()}\n"
                    f"   Fix: Ensure complete template tag on single line"
                )

    def check_block_matching(self, content, filepath):
        """Check for matching block tags."""
        # Simple check for common block tags
        block_pairs = [
            ('if', 'endif'),
            ('for', 'endfor'),
            ('block', 'endblock'),
            ('with', 'endwith'),
            ('comment', 'endcomment'),
        ]

        for start_tag, end_tag in block_pairs:
            start_pattern = rf'{{% \s*{start_tag}\s'
            end_pattern = rf'{{% \s*{end_tag}\s*%}}'

            start_count = len(re.findall(start_pattern, content))
            end_count = len(re.findall(end_pattern, content))

            if start_count != end_count:
                self.warnings.append(
                    f"⚠️  {filepath} - Mismatched {start_tag}/{end_tag} tags\n"
                    f"   Found {start_count} {{% {start_tag} %}} but {end_count} {{% {end_tag} %}}"
                )

    def check_empty_tag_placement(self, content, filepath):
        """Check for {% empty %} used outside {% for %} loops."""
        # This is a simplified check
        # Find all {% empty %} tags
        empty_tags = list(re.finditer(r'{%\s*empty\s*%}', content))

        for match in empty_tags:
            pos = match.start()
            # Get content before this position
            before = content[:pos]

            # Count for loops and endfor before this point
            for_count = len(re.findall(r'{%\s*for\s', before))
            endfor_count = len(re.findall(r'{%\s*endfor\s*%}', before))

            # If endfor count equals for count, we're not inside a for loop
            if for_count == endfor_count:
                line_num = content[:pos].count('\n') + 1
                self.errors.append(
                    f"❌ {filepath}:{line_num} - {{% empty %}} used outside {{% for %}} loop\n"
                    f"   Fix: Use {{% else %}} for {{% if %}} blocks, {{% empty %}} only for {{% for %}} loops"
                )

    def print_results(self):
        """Print validation results."""
        print("\n" + "="*70)

        if self.errors:
            print(f"\n❌ ERRORS FOUND ({len(self.errors)}):\n")
            for error in self.errors:
                print(error)
                print()

        if self.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.warnings)}):\n")
            for warning in self.warnings:
                print(warning)
                print()

        if not self.errors and not self.warnings:
            print("\n✅ All templates validated successfully!")
            print("   No syntax errors found.")

        print("="*70 + "\n")


def main():
    """Main entry point."""
    validator = TemplateValidator()
    success = validator.validate_all()

    # Exit with error code if validation failed
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
