"""Replaceable similarity abstraction; MVP uses transparent tag Jaccard."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable


ALIASES = {
    "badminton": "羽毛球",
    "basketball": "篮球",
    "running": "跑步",
    "photography": "摄影",
    "west": "西区",
    "east": "东区",
    "north": "北区",
    "saturday_afternoon": "周六下午",
    "weekend_afternoon": "周末下午",
    "sports_partner": "运动搭子",
    "interest_friend": "兴趣朋友",
    "study_partner": "学习搭子",
}


def normalize_tag(value: str) -> str:
    value = value.strip().lower().replace(" ", "_")
    return ALIASES.get(value, value)


def normalized_set(values: Iterable[str]) -> set[str]:
    result = {normalize_tag(value) for value in values if value and value.strip()}
    if "周末下午" in result:
        result.update({"周六下午", "周日下午"})
    return result


class SimilarityProvider(ABC):
    @abstractmethod
    def similarity(self, left: Iterable[str], right: Iterable[str]) -> float:
        raise NotImplementedError


class JaccardSimilarity(SimilarityProvider):
    def similarity(self, left: Iterable[str], right: Iterable[str]) -> float:
        a, b = normalized_set(left), normalized_set(right)
        if not a and not b:
            return 0.5
        if not a or not b:
            return 0.0
        return len(a & b) / len(a | b)


def availability_similarity(left: Iterable[str], right: Iterable[str]) -> float:
    """Overlap coefficient is friendlier than Jaccard for broad availability profiles."""
    a, b = normalized_set(left), normalized_set(right)
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def containment_similarity(desired: Iterable[str], available: Iterable[str]) -> float:
    """Score explicit requirements by coverage instead of diluting exact tag matches."""
    desired_tags, available_tags = normalized_set(desired), normalized_set(available)
    if not desired_tags:
        return 0.5
    if not available_tags:
        return 0.0
    return len(desired_tags & available_tags) / len(desired_tags)
