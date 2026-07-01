"""Serialization contract test for asset page responses."""

import pytest

from api.api_models import AssetPageResponse

pytestmark = pytest.mark.unit


def test_asset_page_response_uses_public_has_more_alias() -> None:
    response = AssetPageResponse(items=[], total=2, page=1, per_page=1, has_more=True)

    payload = response.model_dump(by_alias=True)

    assert payload["hasMore"] is True
    assert set(payload) == {"items", "total", "page", "per_page", "hasMore"}
