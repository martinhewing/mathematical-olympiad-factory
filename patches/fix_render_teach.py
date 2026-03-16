path = "src/competitive_programming_factory/routes/voice.py"
text = open(path).read()

old = """  panel.innerHTML   = html;
  panel.className   = 'assessment visible';
  const toSpeak = (verdict === 'PARTIAL' && a.probe) ? a.probe : (a.feedback || '').split('.').slice(0,2).join('.') + '.';
  speakResponse(toSpeak);"""

new = """  // During TEACH phase, show as Alex chat reply not Jordan verdict
  if (stageData && stageData.phase === 'teach') {{
    const alexReply = a.probe || a.feedback || '';
    panel.innerHTML = `<div style="font-size:13px;color:#bbb;line-height:1.7;border-left:2px solid var(--accent);padding-left:12px;">${{alexReply}}</div>
      <button class="next-btn" onclick="resetForProbe()" style="margin-top:8px;">Ask another question</button>`;
    panel.className = 'assessment visible';
    speakResponse(alexReply.split('.').slice(0,2).join('.') + '.');
    return;
  }}

  panel.innerHTML   = html;
  panel.className   = 'assessment visible';
  const toSpeak = (verdict === 'PARTIAL' && a.probe) ? a.probe : (a.feedback || '').split('.').slice(0,2).join('.') + '.';
  speakResponse(toSpeak);"""

if old in text:
    open(path, "w").write(text.replace(old, new))
    print("Fixed")
else:
    print("Not found")
    for i, l in enumerate(text.splitlines()[1118:1130], 1119):
        print(f"  {i}: {repr(l)}")
