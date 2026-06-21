# Architecture Agent 최종 패치 + 샘플 실행 세트

이 폴더는 아키텍처 에이전트 고도화 검증용 샘플입니다.
운영에서는 `run_architecture_agent.py`가 아니라 멀티에이전트가 `ArchitectureAnalysisAgent.execute(state)`를 직접 호출합니다.
이 샘플은 단독 테스트용입니다.

## 포함 샘플 5종

| 번호 | 요구사항 | infra spec | 주요 기술/구성요소 |
|---|---|---|---|
| 01 | AI SDLC 산출물 생성 | `infra_spec.01_fastapi_sdlc.json` | React, Nginx, FastAPI, LangGraph, MySQL, Qdrant, Redis, S3 |
| 02 | 대민 포털 | `infra_spec.02_spring_public_portal.json` | Vue, Apache, Spring Boot, Oracle, Redis, Keycloak, Kafka, NAS |
| 03 | 데이터 수집·분석 플랫폼 | `infra_spec.03_node_data_platform.json` | Node.js, Express, PostgreSQL, MinIO, Kafka, Elasticsearch |
| 04 | 학습관리시스템 | `infra_spec.04_django_lms.json` | Next.js, Django, Celery, RabbitMQ, MariaDB, OpenSearch, OpenAI, Milvus |
| 05 | 금융 내부 업무망 | `infra_spec.05_egov_finance_internal.json` | eGovFrame, JEUS, Tibero, ActiveMQ, NAS, Keycloak, ELK |

## 실행

프로젝트 루트에서 실행합니다.

### Windows

```bat
samples\architecture\scripts\run_architecture_samples.bat
```

### Linux/Mac

```bash
chmod +x samples/architecture/scripts/run_architecture_samples.sh
bash samples/architecture/scripts/run_architecture_samples.sh
```

## 개별 실행 예시

```bash
python run_architecture_agent.py samples/architecture/requirements/requirements.01_ai_sdlc.json \
  --arch-config samples/architecture/infra/infra_spec.01_fastapi_sdlc.json \
  --out-dir _arch_lab_sample_01

python render_arch_docx.py _arch_lab_sample_01/document.json \
  --structure _arch_lab_sample_01/structure.json \
  --template templates/arch_template.docx \
  --out _arch_lab_sample_01/architecture.docx
```

## 확인 포인트

`structure.json`의 `components[].name`에 infra spec의 실제 기술명이 살아 있어야 합니다.
예: `FastAPI API 서버`, `LangGraph Workflow/작업 처리 서버`, `MySQL RDS`, `S3 오브젝트/파일 저장소`.

`components`에 명시된 시스템 구성요소는 최우선 반영하고, `mid_stack`이나 `hard_spec`에 추가로 드러난 DB, 저장소, 큐, 검색, AI, 모니터링 구성요소도 병합합니다.
언어와 ORM 같은 보조 기술은 별도 노드가 아니라 관련 컴포넌트 설명에 반영합니다.
