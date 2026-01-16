"""Azure DevOps API client."""

import base64
import time
from functools import wraps
from typing import Any, Callable, TypeVar
from urllib.parse import quote

import httpx
import markdown

from ado_cli.config import AdoConfig
from ado_cli.exceptions import ApiError, AuthenticationError, WorkItemNotFoundError
from ado_cli.models import Comment, Iteration, PatchOperation, WorkItem, get_field_name

T = TypeVar("T")

MAX_RETRIES = 3
RETRY_DELAY = 1.0
RETRYABLE_EXCEPTIONS = (httpx.ConnectError, httpx.ReadError, ConnectionResetError, OSError)

MD_CONVERTER = markdown.Markdown(extensions=["nl2br", "fenced_code", "tables"])


def md_to_html(text: str | None) -> str | None:
    if not text:
        return text
    MD_CONVERTER.reset()
    return MD_CONVERTER.convert(text)


def with_retry(func: Callable[..., T]) -> Callable[..., T]:
    @wraps(func)
    def wrapper(*args, **kwargs) -> T:
        last_exc = None
        for attempt in range(MAX_RETRIES):
            try:
                return func(*args, **kwargs)
            except RETRYABLE_EXCEPTIONS as e:
                last_exc = e
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (attempt + 1))
        raise last_exc
    return wrapper


class AzureDevOpsClient:
    def __init__(self, config: AdoConfig):
        self.config = config
        self._client: httpx.Client | None = None

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            credentials = f":{self.config.pat}"
            auth = f"Basic {base64.b64encode(credentials.encode()).decode()}"
            self._client = httpx.Client(
                base_url=self.config.base_url,
                headers={"Authorization": auth, "Content-Type": "application/json"},
                timeout=httpx.Timeout(30.0, connect=10.0),
            )
        return self._client

    def _handle_response(self, response: httpx.Response, context: str = "") -> dict:
        if response.status_code == 401:
            raise AuthenticationError("Authentication failed. Check your PAT.")
        if response.status_code == 404:
            raise ApiError(f"Resource not found: {context}", 404)
        if response.status_code >= 400:
            try:
                body = response.json()
                message = body.get("message", response.text)
            except Exception:
                body, message = None, response.text
            raise ApiError(f"API error: {message}", response.status_code, body)
        return {} if response.status_code == 204 else response.json()

    def close(self) -> None:
        if self._client:
            self._client.close()
            self._client = None

    def __enter__(self) -> "AzureDevOpsClient":
        return self

    def __exit__(self, *args) -> None:
        self.close()

    @with_retry
    def get_work_item(self, work_item_id: int, expand: str = "all") -> WorkItem:
        response = self.client.get(
            f"/wit/workitems/{work_item_id}",
            params={"$expand": expand, "api-version": self.config.api_version},
        )
        if response.status_code == 404:
            raise WorkItemNotFoundError(work_item_id)
        return WorkItem.from_api_response(self._handle_response(response, f"work item {work_item_id}"))

    @with_retry
    def get_work_items(self, work_item_ids: list[int], expand: str = "all") -> list[WorkItem]:
        if not work_item_ids:
            return []
        ids_str = ",".join(str(id) for id in work_item_ids[:200])
        response = self.client.get(
            "/wit/workitems",
            params={"ids": ids_str, "$expand": expand, "api-version": self.config.api_version},
        )
        data = self._handle_response(response, "work items batch")
        return [WorkItem.from_api_response(item) for item in data.get("value", [])]

    @with_retry
    def create_work_item(self, work_item_type: str, title: str, **fields: Any) -> WorkItem:
        if "description" in fields and fields["description"]:
            fields["description"] = md_to_html(fields["description"])
        operations = [PatchOperation.for_field("System.Title", title)]
        for field_name, value in fields.items():
            if value is not None:
                operations.append(PatchOperation.for_field(get_field_name(field_name), value))

        response = self.client.post(
            f"/wit/workitems/${work_item_type}",
            params={"api-version": self.config.api_version},
            headers={"Content-Type": "application/json-patch+json"},
            json=[op.model_dump() for op in operations],
        )
        return WorkItem.from_api_response(self._handle_response(response, f"create {work_item_type}"))

    @with_retry
    def update_work_item(self, work_item_id: int, **fields: Any) -> WorkItem:
        if "description" in fields and fields["description"]:
            fields["description"] = md_to_html(fields["description"])
        operations = [
            PatchOperation.for_field(get_field_name(k), v)
            for k, v in fields.items() if v is not None
        ]
        if not operations:
            raise ValueError("No fields to update")

        response = self.client.patch(
            f"/wit/workitems/{work_item_id}",
            params={"api-version": self.config.api_version},
            headers={"Content-Type": "application/json-patch+json"},
            json=[op.model_dump() for op in operations],
        )
        if response.status_code == 404:
            raise WorkItemNotFoundError(work_item_id)
        return WorkItem.from_api_response(self._handle_response(response, f"update {work_item_id}"))

    @with_retry
    def delete_work_item(self, work_item_id: int, destroy: bool = False) -> bool:
        response = self.client.delete(
            f"/wit/workitems/{work_item_id}",
            params={"destroy": str(destroy).lower(), "api-version": self.config.api_version},
        )
        if response.status_code == 404:
            raise WorkItemNotFoundError(work_item_id)
        self._handle_response(response, f"delete {work_item_id}")
        return True

    @with_retry
    def query_work_items(self, wiql: str) -> list[WorkItem]:
        response = self.client.post(
            "/wit/wiql",
            params={"api-version": self.config.api_version},
            json={"query": wiql},
        )
        data = self._handle_response(response, "WIQL query")
        refs = data.get("workItems", [])
        return self.get_work_items([r["id"] for r in refs]) if refs else []

    def get_my_work_items(self, state: str | None = None) -> list[WorkItem]:
        wiql = "SELECT [System.Id] FROM WorkItems WHERE [System.AssignedTo] = @Me"
        if state:
            wiql += f" AND [System.State] = '{state}'"
        wiql += " ORDER BY [System.ChangedDate] DESC"
        return self.query_work_items(wiql)

    def get_sprint_work_items(self, user: str | None = None) -> list[WorkItem]:
        user_filter = f"'{user}'" if user else "@Me"
        wiql = f"""
            SELECT [System.Id] FROM WorkItems
            WHERE [System.AssignedTo] = {user_filter}
              AND [System.IterationPath] = @CurrentIteration
            ORDER BY [System.State], [System.ChangedDate] DESC
        """
        return self.query_work_items(wiql)

    @with_retry
    def get_comments(self, work_item_id: int) -> list[Comment]:
        response = self.client.get(
            f"/wit/workitems/{work_item_id}/comments",
            params={"api-version": "7.0-preview.3"},
        )
        if response.status_code == 404:
            raise WorkItemNotFoundError(work_item_id)
        data = self._handle_response(response, f"comments for {work_item_id}")
        return [Comment(**c) for c in data.get("comments", [])]

    @with_retry
    def add_comment(self, work_item_id: int, text: str) -> Comment:
        response = self.client.post(
            f"/wit/workitems/{work_item_id}/comments",
            params={"api-version": "7.0-preview.3"},
            json={"text": text},
        )
        if response.status_code == 404:
            raise WorkItemNotFoundError(work_item_id)
        return Comment(**self._handle_response(response, f"add comment to {work_item_id}"))

    @with_retry
    def get_iterations(self, timeframe: str | None = None) -> list[Iteration]:
        org = quote(self.config.organization, safe="")
        project = quote(self.config.project, safe="")
        team = quote(self.config.effective_team, safe="")

        params = {"api-version": self.config.api_version}
        if timeframe:
            params["$timeframe"] = timeframe

        url = f"https://dev.azure.com/{org}/{project}/{team}/_apis/work/teamsettings/iterations"
        response = self.client.get(url, params=params)

        if response.status_code == 404:
            url = f"https://dev.azure.com/{org}/{project}/_apis/work/teamsettings/iterations"
            response = self.client.get(url, params=params)

        if response.status_code == 404:
            return []

        data = self._handle_response(response, "iterations")
        return [Iteration.from_api_response(item) for item in data.get("value", [])]

    def get_current_iteration(self) -> Iteration | None:
        try:
            iterations = self.get_iterations(timeframe="current")
            return iterations[0] if iterations else None
        except ApiError:
            return None

    @with_retry
    def test_connection(self) -> bool:
        try:
            response = self.client.get(
                f"https://dev.azure.com/{self.config.organization}/_apis/projects/{self.config.project}",
                params={"api-version": self.config.api_version},
            )
            self._handle_response(response, "connection test")
            return True
        except AuthenticationError:
            raise
        except ApiError as e:
            if e.status_code == 404:
                raise ApiError(f"Project '{self.config.project}' not found", 404)
            raise
