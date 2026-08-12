"""Canonical SQL CHECK-expression normalization for schema verification."""

from __future__ import annotations

import re


def _quoted_run_end(definition: str, start: int, quote: str) -> int:
    """Return the first position after one SQL quoted token."""
    position = start + 1
    while position < len(definition):
        if definition[position] != quote:
            position += 1
        elif position + 1 < len(definition) and definition[position + 1] == quote:
            position += 2
        else:
            return position + 1
    return position


def _canonical_quoted_token(token: str, quote: str) -> str:
    """Remove safe lowercase identifier quotes while preserving all other tokens."""
    if quote != '"' or not token.endswith('"'):
        return token
    identifier = token[1:-1]
    return identifier if re.fullmatch(r"[a-z_][a-z0-9_$]*", identifier) else token


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
        position = _quoted_run_end(definition, start, quote)
        canonical_token = _canonical_quoted_token(definition[start:position], quote)

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
        if not _encloses_whole_expression(definition):
            break
        definition = definition[1:-1]
    return definition


def _encloses_whole_expression(definition: str) -> bool:
    """Return whether the outer parentheses close only at the final character."""
    depth = 0
    for position, char in enumerate(definition):
        depth += (char == "(") - (char == ")")
        if depth == 0 and position != len(definition) - 1:
            return False
    return depth == 0


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
                children.extend(child[1:] if isinstance(child, tuple) and child and child[0] == operator else (child,))
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


def _is_between_atom_character(character: str) -> bool:
    """Return whether a character can occur in one simple BETWEEN operand."""
    return not character.isspace() and character not in "()"


def _is_qualified_identifier_character(character: str) -> bool:
    """Return whether a character can occur in a qualified function identifier."""
    return character.isalnum() or character in "_$.\x00"


def _between_operand_start(expression: str, end: int) -> int:
    """Return the start of the simple or balanced-call operand ending at ``end``."""
    position = end - 1
    if position < 0:
        return end
    if expression[position] != ")":
        while position >= 0 and _is_between_atom_character(expression[position]):
            position -= 1
        return position + 1

    depth = 0
    while position >= 0:
        depth += (expression[position] == ")") - (expression[position] == "(")
        position -= 1
        if depth == 0:
            break
    while position >= 0 and _is_qualified_identifier_character(expression[position]):
        position -= 1
    return position + 1


def _between_bound_end(expression: str, start: int) -> int:
    """Return the end of one non-parenthesized BETWEEN bound."""
    position = start
    while position < len(expression) and not expression[position].isspace() and expression[position] not in "()":
        position += 1
    return position


def _expand_between_predicates(expression: str) -> str:
    """Expand supported BETWEEN predicates with a bounded linear scan."""
    marker = " between "
    output: list[str] = []
    cursor = 0
    marker_start = expression.find(marker)
    while marker_start >= 0:
        operand_start = _between_operand_start(expression, marker_start)
        lower_start = marker_start + len(marker)
        lower_end = _between_bound_end(expression, lower_start)
        and_marker = " and "
        if operand_start < cursor or not expression.startswith(and_marker, lower_end):
            marker_start = expression.find(marker, lower_start)
            continue
        upper_start = lower_end + len(and_marker)
        upper_end = _between_bound_end(expression, upper_start)
        if operand_start == marker_start or lower_start == lower_end or upper_start == upper_end:
            marker_start = expression.find(marker, lower_start)
            continue

        operand = expression[operand_start:marker_start]
        lower_bound = expression[lower_start:lower_end]
        upper_bound = expression[upper_start:upper_end]
        output.append(expression[cursor:operand_start])
        output.append(f"{operand} >= {lower_bound} and {operand} <= {upper_bound}")
        cursor = upper_end
        marker_start = expression.find(marker, cursor)
    output.append(expression[cursor:])
    return "".join(output)


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
    normalized = _expand_between_predicates(normalized)

    def _sort_literal_set(match: re.Match[str]) -> str:
        """Sort protected string literals inside an IN set for stable comparison."""
        literals = [item.strip() for item in match.group(1).split(",")]
        if literals and all(item in protected and protected[item].startswith("'") for item in literals):
            return "in(" + ",".join(sorted(literals, key=protected.__getitem__)) + ")"
        return match.group(0)

    normalized = re.sub(r"\bin\s*\(([^()]*)\)", _sort_literal_set, normalized)
    normalized = _serialize_check_boolean_ast(_check_boolean_ast(normalized))
    return _restore_quoted_sql_tokens(normalized, protected)
