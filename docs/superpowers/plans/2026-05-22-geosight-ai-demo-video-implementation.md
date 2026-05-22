# GeoSight AI Demo Video Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a HyperFrames MP4 demo video for GeoSight AI that combines real app recordings, concise Databricks-style architecture animations, AI-generated English narration, and consistent takeaway subtitles.

**Architecture:** Create the HyperFrames project in `C:\tmp\geosight-ai-demo-video` to avoid UNC path issues with Windows `npx`. Copy source media from `D:\demoing`, compose one root `index.html`, and keep reusable visual data in small JavaScript data files. The video uses app recordings as proof and custom HTML/CSS/GSAP animation for use case, data flow, multi-agent architecture, feedback loop, and close.

**Tech Stack:** HyperFrames `0.6.33`, HTML, CSS, GSAP, local MP4/M4A media, HyperFrames TTS, Chrome headless, optional FFmpeg installation for final rendering.

---

## File Structure

Create this project outside the repo:

```text
C:\tmp\geosight-ai-demo-video\
  DESIGN.md
  index.html
  package.json
  media\
    01_app_incident_queue.mp4
    02_app_incident_detail_plot.mp4
    03_app_ai_draft_analysis.mp4.mp4
    04_app_feedback_submit.mp4
    compare tags.mp4
    data profiling.mp4
    knowledge graph.mp4
  scripts\
    sequence.js
    architecture-data.js
  narration\
    narration.txt
    narration.wav
  renders\
```

Track the implementation source in a local git repo at `C:\tmp\geosight-ai-demo-video`. The final rendered MP4 is an artifact and does not need to be committed.

---

### Task 1: Tooling And Project Scaffold

**Files:**
- Create: `C:\tmp\geosight-ai-demo-video\package.json`
- Create: `C:\tmp\geosight-ai-demo-video\media\`
- Create: `C:\tmp\geosight-ai-demo-video\scripts\`
- Create: `C:\tmp\geosight-ai-demo-video\narration\`
- Create: `C:\tmp\geosight-ai-demo-video\renders\`

- [ ] **Step 1: Check HyperFrames tooling**

Run:

```powershell
npx hyperframes doctor
```

Expected:

```text
✓ Version
✓ Node.js
✓ Chrome
✗ FFmpeg           Not found
✗ FFprobe          Not found
```

If FFmpeg and FFprobe are already present, continue. If they are missing, final render is blocked until Step 2 completes.

- [ ] **Step 2: Install FFmpeg with winget if missing**

Run:

```powershell
winget install --id Gyan.FFmpeg -e --source winget
```

Expected:

```text
Successfully installed
```

Close and reopen the shell, then run:

```powershell
ffmpeg -version
ffprobe -version
```

Expected: both commands print version details.

- [ ] **Step 3: Scaffold the HyperFrames project**

Run:

```powershell
New-Item -ItemType Directory -Force C:\tmp\geosight-ai-demo-video
Set-Location C:\tmp
npx hyperframes init geosight-ai-demo-video --non-interactive
Set-Location C:\tmp\geosight-ai-demo-video
New-Item -ItemType Directory -Force media, scripts, narration, renders
```

Expected:

```text
index.html
hyperframes.json
package.json
```

- [ ] **Step 4: Initialize local git**

Run:

```powershell
Set-Location C:\tmp\geosight-ai-demo-video
git init
git add .
git commit -m "chore: scaffold geosight demo video"
```

Expected:

```text
[main ...] chore: scaffold geosight demo video
```

---

### Task 2: Copy Media And Create Sequence Data

**Files:**
- Copy into: `C:\tmp\geosight-ai-demo-video\media\`
- Create: `C:\tmp\geosight-ai-demo-video\scripts\sequence.js`

- [ ] **Step 1: Copy approved media**

Run:

```powershell
Set-Location C:\tmp\geosight-ai-demo-video
Copy-Item "D:\demoing\01_app_incident_queue.mp4" media\
Copy-Item "D:\demoing\02_app_incident_detail_plot.mp4" media\
Copy-Item "D:\demoing\03_app_ai_draft_analysis.mp4.mp4" media\
Copy-Item "D:\demoing\04_app_feedback_submit.mp4" media\
Copy-Item "D:\demoing\compare tags.mp4" media\
Copy-Item "D:\demoing\data profiling.mp4" media\
Copy-Item "D:\demoing\knowledge graph.mp4" media\
```

Expected: seven video files exist in `media\`.

- [ ] **Step 2: Create sequence data**

Create `C:\tmp\geosight-ai-demo-video\scripts\sequence.js`:

```js
window.GEOSIGHT_SEQUENCE = {
  totalDuration: 228,
  clips: {
    queue: {
      src: "media/01_app_incident_queue.mp4",
      start: 42,
      duration: 13,
      mediaStart: 5,
      label: "Unity Catalog incident records"
    },
    detail: {
      src: "media/02_app_incident_detail_plot.mp4",
      start: 55,
      duration: 22,
      mediaStart: 11,
      label: "Failed window and raw telemetry context"
    },
    ai: {
      src: "media/03_app_ai_draft_analysis.mp4.mp4",
      start: 77,
      duration: 18,
      mediaStart: 10,
      label: "Supervisor Agent investigation draft"
    },
    feedback: {
      src: "media/04_app_feedback_submit.mp4",
      start: 95,
      duration: 11,
      mediaStart: 11,
      label: "Governed feedback capture"
    },
    profiling: {
      src: "media/data profiling.mp4",
      start: 106,
      duration: 4,
      mediaStart: 18,
      label: "Profile context"
    },
    compare: {
      src: "media/compare tags.mp4",
      start: 110,
      duration: 4,
      mediaStart: 10,
      label: "Sensor comparison"
    },
    graph: {
      src: "media/knowledge graph.mp4",
      start: 114,
      duration: 5,
      mediaStart: 15,
      label: "Knowledge graph context"
    }
  },
  segments: [
    { id: "opening", start: 0, duration: 10, subtitle: "Telemetry incidents become governed AI investigations." },
    { id: "use-case", start: 10, duration: 16, subtitle: "Bad telemetry, or a real operating event?" },
    { id: "data-setup", start: 26, duration: 16, subtitle: "Simulated telemetry flows into governed lakehouse tables." },
    { id: "queue", start: 42, duration: 13, subtitle: "Start from the incident queue." },
    { id: "detail", start: 55, duration: 22, subtitle: "Inspect the failed window and raw signal." },
    { id: "ai", start: 77, duration: 18, subtitle: "AI reasoning connects evidence with process context." },
    { id: "feedback", start: 95, duration: 11, subtitle: "Feedback becomes governed review evidence." },
    { id: "context-flash", start: 106, duration: 13, subtitle: "Profiles, comparisons, and graph context support investigation." },
    { id: "data-app-loop", start: 119, duration: 22, subtitle: "Governed telemetry powers the app workflow." },
    { id: "multi-agent", start: 141, duration: 36, subtitle: "Supervisor Agent coordinates specialist evidence paths." },
    { id: "knowledge-loop", start: 177, duration: 31, subtitle: "Reviewed feedback can enrich future graph knowledge." },
    { id: "impact", start: 208, duration: 20, subtitle: "Faster triage. Reusable knowledge. Trusted model inputs." }
  ]
};
```

- [ ] **Step 3: Commit media manifest**

Run:

```powershell
Set-Location C:\tmp\geosight-ai-demo-video
git add scripts\sequence.js
git commit -m "feat: define video sequence timing"
```

Expected:

```text
[main ...] feat: define video sequence timing
```

---

### Task 3: Define Visual Identity

**Files:**
- Create: `C:\tmp\geosight-ai-demo-video\DESIGN.md`

- [ ] **Step 1: Write visual identity**

Create `C:\tmp\geosight-ai-demo-video\DESIGN.md`:

```markdown
# GeoSight AI Video Design

## Style Prompt

Build a clean Databricks Cloud architecture demo video on a dark technical canvas. The video should feel like a continuous hackathon demo: real application recordings are the proof layer, while architecture cards and animated flows explain the system around the app. Avoid generic industrial stock footage, glossy 3D visuals, cluttered full-system diagrams, and over-promotional language.

## Colors

- Canvas: `#080B10`
- Panel: `#111722`
- Muted panel: `#1A202C`
- Text: `#F8FAFC`
- Muted text: `#94A3B8`
- Databricks accent: `#FF3621`
- Data flow cyan: `#58D7FF`
- Graph flow green: `#66E6B1`
- Agent flow purple: `#A78BFA`
- Feedback flow pink: `#F472B6`

## Typography

- Primary: `Inter`
- Numeric / code labels: `JetBrains Mono`

## What NOT To Do

- Do not show the full architecture diagram as a static dense slide.
- Do not use generic stock footage.
- Do not mention or display real station names.
- Do not claim automatic knowledge graph updates.
- Do not use one-color neon gradients or decorative blobs.
```

- [ ] **Step 2: Commit design file**

Run:

```powershell
Set-Location C:\tmp\geosight-ai-demo-video
git add DESIGN.md
git commit -m "docs: add video visual identity"
```

Expected:

```text
[main ...] docs: add video visual identity
```

---

### Task 4: Write Final English Narration Source

**Files:**
- Create: `C:\tmp\geosight-ai-demo-video\narration\narration.txt`

- [ ] **Step 1: Create narration script**

Create `C:\tmp\geosight-ai-demo-video\narration\narration.txt`:

```text
This is GeoSight AI, built by team alpha-2 for geothermal station telemetry intelligence.

It turns raw telemetry incidents into governed investigations, with evidence, process context, and AI-assisted reasoning in one workflow.

Forecasting and generation optimisation depend on trusted sensor data.

But when telemetry breaks, the first question is not just what changed.

It is whether the signal is bad data, or a real operating event.

In this demo, we use simulated noisy geothermal station telemetry.

That keeps the workflow realistic, while sensitive operational data stays protected.

The telemetry is applied into governed lakehouse tables, where it becomes the foundation for monitoring, review, and AI investigation.

GeoSight AI starts where a data scientist starts: the incident queue.

The app surfaces failed monitor windows, affected tags, rule types, incident windows, and review status.

Opening the selected incident brings the rule, failed windows, quality logs, and raw telemetry context into one review surface.

Here, the pattern matters.

The signal drops, stays flat, and then restarts with a transient spike.

That is the shape of a process event that deserves investigation, not just a row in an anomaly table.

The AI draft analysis connects governed evidence with process context.

The goal is not only to summarize the anomaly.

It is to help judge whether the incident is telemetry noise, a rule problem, or a credible process pattern.

For this incident, the draft points toward a real equipment shutdown and restart pattern, rather than a simple data quality issue.

The data scientist still stays in control.

They can submit review feedback directly from the app.

That judgement becomes governed review evidence instead of staying trapped in a conversation.

The app also provides profile views, sensor comparison, and knowledge graph context when the investigation needs more evidence.

Behind the app, GeoSight AI uses a multi-agent investigation architecture.

The front end sends incident context to a Supervisor Agent.

The Supervisor coordinates specialist paths for graph retrieval, incident reasoning, and governed data evidence.

One path retrieves process context from the knowledge graph.

One path reasons about the incident pattern.

One path checks governed telemetry evidence through Databricks data access.

The Supervisor evaluates those findings and synthesizes an investigation draft for the data scientist.

The feedback loop is the second important part.

Each reviewed comment can become more than a one-off note.

It can become a knowledge candidate: an incident pattern, a tag relationship, a process context note, or a reviewed diagnosis.

After review, those candidates can enrich the knowledge graph over time.

That makes future retrieval, tag selection, and agent reasoning more aligned with how the team actually investigates geothermal station telemetry issues.

GeoSight AI reduces manual triage, captures operational judgement, and makes future investigations more reusable and auditable.

The result is stronger trust in telemetry inputs for forecasting, optimisation, and data science workflows.
```

- [ ] **Step 2: Commit narration source**

Run:

```powershell
Set-Location C:\tmp\geosight-ai-demo-video
git add narration\narration.txt
git commit -m "docs: add narration script"
```

Expected:

```text
[main ...] docs: add narration script
```

---

### Task 5: Generate AI Narration Audio

**Files:**
- Create: `C:\tmp\geosight-ai-demo-video\narration\narration.wav`

- [ ] **Step 1: List available voices**

Run:

```powershell
Set-Location C:\tmp\geosight-ai-demo-video
npx hyperframes tts --list
```

Expected: command prints supported voices. Pick `bf_emma` if present because it is a clear professional English voice. If `bf_emma` is absent, pick `af_nova`.

- [ ] **Step 2: Generate narration**

Run:

```powershell
Set-Location C:\tmp\geosight-ai-demo-video
npx hyperframes tts narration\narration.txt --voice bf_emma --output narration\narration.wav
```

Expected:

```text
narration\narration.wav
```

- [ ] **Step 3: Check duration**

Run:

```powershell
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 narration\narration.wav
```

Expected: duration is between `210` and `235` seconds. If duration is below `210`, regenerate with a slightly slower voice speed if HyperFrames exposes speed. If duration is above `235`, remove one sentence from the optional context paragraph and regenerate.

- [ ] **Step 4: Commit narration audio**

Run:

```powershell
Set-Location C:\tmp\geosight-ai-demo-video
git add narration\narration.wav
git commit -m "feat: generate narration audio"
```

Expected:

```text
[main ...] feat: generate narration audio
```

---

### Task 6: Implement The Root Composition

**Files:**
- Modify: `C:\tmp\geosight-ai-demo-video\index.html`
- Read: `C:\tmp\geosight-ai-demo-video\scripts\sequence.js`

- [ ] **Step 1: Replace `index.html` with the composition shell**

Write `C:\tmp\geosight-ai-demo-video\index.html`:

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>GeoSight AI Demo Video</title>
  <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
  <script src="scripts/sequence.js"></script>
  <style>
    * { box-sizing: border-box; }
    body { margin: 0; background: #080B10; font-family: Inter, ui-sans-serif, system-ui, sans-serif; color: #f8fafc; }
    [data-composition-id="geosight-demo"] {
      position: relative;
      overflow: hidden;
      width: 1920px;
      height: 1080px;
      background: #080B10;
    }
    .scene {
      position: absolute;
      inset: 0;
      opacity: 0;
      padding: 76px 96px;
      display: flex;
      flex-direction: column;
      justify-content: center;
      gap: 28px;
    }
    .scene.active { opacity: 1; }
    .eyebrow { color: #ff6b5b; font: 700 20px/1.2 Inter, sans-serif; letter-spacing: 0; }
    .headline { max-width: 1180px; font: 760 76px/1.02 Inter, sans-serif; letter-spacing: 0; margin: 0; }
    .copy { max-width: 980px; color: #cbd5e1; font: 500 31px/1.38 Inter, sans-serif; margin: 0; }
    .card-row { display: flex; gap: 22px; align-items: stretch; flex-wrap: wrap; }
    .arch-card {
      min-width: 240px;
      max-width: 340px;
      border: 1px solid rgba(148, 163, 184, 0.28);
      background: #111722;
      border-radius: 8px;
      padding: 24px;
      box-shadow: 0 18px 50px rgba(0, 0, 0, 0.22);
    }
    .arch-card .label { font: 760 28px/1.1 Inter, sans-serif; }
    .arch-card .sub { margin-top: 10px; color: #94a3b8; font: 520 18px/1.3 Inter, sans-serif; }
    .flow { height: 4px; width: 96px; align-self: center; border-radius: 999px; background: #58d7ff; position: relative; }
    .flow::after { content: ""; position: absolute; right: -10px; top: -6px; border-left: 14px solid currentColor; border-top: 8px solid transparent; border-bottom: 8px solid transparent; color: #58d7ff; }
    .video-wrap {
      position: absolute;
      inset: 78px 118px 100px 118px;
      border: 1px solid rgba(148, 163, 184, 0.24);
      border-radius: 8px;
      overflow: hidden;
      background: #05070a;
      box-shadow: 0 25px 80px rgba(0, 0, 0, 0.38);
    }
    .video-wrap video { width: 100%; height: 100%; object-fit: cover; display: block; }
    .overlay-label {
      position: absolute;
      left: 146px;
      top: 104px;
      z-index: 5;
      border: 1px solid rgba(255, 54, 33, 0.45);
      background: rgba(17, 23, 34, 0.86);
      color: #f8fafc;
      border-radius: 6px;
      padding: 12px 16px;
      font: 740 20px/1.2 Inter, sans-serif;
    }
    .mask {
      position: absolute;
      z-index: 4;
      background: #111722;
      border-radius: 4px;
      border: 1px solid rgba(148, 163, 184, 0.12);
    }
    .subtitle {
      position: absolute;
      left: 96px;
      bottom: 46px;
      z-index: 20;
      max-width: 1120px;
      border-left: 5px solid #ff3621;
      background: rgba(8, 11, 16, 0.84);
      padding: 14px 20px 16px;
      color: #f8fafc;
      font: 720 30px/1.18 Inter, sans-serif;
      letter-spacing: 0;
    }
    .node-grid { display: grid; grid-template-columns: repeat(3, minmax(260px, 1fr)); gap: 26px; max-width: 1180px; }
    .node { border: 1px solid rgba(167,139,250,0.36); background: #111722; border-radius: 8px; padding: 26px; min-height: 128px; }
    .node strong { display: block; font-size: 28px; }
    .node span { display: block; color: #94a3b8; font-size: 19px; margin-top: 8px; line-height: 1.28; }
    .loop-ring {
      position: absolute;
      width: 700px;
      height: 700px;
      right: 120px;
      top: 185px;
      border: 3px dashed rgba(244,114,182,0.65);
      border-radius: 50%;
    }
  </style>
</head>
<body>
  <div data-composition-id="geosight-demo" data-width="1920" data-height="1080">
    <audio id="narration" data-start="0" data-duration="228" data-track-index="9" src="narration/narration.wav" data-volume="1"></audio>

    <div class="scene" id="opening" data-start="0" data-duration="10" data-track-index="1">
      <div class="eyebrow">TEAM ALPHA-2</div>
      <h1 class="headline">GeoSight AI</h1>
      <p class="copy">A multi-agent telemetry intelligence system for geothermal station operations.</p>
      <div class="card-row">
        <div class="arch-card"><div class="label">Telemetry incidents</div><div class="sub">monitor failures that need review</div></div>
        <div class="flow"></div>
        <div class="arch-card"><div class="label">AI investigation</div><div class="sub">evidence, context, and reasoning</div></div>
        <div class="flow"></div>
        <div class="arch-card"><div class="label">Knowledge loop</div><div class="sub">reviewed feedback for future improvement</div></div>
      </div>
    </div>

    <div class="scene" id="use-case" data-start="10" data-duration="16" data-track-index="1">
      <div class="eyebrow">USE CASE</div>
      <h2 class="headline">When telemetry breaks, the question is judgement.</h2>
      <p class="copy">Forecasting and optimisation need trusted inputs. The hard part is deciding whether an incident is bad data or a real operating event.</p>
    </div>

    <div class="scene" id="data-setup" data-start="26" data-duration="16" data-track-index="1">
      <div class="eyebrow">DATA SETUP</div>
      <h2 class="headline">Simulated noisy telemetry. Governed review workflow.</h2>
      <div class="card-row">
        <div class="arch-card"><div class="label">Telemetry</div><div class="sub">sensor signals</div></div>
        <div class="flow"></div>
        <div class="arch-card"><div class="label">Lakeflow</div><div class="sub">streaming pipelines</div></div>
        <div class="flow"></div>
        <div class="arch-card"><div class="label">Unity Catalog</div><div class="sub">governed telemetry tables</div></div>
      </div>
    </div>

    <div id="video-stage"></div>

    <div class="scene" id="data-app-loop" data-start="119" data-duration="22" data-track-index="1">
      <div class="eyebrow">DATA + APP LOOP</div>
      <h2 class="headline">Governed telemetry powers the review surface.</h2>
      <div class="card-row">
        <div class="arch-card"><div class="label">Telemetry</div><div class="sub">simulated noisy stream</div></div>
        <div class="flow"></div>
        <div class="arch-card"><div class="label">Lakehouse</div><div class="sub">incident, profile, and sensor tables</div></div>
        <div class="flow"></div>
        <div class="arch-card"><div class="label">GeoSight AI App</div><div class="sub">data scientist review workflow</div></div>
      </div>
    </div>

    <div class="scene" id="multi-agent" data-start="141" data-duration="36" data-track-index="1">
      <div class="eyebrow">MULTI-AGENT INVESTIGATION</div>
      <h2 class="headline">The Supervisor Agent coordinates specialist evidence paths.</h2>
      <div class="node-grid">
        <div class="node"><strong>Graph assistant</strong><span>retrieves process context and related tag relationships</span></div>
        <div class="node"><strong>Incident analysis</strong><span>forms the initial process-aware investigation</span></div>
        <div class="node"><strong>DBA evidence agent</strong><span>checks governed telemetry evidence through Databricks access</span></div>
      </div>
    </div>

    <div class="scene" id="knowledge-loop" data-start="177" data-duration="31" data-track-index="1">
      <div class="eyebrow">FEEDBACK KNOWLEDGE LOOP</div>
      <h2 class="headline">Reviewed comments can become future graph knowledge.</h2>
      <p class="copy">Feedback becomes governed review evidence, then knowledge candidates: incident patterns, tag relationships, context notes, and reviewed diagnoses.</p>
      <div class="loop-ring"></div>
    </div>

    <div class="scene" id="impact" data-start="208" data-duration="20" data-track-index="1">
      <div class="eyebrow">IMPACT</div>
      <h2 class="headline">Faster triage. Reusable knowledge. Trusted model inputs.</h2>
      <p class="copy">GeoSight AI captures operational judgement and makes future investigations more reusable, auditable, and aligned with real workflows.</p>
    </div>

    <div class="subtitle" id="subtitle"></div>
  </div>

  <script>
    window.__timelines = window.__timelines || {};
    const seq = window.GEOSIGHT_SEQUENCE;
    const root = document.querySelector('[data-composition-id="geosight-demo"]');
    const stage = document.getElementById("video-stage");

    Object.entries(seq.clips).forEach(([id, clip]) => {
      const wrap = document.createElement("div");
      wrap.className = `video-wrap clip-${id}`;
      wrap.id = `clip-${id}`;
      wrap.setAttribute("data-start", String(clip.start));
      wrap.setAttribute("data-duration", String(clip.duration));
      wrap.setAttribute("data-track-index", "2");
      wrap.innerHTML = `<video src="${clip.src}" data-media-start="${clip.mediaStart}" muted playsinline></video><div class="overlay-label">${clip.label}</div>`;
      stage.appendChild(wrap);
    });

    const subtitles = seq.segments.map((segment) => ({
      start: segment.start,
      end: segment.start + segment.duration,
      text: segment.subtitle
    }));

    const tl = gsap.timeline({ paused: true });

    document.querySelectorAll(".scene").forEach((scene) => {
      const start = Number(scene.dataset.start);
      const duration = Number(scene.dataset.duration);
      tl.set(scene, { opacity: 1 }, start);
      tl.from(scene.querySelectorAll(".eyebrow, .headline, .copy, .arch-card, .node, .loop-ring"), {
        y: 34,
        opacity: 0,
        stagger: 0.08,
        duration: 0.7,
        ease: "power3.out"
      }, start + 0.2);
      tl.set(scene, { opacity: 0 }, start + duration);
    });

    Object.values(seq.clips).forEach((clip) => {
      tl.from(`#clip-${Object.keys(seq.clips).find((key) => seq.clips[key] === clip)}`, {
        opacity: 0,
        y: 28,
        duration: 0.45,
        ease: "power2.out"
      }, clip.start + 0.1);
    });

    subtitles.forEach((item, index) => {
      tl.set("#subtitle", { textContent: item.text, opacity: 1 }, item.start + 0.15);
      if (index < subtitles.length - 1) {
        tl.set("#subtitle", { opacity: 0 }, item.end - 0.25);
      }
    });

    tl.to("#subtitle", { opacity: 0, duration: 0.4, ease: "power2.in" }, seq.totalDuration - 0.6);
    window.__timelines["geosight-demo"] = tl;
  </script>
</body>
</html>
```

- [ ] **Step 2: Run lint**

Run:

```powershell
Set-Location C:\tmp\geosight-ai-demo-video
npx hyperframes lint
```

Expected:

```text
No errors
```

- [ ] **Step 3: Commit composition shell**

Run:

```powershell
Set-Location C:\tmp\geosight-ai-demo-video
git add index.html
git commit -m "feat: add root video composition"
```

Expected:

```text
[main ...] feat: add root video composition
```

---

### Task 7: Add Sensitive Information Masks And App Recording Polish

**Files:**
- Modify: `C:\tmp\geosight-ai-demo-video\index.html`

- [ ] **Step 1: Add mask overlays for source table and log identifiers**

In `index.html`, update the `Object.entries(seq.clips).forEach` block to include masks for the queue and detail clips:

```js
const masks = {
  queue: '<div class="mask" style="left:342px;top:374px;width:214px;height:28px;"></div>',
  detail: '<div class="mask" style="left:18px;top:185px;width:170px;height:176px;"></div><div class="mask" style="left:26px;bottom:114px;width:210px;height:26px;"></div>',
  ai: '<div class="mask" style="left:26px;bottom:114px;width:210px;height:26px;"></div>'
};

Object.entries(seq.clips).forEach(([id, clip]) => {
  const wrap = document.createElement("div");
  wrap.className = `video-wrap clip-${id}`;
  wrap.id = `clip-${id}`;
  wrap.setAttribute("data-start", String(clip.start));
  wrap.setAttribute("data-duration", String(clip.duration));
  wrap.setAttribute("data-track-index", "2");
  wrap.innerHTML = `<video src="${clip.src}" data-media-start="${clip.mediaStart}" muted playsinline></video><div class="overlay-label">${clip.label}</div>${masks[id] || ""}`;
  stage.appendChild(wrap);
});
```

This masks obvious source table and log identifier areas while preserving the visible product workflow.

- [ ] **Step 2: Run visual inspect**

Run:

```powershell
Set-Location C:\tmp\geosight-ai-demo-video
npx hyperframes inspect --samples 12
```

Expected: no text overflow errors. If the mask overlays cover important chart labels, reduce their width by `40px` and rerun the same command.

- [ ] **Step 3: Commit masking changes**

Run:

```powershell
Set-Location C:\tmp\geosight-ai-demo-video
git add index.html
git commit -m "fix: mask sensitive app recording identifiers"
```

Expected:

```text
[main ...] fix: mask sensitive app recording identifiers
```

---

### Task 8: Strengthen Architecture Animation

**Files:**
- Create: `C:\tmp\geosight-ai-demo-video\scripts\architecture-data.js`
- Modify: `C:\tmp\geosight-ai-demo-video\index.html`

- [ ] **Step 1: Create architecture data**

Create `scripts\architecture-data.js`:

```js
window.GEOSIGHT_ARCHITECTURE = {
  dataAppLoop: [
    ["Telemetry", "simulated noisy geothermal station sensor stream", "data"],
    ["Lakeflow", "streaming ingestion into the lakehouse", "data"],
    ["Unity Catalog", "governed incident, profile, and feedback tables", "governance"],
    ["SQL Warehouse", "query path for app review and evidence retrieval", "data"],
    ["GeoSight AI App", "incident review and feedback surface", "app"]
  ],
  agents: [
    ["Supervisor Agent", "orchestrates, evaluates, and synthesizes", "agent"],
    ["Graph assistant", "retrieves graph context and related tag relationships", "graph"],
    ["Incident analysis agent", "forms process-aware incident reasoning", "agent"],
    ["DBA evidence agent", "checks governed telemetry evidence", "data"]
  ],
  feedbackLoop: [
    ["Data scientist feedback", "human judgement captured in the app", "feedback"],
    ["Governed review evidence", "stored for review and audit", "governance"],
    ["Knowledge candidates", "incident patterns, tag relationships, context notes", "feedback"],
    ["Knowledge graph enrichment", "reviewed candidates can improve graph context", "graph"],
    ["Future agent reasoning", "better retrieval and tag selection", "agent"]
  ]
};
```

- [ ] **Step 2: Load architecture data**

Add this line after `scripts/sequence.js` in `index.html`:

```html
<script src="scripts/architecture-data.js"></script>
```

- [ ] **Step 3: Replace static architecture cards with generated cards**

Add this script before timeline construction:

```js
function makeCards(containerSelector, rows) {
  const container = document.querySelector(containerSelector);
  container.innerHTML = rows.map(([title, sub, kind], index) => {
    const flow = index === rows.length - 1 ? "" : '<div class="flow"></div>';
    return `<div class="arch-card kind-${kind}"><div class="label">${title}</div><div class="sub">${sub}</div></div>${flow}`;
  }).join("");
}

makeCards("#data-setup .card-row", window.GEOSIGHT_ARCHITECTURE.dataAppLoop.slice(0, 3));
makeCards("#data-app-loop .card-row", window.GEOSIGHT_ARCHITECTURE.dataAppLoop);
```

Update the `multi-agent` section node grid manually to keep the Supervisor prominent:

```html
<div class="node-grid">
  <div class="node"><strong>Supervisor Agent</strong><span>orchestrates specialist paths and synthesizes the answer</span></div>
  <div class="node"><strong>Graph assistant</strong><span>retrieves process context and related tag relationships</span></div>
  <div class="node"><strong>Incident analysis agent</strong><span>forms the process-aware investigation</span></div>
  <div class="node"><strong>DBA evidence agent</strong><span>checks governed telemetry evidence through Databricks access</span></div>
</div>
```

- [ ] **Step 4: Run inspect at architecture timestamps**

Run:

```powershell
Set-Location C:\tmp\geosight-ai-demo-video
npx hyperframes inspect --at 32,130,155,190,216
```

Expected: no text overflow errors and all architecture card labels visible.

- [ ] **Step 5: Commit architecture data**

Run:

```powershell
Set-Location C:\tmp\geosight-ai-demo-video
git add scripts\architecture-data.js index.html
git commit -m "feat: add simplified architecture animation data"
```

Expected:

```text
[main ...] feat: add simplified architecture animation data
```

---

### Task 9: Validate, Preview, And Render

**Files:**
- Output: `C:\tmp\geosight-ai-demo-video\renders\geosight-ai-demo.mp4`

- [ ] **Step 1: Run lint**

Run:

```powershell
Set-Location C:\tmp\geosight-ai-demo-video
npx hyperframes lint
```

Expected:

```text
No errors
```

- [ ] **Step 2: Run visual inspect**

Run:

```powershell
Set-Location C:\tmp\geosight-ai-demo-video
npx hyperframes inspect --samples 18
```

Expected: no layout errors. Contrast warnings on video content can remain only when the text is part of the app recording; all custom overlay text must pass.

- [ ] **Step 3: Preview the project**

Run:

```powershell
Set-Location C:\tmp\geosight-ai-demo-video
npx hyperframes preview --port 3017
```

Expected:

```text
http://localhost:3017/#project/geosight-ai-demo-video
```

Open the URL and verify:

```text
Opening animation appears
App clips play at the expected timestamps
Narration is audible
Subtitles change per segment
No real station name is visible
Architecture appears as three simplified layers
```

- [ ] **Step 4: Render a draft**

Run:

```powershell
Set-Location C:\tmp\geosight-ai-demo-video
npx hyperframes render --output renders\geosight-ai-demo-draft.mp4 --quality draft
```

Expected:

```text
renders\geosight-ai-demo-draft.mp4
```

- [ ] **Step 5: Render the final MP4**

Run:

```powershell
Set-Location C:\tmp\geosight-ai-demo-video
npx hyperframes render --output renders\geosight-ai-demo.mp4 --quality high --fps 30
```

Expected:

```text
renders\geosight-ai-demo.mp4
```

- [ ] **Step 6: Commit final source changes**

Run:

```powershell
Set-Location C:\tmp\geosight-ai-demo-video
git add DESIGN.md index.html scripts narration package.json hyperframes.json
git commit -m "chore: finalize geosight demo video source"
```

Expected:

```text
[main ...] chore: finalize geosight demo video source
```

---

## Self-Review

- Spec coverage: the plan covers real app recordings, concise architecture animation, AI narrator, subtitles, claim boundaries, and sensitive information handling.
- Placeholder scan: no `TBD`, `TODO`, `fill in later`, or unspecified implementation steps remain.
- Type consistency: `GEOSIGHT_SEQUENCE`, `GEOSIGHT_ARCHITECTURE`, scene ids, and clip ids are consistent across tasks.
- Risk: HyperFrames final rendering requires FFmpeg/FFprobe. Task 1 handles that explicitly before render work.
