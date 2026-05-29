"""Tests for graph admin router registration."""

# pylint: disable=redefined-outer-name

# NOSONAR: Integration tests intentionally exercise app/auth/router wiring.

from __future__ import annotations

import asyncio
import contextlib
import logging
import threading
import time
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Generator

import httpx  # pylint: disable=import-error
import pytest  # pylint: disable=import-error
from fastapi import HTTPException  # pylint: disable=import-error
from fastapi.testclient import TestClient  # pylint: disable=import-error

# Module-level import is safe as api.routers.graph_admin is side-effect free on import.
# This allows direct access to internal helpers for tests and ensuring monkeypatch targets are available.
import api.routers.graph_admin as graph_admin
from api.auth import (
    REBUILD_OPERATOR_FORBIDDEN_DETAIL,
    REBUILD_OPERATOR_NOT_CONFIGURED_DETAIL,
    User,
    get_current_active_user,
)
from api.graph_lifecycle import reset_graph
from src.config.settings import get_settings
from src.data.database import create_engine_from_url, create_session_factory, init_db
from src.data.repository import AssetGraphRepository, session_scope

pytestmark = pytest.mark.integration

if TYPE_CHECKING:
    from sqlalchemy.orm import sessionmaker
