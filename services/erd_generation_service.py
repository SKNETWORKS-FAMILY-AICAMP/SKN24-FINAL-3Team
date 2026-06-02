from agents.erd.erd_mapper import (
    build_entity_candidate_json,
    build_requirement_context,
    build_table_structure_json,
    normalize_final_erd_json,
)
from generators.erd.docx_adapter import final_erd_to_template_erd
from generators.erd.mermaid_generator import (
    generate_mermaid_code,
    render_erd_image,
    render_mermaid_by_api,
    render_mermaid_by_cli,
)
from generators.erd.storage import build_erd_output_paths, save_erd_json, save_mermaid_code
from rag.erd_rag_service import build_erd_rag_queries, search_erd_standards


def save_final_erd_files(final_erd_json, mermaid_code, json_path, mmd_path) -> None:
    """Backward-compatible wrapper. Prefer save_erd_json/save_mermaid_code."""
    save_erd_json(final_erd_json, json_path)
    save_mermaid_code(mermaid_code, mmd_path)
