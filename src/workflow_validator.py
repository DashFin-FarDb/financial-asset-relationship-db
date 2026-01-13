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

    def __init__(self, is_valid: bool, errors: List[str], workflow_data: Dict[str, Any]):
        """
        Initialize a ValidationResult representing the outcome of validating a workflow YAML file.

        Parameters:
            is_valid (bool): True when validation passed, False when one or more validation checks failed.
            errors (List[str]): Human-readable error messages describing validation failures; empty when is_valid is True.
            workflow_data (Dict[str, Any]): The parsed workflow data structure from the YAML file (may be empty or partial on failure).
        """
        self.is_valid = is_valid
        self.errors = errors
        self.workflow_data = workflow_data


def validate_workflow(workflow_path: str) -> ValidationResult:
    """
    Validate a workflow YAML file located at the given filesystem path.

    Performs YAML parsing and verifies the file is a mapping with a top-level 'jobs' key. On success returns a ValidationResult with is_valid set to True and the parsed workflow data; on failure returns a ValidationResult with is_valid set to False and a list of human-readable error messages describing the problem (e.g., missing file, syntax error, invalid structure).

    Parameters:
        workflow_path (str): Filesystem path to the workflow YAML file.

    Returns:
        ValidationResult: Validation outcome containing `is_valid`, `errors`, and `workflow_data`.
    """
    filename = os.path.basename(workflow_path)
    allowed_workflow_filenames = globals().get(
        "ALLOWED_WORKFLOW_FILENAMES"
    ) or set(  # may be defined elsewhere at module scope
        os.listdir(os.environ.get("WORKFLOW_DIR") or os.path.join(os.path.dirname(__file__), "workflows"))
    )  # fallback: allow only filenames present in the trusted directory
    if filename not in allowed_workflow_filenames:
        return ValidationResult(False, [f"Invalid workflow filename: {filename}"], {})
    workflow_dir = os.environ.get("WORKFLOW_DIR") or os.path.join(os.path.dirname(__file__), "workflows")
    safe_path = os.path.join(workflow_dir, filename)
    try:
        with open(safe_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if data is None:
            return ValidationResult(False, ["Workflow file is empty or contains only nulls."], {})
        if not isinstance(data, dict):
            return ValidationResult(False, ["Workflow must be a dict"], {})
        if "jobs" not in data:
            return ValidationResult(False, ["Workflow must have a 'jobs' key"], data)

        return ValidationResult(True, [], data)
    except FileNotFoundError:
        return ValidationResult(False, [f"File not found: {safe_path}"], {})
    except yaml.YAMLError as e:
        return ValidationResult(False, [f"Invalid YAML syntax: {e}"], {})
    except PermissionError as e:
        return ValidationResult(False, [f"Permission denied: {e}"], {})
    except IsADirectoryError as e:
        return ValidationResult(False, [f"Expected a file but found a directory: {e}"], {})
    except NotADirectoryError as e:
        return ValidationResult(False, [f"Invalid path component (not a directory): {e}"], {})
    except Exception:
        # Re-raise unexpected exceptions to avoid masking programming errors
        raise
