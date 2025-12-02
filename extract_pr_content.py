#!/usr/bin/env python3
"""Extract the section around line 2900 from the PR content."""

# The PR content I fetched earlier - I'll extract just the relevant section
pr_content = """
    def test_simplified_workflows_reduce_complexity(self):
        \"\"\"Test that simplified workflows have fewer steps after changes.\"\"\"
        # This is a sanity check that simplifications actually reduced complexity
        workflow_files = get_workflow_files()
        
        for workflow_file in workflow_files:
            config = load_yaml_safe(workflow_file)
            
            if not config or "jobs" not in config:
                continue
            
            for job_name, job in config["jobs"].items():
                steps = job.get("steps", [])
                
                # Sanity check: no job should have an excessive number of steps
                # (this would indicate complexity hasn't been reduced)
                assert len(steps) < 50, (
                    f"{workflow_file.name}, job '{job_name}' has {len(steps)} steps. "
                    f"Consider further simplification if this is unexpectedly high."
                )
"""

print(pr_content)
print("\n" + "="*80)
print("This is what should be at the end of the test_simplified_workflows_reduce_complexity method")
print("The file is missing the closing triple quote for the docstring!")
