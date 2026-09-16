from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator


class PublicationStatus(StrEnum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    withdrawn = "withdrawn"


class PublicationReviewCheck(StrEnum):
    pattern_content = "pattern_content"
    metadata = "metadata"
    rights_privacy = "rights_privacy"


REQUIRED_PUBLICATION_REVIEW_CHECKS = frozenset(PublicationReviewCheck)


class PublicationCreateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=50)
    tags: list[str] = Field(default_factory=list, max_length=8)
    finished_image_id: str | None = Field(default=None, min_length=4, max_length=80)

    @field_validator("title", "description")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        tags: list[str] = []
        for tag in value:
            normalized = tag.strip()
            if normalized and normalized not in tags:
                tags.append(normalized[:24])
        return tags


class PublicationReviewRequest(BaseModel):
    decision: PublicationStatus
    note: str | None = Field(default=None, max_length=2_000)
    checks: list[PublicationReviewCheck] = Field(default_factory=list, max_length=3)

    @field_validator("decision")
    @classmethod
    def review_decision_only(cls, value: PublicationStatus) -> PublicationStatus:
        if value not in (PublicationStatus.approved, PublicationStatus.rejected):
            raise ValueError("审核结果只能为通过或驳回")
        return value

    @field_validator("note")
    @classmethod
    def strip_optional_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("checks")
    @classmethod
    def unique_checks(cls, value: list[PublicationReviewCheck]) -> list[PublicationReviewCheck]:
        if len(value) != len(set(value)):
            raise ValueError("合规检查项不能重复")
        return value

    @model_validator(mode="after")
    def rejection_requires_note(self) -> PublicationReviewRequest:
        if self.decision == PublicationStatus.rejected and not self.note:
            raise ValueError("驳回作品时必须填写原因")
        if self.decision == PublicationStatus.approved and set(self.checks) != REQUIRED_PUBLICATION_REVIEW_CHECKS:
            raise ValueError("通过作品前必须完成全部合规检查")
        return self
