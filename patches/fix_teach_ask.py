path = "src/competitive_programming_factory/routes/voice.py"
text = open(path).read()

old = """    const res        = await fetch(`/session/${{SESSION_ID}}/stage/${{currentStage}}/voice`, {{
      method: 'POST',
      body:   form,
    }});"""

new = """    const isTeachPhase = stageData && stageData.phase === 'teach';
    const submitUrl = isTeachPhase
      ? `/session/${{SESSION_ID}}/teach/ask`
      : `/session/${{SESSION_ID}}/stage/${{currentStage}}/voice`;
    const res        = await fetch(submitUrl, {{
      method: 'POST',
      body:   form,
    }});"""

if old in text:
    open(path, "w").write(text.replace(old, new))
    print("Fixed")
else:
    print("Not found — showing /voice fetch lines:")
    for i, l in enumerate(text.splitlines(), 1):
        if "/voice" in l and "fetch" in l:
            for j in range(max(0, i - 3), min(len(text.splitlines()), i + 4)):
                print(f"  {j + 1}: {repr(text.splitlines()[j])}")
            break
