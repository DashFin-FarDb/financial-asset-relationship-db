import re

files_to_update = [
    "Dockerfile.frontend",
    ".github/workflows/frontend-ci.yml",
    ".github/workflows/release-evidence-verify.yml",
]

for file_path in files_to_update:
    with open(file_path, "r") as f:
        content = f.read()

    # Replace node:20.9.0-slim with node:22-slim
    content = content.replace("node:20.9.0-slim", "node:22-slim")
    # Replace node-version: '20.9.0' with node-version: '22'
    content = content.replace("node-version: '20.9.0'", "node-version: '22'")

    with open(file_path, "w") as f:
        f.write(content)
