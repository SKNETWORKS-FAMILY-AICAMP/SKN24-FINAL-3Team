"""
run_architecture_agent.py
─────────────────────────
DB·document_merge 없이 아키텍처 에이전트만 단독 실행하는 테스트 하네스입니다.
운영 로직은 agents/architecture_analysis/agent.py 와 processors/* 에 둡니다.

사용법:
    python run_architecture_agent.py
    python run_architecture_agent.py sample_requirements.json
    python run_architecture_agent.py sample_requirements.json --arch-config data/architecture/infra_spec.json
    python run_architecture_agent.py sample_requirements.json --arch-config data/architecture/infra_spec.json --llm
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


def _stub_search(payload):
    return {
        "success": True,
        "data": {"normalized_results": []},
        "query": payload.get("query"),
        "search_intent": payload.get("search_intent"),
    }


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
            try:
                return {"success": True, "data": json.loads(str(text))}
            except Exception:
                return {"success": False, "data": None, "error": {"message": "parse fail"}}

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
        _register("tools.search.search_router", search=_stub_search)


_install_stubs()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("requirements", nargs="?", default="sample_requirements.json", help="요구사항 JSON 파일")
    parser.add_argument("--arch-config", default=None, help="아키텍처 설정 JSON 파일")
    parser.add_argument("--llm", action="store_true", help="LLM 경로 실행")
    parser.add_argument("--out-dir", default="_arch_lab", help="결과 저장 폴더")
    return parser.parse_args()


def load_json(path: str | Path):
    p = Path(path)
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    return json.loads(p.read_text(encoding="utf-8"))


def resolve_architecture_config(args: argparse.Namespace) -> dict:
    if args.arch_config:
        return load_json(args.arch_config)
    default_path = PROJECT_ROOT / "data" / "architecture" / "infra_spec.json"
    if default_path.exists():
        return json.loads(default_path.read_text(encoding="utf-8"))
    return {}


def build_llm_client(use_llm: bool):
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


def main() -> None:
    args = parse_args()
    raw = load_json(args.requirements)
    requirements = raw["requirements"] if isinstance(raw, dict) and "requirements" in raw else raw
    architecture_config = resolve_architecture_config(args)

    print(f"입력: {Path(args.requirements).name}  요구사항 {len(requirements)}건  | LLM={'ON' if args.llm else 'OFF(폴백)'}")

    from agents.architecture_analysis.agent import ArchitectureAnalysisAgent

    state = {
        "project_sn": 1,
        "docs_cd": "ARCH",
        "udt_yn": "N",
        "status": "RUNNING",
        "etc": {"debug": True, "architecture_config": architecture_config},
        "agent_outputs": {"document_merge_agent": {"integrated_requirement_json_list": requirements}},
    }

    agent = ArchitectureAnalysisAgent(llm_client=build_llm_client(args.llm))
    out = agent.execute(state)

    structure = out.get("architecture_structure_json", {})
    document = out.get("architecture_document_json", {})

    print("\nstatus:", out.get("status"))
    for warning in out.get("warnings", []):
        print("  warn:", warning.get("code"), warning.get("message"))

    print("\n── components ──")
    for component in structure.get("components", []):
        print(f"  {component['component_id']:<22} [{component.get('layer','')}] {component.get('name','')}")

    print("\n── relations ──")
    for relation in structure.get("relations", []):
        print(f"  {relation['source']:>22} → {relation['target']:<22} {relation.get('description','')}")

    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = PROJECT_ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "structure.json").write_text(json.dumps(structure, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "document.json").write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n저장 → {out_dir}/structure.json, document.json")


if __name__ == "__main__":
    main()
