# Data & AI Engineering Assessment

This repository is the take-home part of our hiring process for senior Data Engineers, Data Architects, AI Engineers and AI Architects. It contains three small but real codebases. Each one has a short history: someone built it under time pressure, it mostly works, and a few things are wrong in ways that matter to a client.

We do not test whether you can type code quickly. We test whether you understand what the code does, whether you notice what is wrong, and whether you make sound decisions under constraints. Our seniors run two client projects in parallel, so we also look at how you scope, prioritise and hand over.

## Rules

- **AI assistants are allowed and expected.** Use whatever you use at work. Add a short "AI notes" section to your notes: where AI helped, what you rejected or corrected, and how you verified the result.
- **Timebox: about 3 hours.** Please stop at 4. Choosing what to leave out is part of the assessment; write down what you would do next.
- **Do not change tests to make them pass.** If you think a test is wrong, say why in your notes.
- **Deliverable:** your code changes (branch, patch or zip) plus a `NOTES.md` of at most two pages. Diagrams can be photos of a whiteboard.
- **Debrief (60 minutes):** a 15-minute walkthrough of your work, a 20-minute live change to your own code (AI allowed, screen shared), and 25 minutes of design and trade-off questions. Your submission is the starting point of that conversation. We score the conversation, not the artifact alone.

## Choose your track

| Your role | Track | Core tasks | Pick one extra |
|---|---|---|---|
| AI Engineer | A, Agentic | A1, A2 | one option of A3 |
| AI Architect | A, Agentic | A1, A4 | A2 or one option of A3 |
| Data Engineer | B, Data Platform | B1, B2 | one option of B3 |
| Data Architect | B, Data Platform | B1, B4 | B2 or one option of B3 |
| ML-focused AI Engineer | C, Industrial ML | C1, C2, C3 | C4 |

If your profile sits between two tracks, pick the one you would rather be challenged on and tell us.

## Setup

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12. Everything runs offline by default.

```bash
uv sync --all-groups
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pytest                     # some tests fail on purpose
```

Configuration lives in `utils/settings.toml` and is loaded through Dynaconf in `utils/config.py`. Secrets go into `utils/.secrets.toml` (git-ignored; see `.secrets.toml.example`).

Track A uses a deterministic fake model by default. To use a real model, run `uv sync --extra llm`, set `[default.llm] PROVIDER = "litellm"` and the model ids, and provide a provider key as an environment variable. Any provider works: OpenAI, Anthropic, Bedrock, Azure OpenAI, Vertex AI, or a local Ollama. If you do not have access to a model, ask us for a temporary key.

## Repository map

```
langgraph_base/     AgenticGraph: compiles a LangGraph StateGraph from a JSON config (production code)
agentic/            Track A: onboarding step orchestrator built on langgraph_base
  graph_config.json   nodes and conditional edges
  planner.py          intent classification + ordered rules
  dialog.py           open a step, judge the answer, answer side questions
  gate.py             phase summary and confirmation
  routers.py          edge decisions
  usage.py            token and cost accounting per turn
  tools.py            company register lookup over fixtures
  llm/                provider-agnostic client, scripted fake, litellm client
  cli.py              chat in the terminal: python -m agentic.cli
data_platform/      Track B: SMARD electricity data into DuckDB
  smard_client.py     HTTP client and recorded fixtures
  ingest.py           bronze load (range backfill + incremental) and silver view
  quality.py          completeness check
  cli.py              python -m data_platform.cli --help
industrial_ml/      Track C: NASA C-MAPSS turbofan remaining useful life
  data.py             download and load
  baseline.py         the model the client was shown: python -m industrial_ml.baseline
tests/              one folder per track
```

## Track A: Agentic

`agentic/` is a simplified version of the step orchestrator from one of our products. A client works through a consulting playbook (phases, steps, gates) in a chat. Per user message, the graph runs one turn: the planner decides what to do, the dialog executor opens a step or judges the answer, and the gate reviewer summarises a finished phase. In production this runs on AWS Bedrock with several replicas behind a load balancer. Try it with `python -m agentic.cli`.

**A1 Review.** Read `langgraph_base/` and `agentic/`. Write down your findings, ranked by impact on a client. Cover correctness, failure behaviour, security, cost, and whether the abstraction helps or hurts the next developer. One page at most.

**A2 Fix.** Three tests in `tests/agentic` fail. Find the root causes and fix them. For each one, explain why your fix is correct and not just green. One of the failures comes with an error message that suggests a remedy. Tell us whether you followed it, and why or why not.

**A3 Build (pick one).**
- *Human in the loop:* make gates pause with LangGraph `interrupt()` and resume with `Command(resume=...)`, using a persistent checkpointer (for example SQLite) so a conversation survives a process restart. Explain what is executed again on resume and what that means for side effects.
- *Evaluation:* build an evaluation for the intent classifier and the answer checker against a real model: at least 30 labelled cases, including ambiguous and adversarial ones, plus accuracy, a confusion matrix, cost and latency per case. Use it to tell us whether the confidence threshold of 0.7 is right.
- *Retrieval:* let the dialog answer side questions ("Wozu brauchen Sie das?") from a small document set, with citations and per-client access control. Explain how you would know it got worse after a change.

**A4 Design (architects).** The product goes to more clients. Pick one platform: AWS (Bedrock, AgentCore), Azure (AI Foundry) or Google Cloud (Vertex AI Agent Engine). Describe the target architecture in two pages and one diagram. Cover conversation state and memory across replicas; tool access and prompt injection; tracing and per-client cost metering; evaluation gates in CI; deleting a client's data under GDPR, including traces and logs; and how you would classify the system under the EU AI Act.

## Track B: Data Platform

A municipal utility (Stadtwerk) wants a daily energy KPI mart for Germany as a first step and forecasting later. The source is [SMARD](https://www.smard.de), the electricity market data platform of the Bundesnetzagentur: a free JSON API without a key that serves weekly chunks of hourly values in MWh. `data_platform/fixtures/smard` contains real recorded responses, including the weeks of both daylight-saving switches. Run `python -m data_platform.cli --fixtures range --from 2026-03-23 --to 2026-04-06`, or drop `--fixtures` to use the live API.

**B1 Fix.** Three tests in `tests/data_platform` fail. Fix the root causes. Then review `quality.py` and `cli.py` and note what else would hurt in production. Tell us if any test behaves differently on your machine than in a CI runner, and why.

**B2 Build.** Add a gold model `gold_daily_energy`: one row per local calendar day with consumption (Netzlast), photovoltaics, onshore and offshore wind in MWh, the renewable share, and a completeness flag. SQL or Python, your choice. It must be rebuildable from bronze, and it needs tests that would catch the mistakes from B1.

**B3 Extend (pick one).**
- *Second source:* add [Open-Meteo](https://open-meteo.com) weather (no key) or [Energy-Charts](https://api.energy-charts.info) from Fraunhofer ISE. Reconcile it with SMARD and decide what happens when the sources disagree.
- *Orchestration:* run ingestion on a schedule with a tool of your choice (Dagster, Airflow, Prefect, cron), with backfills, retries, alerting and a story for reruns.
- *Contracts:* define a data contract for bronze and silver. Describe what breaks, and how you would notice, when SMARD switches a series from hourly to quarter-hourly or revises published values.

**B4 Design (architects).** The utility also wants to bring in its own smart-meter readings (personal data, 15-minute intervals, about 400,000 meters) and billing data from SAP IS-U, and the AI team wants to build an assistant on top. Pick one platform: Azure (Fabric or Databricks), AWS (for example S3 with Iceberg, Glue and Athena, or Snowflake) or Google Cloud (BigQuery). Describe the target architecture in two pages and one diagram. Cover ingestion and latency, layering, governance and access control, GDPR (including deletion), cost drivers, and what the AI team gets to consume.

## Track C: Industrial ML

An aircraft maintenance provider wants to know when to take an engine off the wing. The data is NASA's C-MAPSS turbofan simulation (FD001): run-to-failure sensor trajectories for training, and truncated trajectories with the true remaining useful life (RUL) for testing. `python -m industrial_ml.baseline` downloads the data and prints the numbers a previous team showed the client.

**C1 Review and fix.** Make the failing test in `tests/industrial_ml` pass, then list everything that is wrong with the evaluation the client saw. Quantify what each issue changes; do not assume.

**C2 Build.** Evaluate honestly on the official test set and beat the baseline. Report RMSE plus a metric that penalises late predictions more than early ones, and explain your choice.

**C3 Decide.** An unplanned engine failure costs about 250,000 EUR. Removing an engine for maintenance costs about 20,000 EUR, plus about 400 EUR for every cycle of useful life given away by removing it early. Propose a removal rule based on your model, for example "remove when predicted RUL is below k", and show its expected cost on the test set.

**C4 Design.** Describe how this goes into production on Databricks (MLflow), Azure ML or Vertex AI: retraining, monitoring and drift, champion and challenger, edge or cloud scoring. Also describe how an LLM agent should call this model as a tool: the contract, units, uncertainty, and what it must never claim.

## Mood test, must laugh

Ein Hilber Traum ist, wenn Hilber träumt.
