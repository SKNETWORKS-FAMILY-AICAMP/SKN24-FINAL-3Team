# 아키텍처 구조와 문서 JSON을 생성합니다.

from collections import defaultdict
from typing import Any


def build_layers(components: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for component in components:
        grouped[str(component.get("layer") or "Application Layer")].append(component["component_id"])
    preferred = [
        "Presentation Layer",
        "Application Layer",
        "Agent Orchestration Layer",
        "AI/LLM Layer",
        "Data Layer",
        "External Integration Layer",
    ]
    layer_names = [name for name in preferred if name in grouped] + [
        name for name in grouped if name not in preferred
    ]
    return [
        {
            "layer_id": f"LAYER-{index + 1:03d}",
            "name": name,
            "component_ids": grouped[name],
        }
        for index, name in enumerate(layer_names)
    ]


def build_deployment_environment(architecture_config: dict[str, Any]) -> dict[str, Any]:
    return {
        "environment": architecture_config.get("deployment_environment")
        or architecture_config.get("environment")
        or "운영/검증 분리 환경",
        "web_was": architecture_config.get("web_was") or architecture_config.get("server 구성") or "WEB/WAS 분리 또는 논리 분리",
        "dbms": architecture_config.get("dbms") or architecture_config.get("DBMS") or "RDBMS",
        "storage": architecture_config.get("file_storage") or architecture_config.get("storage") or "S3 또는 파일 저장소",
        "vector_db": architecture_config.get("vector_db") or "Qdrant",
        "llm_server": architecture_config.get("llm_server") or "LLM Inference Server",
    }


def build_architecture_structure(
    *,
    components: list[dict[str, Any]],
    relations: list[dict[str, Any]],
    layers: list[dict[str, Any]],
    deployment_environment: dict[str, Any],
    drivers: list[dict[str, Any]],
    architecture_config: dict[str, Any],
) -> dict[str, Any]:
    return {
        "overview": "요구사항, 비기능 요구사항, 아키텍처 설정을 기반으로 구성한 ALPLED 아키텍처 구조입니다.",
        "components": components,
        "relations": relations,
        "edges": relations,
        "layers": layers,
        "subgraphs": layers,
        "deployment_environment": deployment_environment,
        "drivers": drivers,
        "security": "인증, 권한, 데이터 보호, 접근 제어를 반영합니다.",
        "performance": "응답시간, 병렬 처리, 확장성을 고려합니다.",
        "operation": "로그, 모니터링, 백업, 장애 대응을 고려합니다.",
        "integration": "외부 시스템 및 API 연계 구조를 고려합니다.",
        "deployment": "서버 구성과 배포 환경을 고려합니다.",
        "architecture_config": architecture_config,
        "architecture_config_reflected": bool(architecture_config),
    }


def build_architecture_document(
    *,
    structure: dict[str, Any],
    rag_results: list[dict[str, Any]],
    meeting_change_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "overview": structure["overview"],
        "components": [
            {
                "component_id": component["component_id"],
                "name": component["name"],
                "layer": component.get("layer"),
                "description": component.get("description"),
            }
            for component in structure.get("components", [])
        ],
        "relations": structure.get("relations", []),
        "layers": structure.get("layers", []),
        "deployment_environment": structure.get("deployment_environment", {}),
        "design_drivers": structure.get("drivers", []),
        "security_considerations": structure.get("security"),
        "performance_considerations": structure.get("performance"),
        "operation_considerations": structure.get("operation"),
        "integration_considerations": structure.get("integration"),
        "deployment_considerations": structure.get("deployment"),
        "rag_references": rag_results,
        "meeting_change_items": meeting_change_items or [],
        "architecture_config": structure.get("architecture_config", {}),
        "architecture_config_reflected": structure.get("architecture_config_reflected", False),
    }


def extract_existing_structure(existing: dict[str, Any]) -> dict[str, Any]:
    if isinstance(existing.get("architecture_structure_json"), dict):
        return existing["architecture_structure_json"]
    return existing
