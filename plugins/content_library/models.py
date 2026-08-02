from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ContentItem:
    id: str
    channel: str
    chat_id: str
    platform: str
    url: str
    title: str
    note: str
    summary: str
    tags: list[str]
    captured_at: str
    source: str
    feedback: str
    push_excluded: bool


@dataclass(frozen=True)
class TagPreference:
    channel: str
    chat_id: str
    tag: str
    negative_feedback_count: int
    push_state: str
    updated_at: str


@dataclass(frozen=True)
class SaveResult:
    status: str
    item: ContentItem


@dataclass(frozen=True)
class SearchResult:
    count: int
    items: list[ContentItem] = field(default_factory=list)


@dataclass(frozen=True)
class FeedbackResult:
    item: ContentItem | None = None
    tag_preference: TagPreference | None = None
