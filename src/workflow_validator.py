from __future__ import annotations

import os
from typing import Any

import yaml


class ValidationResult:
    """
    Represents the result of validating a workflow YAML file.

    Attributes:
        is_valid (bool): True when the workflow passed validation, False otherwise.
        errors (list[str]): Error messages describing validation failures.
        workflow_data (dict[str, Any]): Parsed YAML workflow data.
    """

    def __init__(
        self,
        is_valid: bool,
        errors: list[str],
        workflow_data: dict[str, Any],
    ) -> None:
        """
        Initialize a ValidationResult representing the outcome of validation.
        """
        self.is_valid = is_valid
        self.errors = errors
        self.workflow_data = workflow_data


    """
    Validate a workflow YAML file at the given filesystem path.

    Performs YAML parsing and verifies the file is a mapping with a top - level
    'jobs' key.

    Args:
        workflow_path: Filesystem path to the workflow YAML file.

    Returns:
        ValidationResult describing the validation outcome.
    """
    try:
        with open(workflow_path, encoding="utf-8") as file_handle:
            data = yaml.safe_load(file_handle)

        if data is None:
            return ValidationResult(
                is_valid=False,
                errors=["Workflow file is empty or contains only nulls."],
                workflow_data={},
            )

        if not isinstance(data, dict):
            return ValidationResult(
                is_valid=False,
                errors=["Workflow must be a dict"],
                workflow_data=data,
            )

        if "jobs" not in data:
            return ValidationResult(
                is_valid=False,
                errors=["Workflow must have a 'jobs' key"],
                workflow_data=data,
            )

        return ValidationResult(
            is_valid=True,
            errors=[],
            workflow_data=data,
        )

    except FileNotFoundError:
        return ValidationResult(
            is_valid=False,
            errors=[f"File not found: {workflow_path}"],
            workflow_data={},
        )

    except yaml.YAMLError as exc:
        return ValidationResult(
            is_valid=False,
            errors=[f"Invalid YAML syntax: {exc}"],
            workflow_data={},
        )

    except PermissionError as exc:
        return ValidationResult(
            is_valid=False,
            errors=[f"Permission denied: {exc}"],
            workflow_data={},
        )

    except IsADirectoryError as exc:
        return ValidationResult(
            is_valid=False,
            errors=[f"Expected a file but found a directory: {exc}"],
            workflow_data={},
        )

    except NotADirectoryError as exc:
        return ValidationResult(
            is_valid=False,
            errors=[f"Invalid path component (not a directory): {exc}"],
            workflow_data={},
        )

    except UnicodeDecodeError as exc:
        return ValidationResult(
            is_valid=False,
            errors=[f"Invalid file encoding: {exc}"],
            workflow_data={},
        )
