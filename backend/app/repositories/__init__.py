"""Persistence adapters selected at the application boundary."""

from .cloudbase_http import CloudBaseDataError, CloudBaseHttpSession

__all__ = ["CloudBaseDataError", "CloudBaseHttpSession"]
