"""Detect contributor-style questions and match commits to a person (self or named)."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from db.models import User


@dataclass
class ContributorIntent:
    """Parsed intent for contributor / ownership questions."""

    self_query: bool = False
    name_needle: Optional[str] = None
    email_needle: Optional[str] = None

    def label_for_prompt(self) -> str:
        if self.self_query:
            return "this developer (the signed-in user)"
        if self.email_needle:
            return self.email_needle
        if self.name_needle:
            return self.name_needle
        return "the contributor"


_SELF_PATTERNS = [
    re.compile(r"\bmy\s+(?:contributions?|work|changes?)\b", re.I),
    re.compile(r"\b(?:what|which)\s+(?:were|was|did|have)\s+my\b", re.I),
    re.compile(
        r"\bwhat\s+did\s+i\s+(?:work\s+on|do|change|contribute|make|add|touch)\b",
        re.I,
    ),
    re.compile(r"\bwhich\s+modules?\s+did\s+i\b", re.I),
    re.compile(r"\bsummarize\s+my\b", re.I),
    re.compile(r"\bcommits?\s+(?:i\s+made|did\s+i)\b", re.I),
    re.compile(r"\bwhere\s+did\s+i\s+contribut", re.I),
    re.compile(r"\bchanges?\s+did\s+i\s+(?:make|do|push)\b", re.I),
]

_NAMED_WORK_ON = re.compile(
    r"\bwhat\s+did\s+([A-Za-z][A-Za-z0-9_.\-\s]{1,60}?)\s+work\s+on\b",
    re.I,
)
_NAMED_BY = re.compile(
    r"\bcontributions?\s+by\s+([^?.!\n]{2,80})\b",
    re.I,
)
_NAMED_WORK_DONE_BY = re.compile(
    r"\b(?:work|changes?|commits?)\s+(?:done|made)\s+by\s+([^?.!\n]{2,80})\b",
    re.I,
)
_NAMED_SUMMARIZE = re.compile(
    r"\bsummar(?:ize|ise)\s+(?:the\s+)?(?:work|contributions?)\s+(?:of|by)\s+([^?.!\n]{2,80})\b",
    re.I,
)
_EMAIL = re.compile(r"[\w.+-]+@[\w.-]+\.\w+")


def _normalize_email(value: str) -> str:
    return (value or "").strip().lower()


def _normalize_name_tokens(value: str) -> List[str]:
    raw = (value or "").strip().lower()
    return [t for t in re.split(r"[\s._-]+", raw) if len(t) > 1]


def _cleanup_name_fragment(value: str) -> str:
    cleaned = (value or "").strip(" .,:\"'")
    # Drop common trailing context so matching focuses on person identity.
    cleaned = re.sub(
        r"\s+(?:in|for|on)\s+(?:this\s+)?(?:repository|repo|project|codebase)\b.*$",
        "",
        cleaned,
        flags=re.I,
    )
    return cleaned.strip()


def parse_contributor_query(query: str) -> Optional[ContributorIntent]:
    """
    Return ContributorIntent if the message is asking about a person's repo work; else None.
    Self-intent wins when both self and named patterns could apply.
    """
    text = (query or "").strip()
    if len(text) < 8:
        return None

    for pat in _SELF_PATTERNS:
        if pat.search(text):
            return ContributorIntent(self_query=True)

    emails = _EMAIL.findall(text)
    if emails and not re.search(r"\bmy\b", text, re.I):
        return ContributorIntent(email_needle=_normalize_email(emails[0]))

    m = _NAMED_WORK_ON.search(text)
    if m:
        name = _cleanup_name_fragment(m.group(1))
        if len(name) >= 2:
            return ContributorIntent(name_needle=name)

    m = _NAMED_BY.search(text)
    if m:
        name = _cleanup_name_fragment(m.group(1))
        if len(name) >= 2:
            return ContributorIntent(name_needle=name)

    m = _NAMED_WORK_DONE_BY.search(text)
    if m:
        name = _cleanup_name_fragment(m.group(1))
        if len(name) >= 2:
            return ContributorIntent(name_needle=name)

    m = _NAMED_SUMMARIZE.search(text)
    if m:
        name = _cleanup_name_fragment(m.group(1))
        if len(name) >= 2:
            return ContributorIntent(name_needle=name)

    return None


def commit_matches_email(commit: Dict, email: str) -> bool:
    want = _normalize_email(email)
    got = _normalize_email(commit.get("author_email") or "")
    return bool(want and got and want == got)


def author_predicate_for_user(user: "User") -> Optional[Callable[[Dict], bool]]:
    if not user or not getattr(user, "email", None):
        return None
    email = _normalize_email(user.email)

    def pred(commit: Dict) -> bool:
        return commit_matches_email(commit, email)

    return pred


def author_predicate_for_needle(email_or_name: str) -> Callable[[Dict], bool]:
    raw = (email_or_name or "").strip()
    if "@" in raw:
        email = _normalize_email(raw)

        def pred_email(c: Dict) -> bool:
            return commit_matches_email(c, email)

        return pred_email

    tokens = _normalize_name_tokens(raw)

    def pred_name(c: Dict) -> bool:
        author = (c.get("author") or "").lower()
        if not author:
            return False
        compact = author.replace(" ", "")
        needle = raw.lower()
        if needle in author or needle in compact:
            return True
        if tokens and all(t in author for t in tokens):
            return True
        return False

    return pred_name


def build_author_predicate(
    intent: ContributorIntent,
    user: Optional["User"],
) -> Optional[Callable[[Dict], bool]]:
    if intent.self_query:
        return author_predicate_for_user(user) if user else None
    if intent.email_needle:
        return author_predicate_for_needle(intent.email_needle)
    if intent.name_needle:
        return author_predicate_for_needle(intent.name_needle)
    return None


def module_touch_summary(results: List[Any], top_modules: int = 12) -> str:
    """Count file touches by top-level path segment for prompt context."""
    counts: Counter[str] = Counter()
    for item in results:
        paths = getattr(item, "files_changed", None) or []
        for path in paths:
            normalized = (path or "").replace("\\", "/").strip()
            if not normalized:
                continue
            top = normalized.split("/", 1)[0] or "(root)"
            counts[top] += 1
    if not counts:
        return ""
    lines = [f"- {name}: {n} file touch(es) in retrieved commits" for name, n in counts.most_common(top_modules)]
    return "Module / directory exposure (from retrieved commits):\n" + "\n".join(lines)
