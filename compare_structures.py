"""
compare_structures.py
─────────────────────
두 아키텍처 산출물(structure.json 또는 document.json)을 비교합니다.
컴포넌트 추가/제거/변경 + 관계/계층 수 변화를 보여줍니다.

사용법:
    python compare_structures.py 이전.json 이후.json
    예) python compare_structures.py _arch_lab_sample_01_db_style/structure.json _arch_lab/structure_updated.json
"""
import sys
import json
from pathlib import Path


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def comp_map(data):
    out = {}
    for c in data.get("components", []):
        if isinstance(c, dict) and c.get("component_id"):
            out[c["component_id"]] = c
    return out


def main():
    if len(sys.argv) < 3:
        sys.exit("사용법: python compare_structures.py 이전.json 이후.json")
    a_path, b_path = sys.argv[1], sys.argv[2]
    A, B = load(a_path), load(b_path)
    ca, cb = comp_map(A), comp_map(B)

    added = [k for k in cb if k not in ca]
    removed = [k for k in ca if k not in cb]
    changed = [
        k for k in ca
        if k in cb and (
            ca[k].get("description") != cb[k].get("description")
            or ca[k].get("layer") != cb[k].get("layer")
            or ca[k].get("name") != cb[k].get("name")
        )
    ]

    print("=" * 60)
    print(f"A (이전): {a_path}")
    print(f"   컴포넌트 {len(ca)}개, 관계 {len(A.get('relations', []))}개, 계층 {len(A.get('layers', []))}개")
    print(f"B (이후): {b_path}")
    print(f"   컴포넌트 {len(cb)}개, 관계 {len(B.get('relations', []))}개, 계층 {len(B.get('layers', []))}개")
    print("=" * 60)

    print(f"\n[+] 추가된 컴포넌트 ({len(added)}):")
    for k in added:
        print(f"    + {k}  ({cb[k].get('name', '')})")
    if not added:
        print("    없음")

    print(f"\n[-] 제거된 컴포넌트 ({len(removed)}):")
    for k in removed:
        print(f"    - {k}  ({ca[k].get('name', '')})")
    if not removed:
        print("    없음")

    print(f"\n[~] 변경된 컴포넌트 ({len(changed)}):")
    for k in changed:
        print(f"    ~ {k}")
        if ca[k].get("layer") != cb[k].get("layer"):
            print(f"        layer: {ca[k].get('layer')} → {cb[k].get('layer')}")
        if ca[k].get("name") != cb[k].get("name"):
            print(f"        name : {ca[k].get('name')} → {cb[k].get('name')}")
        if ca[k].get("description") != cb[k].get("description"):
            print(f"        desc : {str(ca[k].get('description'))[:45]}…")
            print(f"            →  {str(cb[k].get('description'))[:45]}…")
    if not changed:
        print("    없음")

    print(f"\n관계 수 변화: {len(A.get('relations', []))} → {len(B.get('relations', []))}")


if __name__ == "__main__":
    main()
