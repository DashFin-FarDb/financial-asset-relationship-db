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
        workflow_data: Dict[str, Any],
    ):
        """
        Initialize a ValidationResult representing the outcome of validating a
        workflow YAML file.

        Parameters:
            is_valid (bool): True when validation passed, False when one or
                more validation checks failed.
            errors (List[str]): Human-readable error messages describing
                validation failures; empty when is_valid is True.
            workflow_data (Dict[str, Any]): The parsed workflow data structure
                from the YAML file (may be empty or partial on failure).
        """
        self.is_valid = is_valid
        self.errors = errors
        self.workflow_data = workflow_data


def validate_workflow(workflow_path: str) -> ValidationResult:
    """
    Validate the workflow YAML file at the given filesystem path.

    Parses the file as YAML and verifies the parsed document is a mapping
    that contains a top-level "jobs" key.

    On success the parsed workflow mapping is returned in the result;
    on failure the result contains human-readable error messages
    describing the problem.

    Parameters:
        workflow_path (str): Filesystem path to the workflow YAML file.

    Returns:
        ValidationResult: Contains `is_valid`
            (True if the workflow is valid, False otherwise),
            `errors` (list of human-readable error messages), and
            `workflow_data` (the parsed workflow mapping when available,
            otherwise an empty dict).
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
