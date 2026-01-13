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


class TestVercelConfig:
    """Test cases for vercel.json configuration."""

    @pytest.fixture
    @staticmethod
    def vercel_config():
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
    @staticmethod
    def tailwind_config_content():
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
    @staticmethod
    def env_example_content():
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

    @staticmethod
    @pytest.fixture
    def gitignore_content():
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

    @staticmethod
    def test_requirements_exists():
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

    @staticmethod
    def test_postcss_config_has_tailwindcss(postcss_config_content):
        """Test that Tailwind CSS plugin is configured."""
        assert "tailwindcss" in postcss_config_content

    @staticmethod
    def test_postcss_config_has_autoprefixer(postcss_config_content):
        """Test that autoprefixer plugin is configured."""
        assert "autoprefixer" in postcss_config_content


class TestConfigurationConsistency:
    """Test consistency across configuration files."""

    @staticmethod
    def test_api_url_consistency():
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

    @staticmethod
    def test_package_json_and_tsconfig_consistency():
        """Test that package.json and tsconfig are consistent."""
        with open("frontend/package.json") as f:
            package = json.load(f)

        with open("frontend/tsconfig.json") as f:
            tsconfig = json.load(f)

        # If TypeScript is in devDependencies, tsconfig should exist
        if "typescript" in package.get("devDependencies", {}):
            assert "compilerOptions" in tsconfig

    @staticmethod
    def test_frontend_build_configuration_matches():
        """Test that frontend configurations are aligned."""
        # Verify package.json scripts match expected Next.js commands
        with open("frontend/package.json") as f:
            package = json.load(f)

        scripts = package["scripts"]

        # Next.js standard scripts
        assert "next dev" in scripts.get("dev", "") or "next" in scripts.get("dev", "")
        assert "next build" in scripts.get("build", "") or "next" in scripts.get("build", "")
        assert "next start" in scripts.get("start", "") or "next" in scripts.get("start", "")
