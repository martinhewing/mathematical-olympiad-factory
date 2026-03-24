path = "src/competitive_programming_factory/routes/voice.py"
lines = open(path).readlines()

# Find key line numbers
assessment_line = None
audio_line = None
css_right_panel = None
toggle_audio_fn = None

for i, l in enumerate(lines):
    if '<div class="assessment" id="assessment"></div>' in l:
        assessment_line = i
    if '<audio id="stage-audio" style="display:none"></audio>' in l:
        audio_line = i
    if "/* ── Right panel — candidate" in l:
        css_right_panel = i
    if "function toggleAudioPlayback() {{" in l:
        toggle_audio_fn = i

print(
    f"assessment: {assessment_line + 1}, audio: {audio_line + 1}, css: {css_right_panel + 1}, toggleAudio: {toggle_audio_fn + 1}"
)

# 1. Insert whiteboard HTML after assessment div (line assessment_line)
whiteboard_html = """    <div class="whiteboard" id="whiteboard">
      <input type="file" id="whiteboard-input" accept="image/*" multiple style="display:none" onchange="handleWhiteboardUpload(event)">
      <div class="whiteboard-drop" id="whiteboard-drop" onclick="document.getElementById('whiteboard-input').click()">
        <span class="whiteboard-label">+ diagram</span>
      </div>
      <div class="whiteboard-thumbs" id="whiteboard-thumbs"></div>
    </div>
"""
lines.insert(assessment_line + 1, whiteboard_html)

# Re-find audio line after insert
for i, l in enumerate(lines):
    if '<audio id="stage-audio" style="display:none"></audio>' in l:
        audio_line = i
    if "/* ── Right panel — candidate" in l:
        css_right_panel = i
    if "function toggleAudioPlayback() {{" in l:
        toggle_audio_fn = i

# 2. Insert lightbox after audio element
lightbox_html = """<div class="whiteboard-lightbox" id="whiteboard-lightbox" onclick="this.classList.remove('open')">
  <img src="" alt="diagram">
</div>
"""
lines.insert(audio_line + 1, lightbox_html)

# Re-find after second insert
for i, l in enumerate(lines):
    if "/* ── Right panel — candidate" in l:
        css_right_panel = i
    if "function toggleAudioPlayback() {{" in l:
        toggle_audio_fn = i

# 3. Insert CSS before right panel comment
whiteboard_css = """.whiteboard {{
  border-top: 1px solid var(--border);
  padding: 10px 16px;
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  min-height: 44px;
}}
.whiteboard-drop {{
  border: 1px dashed var(--border);
  border-radius: 4px;
  padding: 6px 14px;
  cursor: pointer;
  transition: border-color 0.2s;
  flex-shrink: 0;
}}
.whiteboard-drop:hover {{ border-color: var(--accent); }}
.whiteboard-label {{
  font-family: 'DM Mono', monospace;
  font-size: 10px;
  color: var(--muted);
  letter-spacing: 0.1em;
  pointer-events: none;
}}
.whiteboard-thumbs {{ display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }}
.whiteboard-thumb {{
  position: relative; width: 48px; height: 48px;
  border-radius: 3px; overflow: hidden;
  border: 1px solid var(--border); cursor: pointer; flex-shrink: 0;
}}
.whiteboard-thumb img {{ width: 100%; height: 100%; object-fit: cover; display: block; }}
.whiteboard-thumb .thumb-del {{
  position: absolute; top: 2px; right: 2px;
  background: rgba(0,0,0,0.7); color: var(--muted);
  font-size: 9px; border: none; border-radius: 2px;
  cursor: pointer; padding: 1px 3px; line-height: 1; display: none;
}}
.whiteboard-thumb:hover .thumb-del {{ display: block; }}
.whiteboard-lightbox {{
  display: none; position: fixed; inset: 0;
  background: rgba(0,0,0,0.85); z-index: 1000;
  align-items: center; justify-content: center; cursor: pointer;
}}
.whiteboard-lightbox.open {{ display: flex; }}
.whiteboard-lightbox img {{ max-width: 90vw; max-height: 90vh; border-radius: 4px; object-fit: contain; }}
"""
lines.insert(css_right_panel, whiteboard_css)

# Re-find toggle after third insert
for i, l in enumerate(lines):
    if "function toggleAudioPlayback() {{" in l:
        toggle_audio_fn = i

# 4. Insert JS before toggleAudioPlayback
whiteboard_js = """function handleWhiteboardUpload(event) {{
  const files = Array.from(event.target.files);
  const thumbs = document.getElementById('whiteboard-thumbs');
  files.forEach(file => {{
    const reader = new FileReader();
    reader.onload = e => {{
      const thumb = document.createElement('div');
      thumb.className = 'whiteboard-thumb';
      const img = document.createElement('img');
      img.src = e.target.result;
      img.title = file.name;
      img.onclick = () => openLightbox(e.target.result);
      const del = document.createElement('button');
      del.className = 'thumb-del';
      del.textContent = '✕';
      del.onclick = ev => {{ ev.stopPropagation(); thumb.remove(); }};
      thumb.appendChild(img);
      thumb.appendChild(del);
      thumbs.appendChild(thumb);
    }};
    reader.readAsDataURL(file);
  }});
  event.target.value = '';
}}
function openLightbox(src) {{
  const lb = document.getElementById('whiteboard-lightbox');
  lb.querySelector('img').src = src;
  lb.classList.add('open');
}}
"""
lines.insert(toggle_audio_fn, whiteboard_js)

open(path, "w").writelines(lines)
print("All insertions done")

import py_compile

try:
    py_compile.compile(path, doraise=True)
    print("✓ Syntax OK")
except py_compile.PyCompileError as e:
    print(f"✗ {e}")
