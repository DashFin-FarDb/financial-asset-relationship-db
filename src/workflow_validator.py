import yaml


class ValidationResult:
    """
    Initialize a ValidationResult with a validity flag, a list of error messages and the parsed workflow data.
    
    Parameters:
        is_valid (bool): True when the workflow passed validation, False otherwise.
        errors (list[str]): List of error messages describing validation failures; empty when `is_valid` is True.
        workflow_data (dict): Parsed YAML workflow data when available, otherwise an empty dict.
    """
    Represents the result of validating a workflow YAML file.
    
    Attributes:
        is_valid (bool): True when the workflow passed validation, False otherwise.
        errors (list[str]): List of error messages describing validation failures; empty when `is_valid` is True.
        workflow_data (dict): Parsed YAML workflow data when available, otherwise an empty dict.
    """
    def __init__(self, is_valid, errors, workflow_data):
        self.is_valid = is_valid
        self.errors = errors
        self.workflow_data = workflow_data


def validate_workflow(workflow_path):
class ValidationResult:
    """
    Represents the result of validating a workflow YAML file.

    Parameters:
        is_valid (bool): True when the workflow passed validation, False otherwise.
        errors (list[str]): List of error messages describing validation failures; empty when `is_valid` is True.
        workflow_data (dict): Parsed YAML workflow data when available, otherwise an empty dict.

    Attributes:
        is_valid (bool): Validation outcome.
        errors (list[str]): Validation error messages.
        workflow_data (dict): Parsed YAML workflow data.
    """

    def __init__(self, is_valid, errors, workflow_data):
        self.is_valid = is_valid
        self.errors = errors
        self.workflow_data = workflow_data


def validate_workflow(workflow_path):
    """
    Validate a workflow YAML file at the given filesystem path.

    Performs YAML parsing and checks that the top-level structure is a mapping and that it contains a 'jobs' key. On success returns the parsed workflow data. On failure, returns error messages and:
    - an empty dict ({}) when parsing fails or the top-level structure is not a mapping
    - the parsed dict when parsing succeeds but required keys (e.g., 'jobs') are missing

    Parameters:
        workflow_path (str): Filesystem path to the workflow YAML file.

    Returns:
        ValidationResult: `is_valid` is `True` if the file parsed as a mapping and contains a 'jobs' key, `False` otherwise; `errors` is a list of diagnostic messages; `workflow_data` is the parsed YAML mapping on success, `{}` when parsing fails or the top-level structure is not a mapping, or the parsed dict when required keys (e.g., 'jobs') are missing.
    """
    try:
        with open(workflow_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict):
            return ValidationResult(False, ["Workflow must be a dict"], {})

        if 'jobs' not in data:
            return ValidationResult(False, ["Workflow must have jobs"], data)

        # Additional validations can be added here if needed
        return ValidationResult(True, [], data)
    except Exception as e:
        return ValidationResult(False, [str(e)], {})
    Validate a workflow YAML file at the given filesystem path.
    
    Performs YAML parsing and checks that the top-level structure is a mapping and that it contains a 'jobs' key. On success returns the parsed workflow data. On failure, returns error messages and:
    - an empty dict ({}) when parsing fails or the top-level structure is not a mapping
def validate_workflow(workflow_path):
    """
    Validate a workflow YAML file at the given filesystem path.
    
    Performs YAML parsing and checks that the top-level structure is a mapping and that it contains a 'jobs' key. On success returns the parsed workflow data. On failure, returns error messages and:
    - an empty dict ({}) when parsing fails or the top-level structure is not a mapping
    - the parsed dict when parsing succeeds but required keys (e.g., 'jobs') are missing
    
    Parameters:
        workflow_path (str): Filesystem path to the workflow YAML file.
    Returns:
        ValidationResult: `is_valid` is `True` if the file parsed as a mapping and contains a 'jobs' key, `False` otherwise; `errors` is a list of diagnostic messages; `workflow_data` is the parsed YAML mapping on success, `{}` when parsing fails or the top-level structure is not a mapping, or the parsed dict when required keys (e.g., 'jobs') are missing.
    """
    try:
        with open(workflow_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            return ValidationResult(False, ["Workflow must be a dict"], {})
        if 'jobs' not in data:
            return ValidationResult(False, ["Workflow must have jobs"], data)
        # Additional validations can be added here if needed
        return ValidationResult(True, [], data)
    except Exception as e:
        return ValidationResult(False, [str(e)], {})