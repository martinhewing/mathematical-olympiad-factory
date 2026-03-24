path = "src/competitive_programming_factory/routes/stages.py"
lines = open(path).readlines()

for i, l in enumerate(lines):
    if 'concept_text = "' in l and '".join' not in l:
        # This is the broken line - replace it and the next line
        lines[i] = (
            "    concept_text = \"\\n\".join(f\"- {c.get('name','')}: {c.get('explanation','')}\" for c in concepts)\n"
        )
        # Remove the next line if it's the continuation
        if i + 1 < len(lines) and '".join' in lines[i + 1]:
            lines[i + 1] = ""
        print(f"Fixed line {i + 1}")
        break

open(path, "w").writelines(lines)

import py_compile

try:
    py_compile.compile(path, doraise=True)
    print("✓ Syntax OK")
except py_compile.PyCompileError as e:
    print(f"✗ Still broken: {e}")
