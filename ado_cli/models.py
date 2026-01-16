"""Pydantic models for Azure DevOps entities."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, computed_field


class User(BaseModel):
    display_name: str = Field(alias="displayName")
    unique_name: str | None = Field(default=None, alias="uniqueName")
    id: str | None = None

    class Config:
        populate_by_name = True


class Comment(BaseModel):
    id: int
    text: str
    created_by: User | None = Field(default=None, alias="createdBy")
    created_date: datetime | None = Field(default=None, alias="createdDate")
    modified_date: datetime | None = Field(default=None, alias="modifiedDate")

    class Config:
        populate_by_name = True


class WorkItem(BaseModel):
    id: int
    rev: int = 0
    url: str = ""
    title: str = ""
    state: str = ""
    work_item_type: str = Field(default="", alias="workItemType")
    assigned_to: User | None = None
    created_by: User | None = None
    remaining_work: float | None = None
    original_estimate: float | None = None
    completed_work: float | None = None
    story_points: float | None = None
    area_path: str = ""
    iteration_path: str = ""
    description: str = ""
    acceptance_criteria: str = ""
    created_date: datetime | None = None
    changed_date: datetime | None = None
    tags: str = ""
    raw_fields: dict[str, Any] = Field(default_factory=dict)

    class Config:
        populate_by_name = True

    @computed_field
    @property
    def tag_list(self) -> list[str]:
        return [t.strip() for t in self.tags.split(";") if t.strip()] if self.tags else []

    @classmethod
    def from_api_response(cls, data: dict) -> "WorkItem":
        fields = data.get("fields", {})
        assigned_to = User(**fields["System.AssignedTo"]) if "System.AssignedTo" in fields else None
        created_by = User(**fields["System.CreatedBy"]) if "System.CreatedBy" in fields else None

        return cls(
            id=data.get("id", 0),
            rev=data.get("rev", 0),
            url=data.get("url", ""),
            title=fields.get("System.Title", ""),
            state=fields.get("System.State", ""),
            work_item_type=fields.get("System.WorkItemType", ""),
            assigned_to=assigned_to,
            created_by=created_by,
            remaining_work=fields.get("Microsoft.VSTS.Scheduling.RemainingWork"),
            original_estimate=fields.get("Microsoft.VSTS.Scheduling.OriginalEstimate"),
            completed_work=fields.get("Microsoft.VSTS.Scheduling.CompletedWork"),
            story_points=fields.get("Custom.StoryPoints") or fields.get("Microsoft.VSTS.Scheduling.StoryPoints"),
            area_path=fields.get("System.AreaPath", ""),
            iteration_path=fields.get("System.IterationPath", ""),
            description=fields.get("System.Description", ""),
            acceptance_criteria=fields.get("Microsoft.VSTS.Common.AcceptanceCriteria", ""),
            created_date=fields.get("System.CreatedDate"),
            changed_date=fields.get("System.ChangedDate"),
            tags=fields.get("System.Tags", ""),
            raw_fields=fields,
        )


class Iteration(BaseModel):
    id: str
    name: str
    path: str
    start_date: datetime | None = Field(default=None, alias="startDate")
    finish_date: datetime | None = Field(default=None, alias="finishDate")
    time_frame: str = Field(default="", alias="timeFrame")

    class Config:
        populate_by_name = True

    @property
    def is_current(self) -> bool:
        return self.time_frame == "current"

    @classmethod
    def from_api_response(cls, data: dict) -> "Iteration":
        attrs = data.get("attributes", {})
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            path=data.get("path", ""),
            start_date=attrs.get("startDate"),
            finish_date=attrs.get("finishDate"),
            time_frame=attrs.get("timeFrame", ""),
        )


class PatchOperation(BaseModel):
    op: str = "replace"
    path: str
    value: Any

    @classmethod
    def for_field(cls, field_name: str, value: Any) -> "PatchOperation":
        return cls(op="replace", path=f"/fields/{field_name}", value=value)


FIELD_MAPPING = {
    "title": "System.Title",
    "state": "System.State",
    "description": "System.Description",
    "remaining": "Microsoft.VSTS.Scheduling.RemainingWork",
    "remaining_work": "Microsoft.VSTS.Scheduling.RemainingWork",
    "original_estimate": "Microsoft.VSTS.Scheduling.OriginalEstimate",
    "completed_work": "Microsoft.VSTS.Scheduling.CompletedWork",
    "story_points": "Custom.StoryPoints",
    "points": "Custom.StoryPoints",
    "assigned_to": "System.AssignedTo",
    "area_path": "System.AreaPath",
    "iteration_path": "System.IterationPath",
    "tags": "System.Tags",
    "acceptance_criteria": "Microsoft.VSTS.Common.AcceptanceCriteria",
    "target_date": "Microsoft.VSTS.Scheduling.TargetDate",
    "labels": "Custom.Labels",
    "pii_impact": "Custom.ImpactonPIIorFinancialDataorGroundOperations",
    "load_testing": "Custom.LoadTesting",
    "sprint_committed": "Custom.SprintTargetStatusCommitted",
}


def get_field_name(short_name: str) -> str:
    return FIELD_MAPPING.get(short_name.lower(), short_name)
