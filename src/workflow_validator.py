import yaml


class ValidationResult:
    def __init__(self, is_valid, errors, workflow_data):
        """
        Initialise a ValidationResult with the outcome, collected errors and the parsed workflow data.
        
        Parameters:
            is_valid (bool): True if the workflow validation passed, False otherwise.
            errors (list[str]): List of error messages produced during validation.
            workflow_data (dict): Parsed workflow data (empty dict if parsing failed).
        """
        self.is_valid = is_valid
        self.errors = errors
        self.workflow_data = workflow_data


def validate_workflow(workflow_path):
    """
    Validate a workflow YAML file and return structured validation results.
    
    Parameters:
        workflow_path (str): Path to the workflow YAML file to validate.
    
    Returns:
        ValidationResult: Contains:
            - `is_valid`: `True` if the file was parsed and contains a top-level dict with a `jobs` key, `False` otherwise.
            - `errors`: List of error messages encountered during parsing or validation.
            - `workflow_data`: Parsed workflow dictionary on success, or an empty dict on failure.
    """
    try:
        with open(workflow_path, 'r') as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            return ValidationResult(False, ["Workflow must be a dict"], {})
        if 'jobs' not in data:
            return ValidationResult(False, ["Workflow must have jobs"], data)
        # Additional validations can be added here if needed
        return ValidationResult(True, [], data)
    except Exception as e:
        return ValidationResult(False, [str(e)], {})