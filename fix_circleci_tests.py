import re

with open('tests/unit/test_workflow_yaml_files.py', 'r') as f:
    content = f.read()

# Add a skip to TestCircleCIConfig
content = content.replace('class TestCircleCIConfig:', '@pytest.mark.skip(reason="CircleCI config removed")\nclass TestCircleCIConfig:')

with open('tests/unit/test_workflow_yaml_files.py', 'w') as f:
    f.write(content)
