path = "src/connectionsphere_factory/routes/voice.py"
text = open(path).read()

# Fix 1: Replace HTML audio bar with play/pause + progress
old_html = """    <div class="audio-bar">
      <div class="audio-progress">
        <div class="audio-fill" id="audio-fill"></div>
      </div>
      <span class="audio-label" id="audio-label">—</span>
    </div>"""

new_html = """    <div class="audio-bar">
      <button id="audio-play-btn" onclick="toggleAudioPlayback()" style="background:none;border:1px solid var(--border);color:var(--muted);font-family:'DM Mono',monospace;font-size:11px;letter-spacing:0.08em;padding:4px 10px;border-radius:3px;cursor:pointer;min-width:36px;display:none;">▶</button>
      <div class="audio-progress" style="cursor:default;">
        <div class="audio-fill" id="audio-fill"></div>
      </div>
      <span class="audio-label" id="audio-label">—</span>
    </div>"""

# Fix 2: Replace CSS for audio bar
old_css = """.audio-label {{
  font-family: 'DM Mono', monospace;
  font-size: 10px;
  color: var(--muted);
  letter-spacing: 0.08em;
  min-width: 60px;
  text-align: right;
}}"""

new_css = """.audio-label {{
  font-family: 'DM Mono', monospace;
  font-size: 10px;
  color: var(--muted);
  letter-spacing: 0.08em;
  min-width: 48px;
  text-align: right;
}}"""

# Fix 3: Replace playStageAudio function with cleaner version
old_fn = """async function playStageAudio(n) {{
  const dot   = document.getElementById('speaking-dot');
  const fill  = document.getElementById('audio-fill');
  const label = document.getElementById('audio-label');
  const audio = document.getElementById('stage-audio');
  dot.className  = 'speaking-dot active';
  fill.style.width = '0%';
  label.textContent = '▶ playing';
  audio.src = `/session/${{SESSION_ID}}/stage/${{n}}/audio/file`;
  audio.addEventListener('timeupdate', () => {{
    if (audio.duration) {{
      fill.style.width = (audio.currentTime / audio.duration * 100) + '%';
      const rem = Math.ceil(audio.duration - audio.currentTime);
      label.textContent = rem + 's';
    }}
  }}, {{ once: false }});
  audio.addEventListener('ended', () => {{
    dot.className  = 'speaking-dot';
    fill.style.width = '100%';
    label.textContent = '✓ done';
    enableRecording();
    enableRecording();
  }}, {{ once: true }});
  audio.addEventListener('error', () => {{
    dot.className = 'speaking-dot';
    label.textContent = 'no audio';
    enableRecording();
  }}, {{ once: true }});
  const audioFallback = setTimeout(() => enableRecording(), 60000);
  const skipBtn = document.createElement('button');
  skipBtn.textContent = 'skip ›';
  skipBtn.style.cssText = 'background:none;border:none;color:#666;font-size:11px;cursor:pointer;margin-left:8px;font-family:monospace;';
  skipBtn.onclick = () => {{ audio.pause(); clearTimeout(audioFallback); dot.className='speaking-dot'; label.textContent='skipped'; enableRecording(); skipBtn.remove(); }};
  const oldSkip = document.querySelector('.skip-btn'); if (oldSkip) oldSkip.remove(); skipBtn.className = 'skip-btn'; document.querySelector('.audio-bar').appendChild(skipBtn);
  audio.play().catch(() => {{ label.textContent = 'no audio'; enableRecording(); }});
}}"""

new_fn = """async function playStageAudio(n) {{
  const dot      = document.getElementById('speaking-dot');
  const fill     = document.getElementById('audio-fill');
  const label    = document.getElementById('audio-label');
  const audio    = document.getElementById('stage-audio');
  const playBtn  = document.getElementById('audio-play-btn');

  dot.className    = 'speaking-dot active';
  fill.style.width = '0%';
  label.textContent = '';
  playBtn.style.display = 'none';

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
    playBtn.textContent = '▶';
    playBtn.style.display = 'inline-block';
    enableRecording();
  }};

  audio.onerror = () => {{
    dot.className = 'speaking-dot';
    label.textContent = 'no audio';
    playBtn.style.display = 'none';
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
}}"""

changes = 0
for old, new, label in [
    (old_html, new_html, "HTML audio bar"),
    (old_css, new_css, "CSS audio label"),
    (old_fn, new_fn, "playStageAudio function"),
]:
    if old in text:
        text = text.replace(old, new)
        changes += 1
        print(f"✓ Fixed {label}")
    else:
        print(f"✗ Not found: {label}")

open(path, "w").write(text)
print(f"\nChanges: {changes}/3")

import py_compile
try:
    py_compile.compile(path, doraise=True)
    print("✓ Syntax OK")
except py_compile.PyCompileError as e:
    print(f"✗ {e}")
