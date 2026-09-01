"""Fail-closed helpers shared by PR guardrail documentation tests."""

from __future__ import annotations

import re


def _outside_fenced_code(lines: list[str]) -> list[bool]:
    """Mark lines outside Markdown backtick or tilde fenced code blocks."""
    outside: list[bool] = []
    active_fence: tuple[str, int] | None = None
    for line in lines:
        stripped = line.lstrip(" ")
        indentation = len(line) - len(stripped)
        fence_match = re.match(r"(`{3,}|~{3,})(.*)$", stripped) if indentation <= 3 else None

        if active_fence is not None:
            outside.append(False)
            if fence_match is not None:
                marker, remainder = fence_match.groups()
                if marker[0] == active_fence[0] and len(marker) >= active_fence[1] and not remainder.strip():
                    active_fence = None
            continue

        if fence_match is not None:
            marker = fence_match.group(1)
            active_fence = (marker[0], len(marker))
            outside.append(False)
            continue

        outside.append(True)
    return outside


def markdown_section(content: str, heading: str) -> str:
    """Return one exact Markdown section, rejecting missing or duplicate headings."""
    heading_match = re.fullmatch(r"(#{1,6}) [^\r\n]+", heading)
    assert heading_match is not None, f"Invalid Markdown heading: {heading!r}"
    heading_level = len(heading_match.group(1))

    lines = content.splitlines()
    outside_fence = _outside_fenced_code(lines)
    matches = [index for index, line in enumerate(lines) if outside_fence[index] and line.rstrip() == heading]
    assert len(matches) == 1, f"Heading {heading!r} must appear exactly once; found {len(matches)}"

    start = matches[0] + 1
    end = len(lines)
    for index in range(start, len(lines)):
        if not outside_fence[index]:
            continue
        next_heading = re.match(r"^(#{1,6})(?:[ \t]+|$)", lines[index])
        if next_heading is not None and len(next_heading.group(1)) <= heading_level:
            end = index
            break
    return "\n".join(lines[start:end]).strip("\n")
