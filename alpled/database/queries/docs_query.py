FIND_DOCS_BY_CODE = """
SELECT
    code AS docs_cd,
    code_nm AS docs_nm,
    rmrk_cn
FROM tbl_code
WHERE code = :docs_cd
"""

FIND_ALL_DOCS = """
SELECT
    code AS docs_cd,
    code_nm AS docs_nm,
    rmrk_cn
FROM tbl_code
WHERE code LIKE 'DOC_%'
ORDER BY code
"""
