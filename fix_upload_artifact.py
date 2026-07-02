with open('.github/workflows/release-evidence-verify.yml', 'r') as f:
    content = f.read()

old_upload = """      - name: Upload Artifacts
        if: always()
        uses: actions/upload-artifact@6543ce64cb6eb0d110ebf6fb5b172aeb41d3b5b6 # v4
        with:
          name: release-evidence
          path: |
            results-*.xml
            readiness-output.json"""

new_upload = """      - name: Upload Artifacts
        if: always()
        uses: actions/upload-artifact@6543ce64cb6eb0d110ebf6fb5b172aeb41d3b5b6 # v4
        with:
          name: release-evidence
          path: |
            results-*.xml
            readiness-output.json
            docs-readiness.json"""

if old_upload in content:
    content = content.replace(old_upload, new_upload)
else:
    print("Could not find old_upload")
    
with open('.github/workflows/release-evidence-verify.yml', 'w') as f:
    f.write(content)
