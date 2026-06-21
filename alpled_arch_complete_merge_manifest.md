# ALPLED ARCH Complete Runtime Overlay (Clean)

CORE를 기준으로 네 백업본의 아키텍처 완성본과 운영 호출 경로 파일까지 포함한 push용 overlay입니다.

## 포함 기준

- 아키텍처 본체/샘플/실행 스크립트는 백업본 완성본 기준 반영
- Mermaid/Reduce/Supervisor/Workflow 연결부는 CORE 기준 안전 병합본 반영
- 사용자가 추가로 필요하다고 지정한 main/api/schema/config/workflow/export/mermaid/docx/database/document_merge/requirements 파일도 overlay에 포함
- 단, 대용량 reference 데이터, old 폴더, data_pipeline 산출물, req_agent output은 제외

## 추가 지정 파일 반영 방식

| 파일 | overlay 버전 | 비고 |
|---|---|---|
| `main.py` | CORE 최신 유지 | 아키텍처 실행 경로 포함용으로 overlay에 명시 포함 |
| `api/generation_router.py` | CORE 최신 유지 | 아키텍처 실행 경로 포함용으로 overlay에 명시 포함 |
| `schemas/request/generation_request.py` | CORE 최신 유지 | 아키텍처 실행 경로 포함용으로 overlay에 명시 포함 |
| `config/constants.py` | CORE 최신 유지 | 아키텍처 실행 경로 포함용으로 overlay에 명시 포함 |
| `workflow/state.py` | CORE 최신 유지 | 아키텍처 실행 경로 포함용으로 overlay에 명시 포함 |
| `workflow/nodes/request_preprocess_node.py` | CORE 최신 유지 | 아키텍처 실행 경로 포함용으로 overlay에 명시 포함 |
| `workflow/nodes/export_node.py` | CORE 최신 유지 | 아키텍처 실행 경로 포함용으로 overlay에 명시 포함 |
| `agents/mermaid_generation/agent.py` | CORE 최신 유지 | 아키텍처 실행 경로 포함용으로 overlay에 명시 포함 |
| `tools/docx/docx_exporter.py` | CORE 최신 유지 | 아키텍처 실행 경로 포함용으로 overlay에 명시 포함 |
| `database/models/docs.py` | CORE 최신 유지 | 아키텍처 실행 경로 포함용으로 overlay에 명시 포함 |
| `database/queries/docs_query.py` | CORE 최신 유지 | 아키텍처 실행 경로 포함용으로 overlay에 명시 포함 |
| `database/repositories/docs_repository.py` | CORE 최신 유지 | 아키텍처 실행 경로 포함용으로 overlay에 명시 포함 |
| `database/repositories/docs_detail_repository.py` | CORE 최신 유지 | 아키텍처 실행 경로 포함용으로 overlay에 명시 포함 |
| `agents/document_merge/agent.py` | CORE 최신 유지 | 아키텍처 실행 경로 포함용으로 overlay에 명시 포함 |
| `requirements.txt` | CORE 최신 유지 | 아키텍처 실행 경로 포함용으로 overlay에 명시 포함 |

## 적용

```bash
git checkout -b arch-complete-runtime-merge
unzip -oq alpled_arch_complete_overlay_clean_for_push.zip -d .
git status
git diff --name-status
```

## 검증

```bash
python -m compileall -q main.py api config schemas workflow supervisor agents database tools run_architecture_agent.py run_architecture_update.py render_arch_docx.py

python run_architecture_agent.py samples/architecture/requirements/requirements.01_ai_sdlc.json \
  --arch-config samples/architecture/infra/infra_spec.01_fastapi_sdlc_db_dict.json \
  --out-dir _arch_complete_runtime_smoke \
  --llm
```
