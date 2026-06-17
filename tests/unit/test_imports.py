"""Tests to ensure no import cycles occur during application startup."""


def test_no_import_cycles():
    """Verify that importing the main entrypoints does not raise errors due to import cycles."""
    import api.main
    import app

    assert app is not None
    assert api.main is not None
