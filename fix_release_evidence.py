with open(".github/workflows/release-evidence-verify.yml", "r") as f:
    content = f.read()

# 1. Add tags input
old_inputs = """      require_persistence:
        description: 'Require persistence proof'
        type: boolean
        default: true"""

new_inputs = """      require_persistence:
        description: 'Require persistence proof'
        type: boolean
        default: true
      tags:
        description: 'Manual sign-off tags (e.g., [manual-stop] or [star])'
        required: false
        default: ''"""

if old_inputs in content:
    content = content.replace(old_inputs, new_inputs)
else:
    print("Could not find old_inputs")

# 2. Add Parse Manual Sign-off Tags step
old_steps = """    steps:
      - name: Checkout repository
        uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5 # v4"""

new_steps = """    steps:
      - name: Checkout repository
        uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5 # v4

      - name: Parse Manual Sign-off Tags
        env:
          INPUT_TAGS: ${{ github.event.inputs.tags }}
        run: |
          if echo "$INPUT_TAGS" | grep -qiE '\\[manual-stop\\]|\\[star\\]'; then
            echo "Manual sign-off tag detected. Pausing/failing for manual approval."
            exit 1
          fi"""

if old_steps in content:
    content = content.replace(old_steps, new_steps)
else:
    print("Could not find old_steps")

with open(".github/workflows/release-evidence-verify.yml", "w") as f:
    f.write(content)
