"""Tests for explicit graph rebuild persistence."""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import AsyncGenerator, Iterator
from unittest.mock import MagicMock, patch

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import api.graph_lifecycle_providers as providers

# Module-level import is safe as api.routers.graph_admin is side-effect free on import.
# This allows direct access to internal helpers for tests and ensuring monkeypatch targets are available.
import api.routers.graph_admin as graph_admin
from api.app_factory import create_app
from api.auth import User, get_current_active_user, get_current_rebuild_operator_user
from api.graph_lifecycle import reset_graph
from src.config.settings import get_settings
from src.data.database import create_engine_from_url, create_session_factory, init_db
from src.data.distributed_lock import LockState
from src.data.repository import AssetGraphRepository
from src.logic.asset_graph import AssetRelationshipGraph

pytestmark = pytest.mark.integration
