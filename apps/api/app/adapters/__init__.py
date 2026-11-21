"""Data adapters — mocks now; Person 2 swaps in live HTTP later."""

from app.adapters.mocks import MockAdapterBundle, fetch_all_mocks
from app.adapters.protocol import AdapterProtocol

__all__ = ["AdapterProtocol", "MockAdapterBundle", "fetch_all_mocks"]
