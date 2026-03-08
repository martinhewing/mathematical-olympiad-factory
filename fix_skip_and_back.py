path = "src/connectionsphere_factory/routes/voice.py"
text = open(path).read()

# Fix 1: deduplicate skip buttons
old1 = "  document.querySelector('.audio-bar').appendChild(skipBtn);"
new1 = "  const oldSkip = document.querySelector('.skip-btn'); if (oldSkip) oldSkip.remove(); skipBtn.className = 'skip-btn'; document.querySelector('.audio-bar').appendChild(skipBtn);"

# Fix 2: backToAlex should reset FSM then reload (use session_id from URL)
old2 = "  loadStage(currentStage);"
new2 = "  loadStage(1);"

if old1 in text:
    text = text.replace(old1, new1)
    print("✓ Fixed skip button dedup")
else:
    print("✗ skip button pattern not found")

# Only replace inside backToAlex - count occurrences
count = text.count(old2)
print(f"  loadStage(currentStage) appears {count} times")
if count == 1:
    text = text.replace(old2, new2)
    print("✓ Fixed backToAlex to loadStage(1)")

open(path, "w").write(text)

import py_compile
try:
    py_compile.compile(path, doraise=True)
    print("✓ Syntax OK")
except py_compile.PyCompileError as e:
    print(f"✗ {e}")
