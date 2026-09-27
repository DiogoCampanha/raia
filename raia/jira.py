"""
raia.jira
=========

Optional: sending a sprint to Jira, and reading its status back.

RAIA's board is complete without Jira — every status change has a manual
control — so everything here is an extra for teams that plan in Jira:

* **CSV** (no setup): a file for Jira Cloud's CSV importer, one row per story,
  with a ``Summary`` header, one ``Labels`` column per label and the ethical
  acceptance criteria in the description.
* **Push** (Jira Cloud): with a person's own API token, stories without a Jira
  key are created in batches of 50 (the bulk endpoint's limit), and stories
  changed in RAIA since their last push are updated. Optionally, the issues are
  added to a Jira sprint.
* **Sync**: status is read back by key. A status in Jira's *Done* category
  marks a sprint story done — never verified, which only an approved audit
  does — and a sync never overwrites a manual change: when RAIA and Jira
  disagree, the board shows both and a person picks.

Every story carries labels that identify it (``raia``, ``raia-RAI-4``,
``raia-SPR-3``, and ``raia-ethics`` for RAI stories), so stories that went out
as a CSV can be found and synced later too.

HTTP goes through :mod:`httpx`; tests replace :data:`TRANSPORT` with a mock
transport, so nothing here needs a network to be tested.
"""

from __future__ import annotations

import csv
import datetime as _dt
import hashlib
import io
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from . import backlog as B

#: Replaced by tests with ``httpx.MockTransport``.
TRANSPORT: Any = None
BULK_LIMIT = 50
TIMEOUT = 20.0
DONE_CATEGORY = "done"

_SITE = re.compile(r"^https://[A-Za-z0-9.-]+\.(atlassian\.net|jira\.com)/?$")
_KEY = re.compile(r"^[A-Z][A-Z0-9_]{1,19}$")


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def normalize_site(site: str) -> str:
    site = (site or "").strip().rstrip("/")
    if site and not site.startswith("https://"):
        site = "https://" + site.removeprefix("http://")
    if not _SITE.match(site + "/"):
        raise ValueError("Use your Jira Cloud address, e.g. https://your-team.atlassian.net")
    return site


def check_project_key(key: str) -> str:
    key = (key or "").strip().upper()
    if not _KEY.match(key):
        raise ValueError("A Jira project key is 2 to 20 capital letters or digits, starting with a letter (e.g. RAIA).")
    return key


# ---------------------------------------------------------------------------
# What a story looks like in Jira
# ---------------------------------------------------------------------------


def labels_for(story: Dict[str, Any], sprint_id: str = "") -> List[str]:
    out = ["raia", f"raia-{story['id']}"]
    if sprint_id or story.get("sprint"):
        out.append(f"raia-{sprint_id or story.get('sprint')}")
    if story.get("origin") == B.RAI:
        out.append("raia-ethics")
    return out


def summary_for(story: Dict[str, Any]) -> str:
    title = story.get("title") or (story.get("description") or "")[:80] or story["id"]
    return f"[{story['id']}] {title}"[:250]


def _criteria_lines(story: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    existing = [c.get("text", "") for c in story.get("criteria") or [] if c.get("kind") != "ethical"]
    ethical = [f"{c.get('id')}: {c.get('text', '')}"
               + (f" (evidence: {c['evidence_artifact']})" if c.get("evidence_artifact") else "")
               + (f" (owner: {c['owner_role'].replace('_', ' ')})" if c.get("owner_role") else "")
               for c in B.ethical_criteria(story)]
    return existing, ethical


def description_text(story: Dict[str, Any], project_name: str = "") -> str:
    """The description as plain text (the CSV path)."""
    existing, ethical = _criteria_lines(story)
    parts = [story.get("description") or ""]
    if existing:
        parts += ["", "Acceptance criteria:"] + [f"- {x}" for x in existing]
    if ethical:
        parts += ["", "Ethical acceptance criteria (verified by the RAIA audit):"] + [f"- {x}" for x in ethical]
    if story.get("evr_ids"):
        parts += ["", "Implements: " + ", ".join(story["evr_ids"])]
    parts += ["", f"From RAIA{(' project ' + project_name) if project_name else ''}, story {story['id']}."]
    return "\n".join(parts).strip()


def _text(t: str) -> Dict[str, Any]:
    return {"type": "text", "text": t}


def _para(t: str) -> Dict[str, Any]:
    return {"type": "paragraph", "content": [_text(t)]} if t else {"type": "paragraph"}


def _bullets(items: Sequence[str]) -> Dict[str, Any]:
    return {"type": "bulletList", "content": [{"type": "listItem", "content": [_para(x)]} for x in items]}


def description_adf(story: Dict[str, Any], project_name: str = "") -> Dict[str, Any]:
    """The description in Atlassian Document Format (the API path)."""
    existing, ethical = _criteria_lines(story)
    content: List[Dict[str, Any]] = []
    if story.get("description"):
        content.append(_para(story["description"]))
    if existing:
        content += [{"type": "heading", "attrs": {"level": 3}, "content": [_text("Acceptance criteria")]},
                    _bullets(existing)]
    if ethical:
        content += [{"type": "heading", "attrs": {"level": 3},
                     "content": [_text("Ethical acceptance criteria (verified by the RAIA audit)")]},
                    _bullets(ethical)]
    if story.get("evr_ids"):
        content.append(_para("Implements: " + ", ".join(story["evr_ids"])))
    content.append(_para(f"From RAIA{(' project ' + project_name) if project_name else ''}, story {story['id']}."))
    return {"type": "doc", "version": 1, "content": content}


def fingerprint(story: Dict[str, Any]) -> str:
    """What a push sends, hashed: a story is updated in Jira only when this changes."""
    blob = "|".join([summary_for(story), description_text(story), ",".join(labels_for(story)),
                     str(story.get("estimate") or "")])
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# CSV for Jira's importer
# ---------------------------------------------------------------------------


def to_csv(stories: Sequence[Dict[str, Any]], sprint_id: str = "", issue_type: str = "Story",
           project_name: str = "") -> str:
    """One row per story, for Jira Cloud's CSV importer.

    Jira maps repeated columns of the same name to a multi-value field, so each
    label gets its own ``Labels`` column. Story points are included only when
    some story has an estimate.
    """
    rows = [(s, labels_for(s, sprint_id)) for s in stories]
    n_labels = max((len(l) for _, l in rows), default=1)
    points = any(s.get("estimate") for s in stories)
    header = ["Summary", "Issue Type", "Description"] + ["Labels"] * n_labels + (["Story Points"] if points else [])
    buf = io.StringIO()
    w = csv.writer(buf, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
    w.writerow(header)
    for s, labels in rows:
        w.writerow([summary_for(s), issue_type or "Story", description_text(s, project_name)]
                   + labels + [""] * (n_labels - len(labels))
                   + ([s.get("estimate") or ""] if points else []))
    return buf.getvalue()


CSV_STEPS = [
    "In Jira, open your project and choose Import work items from CSV (in the ⋯ menu of the issue "
    "search, or System > External system import for administrators).",
    "Upload this file and map Summary, Issue Type, Description, Labels and, if present, Story Points.",
    "Import. Every story keeps its RAIA id in its labels, so you can sync status later from the board "
    "if you connect Jira; or tick stories done on the board by hand.",
]


# ---------------------------------------------------------------------------
# The Jira Cloud client
# ---------------------------------------------------------------------------


class JiraError(RuntimeError):
    pass


class JiraClient:
    """The few Jira Cloud REST calls RAIA uses, with the person's own API token."""

    def __init__(self, site: str, email: str, token: str, transport: Any = None) -> None:
        import httpx

        if not (email and token):
            raise ValueError("A Jira connection needs the email you sign in with and an API token.")
        self.site = normalize_site(site)
        self._http = httpx.Client(base_url=self.site, auth=(email, token), timeout=TIMEOUT,
                                  transport=transport if transport is not None else TRANSPORT,
                                  headers={"Accept": "application/json"})

    def close(self) -> None:
        self._http.close()

    def _call(self, method: str, path: str, **kw: Any) -> Any:
        import httpx

        try:
            r = self._http.request(method, path, **kw)
        except httpx.HTTPError as exc:
            raise JiraError(f"Jira could not be reached ({exc.__class__.__name__}).") from exc
        if r.status_code in (401, 403):
            raise JiraError("Jira refused the credentials: check the email and the API token.")
        if r.status_code == 404:
            raise JiraError(f"Jira has no {path.split('?')[0]} here: check the site and the project key.")
        # A bulk create that fails for every issue answers 400 with the per-issue
        # errors in the body: those are read, not raised.
        if r.status_code >= 400 and not (r.status_code == 400 and path.endswith("/issue/bulk")):
            detail = ""
            try:
                body = r.json()
                detail = "; ".join(body.get("errorMessages") or []) or "; ".join(f"{k}: {v}" for k, v in (body.get("errors") or {}).items())
            except ValueError:
                pass
            raise JiraError(f"Jira answered {r.status_code}" + (f": {detail}" if detail else "."))
        return r.json() if r.content else {}

    def myself(self) -> Dict[str, Any]:
        return self._call("GET", "/rest/api/3/myself")

    def points_field(self) -> Optional[str]:
        """The site's story-points field, found by name (it is a custom field)."""
        for f in self._call("GET", "/rest/api/3/field") or []:
            if str(f.get("name", "")).lower() in ("story points", "story point estimate"):
                return f.get("id")
        return None

    def bulk_create(self, updates: List[Dict[str, Any]]) -> Dict[str, Any]:
        return self._call("POST", "/rest/api/3/issue/bulk", json={"issueUpdates": updates})

    def update(self, key: str, fields: Dict[str, Any]) -> None:
        self._call("PUT", f"/rest/api/3/issue/{key}", json={"fields": fields})

    def search(self, jql: str, fields: Sequence[str] = ("status", "labels")) -> List[Dict[str, Any]]:
        """JQL search through ``/rest/api/3/search/jql`` (the old ``/search`` is gone from Jira Cloud)."""
        out: List[Dict[str, Any]] = []
        token = None
        for _ in range(20):
            body: Dict[str, Any] = {"jql": jql, "fields": list(fields), "maxResults": 100}
            if token:
                body["nextPageToken"] = token
            page = self._call("POST", "/rest/api/3/search/jql", json=body)
            out += page.get("issues") or []
            token = page.get("nextPageToken")
            if not token or page.get("isLast"):
                break
        return out

    def boards(self, project_key: str) -> List[Dict[str, Any]]:
        return (self._call("GET", "/rest/agile/1.0/board", params={"projectKeyOrId": project_key}) or {}).get("values") or []

    def sprints(self, board_id: int) -> List[Dict[str, Any]]:
        return (self._call("GET", f"/rest/agile/1.0/board/{int(board_id)}/sprint",
                           params={"state": "active,future"}) or {}).get("values") or []

    def move_to_sprint(self, sprint_id: int, keys: Sequence[str]) -> None:
        for i in range(0, len(keys), BULK_LIMIT):
            self._call("POST", f"/rest/agile/1.0/sprint/{int(sprint_id)}/issue", json={"issues": list(keys[i:i + BULK_LIMIT])})


# ---------------------------------------------------------------------------
# Push and sync
# ---------------------------------------------------------------------------


def _fields(story: Dict[str, Any], project_key: str, issue_type: str, sprint_id: str, points_field: Optional[str],
            project_name: str) -> Dict[str, Any]:
    fields: Dict[str, Any] = {
        "project": {"key": project_key}, "issuetype": {"name": issue_type or "Story"},
        "summary": summary_for(story), "description": description_adf(story, project_name),
        "labels": labels_for(story, sprint_id),
    }
    if points_field and story.get("estimate"):
        fields[points_field] = story["estimate"]
    return fields


def push(client: JiraClient, stories: Sequence[Dict[str, Any]], *, project_key: str, issue_type: str = "Story",
         sprint_id: str = "", jira_sprint: Optional[int] = None, project_name: str = "") -> Dict[str, Any]:
    """Create what has no key, update what changed, and optionally place the issues in a Jira sprint.

    Returns ``{"created": {story id: key}, "updated": [...], "unchanged": [...], "errors": {story id: msg},
    "stamps": {story id: {"key", "url", "hash"}}}``. Nothing is written to RAIA here; the caller records
    the keys in the backlog in one commit.
    """
    project_key = check_project_key(project_key)
    points = None
    if any(s.get("estimate") for s in stories):
        try:
            points = client.points_field()
        except JiraError:
            points = None
    created: Dict[str, str] = {}
    updated: List[str] = []
    unchanged: List[str] = []
    errors: Dict[str, str] = {}
    stamps: Dict[str, Dict[str, str]] = {}
    new = [s for s in stories if not (s.get("jira") or {}).get("key")]
    for i in range(0, len(new), BULK_LIMIT):
        batch = new[i:i + BULK_LIMIT]
        body = client.bulk_create([{"fields": _fields(s, project_key, issue_type, sprint_id, points, project_name)}
                                   for s in batch])
        failed = {int(e.get("failedElementNumber", -1)): e for e in body.get("errors") or []}
        made = iter(body.get("issues") or [])
        for n, s in enumerate(batch):
            if n in failed:
                ee = (failed[n].get("elementErrors") or {})
                errors[s["id"]] = "; ".join(ee.get("errorMessages") or []) or "; ".join(
                    f"{k}: {v}" for k, v in (ee.get("errors") or {}).items()) or "rejected by Jira"
                continue
            issue = next(made, None)
            if not issue:
                errors[s["id"]] = "Jira returned no issue for this story"
                continue
            created[s["id"]] = issue["key"]
            stamps[s["id"]] = {"key": issue["key"], "url": f"{client.site}/browse/{issue['key']}",
                               "hash": fingerprint(s)}
    for s in stories:
        key = (s.get("jira") or {}).get("key")
        if not key:
            continue
        if (s.get("jira") or {}).get("hash") == fingerprint(s) and not (s.get("jira") or {}).get("dirty"):
            unchanged.append(s["id"])
            continue
        try:
            fields = _fields(s, project_key, issue_type, sprint_id, points, project_name)
            fields.pop("project", None)
            fields.pop("issuetype", None)
            client.update(key, fields)
            updated.append(s["id"])
            stamps[s["id"]] = {"key": key, "url": (s.get("jira") or {}).get("url") or f"{client.site}/browse/{key}",
                               "hash": fingerprint(s)}
        except JiraError as exc:
            errors[s["id"]] = str(exc)
    if jira_sprint and (created or updated):
        keys = [v["key"] for v in stamps.values()]
        try:
            client.move_to_sprint(jira_sprint, keys)
        except JiraError as exc:
            errors["(sprint)"] = f"The issues were created but not added to the Jira sprint: {exc}"
    return {"created": created, "updated": updated, "unchanged": unchanged, "errors": errors, "stamps": stamps}


def record_push(bl: Dict[str, Any], result: Dict[str, Any], by: str = "") -> None:
    """Keep each story's Jira key, link and push fingerprint in the backlog."""
    for sid, stamp in (result.get("stamps") or {}).items():
        s = B.story(bl, sid)
        if s is None:
            continue
        j = dict(s.get("jira") or {})
        first = not j.get("key")
        j.update({"key": stamp["key"], "url": stamp["url"], "hash": stamp["hash"], "pushed_at": _now(), "dirty": False})
        s["jira"] = j
        B._log(s, by, f"{'sent to' if first else 'updated in'} Jira as {stamp['key']}")


def fetch_status(client: JiraClient, stories: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, str]]:
    """Jira's status for each story with a key, or found by its RAIA label: story id -> status."""
    keyed = {(s.get("jira") or {}).get("key"): s["id"] for s in stories if (s.get("jira") or {}).get("key")}
    unkeyed = [s["id"] for s in stories if not (s.get("jira") or {}).get("key")]
    clauses = []
    if keyed:
        clauses.append("key in (" + ", ".join(sorted(keyed)) + ")")
    if unkeyed:
        clauses.append("labels in (" + ", ".join(f"raia-{sid}" for sid in unkeyed) + ")")
    if not clauses:
        return {}
    out: Dict[str, Dict[str, str]] = {}
    for issue in client.search(" OR ".join(clauses)):
        fields = issue.get("fields") or {}
        status = fields.get("status") or {}
        info = {"key": issue.get("key", ""), "status": status.get("name", ""),
                "category": ((status.get("statusCategory") or {}).get("key") or "").lower(),
                "url": f"{client.site}/browse/{issue.get('key', '')}"}
        sid = keyed.get(issue.get("key"))
        if not sid:
            for label in fields.get("labels") or []:
                if label.startswith("raia-") and label[5:] in unkeyed:
                    sid = label[5:]
        if sid:
            out[sid] = info
    return out


def apply_sync(bl: Dict[str, Any], sp: Dict[str, Any], statuses: Dict[str, Dict[str, str]],
               by: str = "") -> Dict[str, Any]:
    """Apply Jira's statuses to the open sprint, never over a person's change.

    * Jira Done and the story is in the sprint, not done → done (source: Jira),
      unless a person un-ticked it after the last sync → a disagreement.
    * The story is done in RAIA and open in Jira → a disagreement (never undone).
    * Nothing here sets verified.
    """
    x = B.open_sprint(sp)
    done, disagree, seen = [], [], []
    for s in bl.get("stories") or []:
        info = statuses.get(s["id"])
        if not info:
            continue
        seen.append(s["id"])
        j = dict(s.get("jira") or {})
        last_sync = j.get("synced_at", "")
        j.update({"key": info["key"] or j.get("key", ""), "url": info.get("url") or j.get("url", ""),
                  "status": info["status"], "category": info["category"], "synced_at": _now()})
        j.pop("disagreement", None)
        s["jira"] = j
        in_open = bool(x and s.get("sprint") == x["id"] and x["state"] in (B.ACTIVE, B.REVIEW))
        jira_done = info["category"] == DONE_CATEGORY
        manual = (s.get("done") or {})
        if in_open and jira_done and s["status"] == B.IN_SPRINT:
            undone_by_hand = manual.get("source") == "manual" and manual.get("undone_at", "") >= last_sync
            if undone_by_hand:
                j["disagreement"] = f"Jira says {info['status']}; it was marked not done in RAIA"
                disagree.append(s["id"])
            else:
                B.tick(bl, sp, s["id"], True, by, source="jira")
                done.append(s["id"])
        elif in_open and not jira_done and s["status"] == B.DONE:
            j["disagreement"] = f"Jira says {info['status']}; it is marked done in RAIA"
            disagree.append(s["id"])
    counts: Dict[str, int] = {}
    for sid in seen:
        cat = statuses[sid]["category"] or "unknown"
        label = {"done": "done", "indeterminate": "in progress", "new": "to do"}.get(cat, cat)
        counts[label] = counts.get(label, 0) + 1
    asked = [s["id"] for s in B.in_sprint(bl, x["id"])] if x else []
    missing = [sid for sid in asked if sid not in statuses and (B.story(bl, sid).get("jira") or {}).get("key")]
    return {"done": done, "disagreements": disagree, "counts": counts, "not_found": missing}


def summary_line(result: Dict[str, Any]) -> str:
    parts = [f"{n} {label}" for label, n in result.get("counts", {}).items()]
    if result.get("not_found"):
        parts.append(f"{len(result['not_found'])} not found")
    return ", ".join(parts) or "no story of this sprint was found in Jira"


def resolve(bl: Dict[str, Any], sp: Dict[str, Any], sid: str, keep: str, by: str = "") -> Dict[str, Any]:
    """A person settles a disagreement: ``raia`` keeps the board's state, ``jira`` takes Jira's."""
    s = B.require(bl, sid)
    j = dict(s.get("jira") or {})
    if not j.get("disagreement"):
        raise ValueError(f"{sid} has no disagreement with Jira to settle.")
    if keep == "jira":
        B.tick(bl, sp, sid, j.get("category") == DONE_CATEGORY, by, source="jira")
    elif keep != "raia":
        raise ValueError("Keep RAIA's state or Jira's.")
    j.pop("disagreement", None)
    s["jira"] = j
    B._log(s, by, f"Jira disagreement settled: kept {'Jira' if keep == 'jira' else 'RAIA'}")
    return s
