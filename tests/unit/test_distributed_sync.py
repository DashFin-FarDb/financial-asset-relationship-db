"""Unit tests for graph lifecycle synchronization logic."""

from unittest.mock import MagicMock, patch
import pytest
from api.graph_lifecycle import sync_with_latest_rebuild, GraphRuntimeLifecycleState
from src.logic.asset_graph import AssetRelationshipGraph


@pytest.fixture
def mock_settings():
    """Mock GraphLifecycleSettings."""
    with patch("api.graph_lifecycle_providers.get_graph_lifecycle_settings") as mock:
        settings = MagicMock()
        settings.asset_graph_database_url = "sqlite:///test.db"
        mock.return_value = settings
        yield settings


@pytest.fixture
def mock_graph_state():
    """Mock global graph_state."""
    with patch("api.graph_lifecycle.graph_state") as mock:
        mock.lifecycle_state = GraphRuntimeLifecycleState.READY
        mock.last_synced_job_id = "old-job-id"
        yield mock


@pytest.mark.unit
class TestDistributedSync:
    """Test cases for sync_with_latest_rebuild."""

    def test_sync_no_database_url(self, mock_settings):
        """Test sync does nothing if database URL is not configured."""
        mock_settings.asset_graph_database_url = None
        
        with patch("src.data.repository.AssetGraphRepository.get_latest_successful_rebuild_job") as mock_get:
            sync_with_latest_rebuild()
            mock_get.assert_not_called()

    def test_sync_rebuilding_state(self, mock_graph_state):
        """Test sync does nothing if currently rebuilding."""
        with patch("api.graph_lifecycle.get_runtime_lifecycle_state") as mock_state:
            mock_state.return_value = GraphRuntimeLifecycleState.REBUILDING
            
            with patch("src.data.repository.AssetGraphRepository.get_latest_successful_rebuild_job") as mock_get:
                sync_with_latest_rebuild()
                mock_get.assert_not_called()

    def test_sync_already_up_to_date(self, mock_settings, mock_graph_state):
        """Test sync does nothing if already on latest job id."""
        with patch("src.data.database.create_engine_from_url"):
            with patch("src.data.database.create_session_factory"):
                with patch("src.data.repository.AssetGraphRepository.get_latest_successful_rebuild_job") as mock_get:
                    latest_job = MagicMock()
                    latest_job.job_id = "old-job-id"
                    mock_get.return_value = latest_job
                    
                    with patch("api.graph_lifecycle.synchronize_runtime_graph") as mock_sync:
                        sync_with_latest_rebuild()
                        mock_sync.assert_not_called()

    def test_sync_performs_synchronization(self, mock_settings, mock_graph_state):
        """Test sync performs synchronization when a newer job is found."""
        with patch("src.data.database.create_engine_from_url"):
            with patch("src.data.database.create_session_factory"):
                with patch("src.data.repository.AssetGraphRepository.get_latest_successful_rebuild_job") as mock_get:
                    latest_job = MagicMock()
                    latest_job.job_id = "new-job-id"
                    mock_get.return_value = latest_job
                    
                    with patch("src.data.repository.AssetGraphRepository.load_graph") as mock_load:
                        new_graph = AssetRelationshipGraph()
                        mock_load.return_value = new_graph
                        
                        with patch("api.graph_lifecycle.synchronize_runtime_graph") as mock_sync:
                            sync_with_latest_rebuild()
                            mock_sync.assert_called_once_with(new_graph, job_id="new-job-id")
