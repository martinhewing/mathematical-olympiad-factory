path = "src/connectionsphere_factory/routes/voice.py"
lines = open(path).readlines()

# Find the line with generate_tts inside speak_text (no voice_id arg)
for i, l in enumerate(lines):
    if 'await generate_tts(speak_text, save_path=tmp)' in l and 'voice_id' not in l:
        # Insert voice_id resolution before this line and fix the call
        indent = '        '
        lines.insert(i, indent + 'req_voice = payload.get("voice_id", "")\n')
        lines.insert(i+1, indent + 'cfg = _settings()\n')
        lines.insert(i+2, indent + 'use_voice = cfg.cartesia_tutor_voice_id if req_voice == "ALEX_VOICE" else cfg.cartesia_voice_id\n')
        lines[i+3] = lines[i+3].replace(
            'await generate_tts(speak_text, save_path=tmp)',
            'await generate_tts(speak_text, save_path=tmp, voice_id=use_voice)'
        )
        print(f"✓ Fixed at line {i+1}")
        break
else:
    print("✗ Not found")

open(path, "w").writelines(lines)
