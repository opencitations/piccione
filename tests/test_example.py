"""Example tests for piccione."""

from piccione import example_function


def test_example_function():
    """Test that example_function returns expected value."""
    result = example_function()
    assert result == "Hello from piccione!"
