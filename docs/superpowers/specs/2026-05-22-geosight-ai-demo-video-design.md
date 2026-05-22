# GeoSight AI Demo Video Design

## Goal

Create a polished Databricks AI Hackathon demo video for GeoSight AI by team alpha-2. The video should feel like one continuous technical demo for judges, not a set of unrelated clips. It should use real app recordings as evidence and concise Databricks Cloud architecture-style animation to explain the use case, data flow, multi-agent investigation design, feedback capture, and knowledge improvement loop.

## Audience And Tone

- Audience: Databricks AI Hackathon judges.
- Tone: professional, technical, confident, energetic, not flat.
- Narration: one consistent AI-generated English narrator voice with natural paragraph breaks and clear emphasis.
- Subtitles: one consistent lower-third takeaway style, not word-for-word captions.
- Station naming: never mention any real station name. Use `geothermal station` only.

## Narrative Structure

1. Opening: introduce GeoSight AI and the geothermal station telemetry intelligence use case.
2. Use case: show why trusted telemetry matters for forecasting and generation optimisation workflows.
3. Problem: frame the core judgement: bad telemetry or real operating event.
4. Data setup: explain simulated noisy geothermal station telemetry flowing into governed lakehouse tables.
5. Product demo: use real app recordings to show incident queue, selected incident detail, raw context plot, AI draft analysis, and feedback submission.
6. Multi-agent architecture: explain the innovation architecture, not a generic Databricks service list.
7. Feedback and knowledge loop: show feedback captured as governed review evidence that can become future knowledge graph candidates after review.
8. Impact close: faster triage, reusable operational knowledge, auditability, and more trusted model inputs.

## Source Assets

Primary app recordings in `D:\demoing`:

- `01_app_incident_queue.mp4`: incident queue and incident metrics.
- `02_app_incident_detail_plot.mp4`: selected hero incident, failed windows, quality logs, and raw plot.
- `03_app_ai_draft_analysis.mp4.mp4`: AI investigation result.
- `04_app_feedback_submit.mp4`: user feedback form and submission.

Optional support recordings:

- `compare tags.mp4`: use only as a short optional context flash if pacing allows.
- `data profiling.mp4`: use only as a short optional context flash if pacing allows.
- `knowledge graph.mp4`: useful as visual proof of graph context, but should not replace the simplified architecture animation.

Chinese source audio in `D:\demoing`:

- `voice_01_opening.m4a`
- `voice_02_use_case.m4a`
- `voice_03_data_setup.m4a`
- `voice_04_app_demo_1.m4a`
- `voice_04_app_demo_2.m4a`
- `voice_04_app_demo_3.m4a`
- `voice_05_multi_agent_architecture.m4a`
- `voice_06_feedback_loop.m4a`
- `voice_07_impact_close.m4a`

Architecture reference:

- `产品架构图.html`: detailed reference only. The final video should not show the full diagram as-is because it is too dense for a timed demo.

## Clip Strategy

The source recordings are intentionally longer than the final edit needs. Use them as follows:

- Incident queue: keep roughly 10-14 seconds focused on metrics, queue, and the hero incident row.
- Incident detail and plot: keep roughly 15-22 seconds focused on rule, failed windows, quality log, and shutdown/restart pattern in the plot.
- AI draft analysis: keep roughly 14-20 seconds focused on the conclusion that the pattern is a real operational event rather than simple telemetry noise.
- Feedback submission: keep roughly 8-12 seconds to show feedback captured in the app.
- Optional tabs: if included, keep each to 3-5 seconds maximum and use them only to support the statement that the app has richer process context.

## Architecture Animation Simplification

Redraw the detailed architecture into three readable animated layers:

1. Data and app loop:
   `Telemetry -> Lakeflow -> Lakehouse / Unity Catalog -> SQL Warehouse -> GeoSight AI App`

2. Multi-agent investigation loop:
   `GeoSight AI App -> Supervisor Agent -> graph assistant / incident analysis agent / DBA evidence agent -> synthesized investigation answer`

3. Feedback knowledge loop:
   `User feedback -> governed review evidence -> knowledge candidates -> graph assistant -> Knowledge Graph enrichment path -> better future retrieval`

Databricks components should appear as simple labeled cards, with official or official-style icons where reliable. The video should not over-index on a generic Databricks capability list; the innovation is the multi-agent investigation and knowledge improvement loop.

## Claim Boundaries

Strongly claim what the app demonstrates:

- Incident queue and review workflow.
- Incident details, quality logs, and raw telemetry context.
- AI draft analysis.
- User feedback captured from the app.
- Knowledge graph view exists as context.

Use careful language for the knowledge loop:

- Acceptable: `captured as governed review evidence`, `can become knowledge candidates`, `can enrich the graph after review`, `designed to feed future retrieval and reasoning`.
- Avoid: `automatically updates the knowledge graph`, `autonomous learning`, `self-updating graph`, `the graph learns from every feedback event`.

## Sensitive Information Handling

Before final render, inspect all app clips for real station names or confidential identifiers. If unavoidable on screen, mask or crop them. `geothermal station` is the only allowed station wording in narration and subtitles.

Potential on-screen risk areas:

- Table/log identifiers such as `KAG_...`.
- Fully qualified tables such as `workspace.default...`.
- Any tag or UI text that implies a real station name.

## Visual Direction

- Style: Databricks Cloud architecture demo, clean and minimal.
- Palette: dark app-compatible canvas with Databricks red accents, cyan data flow, green graph/context flow, purple agent flow, pink feedback flow.
- Motion: restrained, readable transitions; each animation should teach one relationship.
- No generic stock footage.
- No cluttered full-architecture slide in the final timeline.

## Output Expectation

The final deliverable should be a HyperFrames project that can preview and render an MP4. It should combine real app recordings, simplified architecture animations, AI-generated English narration, and consistent takeaway subtitles.
