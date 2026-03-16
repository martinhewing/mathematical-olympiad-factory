path = "src/competitive_programming_factory/routes/voice.py"
text = open(path).read()

old = """    // Only play audio once per stage+phase
    const audioKey = (stageData.phase || 'interview') + ':' + n;
    if (!playedAudio.has(audioKey)) {{
      playedAudio.add(audioKey);
      playStageAudio(n);
    }}"""

new = """    // Autoplay once per stage+phase; show play button on revisit
    const audioKey = (stageData.phase || 'interview') + ':' + n;
    const playBtn  = document.getElementById('audio-play-btn');
    if (!playedAudio.has(audioKey)) {{
      playedAudio.add(audioKey);
      playStageAudio(n);
    }} else {{
      // Revisit — preload audio and show play button
      const audio = document.getElementById('stage-audio');
      audio.src   = `/session/${{SESSION_ID}}/stage/${{n}}/audio/file`;
      if (playBtn) {{ playBtn.textContent = '▶'; playBtn.style.display = 'inline-block'; }}
    }}"""

if old in text:
    open(path, "w").write(text.replace(old, new))
    print("Fixed")
else:
    print("Not found")
    for i, l in enumerate(text.splitlines()[920:932], 921):
        print(f"  {i}: {repr(l)}")

import py_compile
try:
    py_compile.compile(path, doraise=True)
    print("✓ Syntax OK")
except py_compile.PyCompileError as e:
    print(f"✗ {e}")
