path = "src/competitive_programming_factory/routes/voice.py"
text = open(path).read()

# Fix 1: Add playedAudio tracker after SESSION_ID
old1 = "  const SESSION_ID = window.location.pathname.split('/')[2];"
new1 = "  const SESSION_ID = window.location.pathname.split('/')[2];\n  const playedAudio = new Set();"

# Fix 2: Skip audio if already played
old2 = "    // Enable record button immediately\n    enableRecording();\n    // Only play audio once per stage+phase combination\n    const audioKey = (stageData.phase || 'interview') + ':' + n;\n    if (!playedAudio.has(audioKey)) {{\n      playedAudio.add(audioKey);\n      playStageAudio(n);\n    }}"

# Check what's actually there
if "enableRecording();" in text and "playStageAudio(n);" in text:
    # find the block after enableRecording
    old2b = "    // Enable record button immediately, audio plays in background\n    enableRecording();\n    // Only play audio once per stage+phase combination\n    const audioKey = (stageData.phase || 'interview') + ':' + n;\n    if (!playedAudio.has(audioKey)) {{\n      playedAudio.add(audioKey);\n      playStageAudio(n);\n    }}"
    old2c = "    enableRecording();\n    playStageAudio(n);"

# Fix 3: Re-enable "Ready for interview" button in backToAlex
old3 = """  btn.disabled = false;
  btn.textContent = '← Alex';
  loadStage(1);"""
new3 = """  btn.disabled = false;
  btn.textContent = '← Alex';
  // Re-enable the handover button
  const readyBtn = document.getElementById('ready-btn');
  if (readyBtn) {{ readyBtn.disabled = false; readyBtn.textContent = 'Ready for interview →'; }}
  loadStage(1);"""

changes = 0

if old1 in text:
    text = text.replace(old1, new1)
    changes += 1
    print("✓ Added playedAudio Set")
else:
    print("✗ SESSION_ID pattern not found")

if old3 in text:
    text = text.replace(old3, new3)
    changes += 1
    print("✓ Fixed backToAlex re-enables handover button")
else:
    print("✗ backToAlex pattern not found")
    for i, l in enumerate(text.splitlines()[1206:1216], 1207):
        print(f"  {i}: {repr(l)}")

# Fix 2: wrap playStageAudio call with playedAudio check
# Find the simple playStageAudio(n) call after enableRecording in loadStage
old2_simple = "    enableRecording();\n    // Play audio in background\n    playStageAudio(n);"
new2_simple = """    enableRecording();
    // Only play audio once per stage+phase
    const audioKey = (stageData.phase || 'interview') + ':' + n;
    if (!playedAudio.has(audioKey)) {{
      playedAudio.add(audioKey);
      playStageAudio(n);
    }}"""

if old2_simple in text:
    text = text.replace(old2_simple, new2_simple)
    changes += 1
    print("✓ Fixed playStageAudio no-replay")
else:
    # try alternate
    for i, l in enumerate(text.splitlines()[912:922], 913):
        print(f"  {i}: {repr(l)}")

open(path, "w").write(text)
print(f"\nTotal changes: {changes}")

import py_compile

try:
    py_compile.compile(path, doraise=True)
    print("✓ Syntax OK")
except py_compile.PyCompileError as e:
    print(f"✗ {e}")
