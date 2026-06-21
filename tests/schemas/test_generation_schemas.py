import unittest

from pydantic import ValidationError

from config.constants import normalize_docs_cd
from schemas.request.generation_request import GenerationRequest
from schemas.response.generation_response import GenerationResponse


class GenerationSchemasTest(unittest.TestCase):
    def test_generation_request_accepts_documented_input(self) -> None:
        request = GenerationRequest(
            project_sn=1,
            docs_cd="ERD",
            udt_yn="N",
            file_list=[10, 11],
            image_list=["12"],
            etc={"architecture_config": {}, "custom_options": {}},
        )

        self.assertEqual(request.project_sn, 1)
        self.assertEqual(request.file_list, [10, 11])
        self.assertEqual(request.image_list, ["12"])

    def test_generation_request_accepts_all_documented_doc_codes(self) -> None:
        cases = {
            "DOC_SRS": "SRS",
            "DOC_ITF": "INTERFACE",
            "DOC_ARCH": "ARCH",
            "DOC_ERD": "ERD",
            "DOC_DB": "DB",
            "DOC_TS": "TS",
        }

        for raw_docs_cd, normalized_docs_cd in cases.items():
            with self.subTest(raw_docs_cd=raw_docs_cd):
                request = GenerationRequest(
                    project_sn=1,
                    docs_cd=raw_docs_cd,
                    udt_yn="N",
                )

                self.assertEqual(request.docs_cd, normalized_docs_cd)

    def test_normalize_docs_cd_accepts_all_documented_doc_codes(self) -> None:
        cases = {
            "DOC_SRS": "SRS",
            "DOC_ITF": "INTERFACE",
            "DOC_ARCH": "ARCH",
            "DOC_ERD": "ERD",
            "DOC_DB": "DB",
            "DOC_TS": "TS",
        }

        for raw_docs_cd, normalized_docs_cd in cases.items():
            with self.subTest(raw_docs_cd=raw_docs_cd):
                self.assertEqual(normalize_docs_cd(raw_docs_cd), normalized_docs_cd)

    def test_generation_request_rejects_invalid_codes(self) -> None:
        with self.assertRaises(ValidationError):
            GenerationRequest(project_sn=1, docs_cd="INVALID", udt_yn="N")

        with self.assertRaises(ValidationError):
            GenerationRequest(project_sn=1, docs_cd="SRS", udt_yn="INVALID")

    def test_generation_request_rejects_non_integer_file_sn(self) -> None:
        with self.assertRaises(ValidationError):
            GenerationRequest(
                project_sn=1,
                docs_cd="SRS",
                udt_yn="N",
                file_list=["file_sn_1"],
            )

    def test_generation_response_validates_docs_cd(self) -> None:
        response = GenerationResponse(project_sn=1, docs_cd="ARCH", status="READY")

        self.assertEqual(response.docs_cd, "ARCH")


if __name__ == "__main__":
    unittest.main()
