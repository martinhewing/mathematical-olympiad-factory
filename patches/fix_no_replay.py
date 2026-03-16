path = "src/competitive_programming_factory/routes/voice.py"
text = open(path).read()

# Add a played-audio tracker after SESSION_ID declaration
old = "  const SESSION_ID = window.location.pathname.split('/')[2];"
new = "  const SESSION_ID = window.location.pathname.split('/')[2];\n  const playedAudio = new Set(); // tracks 'phase:stageN' keys so audio never replays"

# Skip playStageAudio if already played
old2 = "    // Enable record button immediately, audio plays in background\n    enableRecording();\n    // Play audio in background\n    playStageAudio(n);"
new2 = """    // Enable record button immediately
    enableRecording();
    // Only play audio once per stage+phase combination
    const audioKey = (stageData.phase || 'interview') + ':' + n;
    if (!playedAudio.has(audioKey)) {{
      playedAudio.add(audioKey);
      playStageAudio(n);
    }}"""

if old in text:
    text = text.replace(old, new)
    print("✓ Added playedAudio tracker")
else:
    print("✗ SESSION_ID pattern not found")

if old2 in text:
    text = text.replace(old2, new2)
    print("✓ Fixed playStageAudio to skip replays")
else:
    print("✗ playStageAudio pattern not found")
    for i, l in enumerate(text.splitlines()[914:924], 915):
        print(f"  {i}: {repr(l)}")

open(path, "w").write(text)

import py_compile
try:
    py_compile.compile(path, doraise=True)
    print("✓ Syntax OK")
except py_compile.PyCompileError as e:
    print(f"✗ {e}")
