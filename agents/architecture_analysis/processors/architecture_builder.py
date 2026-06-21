# 아키텍처 구조와 문서 JSON을 생성합니다.

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from agents.architecture_analysis.processors.diagram_builder import build_clean_architecture_mermaid_source


LAYER_ORDER = [
    "External Actor",
    "Presentation Layer",
    "Application Layer",
    "Agent Orchestration Layer",
    "AI/LLM Layer",
    "Data Layer",
    "External Integration Layer",
    "Operation Layer",
]


def build_layers(components: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for component in components:
        if not isinstance(component, dict) or not component.get("component_id"):
            continue
        grouped[str(component.get("layer") or "Application Layer")].append(component["component_id"])
    layer_names = [name for name in LAYER_ORDER if name in grouped] + [
        name for name in grouped if name not in LAYER_ORDER
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
        or _cloud_environment(architecture_config)
        or "운영/검증 분리 환경",
        "network": architecture_config.get("network_name") or architecture_config.get("prj_net_nm") or "대상 업무망",
        "network_purpose": architecture_config.get("network_purpose") or architecture_config.get("network_description") or architecture_config.get("prj_net_prps") or "",
        "middleware_stack": architecture_config.get("middleware_stack") or architecture_config.get("mid_stack") or "",
        "web_was": architecture_config.get("web_was") or architecture_config.get("server 구성") or _infer_web_was(architecture_config) or "WEB/WAS 논리 분리",
        "dbms": architecture_config.get("dbms") or architecture_config.get("DBMS") or _infer_dbms(architecture_config) or "RDBMS",
        "storage": architecture_config.get("file_storage") or architecture_config.get("storage") or _infer_storage(architecture_config) or "파일 저장소",
        "auth_method": architecture_config.get("auth_method") or "",
        "firewall_setting": architecture_config.get("firewall_setting") or architecture_config.get("fwl_settings") or "",
        "hardware_spec": architecture_config.get("hardware_spec") or architecture_config.get("server_hardware_spec") or architecture_config.get("hard_spec") or "",
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
    structure = {
        "overview": "요구사항, 비기능 요구사항, 사용자 아키텍처 설정을 기반으로 구성한 시스템 아키텍처 구조입니다.",
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
    structure["architecture_description"] = build_architecture_description(structure)
    structure["architecture_mermaid"] = build_clean_architecture_mermaid_source(structure)
    return structure


def build_architecture_document(
    *,
    structure: dict[str, Any],
    rag_results: list[dict[str, Any]],
    meeting_change_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    requirement_implementations = build_requirement_implementations(
        structure=structure,
        rag_results=rag_results,
    )
    return {
        "overview": structure["overview"],
        "architecture_description": structure.get("architecture_description") or build_architecture_description(structure),
        "architecture_mermaid": structure.get("architecture_mermaid") or build_clean_architecture_mermaid_source(structure),
        "requirement_implementations": requirement_implementations,
        "components": [
            {
                "component_id": component["component_id"],
                "name": component["name"],
                "layer": component.get("layer"),
                "description": component.get("description"),
            }
            for component in structure.get("components", [])
            if isinstance(component, dict) and component.get("component_id")
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


def build_architecture_description(structure: dict[str, Any]) -> str:
    config = structure.get("architecture_config") or {}
    components = [c for c in structure.get("components") or [] if isinstance(c, dict)]
    relations = [r for r in structure.get("relations") or [] if isinstance(r, dict)]

    network_name = _first(config.get("network_name"), config.get("prj_net_nm"), "대상 시스템")
    network_purpose = _first(config.get("network_purpose"), config.get("network_description"), config.get("prj_net_prps"))
    middleware = _first(config.get("middleware_stack"), config.get("mid_stack"))
    firewall = _first(config.get("firewall_setting"), config.get("fwl_settings"))
    auth = _first(config.get("auth_method"))
    hardware = _first(config.get("hardware_spec"), config.get("server_hardware_spec"), config.get("hard_spec"))
    expected = _first(config.get("expected_user_count"), config.get("expected_ccu"), config.get("expected_smtn"))

    sentences: list[str] = []
    if network_purpose:
        sentences.append(f"{network_name}은 {network_purpose}로 구성한다.")
    else:
        sentences.append(f"{network_name}은 요구사항 기반 업무 처리와 산출물 생성을 지원하도록 구성한다.")
    if middleware:
        sentences.append(f"주요 기술 스택은 {middleware}을 기준으로 한다.")
    if firewall:
        sentences.append(f"통신 및 접근 제어는 {firewall}을 적용한다.")
    if auth:
        sentences.append(f"인증 방식은 {auth}을 적용한다.")
    if expected:
        sentences.append(f"예상 사용자 또는 처리 규모는 {expected}을 기준으로 설계한다.")
    if hardware:
        sentences.append(f"인프라 사양은 {hardware}을 기준으로 한다.")
    if components:
        names = ", ".join(_component_name(c) for c in components[:8])
        sentences.append(f"주요 구성요소는 {names}로 구성된다.")
    if relations:
        sentences.append("구성요소 간 연결은 사용자 요청, 업무 처리, 산출물 생성, 데이터 저장, 외부 연계 흐름을 기준으로 정의한다.")
    return " ".join(sentence for sentence in sentences if sentence)


def build_architecture_mermaid(structure: dict[str, Any]) -> str:
    existing_mermaid = structure.get("architecture_mermaid")
    if isinstance(existing_mermaid, str) and existing_mermaid.strip():
        return existing_mermaid

    return build_clean_architecture_mermaid_source(
        structure,
        direction="LR",
        edge_label_mode="none",
        max_edges=16,
    )


def build_requirement_implementations(
    *,
    structure: dict[str, Any],
    rag_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    drivers = structure.get("drivers") or []
    components = structure.get("components") or []
    relations = structure.get("relations") or []
    deployment_environment = structure.get("deployment_environment") or {}
    architecture_config = structure.get("architecture_config") or {}
    references_by_category = _group_rag_references_by_category(rag_results)

    items: list[dict[str, Any]] = []
    for index, driver in enumerate(drivers, start=1):
        if not isinstance(driver, dict):
            continue
        category = str(driver.get("category") or f"driver-{index}")
        references = _dedupe_references(references_by_category.get(category, []))
        target_components = _components_for_driver(category, components)
        content = _architecture_requirement_content(driver, references)
        implementation = _architecture_implementation_content(
            category=category,
            driver=driver,
            components=target_components,
            relations=relations,
            deployment_environment=deployment_environment,
            architecture_config=architecture_config,
            references=references,
        )
        items.append(
            {
                "requirement_id": "",
                "category": category,
                "requirement_name": str(driver.get("name") or category),
                "description": content,
                "implementation": implementation,
                "source_requirement_ids": _reference_ids(references),
            }
        )
    return items


def _architecture_requirement_content(
    driver: dict[str, Any],
    references: list[dict[str, Any]],
) -> str:
    name = str(driver.get("name") or "아키텍처 요구사항")
    reference_summary = _reference_summary(references)
    if reference_summary:
        return f"{name} 확보를 위해 {reference_summary}을 설계 기준으로 반영해야 함"
    description = str(driver.get("description") or "").strip()
    if description:
        return _sentence_to_requirement(description)
    return f"{name}을 시스템 아키텍처 설계 기준으로 반영해야 함"


def _architecture_implementation_content(
    *,
    category: str,
    driver: dict[str, Any],
    components: list[dict[str, Any]],
    relations: list[dict[str, Any]],
    deployment_environment: dict[str, Any],
    architecture_config: dict[str, Any],
    references: list[dict[str, Any]],
) -> str:
    component_names = [
        _component_name(component)
        for component in components
        if isinstance(component, dict)
    ]
    target_text = ", ".join(component_names[:5]) if component_names else "관련 구성요소"
    relation_text = _relation_summary(relations, components)
    environment_text = _deployment_summary(deployment_environment, architecture_config)
    reference_text = _reference_summary(references)

    category_guides = {
        "security": "인증/인가, 접근 제어, 전송/저장 데이터 암호화, 감사 로그를 서비스 경계와 데이터 계층 경계에 적용하고 망 설정에 따라 외부 연계 구간을 분리",
        "performance": "동시 요청과 처리량을 고려해 주요 업무 서비스와 작업 처리 컴포넌트를 독립 확장 가능하게 구성하고 저장소/외부 호출 timeout과 재시도 기준을 분리",
        "quality": "장애 격리, 오류 응답 표준화, 재처리 가능한 workflow 상태 관리를 통해 서비스 품질과 신뢰성을 확보",
        "operation": "요청 추적 ID, 실행 로그, 산출물 상태, 외부 연동 실패 내역을 수집하고 백업/복구 기준을 운영 절차에 반영",
        "integration": "외부 시스템 연계는 업무 서비스 경유로 표준화하고 인증, 오류 처리, 응답 timeout, 재시도 정책을 인터페이스별로 분리",
        "deployment": "WEB/WAS, 업무 서비스, 작업 처리, 데이터 저장소, 파일 저장소를 역할별 계층으로 분리하고 운영/검증 환경 및 망 설정에 맞춰 배포 단위를 분리",
        "data": "DB, 파일 저장소, Vector DB 등 저장소별 저장 대상과 보관 기준을 분리하고 개인정보/첨부파일/임베딩 데이터에 대한 접근 제어와 백업 정책을 적용",
    }
    guide = category_guides.get(category, str(driver.get("description") or "설계 기준에 맞춰 구성요소와 연계 구조를 구체화"))

    sentences = [f"{target_text}를 중심으로 {guide}합니다."]
    config_hint = _config_design_hint(architecture_config)
    if config_hint:
        sentences.append(config_hint)
    if relation_text:
        sentences.append(f"주요 연계 흐름은 {relation_text} 기준으로 정의합니다.")
    if environment_text:
        sentences.append(f"배포 환경은 {environment_text} 기준을 적용합니다.")
    if reference_text:
        sentences.append(f"RAG로 확인한 비기능 근거인 {reference_text}을 상세 설계 검토 기준으로 사용합니다.")
    return " ".join(sentences)


def _group_rag_references_by_category(
    rag_results: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for group in rag_results:
        if not isinstance(group, dict):
            continue
        category = _category_from_text(str(group.get("search_intent") or group.get("query") or ""))
        for item in group.get("normalized_results") or []:
            if isinstance(item, dict):
                grouped[category].append(item)
    return grouped


def _category_from_text(text: str) -> str:
    lowered = text.lower()
    mapping = {
        "security": ("security", "보안", "인증", "암호화", "접근"),
        "performance": ("performance", "성능", "응답", "처리량", "확장"),
        "quality": ("quality", "품질", "가용성", "안정성", "유지보수"),
        "operation": ("operation", "운영", "모니터링", "로그", "백업", "복구"),
        "integration": ("integration", "연계", "인터페이스", "api", "외부"),
        "deployment": ("deployment", "배포", "서버", "클라우드", "네트워크", "망"),
        "data": ("data", "데이터", "보관", "개인정보", "파일", "저장소"),
    }
    for category, needles in mapping.items():
        if any(needle in lowered for needle in needles):
            return category
    return "general"


def _components_for_driver(
    category: str,
    components: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    matched = [
        component
        for component in components
        if isinstance(component, dict)
        and (
            category in component.get("driver_categories", [])
            or category in str(component).lower()
            or _component_matches_category(component, category)
        )
    ]
    return matched or [component for component in components if isinstance(component, dict)]


def _component_matches_category(component: dict[str, Any], category: str) -> bool:
    text = f"{component.get('component_id', '')} {component.get('name', '')} {component.get('description', '')}".lower()
    aliases = {
        "security": ["auth", "인증", "권한", "security", "보안"],
        "performance": ["cache", "redis", "queue", "성능", "처리량"],
        "operation": ["monitor", "log", "backup", "운영", "로그", "백업"],
        "integration": ["external", "interface", "연계", "외부", "sso", "erp"],
        "deployment": ["server", "gateway", "서버", "망", "배포"],
        "data": ["db", "storage", "store", "데이터", "저장", "파일"],
    }
    return any(alias in text for alias in aliases.get(category, []))


def _relation_summary(
    relations: list[dict[str, Any]],
    components: list[dict[str, Any]],
) -> str:
    component_ids = {
        str(component.get("component_id"))
        for component in components
        if isinstance(component, dict) and component.get("component_id")
    }
    selected = []
    for relation in relations:
        if not isinstance(relation, dict):
            continue
        source = str(relation.get("source") or relation.get("from") or "")
        target = str(relation.get("target") or relation.get("to") or "")
        if component_ids and source not in component_ids and target not in component_ids:
            continue
        label = str(relation.get("description") or relation.get("label") or "연계")
        selected.append(f"{source} -> {target}({label})")
        if len(selected) >= 4:
            break
    return ", ".join(item for item in selected if item)


def _deployment_summary(
    deployment_environment: dict[str, Any],
    architecture_config: dict[str, Any],
) -> str:
    values = [
        deployment_environment.get("environment"),
        deployment_environment.get("network"),
        deployment_environment.get("middleware_stack"),
        deployment_environment.get("web_was"),
        deployment_environment.get("dbms"),
        deployment_environment.get("storage"),
        deployment_environment.get("hardware_spec"),
    ]
    networks = architecture_config.get("networks")
    if isinstance(networks, list) and networks:
        network_names = [
            str(item.get("prj_net_nm") or item.get("network_name") or "")
            for item in networks
            if isinstance(item, dict)
        ]
        if any(network_names):
            values.append("망 구성: " + ", ".join(name for name in network_names if name))
    return ", ".join(str(value) for value in values if value)


def _reference_summary(references: list[dict[str, Any]]) -> str:
    texts = []
    for item in _dedupe_references(references)[:3]:
        content = str(item.get("content") or item.get("title") or "").strip()
        if content:
            texts.append(_shorten(content, 90))
    return ", ".join(texts)


def _reference_ids(references: list[dict[str, Any]]) -> list[str]:
    ids: list[str] = []
    for item in references:
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        value = (
            item.get("requirement_id")
            or item.get("req_id")
            or metadata.get("requirement_id")
            or metadata.get("req_id")
        )
        if value and str(value) not in ids:
            ids.append(str(value))
    return ids


def _dedupe_references(references: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in references:
        if not isinstance(item, dict):
            continue
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        key = str(item.get("requirement_id") or metadata.get("requirement_id") or item.get("content") or item.get("title") or item)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _sentence_to_requirement(text: str) -> str:
    normalized = text.strip().rstrip(".")
    normalized = normalized.replace("합니다", "해야 함")
    normalized = normalized.replace("반영합니다", "반영해야 함")
    normalized = normalized.replace("고려합니다", "고려해야 함")
    if normalized.endswith("해야 함"):
        return normalized
    return f"{normalized}해야 함"


def _config_design_hint(config: dict[str, Any]) -> str:
    parts = []
    if config.get("firewall_setting"):
        parts.append(f"망/방화벽 정책은 {config.get('firewall_setting')}을 반영합니다")
    if config.get("auth_method"):
        parts.append(f"인증은 {config.get('auth_method')} 기준으로 적용합니다")
    if config.get("middleware_stack"):
        parts.append(f"기술 스택은 {config.get('middleware_stack')}을 기준으로 매핑합니다")
    if not parts:
        return ""
    return ". ".join(parts) + "."


def _cloud_environment(config: dict[str, Any]) -> str:
    value = config.get("is_cloud")
    if value is True:
        return "클라우드 기반 운영/검증 환경"
    if value is False:
        return "내부망 또는 온프레미스 운영/검증 환경"
    return ""


def _infer_web_was(config: dict[str, Any]) -> str:
    text = str(config).lower()
    if "fastapi" in text:
        return "FastAPI API Server"
    if "tomcat" in text:
        return "Tomcat WAS"
    if "spring" in text:
        return "Spring Boot WAS"
    return ""


def _infer_dbms(config: dict[str, Any]) -> str:
    text = str(config).lower()
    for name in ["mysql", "oracle", "postgresql", "mariadb", "sql server"]:
        if name in text:
            return name.upper() if name != "mysql" else "MySQL"
    return ""


def _infer_storage(config: dict[str, Any]) -> str:
    text = str(config).lower()
    if "s3" in text:
        return "S3 Bucket"
    if "nas" in text:
        return "NAS"
    if "object storage" in text:
        return "Object Storage"
    return ""


def _first(*values: Any) -> str:
    for value in values:
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _component_name(component: dict[str, Any]) -> str:
    return _first(component.get("name"), component.get("component_name"), component.get("component_id"), "컴포넌트")


def _shorten(text: Any, max_length: int) -> str:
    normalized = " ".join(str(text or "").split())
    return normalized if len(normalized) <= max_length else normalized[:max_length].rstrip() + "..."


def _safe_mermaid_id(value: Any) -> str:
    normalized = re.sub(r"[^0-9A-Za-z_]+", "_", str(value or "NODE").upper()).strip("_")
    if not normalized:
        normalized = "NODE"
    if normalized[0].isdigit():
        normalized = "N_" + normalized
    return normalized


def _escape_mermaid(text: Any) -> str:
    return str(text or "").replace('"', "'").replace("|", "/").replace("\n", " ")
