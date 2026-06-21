"""
run_architecture_update.py
──────────────────────────
아키텍처 에이전트의 "수정 모드"(udt_yn="Y")를 단독 테스트합니다.
이전 산출물(structure.json) + 회의록 변경(meeting changes json)을 넣어
컴포넌트가 실제로 추가/수정/삭제되는지 확인합니다.

사용법:
    python run_architecture_update.py
    python run_architecture_update.py sample_meeting_changes.json
    python run_architecture_update.py --prev _arch_lab_sample_01_db_style/structure.json
    python run_architecture_update.py sample_meeting_changes.json --prev _arch_lab_sample_01_db_style/structure.json --llm

전제: 먼저 run_architecture_agent.py 로 이전 structure.json 을 만들어 두어야 합니다.
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
import types
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
if not (PROJECT_ROOT / "agents").exists():
    PROJECT_ROOT = next((p for p in [PROJECT_ROOT, *PROJECT_ROOT.parents] if (p / "agents").exists()), PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))


def _can_import(name: str) -> bool:
    try:
        importlib.import_module(name)
        return True
    except Exception:
        return False


def _ensure_pkg(name: str) -> None:
    if name not in sys.modules and not _can_import(name):
        module = types.ModuleType(name)
        module.__path__ = []
        sys.modules[name] = module


def _register(name: str, **attrs) -> None:
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    sys.modules[name] = module
    if "." in name:
        parent, leaf = name.rsplit(".", 1)
        if parent in sys.modules:
            setattr(sys.modules[parent], leaf, module)


def _install_stubs() -> None:
    if not _can_import("workflow.state"):
        _ensure_pkg("workflow")
        _register("workflow.state", WorkflowState=dict)
    if not _can_import("tools.result"):
        _ensure_pkg("tools")
        _register("tools.result", ToolResult=dict)
    if not _can_import("tools.llm.response_parser"):
        _ensure_pkg("tools")
        _ensure_pkg("tools.llm")

        def parse_json_response(text):
            import re

            if isinstance(text, (dict, list)):
                return {"success": True, "data": text}
            s = str(text or "").strip()
            m = re.search(r"```(?:json)?\s*(.*?)```", s, re.S)
            if m:
                s = m.group(1).strip()
            try:
                return {"success": True, "data": json.loads(s)}
            except Exception:
                pass
            start = s.find("{")
            if start != -1:
                depth = 0
                for i in range(start, len(s)):
                    if s[i] == "{":
                        depth += 1
                    elif s[i] == "}":
                        depth -= 1
                        if depth == 0:
                            try:
                                return {"success": True, "data": json.loads(s[start:i + 1])}
                            except Exception:
                                break
            return {"success": False, "data": None, "error": {"message": "JSON 파싱 실패"}}

        _register("tools.llm.response_parser", parse_json_response=parse_json_response)
    if not _can_import("tools.llm.send_api"):
        _ensure_pkg("tools")
        _ensure_pkg("tools.llm")

        def send_parallel(payloads, client=None, max_workers=4):
            if client is None:
                return {"success": False, "data": [], "error": {"message": "no client"}}
            return {"success": True, "data": [client.chat(p["messages"]) for p in payloads]}

        _register("tools.llm.send_api", send_parallel=send_parallel)
    if not _can_import("tools.llm.llm_client"):
        _ensure_pkg("tools")
        _ensure_pkg("tools.llm")

        class LLMClient:
            def chat(self, messages):
                return {"success": False, "data": "", "error": {"message": "stub"}}

        _register("tools.llm.llm_client", LLMClient=LLMClient)
    if not _can_import("tools.search.search_router"):
        _ensure_pkg("tools")
        _ensure_pkg("tools.search")
        _register("tools.search.search_router",
                  search=lambda p: {"success": True, "data": {"normalized_results": []}})


_install_stubs()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("changes", nargs="?", default="sample_meeting_changes.json", help="회의록 변경 JSON 파일")
    parser.add_argument("--prev", default="_arch_lab/structure.json", help="이전 산출물 structure.json 경로")
    parser.add_argument("--arch-config", default=None, help="아키텍처 설정 JSON 파일")
    parser.add_argument("--llm", action="store_true", help="LLM 으로 관계 재설계 + 영향분석")
    parser.add_argument("--out-dir", default="_arch_lab", help="결과 저장 폴더")
    return parser.parse_args()


def resolve(path):
    p = Path(path)
    return p if p.is_absolute() else PROJECT_ROOT / p


def load_json(path):
    return json.loads(resolve(path).read_text(encoding="utf-8"))


def resolve_architecture_config(args):
    if args.arch_config:
        return load_json(args.arch_config)
    default_path = PROJECT_ROOT / "data" / "architecture" / "infra_spec.json"
    if default_path.exists():
        return json.loads(default_path.read_text(encoding="utf-8"))
    return {}


def build_llm_client(use_llm):
    if not use_llm:
        return None
    import requests
    from config.settings import get_settings

    settings = get_settings()

    class OpenAICompatibleLLMClient:
        def chat(self, messages):
            try:
                response = requests.post(
                    f"{settings.llm_base_url.rstrip('/')}/chat/completions",
                    headers={"Authorization": f"Bearer {settings.llm_api_key or 'dummy'}"},
                    json={
                        "model": settings.llm_model_name,
                        "messages": messages,
                        "temperature": settings.llm_temperature,
                        "max_tokens": settings.llm_max_tokens,
                    },
                    timeout=settings.llm_timeout,
                )
                response.raise_for_status()
                return {"success": True, "data": response.json()["choices"][0]["message"]["content"], "error": None}
            except Exception as exc:
                return {"success": False, "data": "", "error": {"message": str(exc)}}

    return OpenAICompatibleLLMClient()


def main():
    args = parse_args()

    prev_path = resolve(args.prev)
    changes_path = resolve(args.changes)
    if not prev_path.exists():
        sys.exit(f"이전 산출물이 없습니다: {prev_path}\n먼저 run_architecture_agent.py 를 실행하세요.")
    if not changes_path.exists():
        sys.exit(f"회의록 변경 파일이 없습니다: {changes_path}")

    existing_structure = json.loads(prev_path.read_text(encoding="utf-8"))
    changes = json.loads(changes_path.read_text(encoding="utf-8"))
    if isinstance(changes, dict) and "meeting_change_items" in changes:
        changes = changes["meeting_change_items"]
    architecture_config = resolve_architecture_config(args)

    before_ids = [c.get("component_id") for c in existing_structure.get("components", []) if isinstance(c, dict)]

    print(f"이전 산출물: {prev_path}")
    print(f"회의록 변경: {changes_path.name}  |  LLM={'ON' if args.llm else 'OFF'}")

    from agents.architecture_analysis.agent import ArchitectureAnalysisAgent

    state = {
        "project_sn": 1,
        "docs_cd": "ARCH",
        "udt_yn": "Y",
        "status": "RUNNING",
        "etc": {"debug": True, "architecture_config": architecture_config},
        "agent_outputs": {
            "document_merge_agent": {
                "existing_output_raw_json": existing_structure,
                "meeting_change_items": changes,
            }
        },
    }

    out = ArchitectureAnalysisAgent(llm_client=build_llm_client(args.llm)).execute(state)
    structure = out.get("architecture_structure_json", {})
    document = out.get("architecture_document_json", {})
    after_ids = [c.get("component_id") for c in structure.get("components", []) if isinstance(c, dict)]

    print("\nstatus:", out.get("status"))
    for w in out.get("warnings", []):
        print("  warn:", w.get("code"), w.get("message"))

    print("\n── 적용한 회의록 변경 ──")
    for ch in changes:
        item = ch.get("item", ch) if isinstance(ch, dict) else {}
        print(f"  {str(ch.get('change_type', '')):<8} {item.get('component_name') or item.get('component_id')}")

    print("\n── 컴포넌트 변화 ──")
    print("  이전 수:", len(before_ids), "→ 이후 수:", len(after_ids))
    print("  추가됨:", [x for x in after_ids if x not in before_ids] or "없음")
    print("  제거됨:", [x for x in before_ids if x not in after_ids] or "없음")

    out_dir = resolve(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "structure_updated.json").write_text(json.dumps(structure, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "document_updated.json").write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n저장 → {out_dir}/structure_updated.json, document_updated.json")
    print(f"비교: python compare_structures.py \"{prev_path}\" \"{out_dir / 'structure_updated.json'}\"")


if __name__ == "__main__":
    main()
