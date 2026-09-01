"""Fail-closed helpers shared by PR guardrail documentation tests."""

from __future__ import annotations

import re


def _fence_parts(line: str) -> tuple[str, int, str] | None:
    """Return marker character, length, and remainder for a Markdown fence."""
    match = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
    if match is None:
        return None
    marker, remainder = match.groups()
    return marker[0], len(marker), remainder


def _closes_fence(active_fence: tuple[str, int], candidate: tuple[str, int, str] | None) -> bool:
    """Return whether a candidate is a valid close for the active fence."""
    if candidate is None:
        return False
    marker, length, remainder = candidate
    if marker != active_fence[0] or length < active_fence[1]:
        return False
    return not remainder.strip()


def _outside_fenced_code(lines: list[str]) -> list[bool]:
    """Mark lines outside Markdown backtick or tilde fenced code blocks."""
    outside: list[bool] = []
    active_fence: tuple[str, int] | None = None
    for line in lines:
        fence = _fence_parts(line)
        if active_fence is None:
            outside.append(fence is None)
            if fence is not None:
                active_fence = (fence[0], fence[1])
            continue

        outside.append(False)
        if _closes_fence(active_fence, fence):
            active_fence = None
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
