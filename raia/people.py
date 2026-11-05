"""
raia.people
===========

How people are named in what RAIA records.

The audit trail is append-only and hash-chained: nothing in it can be erased
without breaking the chain. A name or an email written into it could never be
removed when the person deletes their account. So everything RAIA *records* —
version messages, approvals, decisions, story history — names a person by a
reference, ``user:<id>``, and the reference is turned into a name only when it
is *shown*, from the accounts table. Deleting an account deletes the only place
the name lives; the record keeps an opaque, still-unique reference.

The same rule keeps names out of model prompts: upstream artifacts reach the
next agent with references in them, never names.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, Set

PREFIX = "user:"
_REF = re.compile(r"user:([0-9a-f]{32})")

#: How a reference to an account that no longer exists is shown.
FORMER_MEMBER = "a former member"


def ref(user_id: str) -> str:
    """The reference recorded for a person."""
    return f"{PREFIX}{user_id}" if user_id else ""


def ids_in(obj: Any) -> Set[str]:
    """Every user id referenced anywhere in a nested structure of str/list/dict."""
    found: Set[str] = set()

    def walk(o: Any) -> None:
        if isinstance(o, str):
            found.update(_REF.findall(o))
        elif isinstance(o, dict):
            for k, v in o.items():
                walk(k)
                walk(v)
        elif isinstance(o, (list, tuple)):
            for v in o:
                walk(v)

    walk(obj)
    return found


def humanize(obj: Any, names: Dict[str, str]) -> Any:
    """A copy of ``obj`` with every reference replaced by the person's name.

    ``names`` maps user id to display name; an id not in it is shown as
    :data:`FORMER_MEMBER`. Only for display: never write the result back.
    """
    def sub(text: str) -> str:
        return _REF.sub(lambda m: names.get(m.group(1), FORMER_MEMBER), text)

    if isinstance(obj, str):
        return sub(obj) if PREFIX in obj else obj
    if isinstance(obj, dict):
        return {humanize(k, names): humanize(v, names) for k, v in obj.items()}
    if isinstance(obj, list):
        return [humanize(v, names) for v in obj]
    if isinstance(obj, tuple):
        return tuple(humanize(v, names) for v in obj)
    return obj


def display_names(db: Any, ids: Iterable[str]) -> Dict[str, str]:
    """Names for a set of user ids, as ``Name <email>`` (or the email alone)."""
    ids = sorted(set(ids))
    if not ids:
        return {}
    marks = ", ".join("?" for _ in ids)
    rows = db.query(f"SELECT id, name, email FROM users WHERE id IN ({marks})", ids)
    return {r["id"]: (f"{r['name']} <{r['email']}>" if r.get("name") else r["email"]) for r in rows}
