from django.conf import settings
from django.db import models

from common.models import (
    CreatedAtMixin,
    CreatedByMixin,
    SoftDeleteMixin,
    UpdatedAtMixin,
    UpdatedByMixin,
)


class Document(CreatedAtMixin, CreatedByMixin, UpdatedAtMixin, UpdatedByMixin):
    sn = models.AutoField(primary_key=True, db_column="docs_sn")
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.PROTECT,
        db_column="prj_sn",
        related_name="documents",
        db_constraint=False,
    )
    possession_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        db_column="pssn_user_sn",
        related_name="occupied_documents",
        db_constraint=False,
        null=True,
        blank=True,
    )
    document_type = models.ForeignKey(
        "common.Code",
        to_field="code",
        on_delete=models.PROTECT,
        db_column="docs_cd",
        related_name="documents",
        db_constraint=False,
    )
    progress_status = models.ForeignKey(
        "common.Code",
        to_field="code",
        on_delete=models.PROTECT,
        db_column="docs_prgrs_stts_cd",
        related_name="documents_by_progress",
        db_constraint=False,
        default="PRGRS_PENDING",
    )
    version = models.CharField(max_length=20, db_column="docs_ver")
    modification_content = models.CharField(max_length=100, db_column="mdfcn_cn")

    class Meta:
        db_table = "tbl_docs"
        verbose_name = "document"
        verbose_name_plural = "documents"

    def __str__(self) -> str:
        return f"{self.project} - {self.document_type} v{self.version}"


class DocumentDetail(CreatedAtMixin, CreatedByMixin, SoftDeleteMixin):
    sn = models.AutoField(primary_key=True, db_column="docs_dtl_sn")
    document = models.ForeignKey(
        Document,
        on_delete=models.PROTECT,
        db_column="docs_sn",
        related_name="details",
        db_constraint=False,
    )
    detail_content = models.BinaryField(db_column="docs_dtl_cn", null=True, blank=True)
    path = models.CharField(max_length=300, db_column="docs_path")

    class Meta:
        db_table = "tbl_docs_detail"
        verbose_name = "document detail"
        verbose_name_plural = "document details"

    def __str__(self) -> str:
        return f"{self.document} detail {self.sn}"


class DocumentApproval(CreatedAtMixin, CreatedByMixin, UpdatedAtMixin, UpdatedByMixin):
    approval_sn = models.AutoField(primary_key=True, db_column="docs_aprv_sn")
    detail = models.ForeignKey(
        DocumentDetail,
        on_delete=models.PROTECT,
        db_column="docs_dtl_sn",
        related_name="approvals",
        db_constraint=False,
    )
    approval_status = models.ForeignKey(
        "common.Code",
        to_field="code",
        on_delete=models.PROTECT,
        db_column="aprv_stts_cd",
        related_name="document_approvals",
        db_constraint=False,
    )
    request_content = models.CharField(max_length=100, db_column="dmnd_cn")
    rejection_reason = models.CharField(
        max_length=100,
        db_column="rjct_rsn",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "tbl_docs_approve"
        verbose_name = "document approval"
        verbose_name_plural = "document approvals"

    def __str__(self) -> str:
        return f"{self.detail} / {self.approval_status}"

    @property
    def sn(self):
        return self.approval_sn
