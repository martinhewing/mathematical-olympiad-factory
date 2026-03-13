path = "src/connectionsphere_factory/routes/voice.py"
text = open(path).read()

old = """    if (stageData.phase === 'teach') {
      teachActions.style.display = 'block';
      backBtn.style.display = 'none';
    } else {
      teachActions.style.display = 'none';
      backBtn.style.display = 'inline-block';
    }
    // Play audio — recording enabled after audio ends
    await playStageAudio(n);    enableRecording();

    // Play audio in background
    playStageAudio(n);"""

new = """    if (stageData.phase === 'teach') {{
      teachActions.style.display = 'block';
      backBtn.style.display = 'none';
    }} else {{
      teachActions.style.display = 'none';
      backBtn.style.display = 'inline-block';
    }}
    // Play audio — recording enabled after audio ends
    await playStageAudio(n);"""

if old in text:
    open(path, "w").write(text.replace(old, new))
    print("Fixed")
else:
    print("Not found — showing lines 893-910:")
    for i, l in enumerate(text.splitlines()[892:910], 893):
        print(f"  {i}: {repr(l)}")
