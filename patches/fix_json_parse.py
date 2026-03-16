import re

path = "src/competitive_programming_factory/routes/stages.py"
text = open(path).read()

old = '''    raw = msg.content[0].text.strip()
    try:
        raw2 = raw.strip().lstrip("`").lstrip("json").strip(); reply = json.loads(raw2).get("reply", raw2)
    except Exception:
        reply = raw'''

new = '''    raw = msg.content[0].text.strip()
    try:
        clean = re.sub(r"^```[a-z]*\\s*|\\s*```$", "", raw, flags=re.MULTILINE).strip()
        reply = json.loads(clean).get("reply", clean)
    except Exception:
        reply = re.sub(r"^```[a-z]*\\s*|\\s*```$", "", raw, flags=re.MULTILINE).strip()'''

if old in text:
    # also need to add import re
    if 'import re' not in text[:500]:
        text = text.replace('import anthropic, json', 'import anthropic, json, re')
    open(path, "w").write(text.replace(old, new))
    print("Fixed")
else:
    # try alternate form
    old2 = '''    raw = msg.content[0].text.strip()
    try:
        reply = json.loads(raw).get("reply", raw)
    except Exception:
        reply = raw'''
    if old2 in text:
        text = text.replace('import anthropic, json', 'import anthropic, json, re')
        new2 = '''    raw = msg.content[0].text.strip()
    try:
        clean = re.sub(r"^```[a-z]*\\s*|\\s*```$", "", raw, flags=re.MULTILINE).strip()
        reply = json.loads(clean).get("reply", clean)
    except Exception:
        reply = re.sub(r"^```[a-z]*\\s*|\\s*```$", "", raw, flags=re.MULTILINE).strip()'''
        open(path, "w").write(text.replace(old2, new2))
        print("Fixed alt")
    else:
        print("Not found")
        for i, l in enumerate(text.splitlines()[125:140], 126):
            print(f"  {i}: {repr(l)}")
