from typing import List, Dict, Any
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
        self.is_valid = is_valid
        self.errors = errors
        self.workflow_data = workflow_data


def validate_workflow(workflow_path: str) -> ValidationResult:
    """
    Validate a workflow YAML file at the given filesystem path.

    Performs YAML parsing and checks that the top-level structure is a mapping
    and that it contains a 'jobs' key.

    Parameters:
        workflow_path (str): Filesystem path to the workflow YAML file.

    Returns:
        ValidationResult: An object containing the validation result.
    """
    try:
        with open(workflow_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        if data is None:
            return ValidationResult(False, ["Workflow file is empty or contains only nulls."], {})
        if not isinstance(data, dict):
            return ValidationResult(False, ["Workflow must be a dict"], {})
        if 'jobs' not in data:
            return ValidationResult(False, ["Workflow must have a 'jobs' key"], data)

        return ValidationResult(True, [], data)
    except FileNotFoundError:
        return ValidationResult(False, [f"File not found: {workflow_path}"], {})
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