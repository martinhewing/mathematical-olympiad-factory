path = "src/competitive_programming_factory/routes/voice.py"
lines = open(path).readlines()

# Find start and end of playStageAudio
start = None
end = None
for i, l in enumerate(lines):
    if 'async function playStageAudio(n) {{' in l:
        start = i
    if start and i > start + 2 and (l.strip().startswith('async function') or l.strip().startswith('function ')) and 'playStageAudio' not in l:
        end = i
        break

print(f"Found playStageAudio at lines {start+1}-{end}")

new_fn = """async function playStageAudio(n) {{
  const dot      = document.getElementById('speaking-dot');
  const fill     = document.getElementById('audio-fill');
  const label    = document.getElementById('audio-label');
  const audio    = document.getElementById('stage-audio');
  const playBtn  = document.getElementById('audio-play-btn');

  dot.className    = 'speaking-dot active';
  fill.style.width = '0%';
  label.textContent = '';
  if (playBtn) playBtn.style.display = 'none';

  audio.src = `/session/${{SESSION_ID}}/stage/${{n}}/audio/file`;

  audio.ontimeupdate = () => {{
    if (audio.duration) {{
      fill.style.width = (audio.currentTime / audio.duration * 100) + '%';
      const rem = Math.ceil(audio.duration - audio.currentTime);
      label.textContent = rem + 's';
    }}
  }};

  audio.onended = () => {{
    dot.className    = 'speaking-dot';
    fill.style.width = '100%';
    label.textContent = '';
    if (playBtn) {{ playBtn.textContent = '▶'; playBtn.style.display = 'inline-block'; }}
    enableRecording();
  }};

  audio.onerror = () => {{
    dot.className = 'speaking-dot';
    label.textContent = 'no audio';
    enableRecording();
  }};

  setTimeout(() => {{ if (!audio.ended) enableRecording(); }}, 60000);
  audio.play().catch(() => {{ label.textContent = 'no audio'; enableRecording(); }});
}}

function toggleAudioPlayback() {{
  const audio   = document.getElementById('stage-audio');
  const playBtn = document.getElementById('audio-play-btn');
  const dot     = document.getElementById('speaking-dot');
  if (audio.paused) {{
    audio.play();
    playBtn.textContent = '❙❙';
    dot.className = 'speaking-dot active';
  }} else {{
    audio.pause();
    playBtn.textContent = '▶';
    dot.className = 'speaking-dot';
  }}
}}

"""

new_lines = lines[:start] + [new_fn] + lines[end:]
open(path, "w").writelines(new_lines)
print("Replaced")

import py_compile
try:
    py_compile.compile(path, doraise=True)
    print("✓ Syntax OK")
except py_compile.PyCompileError as e:
    print(f"✗ {e}")
