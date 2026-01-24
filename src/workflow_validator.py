import os
from typing import Any, Dict, List

import yaml


class ValidationResult:
    """
    Represents the result of validating a workflow YAML file.

    Attributes:
        is_valid (bool): True when the workflow passed validation, False otherwise.
        errors (list[str]): List of error messages describing validation failures.
        workflow_data (dict): Parsed YAML workflow data.
    """

    def __init__(
        self,
        is_valid: bool,
        errors: List[str],
        workflow_data: dict[str, Any],
    ):
        """
        Initialize a ValidationResult representing the outcome of validating a
        workflow YAML file.

        Parameters:
            is_valid (bool): True when validation passed, False when one or
                more validation checks failed.
            errors (List[str]): Human-readable error messages describing
                validation failures; empty when is_valid is True.
            workflow_data (dict[str, Any]): The parsed workflow data structure
                from the YAML file (may be empty or partial on failure).
        """
        self.is_valid = is_valid
        self.errors = errors
        self.workflow_data = workflow_data


def validate_workflow(workflow_path: str) -> ValidationResult:
    """
    Validate the workflow YAML file at the given filesystem path.

    Performs YAML parsing and structural checks: the file must exist, parse to a
    mapping (dict), and contain a top-level "jobs" key. On success the parsed
    workflow data is returned in the result; on failure the result contains
    human-readable error messages such as "File not found: ...",
    "Invalid YAML syntax: ...", "Workflow file is empty or contains only nulls.",
    "Workflow must be a dict", or "Workflow must have a 'jobs' key".

    Parameters:
        workflow_path (str): Filesystem path to the workflow YAML file.

    Returns:
        ValidationResult: Validation outcome. `is_valid` is `True` and
            `workflow_data` contains the parsed mapping on success;
            `is_valid` is `False` and `errors` contains one or more descriptive
            messages on failure.
    """
    try:
        # Resolve the full path to ensure we can open it safely
        safe_path = os.path.abspath(workflow_path)

        if not os.path.isfile(safe_path):
            return ValidationResult(False, [f"File not found: {safe_path}"], {})

        with open(safe_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if data is None:
            return ValidationResult(
                False, ["Workflow file is empty or contains only nulls."], {}
            )

        if not isinstance(data, dict):
            return ValidationResult(False, ["Workflow must be a dict"], {})

        if "jobs" not in data:
            return ValidationResult(False, ["Workflow must have a 'jobs' key"], data)

        return ValidationResult(True, [], data)

    except FileNotFoundError:
        return ValidationResult(False, [f"File not found: {workflow_path}"], {})
    except yaml.YAMLError as e:
        return ValidationResult(False, [f"Invalid YAML syntax: {e}"], {})
    except PermissionError as e:
        return ValidationResult(False, [f"Permission denied: {e}"], {})
    except IsADirectoryError as e:
        return ValidationResult(
            False, [f"Expected a file but found a directory: {e}"], {}
        )
    except OSError as e:
        return ValidationResult(False, [f"OS Error reading file: {e}"], {})
