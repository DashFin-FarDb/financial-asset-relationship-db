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
        """
        Load and parse the repository root vercel.json file.

        Returns:
            dict: Parsed JSON configuration from vercel.json.

        Raises:
            AssertionError: If vercel.json does not exist at the repository root.
            json.JSONDecodeError: If vercel.json contains invalid JSON.
        """
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
        """
        Assert that the parsed vercel.json contains a non-empty `builds` list.

        Parameters:
            vercel_config (dict): Parsed contents of vercel.json loaded from the project root.
        """
        assert "builds" in vercel_config
        assert isinstance(vercel_config["builds"], list)
        assert len(vercel_config["builds"]) > 0

    @staticmethod
    def test_vercel_config_has_routes(vercel_config):
        """
        Ensure the parsed vercel.json contains a non-empty 'routes' list.

        Parameters:
            vercel_config (dict): Parsed contents of vercel.json loaded as a dictionary.
        """
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
        """
        Ensure the Python build's `maxLambdaSize` in vercel.json, if present, falls between 1MB and 250MB.

        Parameters:
            vercel_config (dict): Parsed contents of vercel.json loaded from the project root.
        """
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
        """
        Return the text content of frontend/next.config.js.

        Returns:
            config_text (str): Contents of the Next.js configuration file.

        Raises:
            AssertionError: If frontend/next.config.js does not exist.
        """
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
        """
        Load and parse frontend/package.json.

        Returns:
            dict: Parsed JSON content of frontend/package.json.

        Raises:
            AssertionError: If frontend/package.json does not exist.
        """
        config_path = Path("frontend/package.json")
        assert config_path.exists(), "package.json not found"

        with open(config_path) as f:
            return json.load(f)

    @staticmethod
    def test_package_json_valid_json():
        """
        Validate that frontend/package.json contains well-formed JSON.

        Opens frontend/package.json, parses it as JSON, and asserts the parsed value is a Python dict.
        """
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
        """
        Ensure the package.json includes React and Next.js dependencies.

        Parameters:
            package_json (dict): Parsed contents of frontend/package.json.
        """
        deps = package_json["dependencies"]
        required_deps = ["react", "react-dom", "next"]

        for dep in required_deps:
            assert dep in deps, f"Missing dependency: {dep}"

    @staticmethod
    def test_package_json_has_visualization_deps(package_json):
        """
        Ensure the frontend package.json declares required visualization dependencies.

        Specifically requires "plotly.js" and "react-plotly.js" to be present in the top-level `dependencies`.

        Parameters:
            package_json (dict): Parsed contents of frontend/package.json.
        """
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
        """
        Verify the package.json version follows semantic versioning, allowing optional pre-release identifiers.

        Accepts versions in the form major.minor.patch (e.g., 1.0.0) and with a pre-release suffix (e.g., 1.0.0-beta, 1.0.0-rc.1, 1.0.0-alpha.1).
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
        """
        Load and parse frontend/tsconfig.json.

        Asserts that frontend/tsconfig.json exists.

        Returns:
            dict: Parsed JSON content of the tsconfig file.
        """
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
        """
        Ensure the TypeScript config specifies a valid JSX setting for React.

        Parameters:
            tsconfig (dict): Parsed contents of tsconfig.json.

        Checks that `compilerOptions.jsx` is present and its value is one of: "preserve", "react", or "react-jsx".
        """
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
        """
        Load the frontend/tailwind.config.js file and return its text content.

        Returns:
            str: The full text contents of frontend/tailwind.config.js.

        Raises:
            AssertionError: If frontend/tailwind.config.js does not exist.
        """
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
        """
        Ensure the Tailwind CSS configuration's content paths include the app/ directory.

        Parameters:
            tailwind_config_content (str): Raw text of frontend/tailwind.config.js.
        """
        assert "app/" in tailwind_config_content or "./app/" in tailwind_config_content


@pytest.mark.unit
class TestEnvExampleFixture:
    """Test cases for .env.example file."""

    @pytest.fixture
    def env_example_content(self):
        """
        Read the repository's .env.example file and return its contents as text.

        Returns:
            str: The contents of `.env.example`.

        Raises:
            AssertionError: If `.env.example` does not exist.
        """
        config_path = Path(".env.example")
        assert config_path.exists(), ".env.example not found"
        with open(config_path) as f:
            return f.read()


@pytest.mark.unit
class TestEnvExample:
    """Test cases for .env.example file."""

    @pytest.fixture
    def env_example_content(self):
        """
        Load the content of the .env.example file.

        Returns:
            str: The full text content of .env.example.

        Raises:
            AssertionError: If the .env.example file does not exist.
        """
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
        """
        Read and return the repository root .gitignore file contents.

        Returns:
            str: The full text of the .gitignore file.

        Raises:
            AssertionError: If the .gitignore file is not found at the repository root.
        """
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
        """
        Assert that .gitignore contains an entry excluding local environment files.

        Checks that the pattern ".env.local" appears in the provided gitignore content.
        """
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
        """
        Load non-empty, non-comment requirement lines from requirements.txt.

        Returns:
            list[str]: Requirement lines with surrounding whitespace removed; lines that are empty or start with `#` are omitted.
        """
        config_path = Path("requirements.txt")
        assert config_path.exists(), "requirements.txt not found"

        with open(config_path) as f:
            return [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]

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
        """
        Ensure each non-option requirement includes a version constraint when version pinning is enabled.

        If the test runner's `require_version_pinning` flag is False, this test will be skipped.

        Parameters:
            requirements (list[str]): Filtered lines from requirements.txt (non-empty, non-comment).
        """
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
        """
        Load the frontend/postcss.config.js file contents for use in tests; skip the test if the file is missing.

        Returns:
            str: The contents of frontend/postcss.config.js.

        Notes:
            This fixture calls pytest.skip when the file does not exist.
        """
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
        env_path = Path(".env.local")
        if not env_path.exists():
            env_path = Path(".env.example")

        with open(env_path) as f:
            env_content = f.read()

        # Check next.config.js
        with open("frontend/next.config.js") as f:
            next_config = f.read()

        # Both should mention NEXT_PUBLIC_API_URL
        assert "NEXT_PUBLIC_API_URL" in env_content
        assert "NEXT_PUBLIC_API_URL" in next_config

    @staticmethod
    def test_package_json_and_tsconfig_consistency():
        """
        Ensure that if TypeScript is listed in frontend/package.json devDependencies, frontend/tsconfig.json contains a `compilerOptions` entry.

        Reads both frontend/package.json and frontend/tsconfig.json and asserts that when "typescript" appears under `devDependencies` in package.json, the parsed tsconfig includes a top-level `compilerOptions` key.
        """
        with open("frontend/package.json") as f:
            package = json.load(f)

        with open("frontend/tsconfig.json") as f:
            tsconfig = json.load(f)

        # If TypeScript is in devDependencies, tsconfig should exist
        if "typescript" in package.get("devDependencies", {}):
            assert "compilerOptions" in tsconfig

    @staticmethod
    def test_frontend_build_configuration_matches():
        """
        Ensure the frontend package.json scripts invoke Next.js for development, build, and start.

        Checks that the `dev`, `build`, and `start` entries under `frontend/package.json` → `scripts` reference Next.js commands (e.g., contain `next`, `next dev`, `next build`, or `next start`).

        Raises:
            AssertionError: If any of the `dev`, `build`, or `start` scripts are missing or do not reference Next.js.
        """
        # Verify package.json scripts match expected Next.js commands
        with open("frontend/package.json") as f:
            package = json.load(f)

        scripts = package["scripts"]

        # Next.js standard scripts
        assert "next dev" in scripts.get("dev", "") or "next" in scripts.get("dev", "")
        assert "next build" in scripts.get("build", "") or "next" in scripts.get("build", "")
        assert "next start" in scripts.get("start", "") or "next" in scripts.get("start", "")


@pytest.mark.unit
class TestConfigurationSecurityNegative:
    """Negative test cases for configuration security issues."""

    @staticmethod
    def test_gitignore_prevents_env_file_leak():
        """
        Ensure .env files are listed in .gitignore to prevent accidental commits of secrets.

        Checks that either ".env" or ".env.local" appears in the repository's .gitignore file.
        """
        gitignore_path = Path(".gitignore")
        with open(gitignore_path) as f:
            gitignore_content = f.read()

        # Critical: .env files must be ignored
        assert ".env" in gitignore_content or ".env.local" in gitignore_content

    @staticmethod
    def test_no_api_keys_in_example_env():
        """
        Fail the test if .env.example appears to contain real API keys or other likely secrets.

        Scans .env.example for long alphanumeric strings and known live key prefixes (for example, `sk_live`, `pk_live`, `prod_`). If a match is found and the surrounding line is not clearly marked as a placeholder (does not include words like "your" or "example"), the test fails with a short snippet of the suspicious value.
        """
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

        for pattern in suspicious_patterns:
            for match in re.finditer(pattern, content):
                # Look at the line containing the match to see if it's a placeholder
                line_start = content.rfind("\n", 0, match.start()) + 1
                line_end = content.find("\n", match.end())
                if line_end == -1:
                    line_end = len(content)
                line = content[line_start:line_end]
                if "your" not in line.lower() and "example" not in line.lower():
                    # Might be a real key
                    snippet = match.group(0)[:10]
                    assert False, f"Potential real key found: {snippet}..."

    @staticmethod
    def test_package_json_no_vulnerable_scripts():
        """
        Ensure frontend/package.json scripts do not contain dangerous shell commands.

        If frontend/package.json is missing, the test is skipped. The test fails if any script command contains any of the substrings "rm -rf /", "rm -rf /*", or "sudo rm".
        """
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
                assert pattern not in script_cmd, f"Dangerous pattern '{pattern}' found in script '{script_name}'"


@pytest.mark.unit
class TestMalformedConfigurationHandling:
    """Test handling of malformed configuration files."""

    @staticmethod
    def test_vercel_config_wellformed_json():
        """
        Verify that vercel.json parses as valid JSON.

        Skips the test if vercel.json is not present in the repository root; fails if the file cannot be decoded as JSON.
        """
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
        """
        Verify that frontend/package.json exists and contains valid JSON.

        Skips the test if frontend/package.json is missing. Fails if the file is not well-formed JSON or if parsing does not produce a top-level object (dict).
        """
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
        """
        Checks that frontend/tsconfig.json is valid JSON or intentionally uses JSONC comments.

        Skips the test if the file is missing or if the file parses as JSONC (contains // or /* comments).
        Fails the test if the file exists, does not contain comment markers, and is not valid JSON.
        """
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
        """
        Ensure frontend/package.json declares a non-zero semantic version.

        If frontend/package.json is missing the test is skipped. The test fails if the package's
        "version" field equals "0.0.0".
        """
        package_path = Path("frontend/package.json")
        if not package_path.exists():
            pytest.skip("frontend/package.json not found")

        with open(package_path) as f:
            package = json.load(f)

        version = package.get("version", "0.0.0")
        assert version != "0.0.0", "Package version should not be 0.0.0"

    @staticmethod
    def test_no_excessively_long_script_names():
        """
        Check that all script keys in frontend/package.json are shorter than 50 characters.

        Skips the test if frontend/package.json is missing. Fails if any script name has length greater than or equal to 50 characters.
        """
        package_path = Path("frontend/package.json")
        if not package_path.exists():
            pytest.skip("frontend/package.json not found")

        with open(package_path) as f:
            package = json.load(f)

        scripts = package.get("scripts", {})
        for script_name in scripts.keys():
            assert len(script_name) < 50, f"Script name '{script_name}' is excessively long"


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
        """
        Ensure requirements.txt contains no duplicate package entries.

        Reads non-empty, non-comment lines from requirements.txt (skipping option lines that start with '-'), normalizes package names by removing common version specifiers (==, >=, ~=, <=) and case, and fails the test if any package appears more than once. Skips the test if requirements.txt is not present.
        """
        requirements_path = Path("requirements.txt")
        if not requirements_path.exists():
            pytest.skip("requirements.txt not found")

        with open(requirements_path) as f:
            lines = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]

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
