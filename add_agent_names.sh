#!/usr/bin/env bash
# add_agent_names.sh
#
# Adds tutor (Alex) and interviewer (Jordan) names to:
#   1. session_engine.get_state()  — adds agent_name + agent_role to every state response
#   2. interview_page route        — passes agent_name into _interview_html
#   3. _interview_html             — renders name in left panel header
#   4. loadStage JS                — swaps name live when FSM state changes
#
# Run from project root:  bash add_agent_names.sh

set -euo pipefail

echo "══════════════════════════════════════════"
echo " ConnectionSphere — Agent Names"
echo "══════════════════════════════════════════"

# ── 1. session_engine.py — add agent_name + agent_role to get_state() ─────────
python3 - << 'PYEOF'
path = "src/connectionsphere_factory/engine/session_engine.py"
text = open(path).read()

if "agent_name" in text:
    print("session_engine.py already has agent_name — skipping")
else:
    # Add import at top alongside other domain imports
    text = text.replace(
        "from connectionsphere_factory.domain.fsm.states import State",
        "from connectionsphere_factory.domain.fsm.states import State\n"
        "from connectionsphere_factory.domain.agents import get_agent_for_state",
    )

    # Inject agent_name and agent_role into the get_state() return dict
    text = text.replace(
        '        "progress":            fsm.context.progress_summary,\n    }',
        '        "progress":            fsm.context.progress_summary,\n'
        '        "agent_name":          get_agent_for_state(fsm.state.value).display_name,\n'
        '        "agent_role":          get_agent_for_state(fsm.state.value).role_label,\n'
        '    }',
    )

    open(path, "w").write(text)
    print("✓  session_engine.py updated — agent_name + agent_role added to get_state()")
PYEOF

# ── 2. routes/voice.py — pass agent_name into interview_page + _interview_html ─
python3 - << 'PYEOF'
path = "src/connectionsphere_factory/routes/voice.py"
text = open(path).read()

if "agent_name" in text:
    print("routes/voice.py already has agent_name — skipping")
else:
    # Patch interview_page() to extract agent_name from state and pass it in
    text = text.replace(
        "    return HTMLResponse(content=_interview_html(\n"
        "        session_id = session_id,\n"
        "        problem    = problem,\n"
        "        name       = name,\n"
        "        scene      = scene.get(\"scene\", \"\"),\n"
        "        fsm_state  = state[\"fsm_state\"],\n"
        "        phase      = state[\"phase\"],\n"
        "    ))",
        "    agent_name = state.get(\"agent_name\", \"Interviewer\")\n"
        "    agent_role = state.get(\"agent_role\", \"INTERVIEWER\")\n\n"
        "    return HTMLResponse(content=_interview_html(\n"
        "        session_id = session_id,\n"
        "        problem    = problem,\n"
        "        name       = name,\n"
        "        scene      = scene.get(\"scene\", \"\"),\n"
        "        fsm_state  = state[\"fsm_state\"],\n"
        "        phase      = state[\"phase\"],\n"
        "        agent_name = agent_name,\n"
        "        agent_role = agent_role,\n"
        "    ))",
    )

    # Patch _interview_html signature to accept agent_name + agent_role
    text = text.replace(
        "def _interview_html(session_id, problem, name, scene, fsm_state, phase) -> str:",
        "def _interview_html(session_id, problem, name, scene, fsm_state, phase,\n"
        "                    agent_name=\"Interviewer\", agent_role=\"INTERVIEWER\") -> str:",
    )

    # ── Patch 3a: left panel header — replace hardcoded "Interviewer" label ──
    # Replace the static panel-label span with one that shows the agent name
    text = text.replace(
        '      <span class="panel-label">Interviewer</span>',
        '      <span class="panel-label" id="agent-name-label">{agent_name}</span>\n'
        '      <span class="panel-role" id="agent-role-label">{agent_role}</span>',
    )

    # ── Patch 3b: add .panel-role CSS right after .panel-label CSS ───────────
    text = text.replace(
        ".speaking-dot {{\n"
        "  width: 6px;",
        ".panel-role {{\n"
        "  font-family: 'DM Mono', monospace;\n"
        "  font-size: 9px;\n"
        "  letter-spacing: 0.14em;\n"
        "  text-transform: uppercase;\n"
        "  color: var(--accent);\n"
        "  opacity: 0.7;\n"
        "  margin-left: 6px;\n"
        "}}\n\n"
        ".speaking-dot {{\n"
        "  width: 6px;",
    )

    # ── Patch 3c: inject JS to swap agent name when FSM state changes ─────────
    # Find the loadStage JS function and add agent name update after fsm-badge update
    text = text.replace(
        "document.getElementById('fsm-badge').textContent = s.fsm_state;",
        "document.getElementById('fsm-badge').textContent = s.fsm_state;\n"
        "    if (s.agent_name) {{\n"
        "      document.getElementById('agent-name-label').textContent = s.agent_name;\n"
        "      document.getElementById('agent-role-label').textContent = s.agent_role || '';\n"
        "    }}",
    )

    open(path, "w").write(text)
    print("✓  routes/voice.py updated — agent names in UI + live JS swap")
PYEOF

# ── 3. schemas.py — add agent_name + agent_role to StateResponse ──────────────
python3 - << 'PYEOF'
import os, re
path = "src/connectionsphere_factory/models/schemas.py"
if not os.path.exists(path):
    print(f"⚠  {path} not found — skipping schema update")
else:
    text = open(path).read()
    if "agent_name" in text:
        print("schemas.py already has agent_name — skipping")
    else:
        # Add fields to StateResponse — find the class and append before the closing
        text = re.sub(
            r'(class StateResponse[^:]*:.*?)(requires_voice\s*:\s*bool)',
            r'\1requires_voice: bool\n    agent_name:     str = ""\n    agent_role:     str = ""',
            text,
            flags=re.DOTALL,
            count=1,
        )
        open(path, "w").write(text)
        print("✓  schemas.py updated — agent_name + agent_role in StateResponse")
PYEOF

echo ""
echo "══════════════════════════════════════════"
echo " Done. Changes made:"
echo ""
echo "  session_engine.py  — get_state() now returns agent_name + agent_role"
echo "  routes/voice.py    — interview_page passes agent into HTML"
echo "                     — left panel shows 'Alex' or 'Jordan' + role badge"
echo "                     — JS swaps name live on FSM state change"
echo "  schemas.py         — StateResponse has agent_name + agent_role fields"
echo ""
echo "  TEACH phase        → 'Alex'   + 'TUTOR'       (accent-coloured)"
echo "  All other phases   → 'Jordan' + 'INTERVIEWER'"
echo "══════════════════════════════════════════"
