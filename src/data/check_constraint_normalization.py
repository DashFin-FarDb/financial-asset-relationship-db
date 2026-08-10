"""Canonical SQL CHECK-expression normalization for schema verification."""

from __future__ import annotations

import re


def _protect_quoted_sql_tokens(definition: str) -> tuple[str, dict[str, str]]:
    """Replace quoted SQL tokens with markers before syntax canonicalisation."""
    protected: dict[str, str] = {}
    output: list[str] = []
    position = 0

    while position < len(definition):
        quote = definition[position]
        if quote not in {"'", '"'}:
            output.append(quote)
            position += 1
            continue

        start = position
        position += 1
        while position < len(definition):
            if definition[position] != quote:
                position += 1
                continue
            if position + 1 < len(definition) and definition[position + 1] == quote:
                position += 2
                continue
            position += 1
            break

        token = definition[start:position]
        canonical_token = token
        if quote == '"' and token.endswith('"'):
            identifier = token[1:-1]
            if re.fullmatch(r"[a-z_][a-z0-9_$]*", identifier):
                canonical_token = identifier

        marker = f"\x00fardb_quoted_{len(protected)}\x00"
        protected[marker] = canonical_token
        output.append(marker)

    return "".join(output), protected


def _restore_quoted_sql_tokens(definition: str, protected: dict[str, str]) -> str:
    """Restore quoted SQL tokens after syntax canonicalisation."""
    for marker, token in protected.items():
        definition = definition.replace(marker, token)
    return definition


def _strip_redundant_outer_parentheses(definition: str) -> str:
    """Remove only parentheses that enclose the entire SQL expression."""
    while definition.startswith("(") and definition.endswith(")"):
        depth = 0
        encloses_all = True
        for position, char in enumerate(definition):
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            if depth == 0 and position != len(definition) - 1:
                encloses_all = False
                break
        if not encloses_all or depth != 0:
            break
        definition = definition[1:-1]
    return definition


def _split_top_level_check_boolean(expression: str, operator: str) -> list[str]:
    """Split one CHECK expression on a top-level boolean operator."""
    delimiter = f" {operator} "
    pieces: list[str] = []
    start = 0
    depth = 0
    position = 0
    while position < len(expression):
        char = expression[position]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif depth == 0 and expression.startswith(delimiter, position):
            pieces.append(expression[start:position])
            position += len(delimiter)
            start = position
            continue
        position += 1
    if not pieces:
        return [expression]
    pieces.append(expression[start:])
    return pieces


def _check_boolean_ast(expression: str) -> object:
    """Return an associative AND/OR tree while preserving boolean precedence."""
    expression = _strip_redundant_outer_parentheses(expression.strip())
    for operator in ("or", "and"):
        pieces = _split_top_level_check_boolean(expression, operator)
        if len(pieces) > 1:
            children: list[object] = []
            for piece in pieces:
                child = _check_boolean_ast(piece)
                if isinstance(child, tuple) and child and child[0] == operator:
                    children.extend(child[1:])
                else:
                    children.append(child)
            return (operator, *children)
    atomic = re.sub(r"(?<![a-z0-9_$])\(([a-z_][a-z0-9_$]*)\)", r"\1", expression)
    return re.sub(r'[\s"]+', "", atomic)


def _serialize_check_boolean_ast(node: object) -> str:
    """Serialize a normalized CHECK boolean tree deterministically."""
    if isinstance(node, str):
        return node
    if not isinstance(node, tuple) or not node:
        return str(node)
    operator = str(node[0])
    return operator + "(" + ",".join(_serialize_check_boolean_ast(child) for child in node[1:]) + ")"


def normalize_check_definition(definition: object) -> str:
    """Normalize ORM and reflected CHECK SQL without weakening its predicate."""
    raw_definition = "" if definition is None else str(definition)
    normalized, protected = _protect_quoted_sql_tokens(raw_definition)
    normalized = normalized.lower().strip()
    normalized = re.sub(r"::\s*(?:character varying|text)(?:\[\])?", "", normalized)
    normalized = normalized.removeprefix("check")
    normalized = normalized.replace("!~~", "not like").replace("~~", "like")
    normalized = re.sub(r"\s+", " ", normalized).strip()

    def _replace_any_array(match: re.Match[str]) -> str:
        """Rewrite PostgreSQL ANY/ARRAY deparsing to canonical IN syntax."""
        literals = match.group(1) if match.group(1) is not None else match.group(2)
        return f" in ({literals or ''})"

    normalized = re.sub(
        r"=\s*any\s*\(\s*(?:array\s*\[([^\[\]]*)\]|\(\s*array\s*\[([^\[\]]*)\]\s*\))\s*\)",
        _replace_any_array,
        normalized,
    )
    normalized = re.sub(
        r"([^\s()]+)\s+between\s+([^\s()]+)\s+and\s+([^\s()]+)",
        r"\1 >= \2 and \1 <= \3",
        normalized,
    )

    def _sort_literal_set(match: re.Match[str]) -> str:
        """Sort protected string literals inside an IN set for stable comparison."""
        literals = [item.strip() for item in match.group(1).split(",")]
        if literals and all(item in protected and protected[item].startswith("'") for item in literals):
            return "in(" + ",".join(sorted(literals, key=protected.__getitem__)) + ")"
        return match.group(0)

    normalized = re.sub(r"\bin\s*\(([^()]*)\)", _sort_literal_set, normalized)
    normalized = _serialize_check_boolean_ast(_check_boolean_ast(normalized))
    return _restore_quoted_sql_tokens(normalized, protected)
