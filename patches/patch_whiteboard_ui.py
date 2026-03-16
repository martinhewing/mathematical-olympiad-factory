"""
patch_whiteboard_ui.py

Run from the connectionsphere-factory repo root:
    python3 patch_whiteboard_ui.py

What this patch does
────────────────────
C) UI changes — whiteboard conditional activation

Three triggers activate the whiteboard:

  TRIGGER A — Alex comprehension check
    When stageData.comprehension_check_mode === 'drawing',
    Alex is asking the candidate to sketch their understanding.
    The whiteboard opens automatically after the question loads.
    Submission is gated: submit button disabled until ≥1 diagram uploaded.

  TRIGGER B — Jordan probe response
    When the assessment JSON from stage/voice includes diagram_request.required,
    Jordan has explicitly asked for a diagram.
    The whiteboard opens. Submit is gated until ≥1 diagram uploaded.

  TRIGGER C — Teach phase reference diagram
    When stageData.phase === 'teach' and stageData.concept_id exists,
    the reference SVG is fetched and shown inline in the whiteboard panel
    as a visual anchor for the candidate before they draw.

UI changes
──────────
• Whiteboard panel is HIDDEN by default (display:none via CSS)
• .whiteboard.active → slides in with a smooth transition
• New .whiteboard-banner — coloured prompt strip above the drop zone
  - Neutral (--accent colour) for Alex: "Sketch this for me"
  - Warning (--partial colour) for Jordan: "Draw it out"
  - Required (--danger colour) if diagram required + no diagram yet
• .whiteboard-required state on the panel + record-btn dimming
• Reference diagram slot: .whiteboard-reference shows the SVG inline
• Rubric checklist rendered in the assessment panel after Jordan evaluates
  a candidate diagram

JS additions
────────────
• State vars: diagramRequired, diagramRequiredBy, currentRubric,
  referenceConceptId
• activateWhiteboard(opts) — opens panel, sets banner, optionally loads ref SVG
• deactivateWhiteboard()   — closes panel, resets state
• updateSubmitGate()       — enables/disables record button based on
                             diagramRequired + thumb count
• loadReferenceDiagram(conceptId) — fetches SVG from /concept/{id}/diagram
  and injects it into .whiteboard-reference
• renderRubric(rubric, scores) — renders checklist in assessment panel
  after diagram evaluation

Patches applied (4 total)
──────────────────────────
1. CSS  — new whiteboard states + banner + reference slot + rubric styles
2. HTML — whiteboard markup extended with banner + reference slot
3. JS globals + whiteboard functions (inserted before Boot comment)
4. loadStage — add whiteboard activation for Alex drawing mode
5. renderAssessment — add diagram_request handling + rubric rendering
6. submitAudio — add drawing requirement gate
7. handleWhiteboardUpload — call updateSubmitGate after add/delete
"""

import pathlib
import py_compile
import sys
import tempfile
import os

VOICE = pathlib.Path("src/competitive_programming_factory/routes/voice.py")

if not VOICE.exists():
    sys.exit(f"ERROR: {VOICE} not found. Run from repo root.")

src      = VOICE.read_text()
original = src
changes  = []


# ═══════════════════════════════════════════════════════════════════════════════
# PATCH 1 — CSS: new whiteboard states, banner, reference slot, rubric
# ═══════════════════════════════════════════════════════════════════════════════

OLD_CSS = """\
.whiteboard {{
  border-top: 1px solid var(--border);
  padding: 10px 16px;
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  min-height: 44px;
}}
.whiteboard-drop {{
  border: 1px dashed var(--border);
  border-radius: 4px;
  padding: 6px 14px;
  cursor: pointer;
  transition: border-color 0.2s;
  flex-shrink: 0;
}}
.whiteboard-drop:hover {{ border-color: var(--accent); }}
.whiteboard-label {{
  font-family: 'DM Mono', monospace;
  font-size: 10px;
  color: var(--muted);
  letter-spacing: 0.1em;
  pointer-events: none;
}}
.whiteboard-thumbs {{ display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }}
.whiteboard-thumb {{
  position: relative; width: 48px; height: 48px;
  border-radius: 3px; overflow: hidden;
  border: 1px solid var(--border); cursor: pointer; flex-shrink: 0;
}}
.whiteboard-thumb img {{ width: 100%; height: 100%; object-fit: cover; display: block; }}"""

NEW_CSS = """\
/* ── Whiteboard panel ────────────────────────────────────────── */
.whiteboard {{
  border-top: 1px solid var(--border);
  display: none;           /* hidden by default — activated by JS */
  flex-direction: column;
  gap: 0;
  overflow: hidden;
  transition: max-height 0.3s ease;
}}
.whiteboard.active {{
  display: flex;
}}

/* Banner — appears above the drop zone when whiteboard is activated */
.whiteboard-banner {{
  padding: 8px 16px;
  font-family: 'DM Mono', monospace;
  font-size: 10px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  display: flex;
  align-items: center;
  gap: 8px;
}}
.whiteboard-banner.mode-alex {{
  background: rgba(88, 166, 255, 0.07);
  border-bottom: 1px solid rgba(88, 166, 255, 0.18);
  color: var(--accent);
}}
.whiteboard-banner.mode-jordan {{
  background: rgba(255, 170, 0, 0.07);
  border-bottom: 1px solid rgba(255, 170, 0, 0.18);
  color: var(--partial);
}}
.whiteboard-banner.mode-required {{
  background: rgba(255, 68, 68, 0.07);
  border-bottom: 1px solid rgba(255, 68, 68, 0.2);
  color: var(--danger);
}}
.whiteboard-banner-dot {{
  width: 5px; height: 5px;
  border-radius: 50%;
  background: currentColor;
  flex-shrink: 0;
  animation: wb-pulse 2s ease-in-out infinite;
}}
@keyframes wb-pulse {{
  0%, 100% {{ opacity: 1; }}
  50%       {{ opacity: 0.35; }}
}}

/* Reference diagram — shown as a small inline preview */
.whiteboard-reference {{
  display: none;
  padding: 10px 16px 4px;
  border-bottom: 1px solid var(--border);
}}
.whiteboard-reference.visible {{
  display: block;
}}
.whiteboard-reference-label {{
  font-family: 'DM Mono', monospace;
  font-size: 9px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 6px;
}}
.whiteboard-reference svg,
.whiteboard-reference img {{
  width: 100%;
  max-height: 160px;
  object-fit: contain;
  border-radius: 4px;
  border: 1px solid var(--border);
  display: block;
}}
.whiteboard-reference-loading {{
  height: 80px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: 'DM Mono', monospace;
  font-size: 10px;
  color: var(--muted);
  letter-spacing: 0.08em;
}}

/* Drop zone + thumbs row */
.whiteboard-controls {{
  padding: 10px 16px;
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  min-height: 44px;
}}
.whiteboard-drop {{
  border: 1px dashed var(--border);
  border-radius: 4px;
  padding: 6px 14px;
  cursor: pointer;
  transition: border-color 0.2s;
  flex-shrink: 0;
}}
.whiteboard-drop:hover {{ border-color: var(--accent); }}
.whiteboard.mode-required .whiteboard-drop {{
  border-color: rgba(255,68,68,0.45);
}}
.whiteboard-label {{
  font-family: 'DM Mono', monospace;
  font-size: 10px;
  color: var(--muted);
  letter-spacing: 0.1em;
  pointer-events: none;
}}
.whiteboard-thumbs {{ display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }}
.whiteboard-thumb {{
  position: relative; width: 48px; height: 48px;
  border-radius: 3px; overflow: hidden;
  border: 1px solid var(--border); cursor: pointer; flex-shrink: 0;
}}
.whiteboard-thumb img {{ width: 100%; height: 100%; object-fit: cover; display: block; }}

/* Record button dimming when diagram is required but not yet provided */
.record-btn.diagram-pending {{
  opacity: 0.35;
  pointer-events: none;
  cursor: not-allowed;
}}
.diagram-gate-hint {{
  font-family: 'DM Mono', monospace;
  font-size: 10px;
  color: var(--danger);
  letter-spacing: 0.06em;
  text-align: center;
  opacity: 0;
  transition: opacity 0.3s;
  margin-top: -20px;
}}
.diagram-gate-hint.visible {{ opacity: 1; }}

/* ── Rubric checklist in assessment panel ────────────────────── */
.rubric-list {{
  display: flex;
  flex-direction: column;
  gap: 5px;
  margin-top: 4px;
}}
.rubric-item {{
  font-family: 'DM Mono', monospace;
  font-size: 11px;
  display: flex;
  align-items: flex-start;
  gap: 8px;
  line-height: 1.5;
}}
.rubric-icon {{
  flex-shrink: 0;
  margin-top: 1px;
  font-size: 11px;
}}
.rubric-icon.present  {{ color: var(--confirm); }}
.rubric-icon.partial  {{ color: var(--partial); }}
.rubric-icon.missing  {{ color: var(--danger); }}
.rubric-icon.unknown  {{ color: var(--muted); }}
.rubric-text {{ color: var(--muted); }}
.rubric-text.required-item {{ color: var(--text); }}"""

if OLD_CSS in src:
    src = src.replace(OLD_CSS, NEW_CSS, 1)
    changes.append("✓ PATCH 1 — CSS: whiteboard states, banner, reference, rubric")
else:
    print("✗ PATCH 1 FAILED — whiteboard CSS block not found")
    sys.exit(1)


# ═══════════════════════════════════════════════════════════════════════════════
# PATCH 2 — HTML: extend whiteboard markup
# ═══════════════════════════════════════════════════════════════════════════════

OLD_HTML = """\
    <div class="whiteboard" id="whiteboard">
      <input type="file" id="whiteboard-input" accept="image/*" multiple style="display:none" onchange="handleWhiteboardUpload(event)">
      <div class="whiteboard-drop" id="whiteboard-drop" onclick="document.getElementById('whiteboard-input').click()">
        <span class="whiteboard-label">+ diagram</span>
      </div>
      <div class="whiteboard-thumbs" id="whiteboard-thumbs"></div>
    </div>"""

NEW_HTML = """\
    <div class="whiteboard" id="whiteboard">
      <!-- Banner: coloured prompt strip, toggled by activateWhiteboard() -->
      <div class="whiteboard-banner mode-alex" id="whiteboard-banner" style="display:none">
        <span class="whiteboard-banner-dot"></span>
        <span id="whiteboard-banner-text">Sketch this out</span>
      </div>

      <!-- Reference diagram: fetched from /concept/{id}/diagram on activation -->
      <div class="whiteboard-reference" id="whiteboard-reference">
        <div class="whiteboard-reference-label">reference diagram</div>
        <div id="whiteboard-reference-inner">
          <div class="whiteboard-reference-loading">loading…</div>
        </div>
      </div>

      <!-- Drop zone + thumbnails -->
      <div class="whiteboard-controls">
        <input type="file" id="whiteboard-input" accept="image/*" multiple style="display:none" onchange="handleWhiteboardUpload(event)">
        <div class="whiteboard-drop" id="whiteboard-drop" onclick="document.getElementById('whiteboard-input').click()">
          <span class="whiteboard-label">+ diagram</span>
        </div>
        <div class="whiteboard-thumbs" id="whiteboard-thumbs"></div>
      </div>
    </div>

    <!-- Gate hint: shown below record button when diagram required but missing -->
    <div class="diagram-gate-hint" id="diagram-gate-hint">upload a diagram to continue</div>"""

if OLD_HTML in src:
    src = src.replace(OLD_HTML, NEW_HTML, 1)
    changes.append("✓ PATCH 2 — HTML: whiteboard markup extended")
else:
    print("✗ PATCH 2 FAILED — whiteboard HTML block not found")
    sys.exit(1)


# ═══════════════════════════════════════════════════════════════════════════════
# PATCH 3 — JS globals + whiteboard functions (before Boot comment)
# ═══════════════════════════════════════════════════════════════════════════════

OLD_BOOT = """\
// ── Boot ─────────────────────────────────────────────────────────
startTimer();
loadStage(1);"""

NEW_BOOT = """\
// ── Whiteboard state ─────────────────────────────────────────────
let diagramRequired    = false;   // true → submit gated until ≥1 thumb
let diagramRequiredBy  = null;    // 'alex' | 'jordan' | null
let currentRubric      = [];      // DrawingRubricItem list from last diagram_request
let referenceConceptId = null;    // concept_id currently shown as reference

// ── Whiteboard: activate ─────────────────────────────────────────
function activateWhiteboard(opts = {{}}) {{
  /*
    opts:
      by        — 'alex' | 'jordan'          (default 'alex')
      required  — bool                        (default false)
      prompt    — string shown in banner      (default by-mode)
      conceptId — string, loads reference SVG (default null)
      rubric    — array of rubric items       (default [])
  */
  const by       = opts.by       || 'alex';
  const required = opts.required || false;
  const conceptId = opts.conceptId || null;
  currentRubric   = opts.rubric  || [];

  const panel  = document.getElementById('whiteboard');
  const banner = document.getElementById('whiteboard-banner');
  const btext  = document.getElementById('whiteboard-banner-text');

  panel.classList.add('active');
  banner.style.display = 'flex';

  // Banner mode class
  banner.className = 'whiteboard-banner mode-' + (required ? 'required' : by);
  panel.classList.toggle('mode-required', required);

  // Banner text
  const defaultPrompts = {{
    alex:   'Sketch this out for me',
    jordan: 'Draw it out — show me the architecture',
  }};
  btext.textContent = opts.prompt || defaultPrompts[by] || 'Upload your diagram';

  // Gate state
  diagramRequired   = required;
  diagramRequiredBy = by;

  // Reference diagram
  if (conceptId && conceptId !== referenceConceptId) {{
    referenceConceptId = conceptId;
    loadReferenceDiagram(conceptId);
  }} else if (!conceptId) {{
    document.getElementById('whiteboard-reference').classList.remove('visible');
  }}

  updateSubmitGate();
}}

// ── Whiteboard: deactivate ────────────────────────────────────────
function deactivateWhiteboard() {{
  const panel  = document.getElementById('whiteboard');
  const banner = document.getElementById('whiteboard-banner');

  panel.classList.remove('active', 'mode-required');
  banner.style.display = 'none';
  document.getElementById('whiteboard-reference').classList.remove('visible');
  document.getElementById('whiteboard-thumbs').innerHTML = '';

  diagramRequired    = false;
  diagramRequiredBy  = null;
  currentRubric      = [];
  referenceConceptId = null;

  updateSubmitGate();
}}

// ── Submit gate: disable record button when diagram required but absent ───────
function updateSubmitGate() {{
  const btn      = document.getElementById('record-btn');
  const hint     = document.getElementById('diagram-gate-hint');
  const thumbs   = document.querySelectorAll('.whiteboard-thumb');
  const hasDrawing = thumbs.length > 0;

  const blocked = diagramRequired && !hasDrawing;

  btn.classList.toggle('diagram-pending', blocked);
  if (hint) hint.classList.toggle('visible', blocked);

  // Also update the banner colour to reflect pending state
  const banner = document.getElementById('whiteboard-banner');
  if (diagramRequired && banner) {{
    banner.className = 'whiteboard-banner mode-' + (blocked ? 'required' : diagramRequiredBy);
  }}
}}

// ── Load reference diagram from /concept/{id}/diagram ────────────
async function loadReferenceDiagram(conceptId) {{
  const refPanel = document.getElementById('whiteboard-reference');
  const inner    = document.getElementById('whiteboard-reference-inner');

  refPanel.classList.add('visible');
  inner.innerHTML = '<div class="whiteboard-reference-loading">loading reference…</div>';

  try {{
    const res = await fetch(`/concept/${{conceptId}}/diagram`);
    if (!res.ok) throw new Error('not found');
    const svg = await res.text();
    inner.innerHTML = svg;
    // Constrain the inline SVG to the panel width
    const svgEl = inner.querySelector('svg');
    if (svgEl) {{
      svgEl.style.width    = '100%';
      svgEl.style.height   = 'auto';
      svgEl.style.maxHeight = '160px';
      svgEl.style.display  = 'block';
    }}
  }} catch (e) {{
    // Non-fatal — hide the reference slot silently
    refPanel.classList.remove('visible');
    inner.innerHTML = '';
  }}
}}

// ── Rubric checklist renderer (called from renderAssessment) ─────
function renderRubric(rubric, scores) {{
  /*
    rubric: array of {{ label, description, required }}
    scores: array of {{ label, status }}  — status: PRESENT | PARTIAL | MISSING
    Returns HTML string for the rubric checklist.
  */
  if (!rubric || rubric.length === 0) return '';

  const scoreMap = {{}};
  (scores || []).forEach(s => {{ scoreMap[s.label] = s.status; }});

  const iconMap = {{
    PRESENT: {{ icon: '✓', cls: 'present' }},
    PARTIAL: {{ icon: '◐', cls: 'partial' }},
    MISSING: {{ icon: '✗', cls: 'missing'  }},
  }};

  const items = rubric.map(item => {{
    const status = scoreMap[item.label] || 'unknown';
    const ic     = iconMap[status] || {{ icon: '○', cls: 'unknown' }};
    const req    = item.required ? ' required-item' : '';
    return `
      <div class="rubric-item">
        <span class="rubric-icon ${{ic.cls}}">${{ic.icon}}</span>
        <span class="rubric-text${{req}}">${{item.label}}${{item.required ? ' *' : ''}}</span>
      </div>`;
  }}).join('');

  return `
    <div class="rubric-list">
      ${{items}}
      <div style="font-family:'DM Mono',monospace;font-size:9px;color:var(--muted);margin-top:4px">
        * required element
      </div>
    </div>`;
}}

// ── Boot ─────────────────────────────────────────────────────────
startTimer();
loadStage(1);"""

if OLD_BOOT in src:
    src = src.replace(OLD_BOOT, NEW_BOOT, 1)
    changes.append("✓ PATCH 3 — JS: whiteboard state vars + functions + boot")
else:
    print("✗ PATCH 3 FAILED — Boot comment not found")
    sys.exit(1)


# ═══════════════════════════════════════════════════════════════════════════════
# PATCH 4 — loadStage: activate whiteboard for Alex drawing mode
# ═══════════════════════════════════════════════════════════════════════════════
# We insert the whiteboard activation check right after stageData is loaded and
# the question is rendered. The check looks at phase + comprehension_check_mode.

OLD_LOAD_STAGE_SCENE = """\
    // Show question + scene based on phase
    const isTeach = (stageData.phase === 'teach');
    qt.innerHTML  = isTeach ? (stageData.comprehension_check || '') : (stageData.opening_question || '');"""

NEW_LOAD_STAGE_SCENE = """\
    // Show question + scene based on phase
    const isTeach = (stageData.phase === 'teach');
    qt.innerHTML  = isTeach ? (stageData.comprehension_check || '') : (stageData.opening_question || '');

    // ── Whiteboard: activate for Alex drawing comprehension check ─────────
    deactivateWhiteboard();  // always reset first on stage load
    if (isTeach && stageData.comprehension_check_mode === 'drawing') {{
      activateWhiteboard({{
        by:        'alex',
        required:  true,
        prompt:    'Sketch this before we move on',
        conceptId: stageData.concept_id || null,
        rubric:    stageData.drawing_rubric || [],
      }});
    }}"""

if OLD_LOAD_STAGE_SCENE in src:
    src = src.replace(OLD_LOAD_STAGE_SCENE, NEW_LOAD_STAGE_SCENE, 1)
    changes.append("✓ PATCH 4 — loadStage: whiteboard activation for Alex drawing mode")
else:
    print("✗ PATCH 4 FAILED — loadStage scene section not found")
    sys.exit(1)


# ═══════════════════════════════════════════════════════════════════════════════
# PATCH 5 — renderAssessment: handle diagram_request + render rubric
# ═══════════════════════════════════════════════════════════════════════════════

OLD_RENDER = """\
  if (verdict === 'PARTIAL' && a.probe) {{
    html += `<div class="probe-text">${{a.probe}}</div>`;
  }}"""

NEW_RENDER = """\
  if (verdict === 'PARTIAL' && a.probe) {{
    html += `<div class="probe-text">${{a.probe}}</div>`;
  }}

  // ── Diagram request: Jordan is asking the candidate to draw ───────────
  if (a.diagram_request && a.diagram_request.required) {{
    const dr = a.diagram_request;
    activateWhiteboard({{
      by:        'jordan',
      required:  true,
      prompt:    dr.prompt || 'Draw the architecture — upload your diagram',
      conceptId: dr.concept_id || null,
      rubric:    dr.rubric   || [],
    }});
  }} else if (a.diagram_request && !a.diagram_request.required) {{
    // Suggested but not mandatory
    activateWhiteboard({{
      by:        'jordan',
      required:  false,
      prompt:    a.diagram_request.prompt || 'Diagrams welcome — upload if you have one',
      conceptId: a.diagram_request.concept_id || null,
      rubric:    a.diagram_request.rubric    || [],
    }});
  }}

  // ── Diagram evaluation rubric (when Jordan scored a submitted drawing) ─
  if (a.diagram_scores && currentRubric.length > 0) {{
    html += renderRubric(currentRubric, a.diagram_scores);
  }} else if (a.diagram_scores && a.diagram_scores.length > 0) {{
    // Rubric not in client state — render scores without labels
    const icons = {{ PRESENT: '✓', PARTIAL: '◐', MISSING: '✗' }};
    const scoreHtml = a.diagram_scores.map(s =>
      `<div class="rubric-item">
         <span class="rubric-icon ${{s.status.toLowerCase()}}">${{icons[s.status] || '○'}}</span>
         <span class="rubric-text">${{s.label}}</span>
       </div>`
    ).join('');
    html += `<div class="rubric-list">${{scoreHtml}}</div>`;
  }}"""

if OLD_RENDER in src:
    src = src.replace(OLD_RENDER, NEW_RENDER, 1)
    changes.append("✓ PATCH 5 — renderAssessment: diagram_request + rubric rendering")
else:
    print("✗ PATCH 5 FAILED — renderAssessment probe-text block not found")
    sys.exit(1)


# ═══════════════════════════════════════════════════════════════════════════════
# PATCH 6 — submitAudio: gate on diagramRequired
# ═══════════════════════════════════════════════════════════════════════════════

OLD_SUBMIT_START = """\
  const blob = new Blob(audioChunks, {{ type: 'audio/webm' }});
  // Attach any whiteboard images
  const thumbImgs = document.querySelectorAll('.whiteboard-thumb img');"""

NEW_SUBMIT_START = """\
  // ── Diagram gate: block submission if drawing is required but not uploaded ─
  if (diagramRequired) {{
    const thumbCount = document.querySelectorAll('.whiteboard-thumb').length;
    if (thumbCount === 0) {{
      updateSubmitGate();   // re-flash the gate hint
      return;               // don't submit
    }}
  }}

  const blob = new Blob(audioChunks, {{ type: 'audio/webm' }});
  // Attach any whiteboard images
  const thumbImgs = document.querySelectorAll('.whiteboard-thumb img');"""

if OLD_SUBMIT_START in src:
    src = src.replace(OLD_SUBMIT_START, NEW_SUBMIT_START, 1)
    changes.append("✓ PATCH 6 — submitAudio: diagram requirement gate")
else:
    print("✗ PATCH 6 FAILED — submitAudio blob creation not found")
    sys.exit(1)


# ═══════════════════════════════════════════════════════════════════════════════
# PATCH 7 — handleWhiteboardUpload: call updateSubmitGate after add + on delete
# ═══════════════════════════════════════════════════════════════════════════════

OLD_UPLOAD = """\
      const del = document.createElement('button');
      del.className = 'thumb-del';
      del.textContent = '✕';
      del.onclick = ev => {{ ev.stopPropagation(); thumb.remove(); }};"""

NEW_UPLOAD = """\
      const del = document.createElement('button');
      del.className = 'thumb-del';
      del.textContent = '✕';
      del.onclick = ev => {{
        ev.stopPropagation();
        thumb.remove();
        updateSubmitGate();   // re-evaluate gate after removal
      }};"""

if OLD_UPLOAD in src:
    src = src.replace(OLD_UPLOAD, NEW_UPLOAD, 1)
    changes.append("✓ PATCH 7a — handleWhiteboardUpload: updateSubmitGate on thumb delete")
else:
    print("✗ PATCH 7a FAILED — thumb delete handler not found")
    sys.exit(1)

# Also call updateSubmitGate after each thumb is added (end of reader.onload)
OLD_UPLOAD_END = """\
      thumb.appendChild(img);
      thumb.appendChild(del);
      thumbs.appendChild(thumb);
    }};
    reader.readAsDataURL(file);"""

NEW_UPLOAD_END = """\
      thumb.appendChild(img);
      thumb.appendChild(del);
      thumbs.appendChild(thumb);
      updateSubmitGate();   // ungate if diagram requirement now satisfied
    }};
    reader.readAsDataURL(file);"""

if OLD_UPLOAD_END in src:
    src = src.replace(OLD_UPLOAD_END, NEW_UPLOAD_END, 1)
    changes.append("✓ PATCH 7b — handleWhiteboardUpload: updateSubmitGate on thumb add")
else:
    print("✗ PATCH 7b FAILED — thumbs.appendChild block not found")
    sys.exit(1)


# ═══════════════════════════════════════════════════════════════════════════════
# PATCH 8 — advanceStage / resetForProbe: deactivate whiteboard on transition
# ═══════════════════════════════════════════════════════════════════════════════

OLD_ADVANCE = """\
function advanceStage(n) {{
  document.getElementById('assessment').className = 'assessment';
  document.getElementById('transcript-preview').className = 'transcript-preview';
  loadStage(n);
}}

function resetForProbe() {{
  document.getElementById('assessment').className = 'assessment';
  document.getElementById('transcript-preview').className = 'transcript-preview';
  enableRecording();
  document.getElementById('record-hint').textContent = 'Answer the follow-up';
}}"""

NEW_ADVANCE = """\
function advanceStage(n) {{
  document.getElementById('assessment').className = 'assessment';
  document.getElementById('transcript-preview').className = 'transcript-preview';
  deactivateWhiteboard();
  loadStage(n);
}}

function resetForProbe() {{
  document.getElementById('assessment').className = 'assessment';
  document.getElementById('transcript-preview').className = 'transcript-preview';
  // Keep whiteboard open on probe — candidate may still be drawing
  // But reset the gate so they can re-answer verbally if the diagram is uploaded
  updateSubmitGate();
  enableRecording();
  document.getElementById('record-hint').textContent = 'Answer the follow-up';
}}"""

if OLD_ADVANCE in src:
    src = src.replace(OLD_ADVANCE, NEW_ADVANCE, 1)
    changes.append("✓ PATCH 8 — advanceStage / resetForProbe: whiteboard lifecycle")
else:
    print("✗ PATCH 8 FAILED — advanceStage block not found")
    sys.exit(1)


# ═══════════════════════════════════════════════════════════════════════════════
# Write + validate
# ═══════════════════════════════════════════════════════════════════════════════

VOICE.write_text(src)

tmp = tempfile.mktemp(suffix=".py")
try:
    pathlib.Path(tmp).write_text(src)
    py_compile.compile(tmp, doraise=True)
    print()
    print("── Patches applied ──────────────────────────────────")
    for c in changes:
        print(" ", c)
    print()
    print(f"✓ voice.py passes Python syntax check ({len(changes)}/8 patches applied)")
    print()
    print("Next steps:")
    print("  1. Add concept_id + drawing_rubric + comprehension_check_mode")
    print("     to the teach_spec returned by get_or_generate_stage()")
    print("  2. Add diagram_request + diagram_scores to AssessmentResponse schema")
    print("  3. Wire diagram_request into assess_submission.j2 prompt")
    print("  4. Register /concept/{id}/diagram route in app.py")
except py_compile.PyCompileError as e:
    print(f"\n✗ SYNTAX ERROR after patching: {e}")
    VOICE.write_text(original)
    print("  voice.py rolled back to original")
    sys.exit(1)
finally:
    if os.path.exists(tmp):
        os.unlink(tmp)
