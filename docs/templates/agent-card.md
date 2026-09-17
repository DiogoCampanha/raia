# Agent card — <Agent name>

> Every RAIA agent is documented with this card. Cards in `docs/agents/` are
> generated from the code (`python -m raia.contract.agent_cards`) so they cannot
> drift from the implementation; a new agent gets its card by being registered.
> Use this template by hand only for an agent that is designed but not built.

## 1. Purpose
One or two sentences: what the agent produces and for whom.

## 2. Place in the lifecycle
| | |
|---|---|
| Layer | Product · Dev · Ops |
| SDLC phase | |
| When to run | |
| Requires approved | Stages that must be approved first (stage gate) |
| Reads | Upstream artifacts it reads from the blackboard |
| Produces | Artifact file — record type |

## 3. Normative grounding
| Source | Authority |
|---|---|
| One of: EU AI Act, PL 2338/2023, IEEE 7000-2021, Microsoft RAI Standard v2, NIST AI RMF 1.0, ECCOLA | legal · standard · advisory |

## 4. Inputs
| Group | Question | Kind | Required |
|---|---|---|---|
Every question is read by a rule, a retrieval facet or a check — or it does not exist.

## 5. What the decision procedure settles in code
- What is enumerable and therefore computed.
- The checklist the record must declare, and the excerpts pinned.

## 6. What a person decides
- The open-textured judgements left to people, and every open issue.

## 7. The record it produces
Schema version and file, identifier prefix, the extension fields (field — content),
the rendered sections, the verdict keys the agent declares.

## 8. Checks
The shared contract checks, then the agent-specific ones.

## 9. Limitations
Stated plainly, so nobody finds them first.
