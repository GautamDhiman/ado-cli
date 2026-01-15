"""Custom exceptions for Azure DevOps CLI."""

from typing import Any


class AdoCliError(Exception):
    def __init__(self, message: str, details: Any = None):
        self.message = message
        self.details = details
        super().__init__(self.message)


class ConfigurationError(AdoCliError):
    pass


class AuthenticationError(AdoCliError):
    pass


class WorkItemNotFoundError(AdoCliError):
    def __init__(self, work_item_id: int):
        super().__init__(f"Work item {work_item_id} not found")
        self.work_item_id = work_item_id


class ApiError(AdoCliError):
    def __init__(self, message: str, status_code: int, response_body: dict | None = None):
        super().__init__(message, details=response_body)
        self.status_code = status_code
        self.response_body = response_body
