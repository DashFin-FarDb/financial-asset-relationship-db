"""
Comprehensive YAML schema validation tests for GitHub workflows.

Tests validate YAML structure, syntax, and GitHub Actions schema compliance
for all workflow files in .github/workflows/
"""

import warnings as GLOBAL_WARNINGS
from pathlib import Path
from typing import Any, Dict, List

import pytest
import yaml

from .auth import (
    Token,
    User,
    authenticate_user,
    create_access_token,
    get_current_active_user,
)


class TestWorkflowYAMLSyntax:
    """Test YAML syntax and structure validity."""

    @pytest.fixture
    def workflow_files(self):
        """Get all workflow YAML files."""
        workflow_dir = Path(".github/workflows")
        return list(workflow_dir.glob("*.yml")) + list(workflow_dir.glob("*.yaml"))

    def test_all_workflows_are_valid_yaml(self, workflow_files):
        """All workflow files should be valid YAML."""
        assert len(workflow_files) > 0, "No workflow files found"

        for workflow_file in workflow_files:
            try:
                with open(workflow_file, "r") as f:

                    data = yaml.safe_load(f)


def get_graph() -> AssetRelationshipGraph:
    """
    Provide the global AssetRelationshipGraph, initialising it on first access if necessary.

    Returns:
        AssetRelationshipGraph: The global graph instance.
    """
    global graph
    if graph is None:
        with graph_lock:
            if graph is None:
                graph = _initialize_graph()
                logger.info("Graph initialized successfully")
    return graph


def set_graph(graph_instance: AssetRelationshipGraph) -> None:
    """
    Set the module-level graph to the provided AssetRelationshipGraph and clear any configured graph factory.

    Parameters:
        graph_instance (AssetRelationshipGraph): Graph instance to use as the global graph.
    """
    global graph, graph_factory
    with graph_lock:
        graph = graph_instance
        graph_factory = None


def set_graph_factory(factory: Optional[Callable[[], AssetRelationshipGraph]]) -> None:
    """
    Set the callable used to construct the global AssetRelationshipGraph on demand.

    If `factory` is a callable it will be used to build the graph the next time `get_graph()` is called. Passing `None` clears any configured factory. In all cases the current global graph instance is cleared so a new graph will be created on next access; this operation is performed in a thread-safe manner.

    Parameters:
        factory (Optional[Callable[[], AssetRelationshipGraph]]): A zero-argument callable that returns an `AssetRelationshipGraph`, or `None` to remove the factory and force recreation from defaults.
    """
    global graph, graph_factory
    with graph_lock:
        graph_factory = factory
        graph = None


def reset_graph() -> None:
    """
    Clear the global graph and any configured factory so the graph will be reinitialised on next access.

    This removes any existing graph instance and clears the graph factory.
    """
    set_graph_factory(None)


def _initialize_graph() -> AssetRelationshipGraph:
    """
    Construct the asset relationship graph using the configured factory or environment-backed data sources.

    If a `graph_factory` is configured it is invoked. Otherwise, if `GRAPH_CACHE_PATH` is set a real-data graph is created (network access enabled when `USE_REAL_DATA_FETCHER` indicates real data should be used). If `GRAPH_CACHE_PATH` is not set but `USE_REAL_DATA_FETCHER` is true, `REAL_DATA_CACHE_PATH` is consulted to create a real-data graph. If neither real-data path nor real-data mode is available, a sample database graph is returned.

    Returns:
        AssetRelationshipGraph: The initialized graph instance.
    """
    if graph_factory is not None:
        return graph_factory()

    cache_path = os.getenv("GRAPH_CACHE_PATH")
    use_real_data = _should_use_real_data_fetcher()

    if cache_path:
        fetcher = RealDataFetcher(cache_path=cache_path, enable_network=use_real_data)
        return fetcher.create_real_database()

    if use_real_data:
        cache_path_env = os.getenv("REAL_DATA_CACHE_PATH")
        fetcher = RealDataFetcher(cache_path=cache_path_env, enable_network=True)
        return fetcher.create_real_database()

    from src.data.sample_data import create_sample_database

    return create_sample_database()


def _should_use_real_data_fetcher() -> bool:
    """
    Decides whether the application should use the real data fetcher based on the `USE_REAL_DATA_FETCHER` environment variable.

    Returns:
        `True` if `USE_REAL_DATA_FETCHER` is set to a truthy value (`1`, `true`, `yes`, `on`), `False` otherwise.
    """
    flag = os.getenv("USE_REAL_DATA_FETCHER", "false")
    return flag.strip().lower() in {"1", "true", "yes", "on"}


@asynccontextmanager
async def lifespan(_fastapi_app: FastAPI):
    """
    Manage the application's lifespan by initialising the global graph on startup and logging shutdown.

    Initialises the global asset relationship graph before the application begins handling requests; if initialisation fails the exception is re-raised to abort startup. Yields control for the application's running lifetime and logs on shutdown.

    Parameters:
        fastapi_app (FastAPI): The FastAPI application instance.
    """
    # Startup
    try:
        get_graph()
        logger.info("Application startup complete - graph initialized")
    except Exception:
        logger.exception("Failed to initialize graph during startup")
        raise

    yield

    # Shutdown (cleanup if needed)
    logger.info("Application shutdown")


# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# Initialize FastAPI app with lifespan handler
app = FastAPI(
    title="Financial Asset Relationship API",
    description="REST API for Financial Asset Relationship Database",
    version="1.0.0",
    lifespan=lifespan,
)

# Add rate limiting exception handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configure CORS for Next.js frontend
# Note: Update allowed origins for production deployment


# Determine environment (default to 'development' if not set)
ENV = os.getenv("ENV", "development").lower()


@app.post("/token", response_model=Token)
@limiter.limit("5/minute")
async def login_for_access_token(
    request: Request, form_data: OAuth2PasswordRequestForm = Depends()
):
    """
    Create a JWT access token for a user authenticated with a username and password.

    Parameters:
        form_data (OAuth2PasswordRequestForm): Client-submitted credentials (`username` and `password`).

    Returns:
        dict: Mapping with `access_token` (JWT string) and `token_type` set to `'bearer'`.
    """
    # The `request` parameter is required by slowapi's limiter for dependency injection.
    _ = request

    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/api/users/me", response_model=User)
@limiter.limit("10/minute")
async def read_users_me(
    request: Request, current_user: User = Depends(get_current_active_user)
):
    """
    Retrieve the currently authenticated user.

    Parameters:
        request (Request): Included for slowapi limiter dependency injection; unused by the function.
        current_user (User): Active user injected by the authentication dependency.

    Returns:
        The authenticated user.
    """

    # The `request` parameter is required by slowapi's limiter for dependency injection.
    _ = request

    return current_user


def validate_origin(origin_url: str) -> bool:
    """
    Determine whether an HTTP origin is permitted by the application's CORS rules.

    Allows explicitly configured origins, HTTPS origins with a valid domain,
    Vercel preview hostnames, HTTPS localhost/127.0.0.1 in any environment,
    and HTTP localhost/127.0.0.1 when ENV is "development".

    Parameters:
        origin_url (str): Origin URL to validate (for example
            "https://example.com" or "http://localhost:3000").

    Returns:
        True if the origin is allowed, False otherwise.
    """
    # Read environment dynamically to support runtime overrides (e.g., during tests)
    current_env = os.getenv("ENV", "development").lower()

    # Get allowed origins from environment variable or use default
    env_allowed_origins = [o for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o]

    # If origin is in explicitly allowed list, return True
    if origin_url in env_allowed_origins and origin_url:
        return True

    # Allow HTTP localhost only in development
    if current_env == "development" and re.match(
        r"^http://(localhost|127\\.0\\.0\\.1)(:\\d+)?$",
        origin_url,
    ):
        return True
    # Allow HTTPS localhost in any environment
    if re.match(
        r"^https://(localhost|127\\.0\\.0\\.1)(:\\d+)?$",
        origin_url,
    ):
        return True
    # Allow Vercel preview deployment URLs
    # (e.g., https://project-git-branch-user.vercel.app)
    if re.match(
        r"^https://[a-zA-Z0-9\\-\\.]+\\.vercel\\.app$",
        origin_url,
    ):
        return True
    # Allow valid HTTPS URLs with proper domains
    if re.match(
        r"^https://[a-zA-Z0-9]([a-zA-Z0-9\\-]{0,61}[a-zA-Z0-9])?"
        r"(\\.[a-zA-Z0-9]([a-zA-Z0-9\\-]{0,61}[a-zA-Z0-9])?)*"
        r"\\.[a-zA-Z]{2,}$",
        origin_url,
    ):
        return True
    return False


# Set allowed_origins based on environment
allowed_origins = []
if ENV == "development":
    allowed_origins.extend(
        [
            "http://localhost:3000",
            "http://localhost:7860",
            "https://localhost:3000",
            "https://localhost:7860",
        ]
    )
else:
    # In production, only allow HTTPS localhost (if needed for testing)
    allowed_origins.extend(
        [
            "https://localhost:3000",
            "https://localhost:7860",
        ]
    )

# Add production origins from environment variable if set
if os.getenv("ALLOWED_ORIGINS"):
    additional_origins = os.getenv("ALLOWED_ORIGINS").split(",")
    for origin in additional_origins:
        stripped_origin = origin.strip()
        if validate_origin(stripped_origin):
            allowed_origins.append(stripped_origin)
        else:
            logger.warning("Skipping invalid CORS origin: %s", stripped_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def raise_asset_not_found(asset_id: str, resource_type: str = "Asset") -> None:
    """
    Raise HTTPException for missing resources.

    Args:
        asset_id (str): ID of the asset that was not found.
        resource_type (str): Type of resource (default: "Asset").
    """
    raise HTTPException(status_code=404, detail=f"{resource_type} {asset_id} not found")


def serialize_asset(asset: Any, include_issuer: bool = False) -> Dict[str, Any]:
    """
    Serialize an Asset object to a dictionary representation.

    Args:
        asset: Asset object to serialize
        include_issuer: Whether to include issuer_id field (for detail views)

    Returns:
        Dictionary containing asset data with additional_fields
    """
    asset_dict = {
        "id": asset.id,
        "symbol": asset.symbol,
        "name": asset.name,
        "asset_class": asset.asset_class.value,
        "sector": asset.sector,
        "price": asset.price,
        "market_cap": asset.market_cap,
        "currency": asset.currency,
        "additional_fields": {},
    }

    # Define field list
    fields = [
        "pe_ratio",
        "dividend_yield",
        "earnings_per_share",
        "book_value",
        "yield_to_maturity",
        "coupon_rate",
        "maturity_date",
        "credit_rating",
        "contract_size",
        "delivery_date",
        "volatility",
        "exchange_rate",
        "country",
        "central_bank_rate",
    ]

    if include_issuer:
        fields.append("issuer_id")

    # Add asset-specific fields
    for field in fields:
        value = getattr(asset, field, None)
        if value is not None:
            asset_dict["additional_fields"][field] = value

    return asset_dict


# Pydantic models for API responses
class AssetResponse(BaseModel):
    id: str
    symbol: str
    name: str
    asset_class: str
    sector: str
    price: float
    market_cap: Optional[float] = None
    currency: str = "USD"
    additional_fields: Dict[str, Any] = {}


class RelationshipResponse(BaseModel):
    source_id: str
    target_id: str
    relationship_type: str
    strength: float


class MetricsResponse(BaseModel):
    total_assets: int
    total_relationships: int
    asset_classes: Dict[str, int]
    avg_degree: float
    max_degree: int
    network_density: float
    relationship_density: float = 0.0


class VisualizationDataResponse(BaseModel):
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]


@app.get("/")
async def root():
    """
    Provide basic API metadata and a listing of available endpoints.

    Returns:
        Dict[str, Union[str, Dict[str, str]]]: A mapping containing:
            - "message": short API description string.
            - "version": API version string.
            - "endpoints": dict mapping endpoint keys to their URL paths (e.g., "assets": "/api/assets").
    """
    return {
        "message": "Financial Asset Relationship API",
        "version": "1.0.0",
        "endpoints": {
            "assets": "/api/assets",
            "asset_detail": "/api/assets/{asset_id}",
            "relationships": "/api/relationships",
            "metrics": "/api/metrics",
            "visualization": "/api/visualization",
        },
    }


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "graph_initialized": True}


@app.get("/api/assets", response_model=List[AssetResponse])
async def get_assets(asset_class: Optional[str] = None, sector: Optional[str] = None):
    """
    List assets, optionally filtered by asset class and sector.

    Parameters:
        asset_class (Optional[str]): Filter to include only assets whose `asset_class.value` equals this string.
        sector (Optional[str]): Filter to include only assets whose `sector` equals this string.

    Returns:
        List[AssetResponse]: AssetResponse objects matching the filters. Each object's `additional_fields` contains any non-null, asset-type-specific attributes as defined in the respective asset model classes.
    """
    try:
        g = get_graph()
        assets = []

        for _, asset in g.assets.items():
            # Apply filters
            if asset_class and asset.asset_class.value != asset_class:
                continue
            if sector and asset.sector != sector:
                continue

            # Build response using serialization utility
            asset_dict = serialize_asset(asset)
            assets.append(AssetResponse(**asset_dict))
    except Exception as e:
        logger.exception("Error getting assets:")
        raise HTTPException(status_code=500, detail=str(e)) from e
    return assets


@app.get("/api/assets/{asset_id}", response_model=AssetResponse)
async def get_asset_detail(asset_id: str):
    """
    Retrieve detailed information for the asset identified by `asset_id`.

    Parameters:
        asset_id (str): Identifier of the asset whose details are requested.

    Returns:
        AssetResponse: Detailed asset information as defined in the AssetResponse model, including core fields and an `additional_fields` map containing any asset-specific attributes that are present and non-null.

    Raises:
        HTTPException: 404 if the asset is not found.
        HTTPException: 500 for unexpected errors while retrieving the asset.
    """
    try:
        g = get_graph()
        if asset_id not in g.assets:
            raise_asset_not_found(asset_id)

        asset = g.assets[asset_id]

        # Build response using serialization utility with issuer_id included
        asset_dict = serialize_asset(asset, include_issuer=True)
        return AssetResponse(**asset_dict)
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        logger.exception("Error getting asset detail:")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get(
    "/api/assets/{asset_id}/relationships", response_model=List[RelationshipResponse]
)
async def get_asset_relationships(asset_id: str):
    """
    List outgoing relationships for the specified asset.

    Parameters:
        asset_id (str): Identifier of the asset whose outgoing relationships are requested.

    Returns:
        List[RelationshipResponse]: Outgoing relationship records for the asset (each with source_id, target_id, relationship_type, and strength).

    Raises:
        HTTPException: 404 if the asset is not found; 500 for unexpected errors.
    """
    try:
        g = get_graph()
        if asset_id not in g.assets:
            raise_asset_not_found(asset_id)

        relationships = []

        # Outgoing relationships
        if asset_id in g.relationships:
            for target_id, rel_type, strength in g.relationships[asset_id]:
                relationships.append(
                    RelationshipResponse(
                        source_id=asset_id,
                        target_id=target_id,
                        relationship_type=rel_type,
                        strength=strength,
                    )
                )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        logger.exception("Error getting asset relationships:")
        raise HTTPException(status_code=500, detail=str(e)) from e
    return relationships


@app.get("/api/relationships", response_model=List[RelationshipResponse])
async def get_all_relationships():
    """
    List all directed relationships in the initialized asset graph.

    Returns:
        List[RelationshipResponse]: List of relationships where each item contains `source_id`, `target_id`, `relationship_type`, and `strength`.
    """
    try:
        g = get_graph()
        relationships = []

        for source_id, rels in g.relationships.items():
            for target_id, rel_type, strength in rels:
                relationships.append(
                    RelationshipResponse(
                        source_id=source_id,
                        target_id=target_id,
                        relationship_type=rel_type,
                        strength=strength,
                    )
                )

    def test_workflows_use_consistent_indentation(self, workflow_files):
        """Workflow files should use consistent indentation (2 spaces)."""
        for workflow_file in workflow_files:
            with open(workflow_file, "r") as f:
                lines = f.readlines()

            for i, line in enumerate(lines, 1):
                if line.strip() and not line.strip().startswith("#"):
                    # Count leading spaces
                    leading_spaces = len(line) - len(line.lstrip(" "))
                    if leading_spaces > 0:
                        if leading_spaces % 2 != 0:
                            raise AssertionError(
                                f"{workflow_file.name}:{i} has odd indentation "
                                f"({leading_spaces} spaces)"
                            )

    def test_workflows_have_no_trailing_whitespace(self, workflow_files):
        """Workflow files should not have trailing whitespace."""
        for workflow_file in workflow_files:
            with open(workflow_file, "r") as f:
                lines = f.readlines()

            for i, line in enumerate(lines, 1):
                if line.rstrip("\n").endswith((" ", "\t")):
                    pytest.fail(f"{workflow_file.name}:{i} has trailing whitespace")


class TestWorkflowGitHubActionsSchema:
    """Test GitHub Actions schema compliance."""

    @pytest.fixture
    def workflow_data(self):
        """Load all workflow files as structured data."""
        workflow_dir = Path(".github/workflows")
        workflows = {}

        for workflow_file in list(workflow_dir.glob("*.yml")) + list(
            workflow_dir.glob("*.yaml")
        ):
            with open(workflow_file, "r") as f:
                workflows[workflow_file.name] = yaml.safe_load(f)

        return workflows

    def test_workflows_have_name(self, workflow_data):
        """All workflows should have a name field."""
        for filename, data in workflow_data.items():
            if "name" not in data:
                raise AssertionError(f"{filename} missing 'name' field")
            if not isinstance(data["name"], str):
                raise AssertionError(f"{filename} name should be string")
            if not len(data["name"]) > 0:
                raise AssertionError(f"{filename} name is empty")

    def test_workflows_have_trigger(self, workflow_data):
        """All workflows should have at least one trigger."""
        valid_triggers = {
            "on",
            "push",
            "pull_request",
            "workflow_dispatch",
            "schedule",
            "issues",
            "issue_comment",
            "pull_request_review",
            "pull_request_review_comment",
            "workflow_run",
            "repository_dispatch",
        }

        for filename, data in workflow_data.items():
            if "on" not in data:
                raise AssertionError(f"{filename} missing 'on' trigger")

            # 'on' can be string, list, or dict
            trigger = data["on"]
            if isinstance(trigger, str):
                if trigger not in valid_triggers:
                    raise AssertionError(f"{filename} has invalid trigger: {trigger}")
            elif isinstance(trigger, list):
                if not all(t in valid_triggers for t in trigger):
                    raise AssertionError(f"{filename} has invalid triggers in list")
            elif isinstance(trigger, dict):
                if not any(k in valid_triggers for k in trigger.keys()):
                    raise AssertionError(f"{filename} has no valid triggers in dict")

    def test_workflows_have_jobs(self, workflow_data):
        """All workflows should define at least one job."""
        for filename, data in workflow_data.items():
            if "jobs" not in data:
                raise AssertionError(f"{filename} missing 'jobs' section")
            if not isinstance(data["jobs"], dict):
                raise AssertionError(f"{filename} jobs should be dict")
            if not len(data["jobs"]) > 0:
                raise AssertionError(f"{filename} has no jobs defined")

    def test_jobs_have_runs_on(self, workflow_data):
        """All jobs should specify runs-on."""
        for filename, data in workflow_data.items():
            jobs = data.get("jobs", {})

            for job_name, job_data in jobs.items():
                if "runs-on" not in job_data:
                    raise AssertionError(
                        "{} job '{}' missing 'runs-on'".format(
                            filename,
                            job_name,
                        )
                    )

                runs_on = job_data["runs-on"]
                valid_runners = [
                    "ubuntu-latest",
                    "ubuntu-20.04",
                    "ubuntu-18.04",
                    "windows-latest",
                    "windows-2022",
                    "windows-2019",
                    "macos-latest",
                    "macos-12",
                    "macos-11",
                ]

                if isinstance(runs_on, str):
                    # Can be expression or literal
                    if not runs_on.startswith("${{"):
                        if not any(runner in runs_on for runner in valid_runners):
                            raise AssertionError(
                                "{} job '{}' has invalid runs-on: {}".format(
                                    filename,
                                    job_name,
                                    runs_on,
                                )
                            )

    def test_jobs_have_steps_or_uses(self, workflow_data):
        """Jobs should have either steps or uses (for reusable workflows)."""
        for filename, data in workflow_data.items():
            jobs = data.get("jobs", {})

            for job_name, job_data in jobs.items():
                has_steps = "steps" in job_data
                has_uses = "uses" in job_data

                if not (has_steps or has_uses):
                    raise AssertionError(
                        f"{filename} job '{job_name}' has neither 'steps' nor 'uses'"
                    )

                if has_steps:
                    if not isinstance(job_data["steps"], list):
                        raise AssertionError(
                            f"{filename} job '{job_name}' steps should be a list"
                        )
                    if not len(job_data["steps"]) > 0:
                        raise AssertionError(
                            f"{filename} job '{job_name}' has empty steps"
                        )


class TestWorkflowSecurity:
    """Security-focused tests for GitHub workflows."""

    @pytest.fixture
    def workflow_files(self):
        """Get all workflow files."""
        workflow_dir = Path(".github/workflows")
        return list(workflow_dir.glob("*.yml")) + list(workflow_dir.glob("*.yaml"))

    def test_no_hardcoded_secrets(self, workflow_files):
        """Workflows should not contain hardcoded secrets."""
        dangerous_patterns = [
            "ghp_",
            "github_pat_",
            "gho_",
            "ghu_",
            "ghs_",
            "ghr_",  # GitHub tokens
            "AKIA",
            "ASIA",  # AWS keys
            "-----BEGIN",
            "-----BEGIN RSA PRIVATE KEY",  # Private keys
        ]

        import re

        secret_ref_re = re.compile(r"\$\{\{\s*secrets\.[A-Za-z0-9_]+\s*\}\}")

        for workflow_file in workflow_files:
            with open(workflow_file, "r") as f:
                content = f.read()

            lines = content.splitlines()
            for i, line in enumerate(lines, start=1):
                stripped = line.strip()
                # Skip commented lines
                if stripped.startswith("#"):
                    continue
                for pattern in dangerous_patterns:
                    if pattern in line:
                        valid_refs = list(secret_ref_re.finditer(line))
                        if valid_refs:
                            # Mask valid secret reference spans, then check remaining text for dangerous patterns
                            masked = list(line)
                            for m in valid_refs:
                                for idx in range(m.start(), m.end()):
                                    masked[idx] = " "
                            remaining = "".join(masked)
                            if pattern in remaining:
                                raise AssertionError(
                                    f"{workflow_file.name}:{i} may contain hardcoded secret "
                                    f"outside secrets.* reference: {pattern}"
                                )
                        else:
                            pytest.fail(
                                f"{workflow_file.name}:{i} may contain hardcoded secret "
                                f"without secrets.* reference: {pattern}"
                            )

    def test_pull_request_safe_checkout(self, workflow_files):
        """PR workflows should checkout safely (not HEAD of PR)."""
        for workflow_file in workflow_files:
            with open(workflow_file, "r") as f:
                data = yaml.safe_load(f)

            # Check if triggered by pull_request
            triggers = data.get("on", {})
            if "pull_request" in triggers or (
                isinstance(triggers, list) and "pull_request" in triggers
            ):
                # Look for checkout actions
                jobs = data.get("jobs", {})
                for _, job_data in jobs.items():
                    steps = job_data.get("steps", [])

                    for step in steps:
                        if step.get("uses", "").startswith("actions/checkout"):
                            # Should specify ref or not checkout HEAD
                            # If no ref specified, it's okay (checks out merge commit)
                            # If ref specified, shouldn't be dangerous
                            with_data = step.get("with", {})
                            ref = with_data.get("ref", "")
                            if (
                                ref
                                and "head" in ref.lower()
                                and "sha" not in ref.lower()
                            ):
                                warnings.warn(
                                    f"{workflow_file.name} checks out PR HEAD "
                                    f"(potential security risk)"
                                )

    def test_restricted_permissions(self, workflow_files):
        """Workflows should use minimal required permissions."""
        for workflow_file in workflow_files:
            with open(workflow_file, "r") as f:
                data = yaml.safe_load(f)

            # Check top-level permissions
            permissions = data.get("permissions", {})

            # If permissions defined, shouldn't be 'write-all'
            if permissions:
                if isinstance(permissions, str):
                    if permissions == "write-all":
                        raise AssertionError(
                            f"{workflow_file.name} uses write-all permissions (too broad)"
                        )
                elif isinstance(permissions, dict):
                    # Check individual permissions
                    for perm, level in permissions.items():
                        if level == "write":
                            # Write permissions should have justification in comments
                            warnings.warn(
                                f"{workflow_file.name} uses write permission for '{perm}' (too broad)",
                                UserWarning,
                            )


class TestWorkflowBestPractices:
    """Test adherence to GitHub Actions best practices."""

    @pytest.fixture
    def workflow_data(self):
        """Load all workflow files."""
        workflow_dir = Path(".github/workflows")
        workflows = {}

        for workflow_file in list(workflow_dir.glob("*.yml")) + list(
            workflow_dir.glob("*.yaml")
        ):
            with open(workflow_file, "r") as f:
                workflows[workflow_file.name] = yaml.safe_load(f)

        return workflows

    def test_actions_use_specific_versions(self, workflow_data):
        """Actions should use specific versions (not latest/master)."""
        for filename, data in workflow_data.items():
            jobs = data.get("jobs", {})

            for job_name, job_data in jobs.items():
                steps = job_data.get("steps", [])

                for i, step in enumerate(steps):
                    uses = step.get("uses", "")
                    if uses:
                        # Should not use @main or @master
                        if "@main" in uses or "@master" in uses:
                            warnings.warn(
                                f"{filename} job '{job_name}' step {i} "
                                f"uses unstable version: {uses}"
                            )

    def test_steps_have_names(self, workflow_data):
        """Steps should have descriptive names."""
        for filename, data in workflow_data.items():
            jobs = data.get("jobs", {})

            for job_name, job_data in jobs.items():
                steps = job_data.get("steps", [])

                unnamed_steps = [
                    i for i, step in enumerate(steps) if "name" not in step
                ]

                # Allow a few unnamed steps, but not too many
                unnamed_ratio = len(unnamed_steps) / len(steps) if steps else 0
                if not unnamed_ratio < 0.5:
                    raise AssertionError(
                        f"{filename} job '{job_name}' has too many unnamed steps"
                    )

    def test_timeouts_defined(self, workflow_data):
        """Long-running jobs should have timeouts."""
        for filename, data in workflow_data.items():
            jobs = data.get("jobs", {})

            for job_name, job_data in jobs.items():
                steps = job_data.get("steps", [])

                # If job has many steps or installs dependencies, should have timeout
                if len(steps) > 5:
                    # Check for timeout-minutes
                    if "timeout-minutes" not in job_data:
                        warnings.warn(
                            f"{filename} job '{job_name}' has many steps "
                            f"but no timeout defined"
                        )


class TestWorkflowCrossPlatform:
    """Test cross-platform compatibility issues."""

    @pytest.fixture
    def workflow_data(self):
        """Load workflow data."""
        workflow_dir = Path(".github/workflows")
        workflows = {}

        for workflow_file in list(workflow_dir.glob("*.yml")) + list(
            workflow_dir.glob("*.yaml")
        ):
            with open(workflow_file, "r") as f:
                workflows[workflow_file.name] = yaml.safe_load(f)

        return workflows

    def test_shell_script_compatibility(self, workflow_data):
        """Shell scripts should be compatible with runner OS."""
        for filename, data in workflow_data.items():
            jobs = data.get("jobs", {})

            for job_name, job_data in jobs.items():
                runs_on = job_data.get("runs-on", "")
                steps = job_data.get("steps", [])

                is_windows = "windows" in str(runs_on).lower()

                for step in steps:
                    run_command = step.get("run", "")
                    shell = step.get("shell", "bash" if not is_windows else "pwsh")

                    if run_command:
                        # Check for Unix-specific commands on Windows
                        if is_windows and shell in ["bash", "sh"]:
                            unix_commands = ["grep", "sed", "awk", "find"]
                            for cmd in unix_commands:
                                if cmd in run_command:
                                    warnings.warn(
                                        f"{filename} job '{job_name}' uses "
                                        f"Unix command '{cmd}' on Windows"
                                    )

    def test_path_separators(self, workflow_data):
        """File paths should use forward slashes for cross-platform compatibility."""
        for _, data in workflow_data.items():
            jobs = data.get("jobs", {})

            for _, job_data in jobs.items():
                steps = job_data.get("steps", [])

                for step in steps:
                    run_command = step.get("run", "")

                    # Check for Windows-style paths (backslashes)
                    if (
                        "\\" in run_command
                        and "windows" not in str(job_data.get("runs-on", "")).lower()
                    ):
                        # Might be legitimate (escaped chars), so just warn
                        self.fail(
                            f"Windows-style path (backslashes) found in run command: {run_command}"
                        )


class TestWorkflowMaintainability:
    """Test workflow maintainability and documentation."""

    @staticmethod
    def test_workflows_have_comments():
        """Workflows should have explanatory comments."""
        workflow_dir = Path(".github/workflows")

        for workflow_file in list(workflow_dir.glob("*.yml")) + list(
            workflow_dir.glob("*.yaml")
        ):
            with open(workflow_file, "r") as f:
                content = f.read()

            lines = content.split("\n")
            comment_lines = [line for line in lines if line.strip().startswith("#")]
            code_lines = [
                line
                for line in lines
                if line.strip() and not line.strip().startswith("#")
            ]

            if len(code_lines) > 20:
                # Large workflows should have comments
                comment_ratio = len(comment_lines) / len(code_lines)
                if comment_ratio < 0.05:
                    raise AssertionError(
                        f"{workflow_file.name} is large but has few comments"
                    )

    @staticmethod
    def test_complex_expressions_explained():
        """Complex expressions should have explanatory comments."""
        workflow_dir = Path(".github/workflows")

        for workflow_file in list(workflow_dir.glob("*.yml")) + list(
            workflow_dir.glob("*.yaml")
        ):
            with open(workflow_file, "r") as f:
                content = f.read()

            # Look for complex expressions
            import re

            complex_patterns = [
                r"\$\{\{.*\&\&.*\}\}",  # Multiple conditions
                r"\$\{\{.*\|\|.*\}\}",  # OR conditions
                r"\$\{\{.*\(.*\).*\\}\}",  # Grouping expressions
            ]

            for pattern in complex_patterns:
                for match_item in re.finditer(pattern, content):
                    context = match_item.group()

                    # Should have explanation
                    lines = context.split("\n")
                    if len(lines) < 2 or "#" not in lines[-2]:
                        line_num = content[: match_item.start()].count("\n") + 1
                        GLOBAL_WARNINGS.warn(
                            f"{workflow_file.name}: complex expression at line {line_num} "
                            f"lacks explanation: {match_item.group()}"
                        )
