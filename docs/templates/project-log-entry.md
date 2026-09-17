# Template — PROJECT_LOG entry

Every change recorded in `docs/PROJECT_LOG.md` uses this shape, newest first,
between the `CHANGELOG:START` and `CHANGELOG:END` markers. Decisions go in the
decisions table (section 2) with the next free number and are referenced here.

```markdown
### YYYY-MM-DD — <what changed, in a few words>

Decisions D<n>–D<m>.   (omit if none)

#### What was wrong

- **<ID>** One finding per line, with a stable id (UX-, REL-, DEP- or a new
  prefix named once in the baseline section). Say what a person experienced.

#### What changed

- What now exists, where it lives, and what it enforces. Name modules and files.

#### Tests

- Which test file covers it, and what is asserted.

#### Still open, by decision

- What was deliberately not done, and why.
```

A decision row:

```markdown
| D<n> | The decision, as one sentence a reviewer can disagree with. | Why — the constraint or evidence that made it the right call. |
```

Refer to the RAIA project and architecture as a whole; never cite a specific
paper, section, figure or table.
