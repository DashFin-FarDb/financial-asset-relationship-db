with open(".github/workflows/staging-promotion.yml", "r") as f:
    content = f.read()

# 1. Update Checkout step
old_checkout = """      - name: Checkout
        uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5 # v4"""

new_checkout = """      - name: Checkout
        uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5 # v4
        with:
          persist-credentials: false"""

if old_checkout in content:
    content = content.replace(old_checkout, new_checkout)

# 2. Reorder steps and update upload artifacts
old_trailing = """      - name: Upload Artifacts
        if: always()
        uses: actions/upload-artifact@5d5d22a31266ced268874388b761e4b58bb5c2f3 # v4
        with:
          name: staging-readiness
          path: readiness-output.json

      - name: Audit Logging
        run: |
          echo "Logging promotion decision for AI system transparency (Article 13)..."
          echo "Promotion verified at $(date -u)" >> promotion_audit.log

      - name: Assert Persistence Loaded
        run: |
          if [ "$(jq -r '.observed_fields."graph.persistence_loaded"' readiness-output.json)" != "true" ]; then
            echo "Error: persistence_loaded is not true in the readiness output."
            exit 1
          fi
          if [ "$(jq -r '.observed_fields."graph.startup_source"' readiness-output.json)" != "persisted" ]; then
            echo "Error: startup_source is not \\"persisted\\" in the readiness output."
            exit 1
          fi
          echo "Assertion passed: graph is persistence loaded."
"""

new_trailing = """      - name: Assert Persistence Loaded
        run: |
          if [ "$(jq -r '.observed_fields."graph.persistence_loaded"' readiness-output.json)" != "true" ]; then
            echo "Error: persistence_loaded is not true in the readiness output."
            exit 1
          fi
          if [ "$(jq -r '.observed_fields."graph.startup_source"' readiness-output.json)" != "persisted" ]; then
            echo "Error: startup_source is not \\"persisted\\" in the readiness output."
            exit 1
          fi
          echo "Assertion passed: graph is persistence loaded."

      - name: Audit Logging
        run: |
          echo "Logging promotion decision for AI system transparency (Article 13)..."
          echo "Promotion verified at $(date -u)" >> promotion_audit.log

      - name: Upload Artifacts
        if: always()
        uses: actions/upload-artifact@5d5d22a31266ced268874388b761e4b58bb5c2f3 # v4
        with:
          name: staging-readiness
          path: |
            readiness-output.json
            promotion_audit.log
"""

if old_trailing.strip() in content.strip():
    content = content.replace(old_trailing.strip(), new_trailing.strip())
else:
    print("Could not find old_trailing")

with open(".github/workflows/staging-promotion.yml", "w") as f:
    f.write(content + "\n")
