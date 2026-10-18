"""Render failed Rust checks from observed artifacts."""
import json
from common import OUT

def generate():
    lines = ['# Rust test findings', '']
    for name in ('resources', 'fuzz', 'crash', 'bridge', 'network', 'migration'):
        path = OUT / (name + '.json')
        if not path.exists():
            lines.append(f'- {name}: no evidence')
            continue
        value = json.loads(path.read_text(encoding='utf-8'))
        lines.append(f'- {name}: ' + json.dumps(value, ensure_ascii=False))
    (OUT / 'findings.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')

if __name__ == '__main__':
    generate()
