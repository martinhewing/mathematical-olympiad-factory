path = "src/competitive_programming_factory/routes/voice.py"
text = open(path).read()

old = """function backToAlex() {{
  // Navigate back - reload current stage which will re-enter teach if FSM allows
  // For now just show info — full back-nav requires session reset
  if (confirm('Return to Alex lesson? Your current progress will be saved.')) {{
    window.location.reload();
  }}
}}"""

new = """async function backToAlex() {{
  const btn = document.getElementById('back-to-alex-btn');
  btn.disabled = true;
  btn.textContent = '…';
  try {{
    const audio = document.getElementById('stage-audio');
    try {{ audio.pause(); audio.src = ''; }} catch(e) {{}}
    await fetch(`/session/${{SESSION_ID}}/teach/restart`, {{method:'POST'}});
  }} catch(e) {{}}
  btn.disabled = false;
  btn.textContent = '\u2190 Alex';
  advanceStage(currentStage);
}}"""

if old in text:
    open(path, "w").write(text.replace(old, new))
    print("Fixed voice.py JS")
else:
    print("Not found")
    for i, l in enumerate(text.splitlines()[1168:1180], 1169):
        print(f"  {i}: {repr(l)}")
