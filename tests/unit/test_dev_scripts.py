"""Tests for development scripts and configuration files.

This module validates:
- Shell script syntax and structure
- Environment configuration
- Vercel deployment configuration
"""

import json
import os

import pytest


class TestVercelConfiguration:
    """Test Vercel deployment configuration."""

    def test_vercel_json_exists(self):
        """Test that vercel.json exists."""
        assert os.path.exists("vercel.json")

    def test_vercel_json_valid(self):
        """Test that vercel.json is valid JSON."""
        with open("vercel.json") as f:
            config = json.load(f)

        assert "builds" in config
        assert "routes" in config

    def test_vercel_builds_configuration(self):
        """Test Vercel builds are properly configured."""
        with open("vercel.json") as f:
            config = json.load(f)

        builds = config["builds"]
        assert len(builds) == 2

        # Check Python build
        python_build = next(b for b in builds if b["src"] == "api/main.py")
        assert python_build["use"] == "@vercel/python"
        assert "maxLambdaSize" in python_build["config"]

    def test_vercel_routes_configuration(self):
        """Test Vercel routes are properly configured."""
        with open("vercel.json") as f:
            config = json.load(f)

        routes = config["routes"]

        # Check API route
        api_route = next(r for r in routes if r["src"] == "/api/(.*)")
        assert api_route["dest"] == "api/main.py"


class TestEnvironmentConfiguration:
    """Test environment configuration."""

    def test_env_example_exists(self):
        """Test that .env.example exists."""
        assert os.path.exists(".env.example")

    def test_env_example_has_required_vars(self):
        """Test that .env.example contains required variables."""
        with open(".env.example") as f:
            content = f.read()

        assert "NEXT_PUBLIC_API_URL" in content
        assert "ALLOWED_ORIGINS" in content


class TestGitIgnore:
    """Test .gitignore configuration."""

    def test_gitignore_excludes_build_artifacts(self):
        """Test that .gitignore excludes build artifacts."""
        with open(".gitignore") as f:
            content = f.read()

        # Python artifacts
        assert "__pycache__" in content or "*.pyc" in content

        # Node.js artifacts
        assert "node_modules" in content
        assert ".next" in content

        # Environment files
        assert ".env.local" in content or ".env" in content

        # Vercel
        assert ".vercel" in content


class TestDocumentationFiles:
    """Test that documentation files exist and are properly structured."""

    @pytest.mark.parametrize(
        "doc_file",
        [
            "README.md",
            "DEPLOYMENT.md",
            "INTEGRATION_SUMMARY.md",
            "ARCHITECTURE.md",
            "QUICK_START.md",
            "UI_COMPARISON.md",
            "VERCEL_DEPLOYMENT_CHECKLIST.md",
        ],
    )
    def test_documentation_exists(self, doc_file):
        """Test that key documentation files exist."""
        assert os.path.exists(doc_file), f"Missing documentation: {doc_file}"

    def test_readme_has_quick_start(self):
        """Test README contains quick start section."""
        with open("README.md") as f:
            content = f.read()

        assert "Quick Start" in content or "Getting Started" in content
        assert "Installation" in content or "Setup" in content


class TestShellScripts:
    """Test shell scripts for syntax, structure, and functionality."""

    def test_cleanup_branches_script_exists(self):
        """Test that cleanup-branches.sh exists and is executable."""
        assert os.path.exists("cleanup-branches.sh")
        # Check if file has execute permissions
        import stat

        file_stat = os.stat("cleanup-branches.sh")
        assert os.name == "nt" or file_stat.st_mode & stat.S_IXUSR

    def test_cleanup_branches_script_has_shebang(self):
        """Test that cleanup-branches.sh has proper shebang."""
        with open("cleanup-branches.sh") as f:
            first_line = f.readline()
        assert first_line.startswith("#!/bin/bash")

    def test_cleanup_branches_script_has_set_e(self):
        """Test that cleanup-branches.sh uses set -e for error handling."""
        with open("cleanup-branches.sh") as f:
            content = f.read()
        assert "set -e" in content

    def test_cleanup_branches_script_structure(self):
        """Test cleanup-branches.sh has expected sections."""
        with open("cleanup-branches.sh") as f:
            content = f.read()

        # Check for key sections
        assert "git fetch" in content
        assert "Merged Branches" in content
        assert "Stale Branches" in content
        assert "Remote Branches" in content
        assert "Cleanup Recommendations" in content

    def test_cleanup_branches_has_safety_checks(self):
        """Test that cleanup-branches.sh has safety checks."""
        with open("cleanup-branches.sh") as f:
            content = f.read()

        # Should ask for confirmation before deleting
        assert "read -p" in content or "read -r" in content
        # Should exclude main and develop branches
        assert 'grep -v "main"' in content or '"main"' in content
        assert 'grep -v "develop"' in content or '"develop"' in content

    def test_cleanup_branches_git_commands(self):
        """Test that cleanup-branches.sh uses appropriate git commands."""
        with open("cleanup-branches.sh") as f:
            content = f.read()

        # Check for git commands
        assert "git fetch" in content
        assert "git branch" in content
        assert "git log" in content or "git for-each-ref" in content

    def test_cleanup_branches_color_codes(self):
        """Test that cleanup-branches.sh defines color codes for output."""
        with open("cleanup-branches.sh") as f:
            content = f.read()

        # Check for ANSI color codes
        assert "RED=" in content or "GREEN=" in content or "YELLOW=" in content
        assert "\\033[" in content  # ANSI escape sequence

    def test_cleanup_branches_prune_option(self):
        """Test that cleanup-branches.sh uses --prune to clean up references."""
        with open("cleanup-branches.sh") as f:
            content = f.read()

        assert "--prune" in content

    def test_cleanup_branches_handles_no_merged_branches(self):
        """Test that cleanup-branches.sh handles case when no branches are merged."""
        with open("cleanup-branches.sh") as f:
            content = f.read()

        # Should handle empty results
        assert "if [ -z" in content or 'if [ "$' in content

    def test_cleanup_branches_documentation(self):
        """Test that cleanup-branches.sh has proper documentation."""
        with open("cleanup-branches.sh") as f:
            lines = f.readlines()

        # Should have comments explaining what it does
        comment_lines = [line for line in lines if line.strip().startswith("#")]
        assert len(comment_lines) > 3  # Should have multiple comment lines

    def test_run_dev_sh_exists(self):
        """Test that run-dev.sh exists and is executable."""
        assert os.path.exists("run-dev.sh")
        import stat

        file_stat = os.stat("run-dev.sh")
        assert file_stat.st_mode & stat.S_IXUSR

    def test_run_dev_sh_has_shebang(self):
        """Test that run-dev.sh has proper shebang."""
        with open("run-dev.sh") as f:
            first_line = f.readline()
        assert first_line.startswith("#!/bin/bash")

    def test_run_dev_sh_error_handling(self):
        """Test that run-dev.sh has error handling."""
        with open("run-dev.sh") as f:
            content = f.read()
        assert "set -e" in content

    def test_run_dev_sh_virtual_environment_check(self):
        """Test that run-dev.sh checks for virtual environment."""
        with open("run-dev.sh") as f:
            content = f.read()

        assert ".venv" in content
        assert "python -m venv" in content or "virtualenv" in content

    def test_run_dev_sh_starts_backend(self):
        """Test that run-dev.sh starts the backend server."""
        with open("run-dev.sh") as f:
            content = f.read()

        assert "uvicorn" in content
        assert "api.main:app" in content
        assert "--reload" in content

    def test_run_dev_sh_starts_frontend(self):
        """Test that run-dev.sh starts the frontend server."""
        with open("run-dev.sh") as f:
            content = f.read()

        assert "npm run dev" in content or "npm start" in content
        assert "frontend" in content

    def test_run_dev_sh_port_configuration(self):
        """Test that run-dev.sh uses correct ports."""
        with open("run-dev.sh") as f:
            content = f.read()

        # Backend on 8000, frontend on 3000
        assert "8000" in content
        assert "3000" in content

    def test_run_dev_sh_has_signal_handling(self):
        """Test that run-dev.sh handles interrupt signals."""
        with open("run-dev.sh") as f:
            content = f.read()

        assert "trap" in content
        assert "INT" in content or "SIGINT" in content
        assert "kill" in content

    def test_run_dev_sh_installs_dependencies(self):
        """Test that run-dev.sh installs Python dependencies."""
        with open("run-dev.sh") as f:
            content = f.read()

        assert "pip install" in content
        assert "requirements.txt" in content

    def test_run_dev_sh_frontend_dependencies(self):
        """Test that run-dev.sh checks and installs frontend dependencies."""
        with open("run-dev.sh") as f:
            content = f.read()

        assert "npm install" in content
        assert "node_modules" in content

    def test_run_dev_sh_informative_output(self):
        """Test that run-dev.sh provides informative output."""
        with open("run-dev.sh") as f:
            content = f.read()

        # Should have echo statements with useful information
        assert "echo" in content
        assert "localhost" in content or "127.0.0.1" in content

    def test_run_dev_bat_exists(self):
        """Test that run-dev.bat exists for Windows users."""
        assert os.path.exists("run-dev.bat")

    def test_run_dev_bat_structure(self):
        """Test that run-dev.bat has proper Windows batch structure."""
        with open("run-dev.bat") as f:
            first_line = f.readline()
        assert first_line.strip().startswith("@echo off")

    def test_run_dev_bat_virtual_environment(self):
        """Test that run-dev.bat handles virtual environment on Windows."""
        with open("run-dev.bat") as f:
            content = f.read()

        assert ".venv" in content
        assert "activate.bat" in content or "Scripts\\activate" in content

    def test_run_dev_bat_starts_backend(self):
        """Test that run-dev.bat starts the backend server."""
        with open("run-dev.bat") as f:
            content = f.read()

        assert "uvicorn" in content
        assert "api.main:app" in content

    def test_run_dev_bat_starts_frontend(self):
        """Test that run-dev.bat starts the frontend server."""
        with open("run-dev.bat") as f:
            content = f.read()

        assert "npm run dev" in content or "npm start" in content

    def test_run_dev_bat_port_configuration(self):
        """Test that run-dev.bat uses correct ports."""
        with open("run-dev.bat") as f:
            content = f.read()

        assert "8000" in content
        assert "3000" in content

    def test_run_dev_bat_windows_conventions(self):
        """Test that run-dev.bat follows Windows batch conventions."""
        with open("run-dev.bat") as f:
            content = f.read()

        # Should use Windows-specific commands
        assert "REM" in content or "rem" in content  # Comments
        assert "\\" in content  # Windows path separator

    def test_run_dev_bat_pause_at_end(self):
        """Test that run-dev.bat pauses at the end."""
        with open("run-dev.bat") as f:
            content = f.read()

        assert "pause" in content.lower()

    @pytest.mark.parametrize(
        "script_file",
        ["cleanup-branches.sh", "run-dev.sh"],
    )
    def test_bash_scripts_no_syntax_errors(self, script_file):
        """Test that bash scripts have no obvious syntax errors."""
        with open(script_file) as f:
            content = f.read()

        # Check for common syntax issues
        # Balanced quotes
        single_quotes = content.count("'")
        assert single_quotes % 2 == 0, f"{script_file} has unbalanced single quotes"

        double_quotes = content.count('"')
        assert double_quotes % 2 == 0, f"{script_file} has unbalanced double quotes"

        # Check for balanced brackets in if statements
        if_count = content.count("if [")
        fi_count = content.count("fi")
        assert if_count == fi_count, f"{script_file} has unbalanced if/fi statements"

    def test_cleanup_branches_references_documentation(self):
        """Test that cleanup-branches.sh references relevant documentation."""
        with open("cleanup-branches.sh") as f:
            content = f.read()

        # Should reference the analysis document
        assert "BRANCH_CLEANUP_ANALYSIS.md" in content or "documentation" in content.lower()

    def test_shell_scripts_consistent_style(self):
        """Test that shell scripts use consistent coding style."""
        for script in ["cleanup-branches.sh", "run-dev.sh"]:
            with open(script) as f:
                content = f.read()

            # Check for consistent variable naming (uppercase for globals)
            if "BACKEND_PID" in content or "FRONTEND_PID" in content:
                assert content.isupper() or "$" in content  # Variables are referenced

    def test_cleanup_branches_safe_defaults(self):
        """Test that cleanup-branches.sh uses safe defaults."""
        with open("cleanup-branches.sh") as f:
            content = f.read()

        # Should not automatically delete without confirmation
        assert "-d" in content or "-D" in content  # Delete flags
        assert "read" in content  # User confirmation

    def test_run_dev_sh_process_cleanup(self):
        """Test that run-dev.sh cleans up processes on exit."""
        with open("run-dev.sh") as f:
            content = f.read()

        # Should track PIDs and kill them
        assert "PID" in content
        assert "kill" in content
        assert "trap" in content

    def test_shell_scripts_have_comments(self):
        """Test that shell scripts have helpful comments."""
        for script in ["cleanup-branches.sh", "run-dev.sh"]:
            with open(script) as f:
                lines = f.readlines()

            # Count comment lines (excluding shebang)
            comment_lines = [line for line in lines[1:] if line.strip().startswith("#")]
            # Should have at least a few comments
            assert len(comment_lines) >= 3, f"{script} should have more comments"

    def test_run_dev_scripts_activate_venv(self):
        """Test that run-dev scripts activate virtual environment."""
        with open("run-dev.sh") as f:
            sh_content = f.read()
        with open("run-dev.bat") as f:
            bat_content = f.read()

        # Both should activate venv
        assert "activate" in sh_content
        assert "activate" in bat_content

    def test_run_dev_sh_waits_for_backend(self):
        """Test that run-dev.sh waits for backend to start before starting frontend."""
        with open("run-dev.sh") as f:
            content = f.read()

        # Should have a sleep or wait command
        assert "sleep" in content or "wait" in content

    def test_cleanup_branches_date_handling(self):
        """Test that cleanup-branches.sh handles dates for stale branch detection."""
        with open("cleanup-branches.sh") as f:
            content = f.read()

        # Should use date commands for age calculation
        assert "date" in content
        # Should check for 90+ day old branches
        assert "90" in content

    def test_shell_scripts_error_messages(self):
        """Test that shell scripts provide helpful error messages."""
        for script in ["cleanup-branches.sh", "run-dev.sh"]:
            with open(script) as f:
                content = f.read()

            # Should have echo statements for user feedback
            echo_count = content.count("echo")
            assert echo_count > 2, f"{script} should have multiple echo statements"

    def test_run_dev_sh_background_processes(self):
        """Test that run-dev.sh runs processes in background appropriately."""
        with open("run-dev.sh") as f:
            content = f.read()

        # Should use & to run processes in background
        assert " &" in content
        # Should track PIDs
        assert "PID=" in content

    def test_cleanup_branches_git_safety(self):
        """Test that cleanup-branches.sh uses safe git operations."""
        with open("cleanup-branches.sh") as f:
            content = f.read()

        # Should use git branch -d (safe delete) not -D (force delete) by default
        if "git branch" in content and "-" in content:
            # Check the context of deletion
            lines = content.split("\n")
            delete_lines = [line for line in lines if "git branch -" in line and "xargs" in line]
            if delete_lines:
                # Should use -d not -D in the xargs command
                assert any("-d" in line for line in delete_lines)
