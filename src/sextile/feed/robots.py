"""robots.txt, read the way RFC 9309 says.

Python's `urllib.robotparser` returns the first matching rule, which reads
Stardot's file backwards: the `Allow: /` near the top masks every `Disallow`
below it, so it permits `viewtopic.php?p=` although the board plainly forbids
it. The standard rule is that the **longest** matching pattern wins, with a tie
going to Allow.

Getting this wrong would mean fetching pages we have been asked not to, which is
not a mistake worth risking to save fifty lines.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Final, Self

_WILDCARD: Final = "*"


@dataclass
class _Group:
    """The rules for one set of user-agents."""

    agents: set[str] = field(default_factory=set)
    rules: list[tuple[str, bool]] = field(default_factory=list)
    crawl_delay: float | None = None


class RobotsRules:
    """The rules a site publishes for automated clients."""

    def __init__(self, groups: list[_Group]) -> None:
        self._groups = groups

    @classmethod
    def parse(cls, document: str) -> Self:
        groups: list[_Group] = []
        current: _Group | None = None
        starting_group = False

        for line in document.splitlines():
            field_name, _, value = _clean(line).partition(":")
            field_name = field_name.strip().lower()
            value = value.strip()
            if not field_name:
                continue

            if field_name == "user-agent":
                if current is None or not starting_group:
                    current = _Group()
                    groups.append(current)
                    starting_group = True
                current.agents.add(value.lower())
                continue

            starting_group = False
            if current is None:
                #  Rules before any user-agent line belong to nobody.
                continue
            if field_name in ("allow", "disallow") and value:
                current.rules.append((value, field_name == "allow"))
            elif field_name == "crawl-delay":
                current.crawl_delay = _number(value)

        return cls(groups)

    def permits(self, user_agent: str, path: str) -> bool:
        """Whether a client may fetch a path, which may include a query string."""
        group = self._group_for(user_agent)
        if group is None:
            return True

        best_length = -1
        allowed = True
        for pattern, allows in group.rules:
            if not _matches(pattern, path):
                continue
            length = len(pattern)
            #  Longest match wins; a tie goes to Allow.
            if length > best_length or (length == best_length and allows):
                best_length = length
                allowed = allows
        return allowed

    def crawl_delay(self, user_agent: str) -> float | None:
        """The delay the site asks for between requests, if it asks for one."""
        group = self._group_for(user_agent)
        return group.crawl_delay if group else None

    def _group_for(self, user_agent: str) -> _Group | None:
        """The rules applying to a client, preferring a group that names it.

        Groups naming the same agent are merged, because a file may repeat a
        user-agent -- as Stardot's does for `*` -- and the later rules bind
        just as much as the earlier ones.
        """
        name = user_agent.lower()
        named = [group for group in self._groups if _names(group, name)]
        applicable = named or [group for group in self._groups if _WILDCARD in group.agents]
        if not applicable:
            return None
        return _merged(applicable)


def _names(group: _Group, user_agent: str) -> bool:
    return any(agent != _WILDCARD and agent in user_agent for agent in group.agents)


def _merged(groups: list[_Group]) -> _Group:
    if len(groups) == 1:
        return groups[0]
    merged = _Group()
    for group in groups:
        merged.agents |= group.agents
        merged.rules.extend(group.rules)
        if merged.crawl_delay is None:
            merged.crawl_delay = group.crawl_delay
    return merged


def _matches(pattern: str, path: str) -> bool:
    """Whether a rule pattern matches a path, honouring `*` and `$`."""
    anchored = pattern.endswith("$")
    body = pattern[:-1] if anchored else pattern
    expression = ".*".join(re.escape(part) for part in body.split(_WILDCARD))
    return re.match(f"{expression}{'$' if anchored else ''}", path) is not None


def _clean(line: str) -> str:
    return line.split("#", 1)[0].strip()


def _number(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None
