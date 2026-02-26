"""Unit tests for validating configuration files.

This module tests JSON and other configuration files to ensure:
- Valid JSON/YAML syntax
- Required keys are present
- Values meet expected types and constraints
- Configuration is internally consistent
"""

import json
import re
from pathlib import Path

import pytest
import yaml


class TestVercelConfig:
    """Test cases for vercel.json configuration."""

    @pytest.fixture
    def vercel_config(self):
        """Load vercel.json configuration."""
        config_path = Path("vercel.json")
        assert config_path.exists(), "vercel.json not found"

        with open(config_path) as f:
            return json.load(f)

    def test_vercel_config_valid_json(self):
        """Test that vercel.json is valid JSON."""
        config_path = Path("vercel.json")
        with open(config_path) as f:
            data = json.load(f)
        assert isinstance(data, dict)

    def test_vercel_config_has_builds(self, vercel_config):
        """Test that vercel.json has builds configuration."""
        assert "builds" in vercel_config
        assert isinstance(vercel_config["builds"], list)
        assert len(vercel_config["builds"]) > 0

    def test_vercel_config_has_routes(self, vercel_config):
        """Test that vercel.json has routes configuration."""
        assert "routes" in vercel_config
        assert isinstance(vercel_config["routes"], list)
        assert len(vercel_config["routes"]) > 0

    def test_vercel_build_python_backend(self, vercel_config):
        """Test that Python backend build is configured correctly."""
        builds = vercel_config["builds"]
        python_build = next((b for b in builds if "api/main.py" in b["src"]), None)

        assert python_build is not None, "Python backend build not found"
        assert python_build["use"] == "@vercel/python"
        assert "config" in python_build
        assert "maxLambdaSize" in python_build["config"]

    def test_vercel_build_nextjs_frontend(self, vercel_config):
        """Test that Next.js frontend build is configured correctly."""
        builds = vercel_config["builds"]
        nextjs_build = next((b for b in builds if "package.json" in b["src"]), None)

        assert nextjs_build is not None, "Next.js frontend build not found"
        assert nextjs_build["use"] == "@vercel/next"

    def test_vercel_routes_api_routing(self, vercel_config):
        """Test that API routes are configured correctly."""
        routes = vercel_config["routes"]
        api_route = next((r for r in routes if "/api/" in r["src"]), None)

        assert api_route is not None, "API route not found"
        assert api_route["dest"] == "api/main.py"

    def test_vercel_routes_frontend_routing(self, vercel_config):
        """Test that frontend routes are configured correctly."""
        routes = vercel_config["routes"]
        frontend_route = next((r for r in routes if r["src"] == "/(.*)"), None)

        assert frontend_route is not None, "Frontend route not found"
        assert "frontend" in frontend_route["dest"]

    def test_vercel_lambda_size_reasonable(self, vercel_config):
        """Test that Lambda size limit is reasonable."""
        builds = vercel_config["builds"]
        python_build = next((b for b in builds if "api/main.py" in b["src"]), None)

        if python_build and "config" in python_build:
            max_size = python_build["config"].get("maxLambdaSize", "50mb")
            # Parse size (e.g., "50mb")
            size_value = int(max_size.replace("mb", ""))
            assert 1 <= size_value <= 250, "Lambda size should be between 1MB and 250MB"


class TestNextConfig:
    """Test cases for Next.js configuration."""

    @pytest.fixture
    def next_config_content(self):
        """Load Next.js configuration file content."""
        config_path = Path("frontend/next.config.js")
        assert config_path.exists(), "next.config.js not found"

        with open(config_path) as f:
            return f.read()

    def test_next_config_exists(self):
        """Test that next.config.js exists."""
        config_path = Path("frontend/next.config.js")
        assert config_path.exists()

    def test_next_config_has_module_exports(self, next_config_content):
        """Test that next.config.js exports configuration."""
        assert "module.exports" in next_config_content

    def test_next_config_has_react_strict_mode(self, next_config_content):
        """Test that React strict mode is configured."""
        assert "reactStrictMode" in next_config_content

    def test_next_config_has_env_configuration(self, next_config_content):
        """Test that environment variables are configured."""
        assert "env" in next_config_content or "NEXT_PUBLIC" in next_config_content


class TestPackageJson:
    """Test cases for package.json configuration."""

    @pytest.fixture
    def package_json(self):
        """Load package.json configuration."""
        config_path = Path("frontend/package.json")
        assert config_path.exists(), "package.json not found"

        with open(config_path) as f:
            return json.load(f)

    def test_package_json_valid_json(self):
        """Test that package.json is valid JSON."""
        config_path = Path("frontend/package.json")
        with open(config_path) as f:
            data = json.load(f)
        assert isinstance(data, dict)

    def test_package_json_has_required_fields(self, package_json):
        """Test that package.json has required fields."""
        required_fields = ["name", "version", "scripts", "dependencies"]
        for field in required_fields:
            assert field in package_json, f"Missing required field: {field}"

    def test_package_json_has_build_scripts(self, package_json):
        """Test that package.json has necessary build scripts."""
        scripts = package_json["scripts"]
        required_scripts = ["dev", "build", "start"]

        for script in required_scripts:
            assert script in scripts, f"Missing script: {script}"

    def test_package_json_has_react_dependencies(self, package_json):
        """Test that React dependencies are present."""
        deps = package_json["dependencies"]
        required_deps = ["react", "react-dom", "next"]

        for dep in required_deps:
            assert dep in deps, f"Missing dependency: {dep}"

    def test_package_json_has_visualization_deps(self, package_json):
        """Test that visualization dependencies are present."""
        deps = package_json["dependencies"]
        viz_deps = ["plotly.js", "react-plotly.js"]

        for dep in viz_deps:
            assert dep in deps, f"Missing visualization dependency: {dep}"

    def test_package_json_has_axios(self, package_json):
        """Test that axios is included for API calls."""
        deps = package_json["dependencies"]
        assert "axios" in deps, "Missing axios dependency"

    def test_package_json_has_typescript_deps(self, package_json):
        """Test that TypeScript dependencies are present."""
        dev_deps = package_json.get("devDependencies", {})
        ts_deps = ["typescript", "@types/react", "@types/node"]

        for dep in ts_deps:
            assert dep in dev_deps, f"Missing TypeScript dependency: {dep}"

    def test_package_json_version_format(self, package_json):
        """Test that version follows semantic versioning.

        Supports standard semantic versions (e.g., 1.0.0) and pre-release versions
        (e.g., 1.0.0-beta, 1.0.0-rc.1, 1.0.0-alpha.1).
        """
        version = package_json["version"]
        # Semantic versioning pattern: major.minor.patch with optional pre-release suffix
        semver_pattern = r"^\d+\.\d+\.\d+(-[\w.]+)?$"
        assert re.match(
            semver_pattern, version
        ), f"Version should follow semantic versioning (x.y.z or x.y.z-prerelease): {version}"


class TestTSConfig:
    """Test cases for TypeScript configuration."""

    @pytest.fixture
    def tsconfig(self):
        """Load tsconfig.json."""
        config_path = Path("frontend/tsconfig.json")
        assert config_path.exists(), "tsconfig.json not found"

        with open(config_path) as f:
            return json.load(f)

    def test_tsconfig_valid_json(self):
        """Test that tsconfig.json is valid JSON."""
        config_path = Path("frontend/tsconfig.json")
        with open(config_path) as f:
            data = json.load(f)
        assert isinstance(data, dict)

    def test_tsconfig_has_compiler_options(self, tsconfig):
        """Test that tsconfig has compiler options."""
        assert "compilerOptions" in tsconfig
        assert isinstance(tsconfig["compilerOptions"], dict)

    def test_tsconfig_strict_mode_enabled(self, tsconfig):
        """Test that TypeScript strict mode is enabled."""
        compiler_options = tsconfig["compilerOptions"]
        assert compiler_options.get("strict", False), "Strict mode should be enabled"

    def test_tsconfig_has_jsx_configuration(self, tsconfig):
        """Test that JSX is configured for React."""
        compiler_options = tsconfig["compilerOptions"]
        assert "jsx" in compiler_options
        assert compiler_options["jsx"] in ["preserve", "react", "react-jsx"]

    def test_tsconfig_module_resolution(self, tsconfig):
        """Test that module resolution is configured."""
        compiler_options = tsconfig["compilerOptions"]
        assert "moduleResolution" in compiler_options

    def test_tsconfig_has_path_mapping(self, tsconfig):
        """Test that path mapping is configured."""
        compiler_options = tsconfig["compilerOptions"]
        if "paths" in compiler_options:
            paths = compiler_options["paths"]
            assert isinstance(paths, dict)


class TestTailwindConfig:
    """Test cases for Tailwind CSS configuration."""

    @pytest.fixture
    def tailwind_config_content(self):
        """Load Tailwind configuration content."""
        config_path = Path("frontend/tailwind.config.js")
        assert config_path.exists(), "tailwind.config.js not found"

        with open(config_path) as f:
            return f.read()

    def test_tailwind_config_exists(self):
        """Test that tailwind.config.js exists."""
        config_path = Path("frontend/tailwind.config.js")
        assert config_path.exists()

    def test_tailwind_config_has_module_exports(self, tailwind_config_content):
        """Test that Tailwind config exports configuration."""
        assert "module.exports" in tailwind_config_content

    def test_tailwind_config_has_content_paths(self, tailwind_config_content):
        """Test that content paths are configured."""
        assert "content" in tailwind_config_content

    def test_tailwind_config_includes_app_directory(self, tailwind_config_content):
        """Test that content paths include app directory."""
        assert "app/" in tailwind_config_content or "./app/" in tailwind_config_content


class TestEnvExample:
    """Test cases for .env.example file."""

    @pytest.fixture
    def env_example_content(self):
        """Load .env.example content."""
        config_path = Path(".env.example")
        assert config_path.exists(), ".env.example not found"

        with open(config_path) as f:
            return f.read()

    def test_env_example_exists(self):
        """Test that .env.example exists."""
        config_path = Path(".env.example")
        assert config_path.exists()

    def test_env_example_has_api_url(self, env_example_content):
        """Test that NEXT_PUBLIC_API_URL is documented."""
        assert "NEXT_PUBLIC_API_URL" in env_example_content

    def test_env_example_has_cors_config(self, env_example_content):
        """Test that CORS configuration is documented."""
        assert "ALLOWED_ORIGINS" in env_example_content or "CORS" in env_example_content

    def test_env_example_has_comments(self, env_example_content):
        """Test that .env.example has helpful comments."""
        assert "#" in env_example_content

    def test_env_example_no_real_secrets(self, env_example_content):
        """Test that .env.example doesn't contain real secrets."""
        # Check for common secret patterns
        suspicious_patterns = [
            "sk_live",  # Stripe live keys
            "prod_",  # Production keys
            "pk_live",  # Public live keys
        ]

        for pattern in suspicious_patterns:
            assert pattern not in env_example_content.lower(), f"Potential real secret found: {pattern}"


class TestGitignore:
    """Test cases for .gitignore configuration."""

    @pytest.fixture
    def gitignore_content(self):
        """Load .gitignore content."""
        config_path = Path(".gitignore")
        assert config_path.exists(), ".gitignore not found"

        with open(config_path) as f:
            return f.read()

    def test_gitignore_exists(self):
        """Test that .gitignore exists."""
        config_path = Path(".gitignore")
        assert config_path.exists()

    def test_gitignore_excludes_node_modules(self, gitignore_content):
        """Test that node_modules is excluded."""
        assert "node_modules" in gitignore_content

    def test_gitignore_excludes_next_artifacts(self, gitignore_content):
        """Test that Next.js build artifacts are excluded."""
        assert ".next" in gitignore_content or ".next/" in gitignore_content

    def test_gitignore_excludes_env_files(self, gitignore_content):
        """Test that environment files are excluded."""
        assert ".env.local" in gitignore_content

    def test_gitignore_excludes_vercel(self, gitignore_content):
        """Test that Vercel directory is excluded."""
        assert ".vercel" in gitignore_content

    def test_gitignore_excludes_python_artifacts(self, gitignore_content):
        """Test that Python artifacts are excluded."""
        assert "__pycache__" in gitignore_content
        # Check for *.pyc explicitly or the pattern *.py[cod] (which matches files ending in .pyc, .pyo, or .pyd; [cod] means any single character from the set {c, o, d})
        assert "*.pyc" in gitignore_content or "*.py[cod]" in gitignore_content


class TestRequirementsTxt:
    """Test cases for requirements.txt."""

    require_version_pinning = True  # When True, enforces version constraints for all dependencies in requirements.txt

    @pytest.fixture
    def requirements(self):
        """Load requirements.txt content."""
        config_path = Path("requirements.txt")
        assert config_path.exists(), "requirements.txt not found"

        with open(config_path) as f:
            return [line.strip() for line in f if line.strip() and not line.startswith("#")]

    def test_requirements_exists(self):
        """Test that requirements.txt exists."""
        config_path = Path("requirements.txt")
        assert config_path.exists()

    def test_requirements_has_fastapi(self, requirements):
        """Test that FastAPI is in requirements."""
        assert any("fastapi" in req.lower() for req in requirements)

    def test_requirements_has_uvicorn(self, requirements):
        """Test that Uvicorn is in requirements."""
        assert any("uvicorn" in req.lower() for req in requirements)

    def test_requirements_has_pydantic(self, requirements):
        """Test that Pydantic is in requirements."""
        assert any("pydantic" in req.lower() for req in requirements)

    def test_requirements_has_version_constraints(self, requirements):
        """Test that packages have version constraints (if project policy requires)."""
        # Skip this test if project doesn't require version pinning
        if not self.require_version_pinning:
            pytest.skip("Version pinning not required for this project")

        for req in requirements:
            if not req.startswith("-"):
                assert any(
                    op in req for op in [">=", "==", "~=", "<="]
                ), f"Package should have version constraint: {req}"


class TestPostCSSConfig:
    """Test cases for PostCSS configuration."""

    @pytest.fixture
    def postcss_config_content(self):
        """Load PostCSS configuration."""
        config_path = Path("frontend/postcss.config.js")
        if not config_path.exists():
            pytest.skip("postcss.config.js not found")

        with open(config_path) as f:
            return f.read()

    def test_postcss_config_has_tailwindcss(self, postcss_config_content):
        """Test that Tailwind CSS plugin is configured."""
        assert "tailwindcss" in postcss_config_content

    def test_postcss_config_has_autoprefixer(self, postcss_config_content):
        """Test that autoprefixer plugin is configured."""
        assert "autoprefixer" in postcss_config_content


class TestConfigurationConsistency:
    """Test consistency across configuration files."""

    def test_api_url_consistency(self):
        """Test that API URL is consistent across configurations."""
        # Check .env.example
        with open(".env.example") as f:
            env_content = f.read()

        # Check next.config.js
        with open("frontend/next.config.js") as f:
            next_config = f.read()

        # Both should mention NEXT_PUBLIC_API_URL
        assert "NEXT_PUBLIC_API_URL" in env_content
        assert "NEXT_PUBLIC_API_URL" in next_config

    def test_package_json_and_tsconfig_consistency(self):
        """Test that package.json and tsconfig are consistent."""
        with open("frontend/package.json") as f:
            package = json.load(f)

        with open("frontend/tsconfig.json") as f:
            tsconfig = json.load(f)

        # If TypeScript is in devDependencies, tsconfig should exist
        if "typescript" in package.get("devDependencies", {}):
            assert "compilerOptions" in tsconfig

    def test_frontend_build_configuration_matches(self):
        """Test that frontend configurations are aligned."""
        # Verify package.json scripts match expected Next.js commands
        with open("frontend/package.json") as f:
            package = json.load(f)

        scripts = package["scripts"]

        # Next.js standard scripts
        assert "next dev" in scripts.get("dev", "") or "next" in scripts.get("dev", "")
        assert "next build" in scripts.get("build", "") or "next" in scripts.get("build", "")
        assert "next start" in scripts.get("start", "") or "next" in scripts.get("start", "")


class TestCircleCIConfig:
    """Test cases for CircleCI configuration."""

    @pytest.fixture
    def circleci_config(self):
        """Load CircleCI configuration."""
        config_path = Path(".circleci/config.yml")
        assert config_path.exists(), "CircleCI config not found"

        with open(config_path) as f:
            return yaml.safe_load(f)

    def test_circleci_config_valid_yaml(self):
        """Test that CircleCI config is valid YAML."""
        config_path = Path(".circleci/config.yml")
        with open(config_path) as f:
            data = yaml.safe_load(f)
        assert isinstance(data, dict)

    def test_circleci_config_has_version(self, circleci_config):
        """Test that CircleCI config specifies a version."""
        assert "version" in circleci_config
        # CircleCI 2.1 is current standard
        assert circleci_config["version"] >= 2.0

    def test_circleci_config_has_jobs(self, circleci_config):
        """Test that CircleCI config defines jobs."""
        assert "jobs" in circleci_config
        assert isinstance(circleci_config["jobs"], dict)
        assert len(circleci_config["jobs"]) > 0

    def test_circleci_config_has_workflows(self, circleci_config):
        """Test that CircleCI config defines workflows."""
        assert "workflows" in circleci_config
        assert isinstance(circleci_config["workflows"], dict)

    def test_circleci_python_lint_job(self, circleci_config):
        """Test that python-lint job is properly configured."""
        jobs = circleci_config["jobs"]
        assert "python-lint" in jobs

        python_lint = jobs["python-lint"]
        assert "executor" in python_lint
        assert "steps" in python_lint
        assert isinstance(python_lint["steps"], list)

        # Check for checkout step
        steps = python_lint["steps"]
        assert any(step == "checkout" or (isinstance(step, dict) and "checkout" in step) for step in steps)

    def test_circleci_python_test_job(self, circleci_config):
        """Test that python-test job is properly configured."""
        jobs = circleci_config["jobs"]
        assert "python-test" in jobs

        python_test = jobs["python-test"]
        assert "executor" in python_test
        assert "steps" in python_test

        # Check for parallelism
        if "parallelism" in python_test:
            assert python_test["parallelism"] > 0
            assert python_test["parallelism"] <= 10  # Reasonable upper bound

    def test_circleci_python_security_job(self, circleci_config):
        """Test that python-security job is properly configured."""
        jobs = circleci_config["jobs"]
        assert "python-security" in jobs

        python_security = jobs["python-security"]
        assert "executor" in python_security
        assert "steps" in python_security

    def test_circleci_frontend_jobs(self, circleci_config):
        """Test that frontend jobs are defined."""
        jobs = circleci_config["jobs"]
        assert "frontend-lint" in jobs
        assert "frontend-build" in jobs

        # Verify they use appropriate executor
        frontend_lint = jobs["frontend-lint"]
        assert "executor" in frontend_lint

    def test_circleci_docker_build_job(self, circleci_config):
        """Test that docker-build job is properly configured."""
        jobs = circleci_config["jobs"]
        assert "docker-build" in jobs

        docker_build = jobs["docker-build"]
        assert "steps" in docker_build

        # Should have setup_remote_docker step
        steps = docker_build["steps"]
        assert any(
            isinstance(step, dict) and "setup_remote_docker" in step
            for step in steps
        )

    def test_circleci_executors_defined(self, circleci_config):
        """Test that executors are properly defined."""
        assert "executors" in circleci_config
        executors = circleci_config["executors"]

        assert "python-executor" in executors
        assert "node-executor" in executors

        # Verify executor structure
        python_executor = executors["python-executor"]
        assert "docker" in python_executor
        assert isinstance(python_executor["docker"], list)
        assert len(python_executor["docker"]) > 0

    def test_circleci_orbs_usage(self, circleci_config):
        """Test that orbs are properly declared."""
        if "orbs" in circleci_config:
            orbs = circleci_config["orbs"]
            assert isinstance(orbs, dict)

            # Check for commonly used orbs
            # CodeCov orb for coverage reporting
            if "codecov" in orbs:
                assert isinstance(orbs["codecov"], str)

    def test_circleci_cache_keys_consistent(self, circleci_config):
        """Test that cache keys follow consistent patterns."""
        jobs = circleci_config["jobs"]

        for job_name, job_config in jobs.items():
            if "steps" not in job_config:
                continue

            steps = job_config["steps"]
            restore_keys = []
            save_keys = []

            for step in steps:
                if isinstance(step, dict):
                    if "restore_cache" in step:
                        keys = step["restore_cache"].get("keys", [])
                        restore_keys.extend(keys)
                    if "save_cache" in step:
                        key = step["save_cache"].get("key", "")
                        if key:
                            save_keys.append(key)

            # If we have save_cache, we should have restore_cache
            if save_keys:
                assert len(restore_keys) > 0, f"Job {job_name} saves cache but doesn't restore"

    def test_circleci_workflow_dependencies_valid(self, circleci_config):
        """Test that workflow job dependencies reference existing jobs."""
        workflows = circleci_config["workflows"]
        jobs = circleci_config["jobs"]
        job_names = set(jobs.keys())

        for workflow_name, workflow_config in workflows.items():
            # Skip non-dict entries (e.g., version key)
            if not isinstance(workflow_config, dict):
                continue

            if "jobs" not in workflow_config:
                continue

            workflow_jobs = workflow_config["jobs"]
            for job_entry in workflow_jobs:
                if isinstance(job_entry, dict):
                    # Get the job name (first key in dict)
                    job_name = list(job_entry.keys())[0]
                    job_config = job_entry[job_name]

                    # Check if requires field references valid jobs
                    if "requires" in job_config:
                        required_jobs = job_config["requires"]
                        for required_job in required_jobs:
                            assert required_job in job_names, f"Job {job_name} requires non-existent job {required_job}"

    def test_circleci_nightly_security_schedule(self, circleci_config):
        """Test that nightly security scan is properly scheduled."""
        workflows = circleci_config["workflows"]

        if "nightly-security" in workflows:
            nightly = workflows["nightly-security"]
            assert "triggers" in nightly

            triggers = nightly["triggers"]
            assert isinstance(triggers, list)
            assert len(triggers) > 0

            # Check for schedule trigger
            schedule_trigger = triggers[0]
            assert "schedule" in schedule_trigger
            schedule = schedule_trigger["schedule"]
            assert "cron" in schedule
            assert "filters" in schedule

    def test_circleci_docker_build_on_main_only(self, circleci_config):
        """Test that docker-build only runs on main/develop branches."""
        workflows = circleci_config["workflows"]

        # Find workflow containing docker-build
        for workflow_name, workflow_config in workflows.items():
            # Skip non-dict entries (e.g., version key)
            if not isinstance(workflow_config, dict):
                continue

            if "jobs" not in workflow_config:
                continue

            for job_entry in workflow_config["jobs"]:
                if isinstance(job_entry, dict) and "docker-build" in job_entry:
                    docker_build_config = job_entry["docker-build"]
                    assert "filters" in docker_build_config
                    filters = docker_build_config["filters"]
                    assert "branches" in filters
                    branches = filters["branches"]
                    assert "only" in branches
                    # Should specify main and/or develop
                    allowed_branches = branches["only"]
                    assert isinstance(allowed_branches, list)
                    assert any(branch in ["main", "develop"] for branch in allowed_branches)


class TestGitHubActionsCommon:
    """Test cases for GitHub Actions composite action."""

    @pytest.fixture
    def github_action_config(self):
        """Load GitHub Actions composite action configuration."""
        config_path = Path(".github/actions/ci-common/action.yml")
        assert config_path.exists(), "GitHub Actions composite action not found"

        with open(config_path) as f:
            return yaml.safe_load(f)

    def test_github_action_valid_yaml(self):
        """Test that GitHub Actions config is valid YAML."""
        config_path = Path(".github/actions/ci-common/action.yml")
        with open(config_path) as f:
            data = yaml.safe_load(f)
        assert isinstance(data, dict)

    def test_github_action_has_required_fields(self, github_action_config):
        """Test that action has required metadata fields."""
        assert "name" in github_action_config
        assert "description" in github_action_config
        assert isinstance(github_action_config["name"], str)
        assert isinstance(github_action_config["description"], str)
        assert len(github_action_config["name"]) > 0
        assert len(github_action_config["description"]) > 0

    def test_github_action_has_inputs(self, github_action_config):
        """Test that action defines inputs."""
        assert "inputs" in github_action_config
        inputs = github_action_config["inputs"]
        assert isinstance(inputs, dict)

        # Check for expected inputs
        assert "language" in inputs
        assert "working-directory" in inputs

    def test_github_action_language_input_required(self, github_action_config):
        """Test that language input is marked as required."""
        inputs = github_action_config["inputs"]
        language = inputs["language"]
        assert "required" in language
        assert language["required"] is True

    def test_github_action_has_runs(self, github_action_config):
        """Test that action defines runs configuration."""
        assert "runs" in github_action_config
        runs = github_action_config["runs"]
        assert isinstance(runs, dict)
        assert "using" in runs
        assert runs["using"] == "composite"

    def test_github_action_has_steps(self, github_action_config):
        """Test that action defines steps."""
        runs = github_action_config["runs"]
        assert "steps" in runs
        steps = runs["steps"]
        assert isinstance(steps, list)
        assert len(steps) > 0

    def test_github_action_setup_python_step(self, github_action_config):
        """Test that Python setup step is properly configured."""
        steps = github_action_config["runs"]["steps"]

        python_step = next((s for s in steps if s.get("name") == "Setup Python"), None)
        assert python_step is not None

        # Should have conditional
        assert "if" in python_step
        assert "inputs.language == 'python'" in python_step["if"]

        # Should use setup-python action
        assert "uses" in python_step
        assert "setup-python" in python_step["uses"]

    def test_github_action_setup_node_step(self, github_action_config):
        """Test that Node.js setup step is properly configured."""
        steps = github_action_config["runs"]["steps"]

        node_step = next((s for s in steps if s.get("name") == "Setup Node.js"), None)
        assert node_step is not None

        # Should have conditional
        assert "if" in node_step
        assert "inputs.language == 'node'" in node_step["if"]

        # Should use setup-node action
        assert "uses" in node_step
        assert "setup-node" in node_step["uses"]

    def test_github_action_steps_use_composite_shell(self, github_action_config):
        """Test that all run steps specify shell for composite actions."""
        steps = github_action_config["runs"]["steps"]

        for step in steps:
            if "run" in step:
                # Composite actions require shell to be specified
                assert "shell" in step, f"Step {step.get('name', 'unnamed')} is missing shell specification"
                assert step["shell"] == "bash"

    def test_github_action_conditional_steps(self, github_action_config):
        """Test that install/build/test steps are conditional."""
        steps = github_action_config["runs"]["steps"]

        conditional_steps = ["Install dependencies", "Build", "Test"]

        for step_name in conditional_steps:
            step = next((s for s in steps if s.get("name") == step_name), None)
            if step:
                assert "if" in step, f"Step {step_name} should be conditional"

    def test_github_action_working_directory_usage(self, github_action_config):
        """Test that steps use working-directory input."""
        steps = github_action_config["runs"]["steps"]

        # Steps with run commands should use working-directory
        for step in steps:
            if "run" in step and "working-directory" in step:
                working_dir = step["working-directory"]
                assert "inputs.working-directory" in working_dir


class TestGitHubCopilotInstructions:
    """Test cases for GitHub Copilot instructions documentation."""

    @pytest.fixture
    def copilot_instructions(self):
        """Load Copilot instructions content."""
        doc_path = Path(".github/copilot-instructions.md")
        assert doc_path.exists(), "Copilot instructions not found"

        with open(doc_path) as f:
            return f.read()

    def test_copilot_instructions_exists(self):
        """Test that Copilot instructions file exists."""
        doc_path = Path(".github/copilot-instructions.md")
        assert doc_path.exists()

    def test_copilot_instructions_has_headers(self, copilot_instructions):
        """Test that documentation has proper header structure."""
        # Should have main header
        assert "# Copilot instructions" in copilot_instructions or "#" in copilot_instructions

        # Check for key sections
        assert "Purpose" in copilot_instructions or "purpose" in copilot_instructions.lower()
        assert "Quick start" in copilot_instructions or "quick start" in copilot_instructions.lower()

    def test_copilot_instructions_mentions_key_files(self, copilot_instructions):
        """Test that documentation mentions key project files."""
        key_files = ["app.py", "asset_graph.py", "financial_models.py"]

        for file_name in key_files:
            assert file_name in copilot_instructions, f"Should mention key file: {file_name}"

    def test_copilot_instructions_has_code_examples(self, copilot_instructions):
        """Test that documentation includes code examples."""
        # Check for code blocks or backticks
        assert "```" in copilot_instructions or "`" in copilot_instructions

    def test_copilot_instructions_mentions_dependencies(self, copilot_instructions):
        """Test that documentation mentions project dependencies."""
        # Should mention key dependencies
        dependencies = ["Gradio", "Plotly", "requirements.txt"]

        mentions_deps = any(dep in copilot_instructions for dep in dependencies)
        assert mentions_deps, "Should mention at least one key dependency"

    def test_copilot_instructions_has_conventions_section(self, copilot_instructions):
        """Test that documentation describes project conventions."""
        conventions_keywords = ["convention", "pattern", "guideline", "practice"]

        has_conventions = any(keyword in copilot_instructions.lower() for keyword in conventions_keywords)
        assert has_conventions, "Should describe coding conventions or patterns"

    def test_copilot_instructions_mentions_testing(self, copilot_instructions):
        """Test that documentation mentions testing practices."""
        testing_keywords = ["test", "testing"]

        has_testing_info = any(keyword in copilot_instructions.lower() for keyword in testing_keywords)
        assert has_testing_info, "Should provide testing guidance"


class TestGitHubIssueTemplates:
    """Test cases for GitHub issue templates."""

    @pytest.fixture
    def custom_issue_template(self):
        """Load custom issue template."""
        template_path = Path(".github/ISSUE_TEMPLATE/custom.md")
        assert template_path.exists(), "Custom issue template not found"

        with open(template_path) as f:
            return f.read()

    def test_custom_issue_template_exists(self):
        """Test that custom issue template exists."""
        template_path = Path(".github/ISSUE_TEMPLATE/custom.md")
        assert template_path.exists()

    def test_custom_issue_template_has_frontmatter(self, custom_issue_template):
        """Test that template has YAML frontmatter."""
        assert "---" in custom_issue_template
        # Should have at least 2 occurrences (start and end of frontmatter)
        assert custom_issue_template.count("---") >= 2

    def test_custom_issue_template_frontmatter_fields(self, custom_issue_template):
        """Test that frontmatter has required fields."""
        # Extract frontmatter
        lines = custom_issue_template.split("\n")
        if lines[0] == "---":
            # Find end of frontmatter
            end_idx = lines[1:].index("---") + 1
            frontmatter = "\n".join(lines[1:end_idx])

            # Should have name and about fields
            assert "name:" in frontmatter
            assert "about:" in frontmatter


class TestCodacyInstructions:
    """Test cases for Codacy instructions documentation."""

    @pytest.fixture
    def codacy_instructions(self):
        """Load Codacy instructions content."""
        doc_path = Path(".github/instructions/codacy.instructions.md")
        assert doc_path.exists(), "Codacy instructions not found"

        with open(doc_path) as f:
            return f.read()

    def test_codacy_instructions_exists(self):
        """Test that Codacy instructions file exists."""
        doc_path = Path(".github/instructions/codacy.instructions.md")
        assert doc_path.exists()

    def test_codacy_instructions_has_yaml_frontmatter(self, codacy_instructions):
        """Test that instructions have YAML frontmatter."""
        assert "---" in codacy_instructions
        # Should start with frontmatter
        assert codacy_instructions.strip().startswith("---")

    def test_codacy_instructions_has_critical_rules(self, codacy_instructions):
        """Test that instructions define critical rules."""
        assert "CRITICAL" in codacy_instructions

    def test_codacy_instructions_mentions_codacy_cli(self, codacy_instructions):
        """Test that instructions mention Codacy CLI tool."""
        assert "codacy_cli_analyze" in codacy_instructions or "Codacy CLI" in codacy_instructions

    def test_codacy_instructions_has_security_checks(self, codacy_instructions):
        """Test that instructions include security checking guidance."""
        security_keywords = ["security", "vulnerabilit", "trivy"]

        has_security = any(keyword in codacy_instructions.lower() for keyword in security_keywords)
        assert has_security, "Should mention security checks"

    def test_codacy_instructions_has_dependency_check_rules(self, codacy_instructions):
        """Test that instructions cover dependency checking."""
        assert "dependencies" in codacy_instructions.lower() or "package" in codacy_instructions.lower()

    def test_codacy_instructions_has_mcp_server_guidance(self, codacy_instructions):
        """Test that instructions mention MCP Server."""
        assert "MCP" in codacy_instructions or "mcp" in codacy_instructions.lower()

    def test_codacy_instructions_structured_sections(self, codacy_instructions):
        """Test that instructions are well-structured with sections."""
        # Should have multiple ## headers for sections
        assert codacy_instructions.count("##") >= 3, "Should have multiple sections"


class TestCircleCIEdgeCases:
    """Additional edge case and regression tests for CircleCI config."""

    @pytest.fixture
    def circleci_config(self):
        """Load CircleCI configuration."""
        config_path = Path(".circleci/config.yml")
        assert config_path.exists(), "CircleCI config not found"

        with open(config_path) as f:
            return yaml.safe_load(f)

    def test_circleci_no_empty_jobs(self, circleci_config):
        """Test that no jobs are empty or missing critical fields."""
        jobs = circleci_config["jobs"]

        for job_name, job_config in jobs.items():
            # Every job should have steps or executor
            assert "steps" in job_config or "executor" in job_config or "docker" in job_config, \
                f"Job {job_name} is missing steps or executor configuration"

    def test_circleci_checkout_in_jobs(self, circleci_config):
        """Test that jobs with steps include checkout step."""
        jobs = circleci_config["jobs"]

        for job_name, job_config in jobs.items():
            if "steps" in job_config:
                steps = job_config["steps"]
                # Check for checkout step (critical for getting code)
                has_checkout = any(
                    step == "checkout" or (isinstance(step, dict) and "checkout" in step)
                    for step in steps
                )
                # Some jobs like docker-build might not need checkout if they use special setup
                # But most jobs should have it
                if job_name not in ["docker-build"]:  # Exclude known exceptions
                    assert has_checkout or "setup_remote_docker" in str(steps), \
                        f"Job {job_name} should include checkout step"

    def test_circleci_reasonable_parallelism(self, circleci_config):
        """Test that parallelism values are reasonable."""
        jobs = circleci_config["jobs"]

        for job_name, job_config in jobs.items():
            if "parallelism" in job_config:
                parallelism = job_config["parallelism"]
                assert 1 <= parallelism <= 20, \
                    f"Job {job_name} has unreasonable parallelism: {parallelism}"

    def test_circleci_resource_class_specified(self, circleci_config):
        """Test that executors specify resource class for cost optimization."""
        if "executors" in circleci_config:
            executors = circleci_config["executors"]

            for executor_name, executor_config in executors.items():
                # Having resource_class helps with cost and performance tuning
                if "resource_class" in executor_config:
                    resource_class = executor_config["resource_class"]
                    # Should be valid CircleCI resource class
                    valid_classes = ["small", "medium", "medium+", "large", "xlarge", "2xlarge"]
                    assert resource_class in valid_classes, \
                        f"Executor {executor_name} has invalid resource class: {resource_class}"

    def test_circleci_docker_images_pinned(self, circleci_config):
        """Test that Docker images use specific versions (not latest)."""
        executors = circleci_config.get("executors", {})

        for executor_name, executor_config in executors.items():
            if "docker" in executor_config:
                images = executor_config["docker"]
                for image_config in images:
                    if "image" in image_config:
                        image = image_config["image"]
                        # Should include version tag, not just :latest or no tag
                        assert ":" in image, \
                            f"Docker image in {executor_name} should specify version: {image}"
                        # Check it's not using :latest (bad practice)
                        assert not image.endswith(":latest"), \
                            f"Docker image in {executor_name} should not use :latest tag"


class TestGitHubActionsEdgeCases:
    """Additional edge case tests for GitHub Actions."""

    @pytest.fixture
    def github_action_config(self):
        """Load GitHub Actions composite action configuration."""
        config_path = Path(".github/actions/ci-common/action.yml")
        assert config_path.exists(), "GitHub Actions composite action not found"

        with open(config_path) as f:
            return yaml.safe_load(f)

    def test_github_action_input_defaults(self, github_action_config):
        """Test that optional inputs have defaults where appropriate."""
        inputs = github_action_config["inputs"]

        for input_name, input_config in inputs.items():
            is_required = input_config.get("required", False)
            has_default = "default" in input_config

            # If not required and not a conditional input (like python-version), should have a default
            # Conditional inputs like python-version are only used when language==python
            conditional_inputs = ["python-version", "node-version"]

            if not is_required and input_name not in conditional_inputs:
                assert has_default, \
                    f"Optional input {input_name} should have a default value"

    def test_github_action_error_handling_in_steps(self, github_action_config):
        """Test that run steps use proper error handling."""
        steps = github_action_config["runs"]["steps"]

        for step in steps:
            if "run" in step:
                run_command = step["run"]
                # Check for set -e or pipefail for proper error propagation
                if "eval" in run_command or len(run_command.split("\n")) > 1:
                    assert "set -" in run_command or "pipefail" in run_command, \
                        f"Multi-line step {step.get('name', 'unnamed')} should use set -e or pipefail"

    def test_github_action_no_hardcoded_values(self, github_action_config):
        """Test that steps use inputs rather than hardcoded values."""
        steps = github_action_config["runs"]["steps"]

        for step in steps:
            if "with" in step:
                with_values = step["with"]
                # Version pinning is OK, but paths should use inputs
                if "python-version" in with_values:
                    python_version = with_values["python-version"]
                    # Should reference input
                    assert "inputs." in python_version, \
                        "Python version should reference input parameter"


class TestDocumentationEdgeCases:
    """Additional edge case tests for documentation files."""

    @pytest.fixture
    def copilot_instructions(self):
        """Load Copilot instructions content."""
        doc_path = Path(".github/copilot-instructions.md")
        assert doc_path.exists(), "Copilot instructions not found"

        with open(doc_path) as f:
            return f.read()

    def test_copilot_instructions_no_broken_links(self, copilot_instructions):
        """Test that documentation doesn't have obviously broken markdown links."""
        # Find markdown links [text](url)
        import re
        links = re.findall(r'\[([^\]]+)\]\(([^\)]+)\)', copilot_instructions)

        for link_text, link_url in links:
            # Check for common mistakes
            assert not link_url.startswith(" "), f"Link has leading space: [{link_text}]({link_url})"
            assert not link_url.endswith(" "), f"Link has trailing space: [{link_text}]({link_url})"

    def test_copilot_instructions_command_syntax(self, copilot_instructions):
        """Test that shell commands use consistent formatting."""
        # Commands should be in code blocks or inline code
        if "python" in copilot_instructions.lower():
            lines = copilot_instructions.split("\n")
            in_code_block = False

            for i, line in enumerate(lines):
                # Track if we're in a code block
                if line.strip().startswith("```"):
                    in_code_block = not in_code_block
                    continue

                # Check lines with python commands
                if "python" in line.lower():
                    # Should be in code block, inline code, or prose
                    is_in_code_block = in_code_block
                    is_inline_code = "`" in line
                    is_indented = line.strip() != line and line.startswith("    ")
                    is_prose = any(phrase in line for phrase in [
                        "Python environment", "Python-only", "dataclass", "@dataclass",
                        "Python dependencies", "Python imports"
                    ])

                    # Allow any of these valid formats
                    if not (is_in_code_block or is_inline_code or is_indented or is_prose):
                        # Only fail if it looks like a command (starts with python and has no prose context)
                        looks_like_command = line.strip().startswith("python")
                        if looks_like_command:
                            assert False, f"Python command should be in code format: {line.strip()}"

    def test_copilot_instructions_reasonable_length(self, copilot_instructions):
        """Test that documentation is comprehensive but not too long."""
        line_count = len(copilot_instructions.split("\n"))
        # Should be substantial but not overwhelming
        assert 20 <= line_count <= 500, \
            f"Documentation should be reasonable length (20-500 lines), got {line_count}"

    def test_codacy_instructions_example_formatting(self):
        """Test that Codacy instructions have properly formatted examples."""
        doc_path = Path(".github/instructions/codacy.instructions.md")
        with open(doc_path) as f:
            content = f.read()

        # If there are examples, they should be clearly marked
        if "example" in content.lower() or "EXAMPLE" in content:
            # Examples should be in a clear section or code block
            assert "##" in content or "```" in content or "-" in content, \
                "Examples should be clearly formatted"