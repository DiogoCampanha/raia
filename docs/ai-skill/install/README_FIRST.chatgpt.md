# RAIA AI Skill for ChatGPT

Skill version 2.0.0.

## What is inside

```
README_FIRST.md              This file
raia-responsible-ai.zip      The fixed part: the skill, the same for every project, never edited
raia-project/                The project part: this project's outputs (see its README.md)
```

## Install

1. In ChatGPT, open Skills, choose to create a skill by uploading from your computer, and select `raia-responsible-ai.zip`. Menu names change between versions; look for the upload option.
2. Start a conversation or a project and attach `raia-project/PROJECT_CONTEXT.md`. Attach the CSV files too when you want the assistant to read the backlog or the roadmap.

If your workspace does not allow uploading skills, download the format "One Markdown file" from RAIA instead and add it to a project's instructions or attach it to the conversation.

## Use

Then try:

- "Using the RAIA skill, triage this backlog." (attach an export or paste the stories)
- "Refine this story with the RAIA skill."
- "Review this product document for Responsible AI gaps."
- "Which requirements have no story yet? Draft RAI stories for the top three."
- "Suggest the next sprint from the RAIA backlog."
- "Write a one-page Responsible AI brief for my manager."

The skill also works with no project part: it screens the product itself and says that the result is self-assessed.

## The two parts

- **The fixed part never changes** within a version. It is identical for every project and every download. Do not edit it; a new version comes from RAIA.
- **The project part changes** whenever work is approved in RAIA. Download again and replace `raia-project/` (or the attached files). The skill itself stays where it is.

## Good to know

- **Share your backlog only with an assistant your organisation approves.** Nothing in this package is sent anywhere; it was produced on request and downloaded by you.
- **Approver names stay in the records** inside `raia-project/artifacts/`: that is their provenance.
- **It is lighter than RAIA.** The assistant follows RAIA's rules but has no rule engine, no retrieval over the normative texts and no approval gate. Material changes (a new purpose, market, data category or level of automation) go back to RAIA; the skill tells the assistant to say so.
- **PL 2338/2023 is a bill, not yet law.** The skill names it as such.
- RAIA is a research prototype developed at Universidade Presbiteriana Mackenzie. Its outputs support, and do not replace, legal and compliance advice.
