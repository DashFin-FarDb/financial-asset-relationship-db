import re

# 1. Dockerfile.api
with open('Dockerfile.api', 'r') as f:
    content = f.read()
content = content.replace(
    'RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*\nRUN pip install --no-cache-dir -r requirements.txt',
    'RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/* \\\n    && pip install --no-cache-dir -r requirements.txt'
)
with open('Dockerfile.api', 'w') as f:
    f.write(content)

# 2. tests/unit/test_verify_staging_promotion.py
with open('tests/unit/test_verify_staging_promotion.py', 'r') as f:
    content = f.read()

content = content.replace(
"""    with (
        patch("scripts.verify_staging_promotion.Path.is_relative_to", return_value=True),
        pytest.raises(SystemExit) as exc_info,
    ):""",
"""    with patch("scripts.verify_staging_promotion.Path.is_relative_to", return_value=True):
        with pytest.raises(SystemExit) as exc_info:"""
)
with open('tests/unit/test_verify_staging_promotion.py', 'w') as f:
    f.write(content)

# 3. tests/unit/test_workflow_yaml_files.py
with open('tests/unit/test_workflow_yaml_files.py', 'r') as f:
    content = f.read()

content = content.replace(
"""            try:
                return request.param, yaml.safe_load(f)
            except yaml.YAMLError as exc:
                pytest.fail(f"{request.param} has invalid YAML syntax: {exc}")""",
"""            return request.param, yaml.safe_load(f)"""
)

content = content.replace(
"""            try:
                config = yaml.safe_load(content)
            except yaml.YAMLError as exc:
                pytest.fail(f"{workflow_file.name} has invalid YAML syntax: {exc}")""",
"""            config = yaml.safe_load(content)"""
)

content = content.replace(
"""                    try:
                        list(yaml.safe_load_all(f))
                    except yaml.YAMLError as e:
                        pytest.fail(f"{yaml_file} has invalid YAML syntax: {e}")""",
"""                    list(yaml.safe_load_all(f))"""
)

with open('tests/unit/test_workflow_yaml_files.py', 'w') as f:
    f.write(content)
