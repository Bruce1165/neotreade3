"""Lab registry models and loaders for NeoTrade3 bootstrap."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from neotrade3.config_contracts import raise_for_contract_issues, validate_lab_registry


@dataclass
class LabJobContract:
    """Minimal daily job contract for one lab."""

    task_id: str
    job_id: str
    display_name: str
    trigger_type: str
    phase: str
    entrypoint: str
    depends_on: list[str]
    requires_publish_status: bool
    outputs: list[str]
    artifacts: list[str]
    health_checks: list[str]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "LabJobContract":
        depends_on_raw = payload.get("depends_on", [])
        depends_on = (
            [str(item) for item in depends_on_raw]
            if isinstance(depends_on_raw, list)
            else []
        )
        outputs_raw = payload.get("outputs", [])
        outputs = (
            [str(item) for item in outputs_raw] if isinstance(outputs_raw, list) else []
        )
        artifacts_raw = payload.get("artifacts", [])
        artifacts = (
            [str(item) for item in artifacts_raw]
            if isinstance(artifacts_raw, list)
            else []
        )
        health_checks_raw = payload.get("health_checks", [])
        health_checks = (
            [str(item) for item in health_checks_raw]
            if isinstance(health_checks_raw, list)
            else []
        )
        return cls(
            task_id=str(payload["task_id"]),
            job_id=str(payload["job_id"]),
            display_name=str(payload["display_name"]),
            trigger_type=str(payload["trigger_type"]),
            phase=str(payload["phase"]),
            entrypoint=str(payload["entrypoint"]),
            depends_on=depends_on,
            requires_publish_status=bool(payload.get("requires_publish_status", False)),
            outputs=outputs,
            artifacts=artifacts,
            health_checks=health_checks,
        )


@dataclass
class LabArtifactContract:
    """Declared artifact contract for one lab output."""

    artifact_id: str
    path: str
    description: str

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "LabArtifactContract":
        return cls(
            artifact_id=str(payload["artifact_id"]),
            path=str(payload["path"]),
            description=str(payload.get("description", "")),
        )


@dataclass
class LabHealthCheck:
    """Bootstrap health check contract for one lab."""

    check_id: str
    description: str

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "LabHealthCheck":
        return cls(
            check_id=str(payload["check_id"]),
            description=str(payload.get("description", "")),
        )


@dataclass
class LabRegistration:
    """Minimal lab registration structure used by the orchestrator bootstrap."""

    lab_id: str
    display_name: str
    domain: str
    owner: str
    enabled: bool
    input_dependencies: list[str]
    daily_jobs: list[LabJobContract]
    artifacts: list[LabArtifactContract]
    health_checks: list[LabHealthCheck]
    learning_inputs: list[str]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "LabRegistration":
        input_dependencies_raw = payload.get("input_dependencies", [])
        input_dependencies = (
            [str(item) for item in input_dependencies_raw]
            if isinstance(input_dependencies_raw, list)
            else []
        )
        daily_jobs_raw = payload.get("daily_jobs", [])
        daily_jobs = (
            [
                LabJobContract.from_dict(item)
                for item in daily_jobs_raw
                if isinstance(item, dict)
            ]
            if isinstance(daily_jobs_raw, list)
            else []
        )
        artifacts_raw = payload.get("artifacts", [])
        artifacts = (
            [
                LabArtifactContract.from_dict(item)
                for item in artifacts_raw
                if isinstance(item, dict)
            ]
            if isinstance(artifacts_raw, list)
            else []
        )
        health_checks_raw = payload.get("health_checks", [])
        health_checks = (
            [
                LabHealthCheck.from_dict(item)
                for item in health_checks_raw
                if isinstance(item, dict)
            ]
            if isinstance(health_checks_raw, list)
            else []
        )
        learning_inputs_raw = payload.get("learning_inputs", [])
        learning_inputs = (
            [str(item) for item in learning_inputs_raw]
            if isinstance(learning_inputs_raw, list)
            else []
        )
        return cls(
            lab_id=str(payload["lab_id"]),
            display_name=str(payload["display_name"]),
            domain=str(payload["domain"]),
            owner=str(payload["owner"]),
            enabled=bool(payload["enabled"]),
            input_dependencies=input_dependencies,
            daily_jobs=daily_jobs,
            artifacts=artifacts,
            health_checks=health_checks,
            learning_inputs=learning_inputs,
        )


@dataclass
class LabRegistry:
    """Collection wrapper for lab registrations."""

    version: int
    description: str
    labs: list[LabRegistration]

    @classmethod
    def from_file(cls, file_path: str | Path) -> "LabRegistry":
        payload = json.loads(Path(file_path).read_text(encoding="utf-8"))
        return cls.from_dict(payload)

    @classmethod
    def from_dict(cls, payload: Any) -> "LabRegistry":
        if not isinstance(payload, dict):
            raise TypeError("lab registry root must be a JSON object")
        payload_dict = cast(dict[str, Any], payload)
        labs_raw = payload_dict.get("labs", [])
        labs = (
            [
                LabRegistration.from_dict(item)
                for item in labs_raw
                if isinstance(item, dict)
            ]
            if isinstance(labs_raw, list)
            else []
        )
        registry = cls(
            version=int(payload_dict["version"]),
            description=str(payload_dict.get("description", "")),
            labs=labs,
        )
        raise_for_contract_issues("lab registry", validate_lab_registry(registry))
        return registry

    def enabled_labs(self) -> list[LabRegistration]:
        return [lab for lab in self.labs if lab.enabled]

    def get_lab(self, lab_id: str) -> LabRegistration | None:
        for lab in self.labs:
            if lab.lab_id == lab_id:
                return lab
        return None

    def all_job_contracts(self) -> list[LabJobContract]:
        return [job for lab in self.enabled_labs() for job in lab.daily_jobs]

    def get_job_contract(self, task_id: str) -> LabJobContract | None:
        for job in self.all_job_contracts():
            if job.task_id == task_id:
                return job
        return None
