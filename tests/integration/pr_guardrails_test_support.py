"""Fail-closed helpers shared by PR guardrail documentation tests."""

from __future__ import annotations

import re


def markdown_section(content: str, heading: str) -> str:
    """Return one exact Markdown section, rejecting missing or duplicate headings."""
    heading_match = re.fullmatch(r"(#{1,6}) [^\r\n]+", heading)
    assert heading_match is not None, f"Invalid Markdown heading: {heading!r}"
    heading_level = len(heading_match.group(1))

    lines = content.splitlines()
    matches = [index for index, line in enumerate(lines) if line.rstrip() == heading]
    assert len(matches) == 1, f"Heading {heading!r} must appear exactly once; found {len(matches)}"

    start = matches[0] + 1
    end = len(lines)
    for index in range(start, len(lines)):
        next_heading = re.match(r"^(#{1,6})(?:[ \t]+|$)", lines[index])
        if next_heading is not None and len(next_heading.group(1)) <= heading_level:
            end = index
            break
    return "\n".join(lines[start:end]).strip("\n")
