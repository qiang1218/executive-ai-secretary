"""Compatibility shim: see ``core.data_source_configuration``."""
from __future__ import annotations

from core.data_source_configuration import (  # noqa: F401
    DataSourceConfigurationError,
    merge_data_source_configuration,
    public_data_source_configuration,
    validate_data_source_configuration,
)

__all__ = [
    "DataSourceConfigurationError",
    "merge_data_source_configuration",
    "public_data_source_configuration",
    "validate_data_source_configuration",
]
