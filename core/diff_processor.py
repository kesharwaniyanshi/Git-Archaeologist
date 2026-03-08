"""
Diff Processor - Extract meaning from raw unified diffs.
Parses diffs to identify:
- What files changed
- What dependencies/imports are involved
- Context for the LLM to understand the change
"""

import re
from pathlib import Path


def extract_diff_summary(files_changed: list[dict]) -> dict:
    """
    Extract structured information from raw diffs.
    
    Args:
        files_changed: List of file change dicts from PyDriller
                      (contains filename, change_type, diff, additions, deletions)
    
    Returns:
        Dictionary with:
        - total_files: Number of files modified
        - total_additions: Total lines added
        - total_deletions: Total lines deleted
        - primary_diff: Most significant diff (largest change)
        - imports_mentioned: Set of imported modules/files referenced
    """
    summary = {
        "total_files": len(files_changed),
        "total_additions": sum(f.get("additions", 0) for f in files_changed),
        "total_deletions": sum(f.get("deletions", 0) for f in files_changed),
        "primary_diff": None,
        "imports_mentioned": set(),
        "file_list": [],
    }
    
    # Find the largest change (most significant file)
    largest_change = None
    largest_size = 0
    
    for file_info in files_changed:
        additions = file_info.get("additions", 0)
        deletions = file_info.get("deletions", 0)
        total_change = additions + deletions
        
        summary["file_list"].append({
            "filename": file_info["filename"],
            "change_type": file_info["change_type"],
            "additions": additions,
            "deletions": deletions,
        })
        
        # Track largest change for context
        if total_change > largest_size:
            largest_size = total_change
            largest_change = file_info
        
        # Extract imports/dependencies from diff
        if file_info.get("diff"):
            imports = _extract_imports_from_diff(file_info["diff"], file_info["filename"])
            summary["imports_mentioned"].update(imports)
    
    # Use the largest change as primary context for LLM
    if largest_change:
        summary["primary_diff"] = {
            "filename": largest_change["filename"],
            "change_type": largest_change["change_type"],
            "additions": largest_change.get("additions", 0),
            "deletions": largest_change.get("deletions", 0),
            "diff": _truncate_diff(largest_change.get("diff", ""), max_lines=50),
        }
    
    # Convert set to list for JSON serialization
    summary["imports_mentioned"] = list(summary["imports_mentioned"])
    
    return summary


def _extract_imports_from_diff(diff: str, filename: str) -> set[str]:
    """
    Extract import statements and file references from a diff.
    
    Looks for patterns like:
    - Python: import X, from Y import Z
    - JavaScript: import X from 'Y', require('Z')
    
    Args:
        diff: Raw unified diff string
        filename: Name of the file being changed (helps identify language)
    
    Returns:
        Set of imported module/file names
    """
    imports = set()
    
    # Python import patterns
    python_import_pattern = r'(?:\+|\-|\s)(?:from|import)\s+([\w\.]+)'
    python_matches = re.findall(python_import_pattern, diff)
    imports.update(python_matches)
    
    # JavaScript/TypeScript import patterns
    js_import_pattern = r'(?:import|require)\s*\(\s*[\'"]([^\'"]+)[\'"]'
    js_matches = re.findall(js_import_pattern, diff)
    imports.update(js_matches)
    
    # Remove duplicates and clean up
    imports = {imp.strip() for imp in imports if imp.strip()}
    
    return imports


def _truncate_diff(diff: str, max_lines: int = 50) -> str:
    """
    Truncate diff to avoid overwhelming the LLM.
    
    Args:
        diff: Raw diff string
        max_lines: Maximum number of lines to keep
    
    Returns:
        Truncated diff with ellipsis if it was too long
    """
    lines = diff.split("\n")
    
    if len(lines) <= max_lines:
        return diff
    
    # Keep first max_lines and add indicator
    truncated = "\n".join(lines[:max_lines])
    truncated += f"\n\n... ({len(lines) - max_lines} more lines omitted)"
    
    return truncated


def format_diff_for_llm(commit: dict, diff_summary: dict) -> str:
    """
    Format diff and context into a readable prompt section for the LLM.
    
    Args:
        commit: Commit dict from extract_commits
        diff_summary: Output from extract_diff_summary
    
    Returns:
        Formatted string ready to include in LLM prompt
    """
    lines = []
    
    # Files changed overview
    lines.append(f"Files Changed: {diff_summary['total_files']}")
    for file_info in diff_summary["file_list"]:
        lines.append(f"  - {file_info['filename']} ({file_info['change_type']}) "
                    f"+{file_info['additions']} -{file_info['deletions']}")
    
    lines.append("")
    
    # Import/dependency context
    if diff_summary["imports_mentioned"]:
        lines.append("Dependencies/Imports Referenced:")
        for imp in sorted(diff_summary["imports_mentioned"])[:10]:  # Limit to 10
            lines.append(f"  - {imp}")
        lines.append("")
    
    # Primary diff with context
    if diff_summary["primary_diff"]:
        primary = diff_summary["primary_diff"]
        lines.append(f"Primary Change: {primary['filename']}")
        lines.append(f"Type: {primary['change_type']}")
        lines.append(f"Changes: +{primary['additions']} -{primary['deletions']} lines")
        lines.append("")
        lines.append("Diff:")
        lines.append("```")
        lines.append(primary["diff"])
        lines.append("```")
    
    return "\n".join(lines)
