path = "src/connectionsphere_factory/engine/prompt_renderer.py"
text = open(path).read()

# Fix 1: call_claude accepts images
old1 = '''def call_claude(prompt: str, max_tokens: int = 2000) -> str:
    settings = get_settings()
    start    = time.perf_counter()
    try:
        message = _get_client().messages.create(
            model      = settings.anthropic_model,
            max_tokens = max_tokens,  # default 600 in dev
            messages   = [{"role": "user", "content": prompt}],
        )'''

new1 = '''def call_claude(prompt: str, max_tokens: int = 2000, images: list | None = None) -> str:
    settings = get_settings()
    start    = time.perf_counter()
    # Build message content — images first, then prompt text
    content: list = []
    for img in (images or []):
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": img.get("media_type", "image/png"),
                       "data": img["data"]},
        })
    content.append({"type": "text", "text": prompt})
    try:
        message = _get_client().messages.create(
            model      = settings.anthropic_model,
            max_tokens = max_tokens,
            messages   = [{"role": "user", "content": content}],
        )'''

# Fix 2: render_and_call passes images through
old2 = '''def render_and_call(
    template_name: str,
    context:       dict[str, Any],
    max_tokens:    int = 2000,
) -> dict[str, Any]:
    return _parse_json(call_claude(render(template_name, context), max_tokens), template_name)'''

new2 = '''def render_and_call(
    template_name: str,
    context:       dict[str, Any],
    max_tokens:    int = 2000,
    images:        list | None = None,
) -> dict[str, Any]:
    return _parse_json(call_claude(render(template_name, context), max_tokens, images=images), template_name)'''

changes = 0
for old, new, label in [(old1, new1, "call_claude"), (old2, new2, "render_and_call")]:
    if old in text:
        text = text.replace(old, new)
        changes += 1
        print(f"✓ {label}")
    else:
        print(f"✗ not found: {label}")

open(path, "w").write(text)

import py_compile
try:
    py_compile.compile(path, doraise=True)
    print("✓ Syntax OK")
except py_compile.PyCompileError as e:
    print(f"✗ {e}")

print(f"\nChanges: {changes}/2")
