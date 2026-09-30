from typing import Literal

from pydantic import BaseModel, Field


class PlannedQuery(BaseModel):
    query: str = Field(min_length=1)
    purpose: Literal["background", "technical", "edge_case", "metrics", "current_state"]


class PlannerOutput(BaseModel):
    queries: list[PlannedQuery] = Field(min_length=3, max_length=5)


class ExtractedClaim(BaseModel):
    claim: str = Field(min_length=1)
    source_indexes: list[int] = Field(min_length=1)
    confidence: Literal["high", "medium", "low"]
    evidence_type: Literal["documentation", "study", "benchmark", "official_statement", "news", "other"]


class ExtractorOutput(BaseModel):
    claims: list[ExtractedClaim]


class AuditOutput(BaseModel):
    status: Literal["COMPLETE", "REFINE"]
    gaps: list[str]
    follow_up_queries: list[str] = Field(max_length=2)

    def model_post_init(self, __context) -> None:
        if self.status == "COMPLETE" and self.follow_up_queries:
            raise ValueError("COMPLETE audits must not include follow-up queries.")
        if self.status == "REFINE" and not 1 <= len(self.follow_up_queries) <= 2:
            raise ValueError("REFINE audits require one or two follow-up queries.")


class VerifiedSource(BaseModel):
    title: str = Field(min_length=1)
    url: str = Field(min_length=1)
    query: str
    search_queries: list[str] = Field(default_factory=list)
    citation_metadata: list[dict] = Field(default_factory=list)
    content: str
