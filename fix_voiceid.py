path = "src/connectionsphere_factory/routes/voice.py"
text = open(path).read()

old = """    const res  = await fetch(`/session/${{SESSION_ID}}/speak`, {{
      method:  'POST',
      headers: {{'Content-Type': 'application/json'}},
      const voiceId = stageData && stageData.phase === 'teach' ? 'ALEX_VOICE' : '';
      body:    JSON.stringify({{ text: spokenText, voice_id: voiceId }}),
    }});"""

new = """    const voiceId = stageData && stageData.phase === 'teach' ? 'ALEX_VOICE' : '';
    const res  = await fetch(`/session/${{SESSION_ID}}/speak`, {{
      method:  'POST',
      headers: {{'Content-Type': 'application/json'}},
      body:    JSON.stringify({{ text: spokenText, voice_id: voiceId }}),
    }});"""

if old in text:
    open(path, "w").write(text.replace(old, new))
    print("Fixed")
else:
    print("Not found")
