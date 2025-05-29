"""Test package for staarb statistical arbitrage trading system."""

# Test configuration and shared fixtures can be added here

# Common test configuration
pytest_plugins: list[str] = []


# Mark async tests
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "asyncio: mark test as async")
