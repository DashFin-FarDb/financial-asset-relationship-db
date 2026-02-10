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


@pytest.mark.unit
class TestVercelConfig:
    """Test cases for vercel.json configuration."""

    @staticmethod
    @pytest.fixture
    def vercel_config():
        """Load vercel.json configuration."""
        config_path = Path("vercel.json")
        assert config_path.exists(), "vercel.json not found"

        with open(config_path) as f:
            return json.load(f)

    @staticmethod
    def test_vercel_config_valid_json():
        """Test that vercel.json is valid JSON."""
        config_path = Path("vercel.json")
        with open(config_path) as f:
            data = json.load(f)
        assert isinstance(data, dict)

    @staticmethod
    def test_vercel_config_has_builds(vercel_config):
        """Test that vercel.json has builds configuration."""
        assert "builds" in vercel_config
        assert isinstance(vercel_config["builds"], list)
        assert len(vercel_config["builds"]) > 0

    @staticmethod
    def test_vercel_config_has_routes(vercel_config):
        """Test that vercel.json has routes configuration."""
        assert "routes" in vercel_config
        assert isinstance(vercel_config["routes"], list)
        assert len(vercel_config["routes"]) > 0

    @staticmethod
    def test_vercel_build_python_backend(vercel_config):
        """Test that Python backend build is configured correctly."""
        builds = vercel_config["builds"]
        python_build = next((b for b in builds if "api/main.py" in b["src"]), None)

        assert python_build is not None, "Python backend build not found"
        assert python_build["use"] == "@vercel/python"
        assert "config" in python_build
        assert "maxLambdaSize" in python_build["config"]

    @staticmethod
    def test_vercel_build_nextjs_frontend(vercel_config):
        """Test that Next.js frontend build is configured correctly."""
        builds = vercel_config["builds"]
        nextjs_build = next((b for b in builds if "package.json" in b["src"]), None)

        assert nextjs_build is not None, "Next.js frontend build not found"
        assert nextjs_build["use"] == "@vercel/next"

    @staticmethod
    def test_vercel_routes_api_routing(vercel_config):
        """Test that API routes are configured correctly."""
        routes = vercel_config["routes"]
        api_route = next((r for r in routes if "/api/" in r["src"]), None)

        assert api_route is not None, "API route not found"
        assert api_route["dest"] == "api/main.py"

    @staticmethod
    def test_vercel_routes_frontend_routing(vercel_config):
        """Test that frontend routes are configured correctly."""
        routes = vercel_config["routes"]
        frontend_route = next((r for r in routes if r["src"] == "/(.*)"), None)

        assert frontend_route is not None, "Frontend route not found"
        assert "frontend" in frontend_route["dest"]

    @staticmethod
    def test_vercel_lambda_size_reasonable(vercel_config):
        """Test that Lambda size limit is reasonable."""
        builds = vercel_config["builds"]
        python_build = next((b for b in builds if "api/main.py" in b["src"]), None)

        if python_build and "config" in python_build:
            max_size = python_build["config"].get("maxLambdaSize", "50mb")
            # Parse size (e.g., "50mb")
            size_value = int(max_size.replace("mb", ""))
            assert 1 <= size_value <= 250, "Lambda size should be between 1MB and 250MB"


@pytest.mark.unit
class TestNextConfig:
    """Test cases for Next.js configuration."""

    @staticmethod
    @pytest.fixture
    def next_config_content():
        """Load Next.js configuration file content."""
        config_path = Path("frontend/next.config.js")
        assert config_path.exists(), "next.config.js not found"

        with open(config_path) as f:
            return f.read()

    @staticmethod
    def test_next_config_exists():
        """Test that next.config.js exists."""
        config_path = Path("frontend/next.config.js")
        assert config_path.exists()

    @staticmethod
    def test_next_config_has_module_exports(next_config_content):
        """Test that next.config.js exports configuration."""
        assert "module.exports" in next_config_content

    @staticmethod
    def test_next_config_has_react_strict_mode(next_config_content):
        """Test that React strict mode is configured."""
        assert "reactStrictMode" in next_config_content

    @staticmethod
    def test_next_config_has_env_configuration(next_config_content):
        """Test that environment variables are configured."""
        assert "env" in next_config_content or "NEXT_PUBLIC" in next_config_content


@pytest.mark.unit
class TestPackageJson:
    """Test cases for package.json configuration."""

    @pytest.fixture
    def package_json(self):
        """Load package.json configuration."""
        config_path = Path("frontend/package.json")
        assert config_path.exists(), "package.json not found"

        with open(config_path) as f:
            return json.load(f)

    @staticmethod
    def test_package_json_valid_json():
        """Test that package.json is valid JSON."""
        config_path = Path("frontend/package.json")
        with open(config_path) as f:
            data = json.load(f)
        assert isinstance(data, dict)

    @staticmethod
    def test_package_json_has_required_fields(package_json):
        """Test that package.json has required fields."""
        required_fields = ["name", "version", "scripts", "dependencies"]
        for field in required_fields:
            assert field in package_json, f"Missing required field: {field}"

    @staticmethod
    def test_package_json_has_build_scripts(package_json):
        """Test that package.json has necessary build scripts."""
        scripts = package_json["scripts"]
        required_scripts = ["dev", "build", "start"]

        for script in required_scripts:
            assert script in scripts, f"Missing script: {script}"

    @staticmethod
    def test_package_json_has_react_dependencies(package_json):
        """Test that React dependencies are present."""
        deps = package_json["dependencies"]
        required_deps = ["react", "react-dom", "next"]

        for dep in required_deps:
            assert dep in deps, f"Missing dependency: {dep}"

    @staticmethod
    def test_package_json_has_visualization_deps(package_json):
        """Test that visualization dependencies are present."""
        deps = package_json["dependencies"]
        viz_deps = ["plotly.js", "react-plotly.js"]

        for dep in viz_deps:
            assert dep in deps, f"Missing visualization dependency: {dep}"

    @staticmethod
    def test_package_json_has_axios(package_json):
        """Test that axios is included for API calls."""
        deps = package_json["dependencies"]
        assert "axios" in deps, "Missing axios dependency"

    @staticmethod
    def test_package_json_has_typescript_deps(package_json):
        """Test that TypeScript dependencies are present."""
        dev_deps = package_json.get("devDependencies", {})
        ts_deps = ["typescript", "@types/react", "@types/node"]

        for dep in ts_deps:
            assert dep in dev_deps, f"Missing TypeScript dependency: {dep}"

    def test_package_json_version_format(self, package_json):
        """Test that version follows semantic versioning.

        Supports standard semantic versions(e.g., 1.0.0) and pre - release versions
        (e.g., 1.0.0 - beta, 1.0.0 - rc.1, 1.0.0 - alpha.1).
        """
        version = package_json["version"]
        # Semantic versioning pattern: major.minor.patch with optional pre-release suffix
        semver_pattern = r"^\d+\.\d+\.\d+(-[\w.]+)?$"
        assert re.match(
            semver_pattern, version
        ), f"Version should follow semantic versioning (x.y.z or x.y.z-prerelease): {version}"


@pytest.mark.unit
class TestTSConfig:
    """Test cases for TypeScript configuration."""

    @pytest.fixture
    def tsconfig(self):
        """Load tsconfig.json."""
        config_path = Path("frontend/tsconfig.json")
        assert config_path.exists(), "tsconfig.json not found"

        with open(config_path) as f:
            return json.load(f)

    @staticmethod
    def test_tsconfig_valid_json():
        """Test that tsconfig.json is valid JSON."""
        config_path = Path("frontend/tsconfig.json")
        with open(config_path) as f:
            data = json.load(f)
        assert isinstance(data, dict)

    @staticmethod
    def test_tsconfig_has_compiler_options(tsconfig):
        """Test that tsconfig has compiler options."""
        assert "compilerOptions" in tsconfig
        assert isinstance(tsconfig["compilerOptions"], dict)

    @staticmethod
    def test_tsconfig_strict_mode_enabled(tsconfig):
        """Test that TypeScript strict mode is enabled."""
        compiler_options = tsconfig["compilerOptions"]
        assert compiler_options.get("strict", False), "Strict mode should be enabled"

    @staticmethod
    def test_tsconfig_has_jsx_configuration(tsconfig):
        """Test that JSX is configured for React."""
        compiler_options = tsconfig["compilerOptions"]
        assert "jsx" in compiler_options
        assert compiler_options["jsx"] in ["preserve", "react", "react-jsx"]

    @staticmethod
    def test_tsconfig_module_resolution(tsconfig):
        """Test that module resolution is configured."""
        compiler_options = tsconfig["compilerOptions"]
        assert "moduleResolution" in compiler_options

    def test_tsconfig_has_path_mapping(self, tsconfig):
        """Test that path mapping is configured."""
        compiler_options = tsconfig["compilerOptions"]
        if "paths" in compiler_options:
            paths = compiler_options["paths"]
            assert isinstance(paths, dict)


@pytest.mark.unit
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

    @staticmethod
    @staticmethod
    def test_tailwind_config_exists():
        """Test that tailwind.config.js exists."""
        config_path = Path("frontend/tailwind.config.js")
        assert config_path.exists()

    @staticmethod
    def test_tailwind_config_has_module_exports(tailwind_config_content):
        """Test that Tailwind config exports configuration."""
        assert "module.exports" in tailwind_config_content

    @staticmethod
    def test_tailwind_config_has_content_paths(tailwind_config_content):
        """Test that content paths are configured."""
        assert "content" in tailwind_config_content

    @staticmethod
    def test_tailwind_config_includes_app_directory(tailwind_config_content):
        """Test that content paths include app directory."""
        assert "app/" in tailwind_config_content or "./app/" in tailwind_config_content


@pytest.mark.unit
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
        """Test that .env.example does not contain real secrets."""
        # Check for common secret patterns
        suspicious_patterns = [
            "sk_live",  # Stripe live keys
            "prod_",  # Production keys
            "pk_live",  # Public live keys
        ]

        for pattern in suspicious_patterns:
            assert pattern not in env_example_content.lower(), f"Potential real secret found: {pattern}"


@pytest.mark.unit
class TestGitignore:
    """Unit tests for .gitignore configuration validation."""

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
        config_path = Path(".gitignore")
        assert config_path.exists()

    @staticmethod
    def test_gitignore_excludes_node_modules(gitignore_content):
        """Test that node_modules is excluded."""
        assert "node_modules" in gitignore_content

    @staticmethod
    def test_gitignore_excludes_next_artifacts(gitignore_content):
        """Test that Next.js build artifacts are excluded."""
        assert ".next" in gitignore_content or ".next/" in gitignore_content

    @staticmethod
    def test_gitignore_excludes_env_files(gitignore_content):
        """Test that environment files are excluded."""
        assert ".env.local" in gitignore_content

    @staticmethod
    def test_gitignore_excludes_vercel(gitignore_content):
        """Test that Vercel directory is excluded."""
        assert ".vercel" in gitignore_content

    @staticmethod
    def test_gitignore_excludes_python_artifacts(gitignore_content):
        """Test that Python artifacts are excluded."""
        assert "__pycache__" in gitignore_content
        # Check for *.pyc explicitly or the pattern *.py[cod] (which matches files ending in .pyc, .pyo, or .pyd; [cod] means any single character from the set {c, o, d})
        assert "*.pyc" in gitignore_content or "*.py[cod]" in gitignore_content


@pytest.mark.unit
class TestRequirementsTxt:
    """Test cases for requirements.txt."""

    require_version_pinning = True  # When True, enforces version constraints for all dependencies in requirements.txt

    @staticmethod
    @pytest.fixture
    def requirements():
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

    @staticmethod
    def test_requirements_has_fastapi(requirements):
        """Test that FastAPI is in requirements."""
        assert any("fastapi" in req.lower() for req in requirements)

    @staticmethod
    def test_requirements_has_uvicorn(requirements):
        """Test that Uvicorn is in requirements."""
        assert any("uvicorn" in req.lower() for req in requirements)

    @staticmethod
    def test_requirements_has_pydantic(requirements):
        """Test that Pydantic is in requirements."""
        assert any("pydantic" in req.lower() for req in requirements)

    def test_requirements_has_version_constraints(self, requirements):
        """Test that packages have version constraints(if project policy requires)."""
        # Skip this test if project doesn't require version pinning
        if not self.require_version_pinning:
            pytest.skip("Version pinning not required for this project")

        for req in requirements:
            if not req.startswith("-"):
                assert any(
                    op in req for op in [">=", "==", "~=", "<="]
                ), f"Package should have version constraint: {req}"


@pytest.mark.unit
class TestPostCSSConfig:
    """Test cases for PostCSS configuration."""

    @staticmethod
    @pytest.fixture
    def postcss_config_content():
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


@pytest.mark.unit
class TestConfigurationConsistency:
    """Test consistency across configuration files."""

    @staticmethod
    def test_api_url_consistency():
        """Test that API URL is consistent across configurations."""
        # Check .env.example
        with open(".env.example") as f:
            env_content = f.read()
        assert "NEXT_PUBLIC_API_URL" in env_content

    @staticmethod
    def test_env_and_next_config():
        """Test that .env and next.config.js both contain NEXT_PUBLIC_API_URL."""
        with open(".env.local") as f:
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





        assert "next start" in scripts.get("start", "") or "next" in scripts.get(
            "start", ""
        )


@pytest.mark.unit
class TestConfigurationSecurityNegative:
    """Negative test cases for configuration security issues."""

    @staticmethod
    def test_gitignore_prevents_env_file_leak():
        """Negative: .env files should be gitignored to prevent secret leaks."""
        gitignore_path = Path(".gitignore")
        with open(gitignore_path) as f:
            gitignore_content = f.read()

        # Critical: .env files must be ignored
        assert ".env" in gitignore_content or ".env.local" in gitignore_content

    @staticmethod
    def test_no_api_keys_in_example_env():
        """Negative: .env.example should not contain real API keys."""
        env_example_path = Path(".env.example")
        if not env_example_path.exists():
            pytest.skip(".env.example not found")

        with open(env_example_path) as f:
            content = f.read()

        # Check for patterns that might indicate real keys
        suspicious_patterns = [
            r"[A-Za-z0-9]{32,}",  # Long alphanumeric strings
            "sk_live",
            "pk_live",
            "prod_",
        ]

        import re

        for pattern in suspicious_patterns:
            matches = re.findall(pattern, content)
            # If found, ensure they're in comments or placeholders
            for match in matches:
                if "your" not in content.lower() and "example" not in content.lower():
                    # Might be a real key
                    assert False, f"Potential real key found: {match[:10]}..."

    @staticmethod
    def test_package_json_no_vulnerable_scripts():
        """Negative: package.json scripts should not have dangerous patterns."""
        package_path = Path("frontend/package.json")
        if not package_path.exists():
            pytest.skip("frontend/package.json not found")

        with open(package_path) as f:
            package = json.load(f)

        scripts = package.get("scripts", {})
        for script_name, script_cmd in scripts.items():
            # Should not have rm -rf / or similar dangerous commands
            dangerous_patterns = ["rm -rf /", "rm -rf /*", "sudo rm"]
            for pattern in dangerous_patterns:
                assert pattern not in script_cmd, (
                    f"Dangerous pattern '{pattern}' found in script '{script_name}'"
                )


@pytest.mark.unit
class TestMalformedConfigurationHandling:
    """Test handling of malformed configuration files."""

    @staticmethod
    def test_vercel_config_wellformed_json():
        """Malformed: Vercel config must be valid JSON."""
        vercel_path = Path("vercel.json")
        if not vercel_path.exists():
            pytest.skip("vercel.json not found")

        try:
            with open(vercel_path) as f:
                json.load(f)
        except json.JSONDecodeError as e:
            pytest.fail(f"vercel.json is malformed JSON: {e}")

    @staticmethod
    def test_package_json_wellformed():
        """Malformed: package.json must be valid JSON."""
        package_path = Path("frontend/package.json")
        if not package_path.exists():
            pytest.skip("frontend/package.json not found")

        try:
            with open(package_path) as f:
                data = json.load(f)
            assert isinstance(data, dict)
        except json.JSONDecodeError as e:
            pytest.fail(f"package.json is malformed JSON: {e}")

    @staticmethod
    def test_tsconfig_allows_comments():
        """Edge: tsconfig.json may have comments (JSONC format)."""
        tsconfig_path = Path("frontend/tsconfig.json")
        if not tsconfig_path.exists():
            pytest.skip("frontend/tsconfig.json not found")

        # JSONC allows comments, so we need special handling
        with open(tsconfig_path) as f:
            content = f.read()

        # Try to parse; if it fails, check if it's because of comments
        try:
            json.loads(content)
        except json.JSONDecodeError:
            # Check if there are comments
            if "//" in content or "/*" in content:
                # This is expected for JSONC
                pytest.skip("tsconfig.json uses JSONC format with comments")
            else:
                pytest.fail("tsconfig.json is malformed")


@pytest.mark.unit
class TestConfigurationBoundaryValues:
    """Boundary value tests for configuration parameters."""

    @staticmethod
    def test_vercel_lambda_size_not_excessive():
        """Boundary: Lambda size should not be unreasonably large."""
        vercel_path = Path("vercel.json")
        if not vercel_path.exists():
            pytest.skip("vercel.json not found")

        with open(vercel_path) as f:
            vercel_config = json.load(f)

        builds = vercel_config.get("builds", [])
        for build in builds:
            if "config" in build and "maxLambdaSize" in build["config"]:
                size_str = build["config"]["maxLambdaSize"]
                # Extract numeric value
                size_value = int(size_str.replace("mb", "").replace("MB", ""))
                # 250MB is Vercel's maximum
                assert size_value <= 250, f"Lambda size {size_value}MB exceeds maximum"
                # Should be at least 1MB
                assert size_value >= 1, f"Lambda size {size_value}MB is too small"

    @staticmethod
    def test_package_version_not_zero():
        """Boundary: Package version should not be 0.0.0."""
        package_path = Path("frontend/package.json")
        if not package_path.exists():
            pytest.skip("frontend/package.json not found")

        with open(package_path) as f:
            package = json.load(f)

        version = package.get("version", "0.0.0")
        assert version != "0.0.0", "Package version should not be 0.0.0"

    @staticmethod
    def test_no_excessively_long_script_names():
        """Boundary: Script names should be reasonably short."""
        package_path = Path("frontend/package.json")
        if not package_path.exists():
            pytest.skip("frontend/package.json not found")

        with open(package_path) as f:
            package = json.load(f)

        scripts = package.get("scripts", {})
        for script_name in scripts.keys():
            assert len(script_name) < 50, (
                f"Script name '{script_name}' is excessively long"
            )


@pytest.mark.unit
class TestConfigurationRobustness:
    """Robustness tests for configuration edge cases."""

    @staticmethod
    def test_gitignore_covers_common_artifacts():
        """Robustness: .gitignore should cover common build artifacts."""
        gitignore_path = Path(".gitignore")
        with open(gitignore_path) as f:
            content = f.read()

        # Essential patterns that should be present
        essential_patterns = [
            "node_modules",
            "__pycache__",
            ".env",
        ]

        for pattern in essential_patterns:
            assert pattern in content, f"Missing essential pattern: {pattern}"

    @staticmethod
    def test_requirements_no_conflicting_versions():
        """Robustness: requirements.txt should not have duplicate packages."""
        requirements_path = Path("requirements.txt")
        if not requirements_path.exists():
            pytest.skip("requirements.txt not found")

        with open(requirements_path) as f:
            lines = [
                line.strip()
                for line in f
                if line.strip() and not line.startswith("#")
            ]

        # Extract package names (before ==, >=, etc.)
        packages = []
        for line in lines:
            if not line.startswith("-"):
                # Extract package name
                package_name = line.split("==")[0].split(">=")[0].split("~=")[0].split("<=")[0].strip()
                packages.append(package_name.lower())

        # Check for duplicates
        from collections import Counter

        counts = Counter(packages)
        duplicates = [pkg for pkg, count in counts.items() if count > 1]
        assert len(duplicates) == 0, f"Duplicate packages found: {duplicates}"

    @staticmethod
    def test_env_example_documents_all_required_vars():
        """Robustness: .env.example should document key variables."""
        env_example_path = Path(".env.example")
        if not env_example_path.exists():
            pytest.skip(".env.example not found")

        with open(env_example_path) as f:
            content = f.read()

        # Key variables that should be documented
        important_vars = ["API_URL", "NEXT_PUBLIC"]

        # At least one should be present
        has_important = any(var in content for var in important_vars)
        assert has_important, "No important environment variables documented"