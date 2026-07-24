"""Count all ACTION_MAP entries across 15 Control Core layers."""
import re, os

layers_dir = 'core/layers'
layer_names = {
    1:'filesystem', 2:'process', 3:'application', 4:'window', 5:'input',
    6:'registry', 7:'services', 8:'system', 9:'browser',
    10:'network', 11:'media', 12:'developer', 13:'cloud', 14:'automation', 15:'advanced'
}

total = 0
for i in range(1, 16):
    files = [f for f in os.listdir(layers_dir) if f.startswith(f'L{i}_') and f.endswith('.py')]
    if not files:
        continue
    content = open(os.path.join(layers_dir, files[0]), 'r', encoding='utf-8').read()
    m = re.search(r'ACTION_MAP\s*:\s*dict\[.*?\]\s*=\s*\{', content)
    if not m:
        continue
    start = m.end()
    depth = 1
    pos = start
    while depth > 0 and pos < len(content):
        if content[pos] == '{':
            depth += 1
        elif content[pos] == '}':
            depth -= 1
        pos += 1
    block = content[start:pos-1]
    keys = re.findall(r'^\s+["\'](.+?)["\']\s*:', block, re.MULTILINE)
    name = layer_names[i]
    print(f'  L{i:2d} {name:12s}: {len(keys):3d} actions')
    total += len(keys)

print(f'\n  TOTAL: {total} actions across {len(layer_names)} layers')
print(f'  Target: 467 actions')
print(f'  Status: {"EXCEEDS TARGET" if total >= 467 else "BELOW TARGET"} by {abs(total - 467)}')
