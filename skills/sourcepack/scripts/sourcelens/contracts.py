"""Strict boundary validation. Source text is never executable configuration."""
from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Any


class ContractError(ValueError):
    pass


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


@dataclass(frozen=True)
class Policy:
    max_bytes: int = 64 * 1024 * 1024
    max_inputs: int = 16
    max_spans: int = 2000
    max_video_seconds: int = 300
    max_frames: int = 12
    max_ticket_spans: int = 8
    max_ticket_characters: int = 12000
    max_result_bytes: int = 64000
    lease_seconds: int = 900
    network: bool = False
    version: str = 'local-import-v1'

    @property
    def id(self) -> str:
        return 'policy-' + digest(asdict(self))


def object_fields(obj: Any, required: set[str], optional: set[str] = frozenset()) -> None:
    if not isinstance(obj, dict) or not required <= obj.keys() or obj.keys() - required - optional:
        raise ContractError('Missing or unsupported object fields')


def text_value(value: Any, limit: int = 12000) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ContractError('Expected nonempty bounded text')
    return value


@dataclass(frozen=True)
class HostResult:
    schema_version: str
    job_id: str
    task_id: str
    attempt_id: str
    lease_id: str
    policy_id: str
    source_revision_ids: list[str]
    inspection_records: list[dict]
    observations: list[dict]
    gaps: list[dict]

    @classmethod
    def parse(cls, value: dict, policy: Policy) -> 'HostResult':
        object_fields(value, set(cls.__dataclass_fields__))
        if len(canonical(value).encode()) > policy.max_result_bytes:
            raise ContractError('Result exceeds byte budget')
        if value['schema_version'] != 'sourcelens.host-result.v1':
            raise ContractError('Unsupported result schema')
        for key in ('job_id', 'task_id', 'attempt_id', 'lease_id', 'policy_id'):
            text_value(value[key], 128)
        for key in ('source_revision_ids', 'inspection_records', 'observations', 'gaps'):
            if not isinstance(value[key], list) or len(value[key]) > 64:
                raise ContractError('Expected bounded list')
        if not value['source_revision_ids'] or any(not isinstance(x, str) for x in value['source_revision_ids']):
            raise ContractError('Invalid revisions')
        return cls(**value)
