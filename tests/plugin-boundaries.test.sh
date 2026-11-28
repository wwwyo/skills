#!/usr/bin/env bash
# plugin の横断参照の禁止（AGENTS.md「plugin の配布」）を検査する。plugin は自分の dir だけを
# cache へコピーされ、cloud には core・design だけが届くので、別 plugin の skill を path で
# 指すと届かない環境で切れる。名前で言っても届かない環境では使えないので、別 plugin の skill を
# 名前（`name`・**name**・name skill・/name・$name）や「<plugin> plugin」で参照することも禁止する。
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
python3 - <<'PYTHON'
import os, re, sys
plugins = sorted(d for d in os.listdir('plugins') if os.path.isdir(f'plugins/{d}'))
owner = {skill: p for p in plugins for skill in os.listdir(f'plugins/{p}/skills')}
relative = re.compile(r'(?:\.\./)+[A-Za-z0-9_.-]+')
canonical = re.compile(r'(?:^|[^A-Za-z0-9_.-])(?:\.agents/skills|plugins/([a-z0-9-]+)/skills)/([A-Za-z0-9_-]+)')
names = {}
for p in plugins:
    names[p] = [(s, re.compile(r'(?:`[/$]?%s`|\*\*%s\*\*|(?<![\w./-])%s(?![\w-])\s*skill|(?:^|[\s(])[/$]%s(?![\w/.-]))' % ((re.escape(s),) * 4)))
                for s, o in owner.items() if o != p]
plugin_word = re.compile(r'\b(%s)\s*plugin' % '|'.join(plugins))
errors = []
for plugin in plugins:
    base = f'plugins/{plugin}'
    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d not in ('node_modules', '.git', '__pycache__')]
        for name in files:
            path = os.path.join(root, name)
            try:
                text = open(path, encoding='utf-8').read()
            except (UnicodeDecodeError, OSError):
                continue
            for number, line in enumerate(text.splitlines(), 1):
                for match in relative.finditer(line):
                    target = os.path.normpath(os.path.join(root, match.group(0)))
                    parts = target.split(os.sep)
                    escapes = not target.startswith(base + os.sep)
                    # ../<skill>/ from inside this plugin that names another plugin's skill
                    foreign = len(parts) >= 4 and parts[:3] == ['plugins', plugin, 'skills'] and \
                        owner.get(parts[3], plugin) != plugin
                    if escapes or foreign:
                        errors.append(f'{path}:{number}: {match.group(0)} leaves plugin {plugin}')
                for skill, pattern in names[plugin]:
                    if pattern.search(line):
                        errors.append(f'{path}:{number}: names {owner[skill]} plugin skill {skill}')
                for match in plugin_word.finditer(line):
                    if match.group(1) != plugin:
                        errors.append(f'{path}:{number}: mentions {match.group(0)}')
                for match in canonical.finditer(line):
                    other, skill = match.group(1), match.group(2)
                    if skill in owner and (other is None or owner[skill] != plugin):
                        errors.append(f'{path}:{number}: {match.group(0).strip()} points at another plugin or the old layout')
for error in errors:
    print(f'error: {error}', file=sys.stderr)
sys.exit(1 if errors else 0)
PYTHON
echo "OK: no plugin refers to another plugin"
