"""Configuration management for Azure DevOps CLI."""

import os
from pathlib import Path
from functools import lru_cache

import yaml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from ado_cli.exceptions import ConfigurationError

CONFIG_DIR = Path.home() / ".ado-cli"
CONFIG_FILE = CONFIG_DIR / "config.yaml"


class AdoConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ADO_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    organization: str = Field(default="")
    project: str = Field(default="")
    pat: str = Field(default="")
    team: str = Field(default="")
    api_version: str = Field(default="7.0")

    @field_validator("organization", "project", "pat")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip() if v else v

    @property
    def base_url(self) -> str:
        return f"https://dev.azure.com/{self.organization}/{self.project}/_apis"

    @property
    def web_url(self) -> str:
        return f"https://dev.azure.com/{self.organization}/{self.project}/_workitems/edit"

    @property
    def effective_team(self) -> str:
        return self.team or self.project

    def is_configured(self) -> bool:
        return bool(self.organization and self.project and self.pat)

    def validate_or_raise(self) -> None:
        missing = [k for k in ("organization", "project", "pat") if not getattr(self, k)]
        if missing:
            raise ConfigurationError(
                f"Missing: {', '.join(missing)}. "
                f"Set via ADO_ORGANIZATION, ADO_PROJECT, ADO_PAT or {CONFIG_FILE}"
            )


def load_yaml_config() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    try:
        with open(CONFIG_FILE) as f:
            return yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        raise ConfigurationError(f"Invalid YAML: {e}")


def save_config(organization: str, project: str, pat: str, team: str = "") -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config_data = {"organization": organization, "project": project, "pat": pat}
    if team:
        config_data["team"] = team
    with open(CONFIG_FILE, "w") as f:
        yaml.safe_dump(config_data, f, default_flow_style=False)
    os.chmod(CONFIG_FILE, 0o600)


@lru_cache
def get_config() -> AdoConfig:
    return AdoConfig(**load_yaml_config())


def clear_config_cache() -> None:
    get_config.cache_clear()
