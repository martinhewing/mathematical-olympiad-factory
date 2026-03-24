path = "src/competitive_programming_factory/routes/voice.py"
text = open(path).read()

old = '        req_voice = payload.get("voice_id", "")\n        cfg = _settings()\n        use_voice = cfg.cartesia_tutor_voice_id if req_voice == "ALEX_VOICE" else cfg.cartesia_voice_id'

new = '        req_voice = payload.get("voice_id", "")\n        from competitive_programming_factory.config import get_settings as _settings\n        cfg = _settings()\n        use_voice = cfg.cartesia_tutor_voice_id if req_voice == "ALEX_VOICE" else cfg.cartesia_voice_id'

if old in text:
    open(path, "w").write(text.replace(old, new))
    print("Fixed")
else:
    # show context
    for i, l in enumerate(text.splitlines()[158:168], 159):
        print(f"  {i}: {repr(l)}")
