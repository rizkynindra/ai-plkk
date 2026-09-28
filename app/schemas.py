from __future__ import annotations

from pydantic import BaseModel, Field


class CostLine(BaseModel):
    sequence_no: int
    item_name: str
    quantity: float = 1.0
    tariff: float
    discounted_cost: float
    needs_review: bool = False
    review_reason: str | None = None
    source_page: int | None = None
    evidence: str | None = None
    service_date: str | None = None


class ExtractedTable(BaseModel):
    headers: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)


class DocumentContent(BaseModel):
    filename: str
    media_type: str = ""
    source: str
    pages_text: list[str] = Field(default_factory=list)
    tables: list[ExtractedTable] = Field(default_factory=list)


class ClassificationResult(BaseModel):
    is_claim_invoice: bool
    confidence: float = 0.0
    reason: str = ""
    method: str = "heuristic"


class ConversionPreview(BaseModel):
    filename: str
    source: str
    classification: ClassificationResult
    lines: list[CostLine]
    written_count: int
    review_count: int
    elapsed_seconds: float | None = None


class ConvertBase64Request(BaseModel):
    chId: str
    reqId: str
    docBase64: str


class AgreementSaveRequest(BaseModel):
    group_name: str
    branch_name: str
    city: str = ""
    address: str = ""
    code: str = ""
    aliases: list[str] = Field(default_factory=list)
    effective_date: str = ""
    source_filename: str = "pks.pdf"
    items: list[dict] = Field(default_factory=list)


class AgreementBase64Request(BaseModel):
    chId: str
    reqId: str
    docBase64: str
    filename: str = ""
    group_name: str = ""
    branch_name: str = ""
    city: str = ""
    address: str = ""
    code: str = ""
    aliases: list[str] = Field(default_factory=list)
    effective_date: str = ""


class CompareRequest(BaseModel):
    branch_id: int
    lines: list[CostLine] | None = None
    conversion_id: str | None = None
