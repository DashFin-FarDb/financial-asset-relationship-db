import yaml


class ValidationResult:
    def __init__(self, is_valid, errors, workflow_data):
        """
        Initialise a ValidationResult with a validity flag, a list of error messages and the parsed workflow data.
        
        Parameters:
            is_valid (bool): True when the workflow passed validation, False otherwise.
            errors (list[str]): List of error messages describing validation failures; empty when `is_valid` is True.
            workflow_data (dict): Parsed YAML workflow data when available, otherwise an empty dict.
        """
        self.is_valid = is_valid
        self.errors = errors
        self.workflow_data = workflow_data


def validate_workflow(workflow_path):
    """
    Validate a workflow YAML file at the given filesystem path.
    
    Performs YAML parsing and checks that the top-level structure is a mapping and that it contains a 'jobs' key. On success returns the parsed workflow data; on failure returns error messages and an empty workflow payload.
    
    Parameters:
        workflow_path (str): Filesystem path to the workflow YAML file.
    
    Returns:
        ValidationResult: `is_valid` is `True` if the file parsed as a mapping and contains a 'jobs' key, `False` otherwise; `errors` is a list of diagnostic messages; `workflow_data` is the parsed YAML mapping on success or `{}` on failure.
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