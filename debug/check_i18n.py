"""Check missing i18n keys across all languages."""
import re
import json
import os

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

files = ['launcher.py', 'launcher_emu.py', 'launcher_cmd.py', 'autoPVE.py', 'i18n.py']
keys_used = set()
pattern = re.compile(r"""t\(\s*["']([\w]+)["']""")

for f in files:
    try:
        with open(f, 'r', encoding='utf-8') as fh:
            for line in fh:
                for m in pattern.finditer(line):
                    keys_used.add(m.group(1))
    except FileNotFoundError:
        pass

with open('localization.json', 'r', encoding='utf-8') as fh:
    loc = json.load(fh)

zh_tw_keys = set(loc.get('zh_TW', {}).keys())
zh_cn_keys = set(loc.get('zh_CN', {}).keys())
en_keys = set(loc.get('en', {}).keys())

print('=== Keys used in code but missing in zh_TW ===')
for k in sorted(keys_used - zh_tw_keys):
    print(f'  {k}')

print('\n=== Keys used in code but missing in zh_CN ===')
for k in sorted(keys_used - zh_cn_keys):
    print(f'  {k}')

print('\n=== Keys used in code but missing in en ===')
for k in sorted(keys_used - en_keys):
    print(f'  {k}')

print('\n=== Keys in zh_TW but missing in zh_CN ===')
for k in sorted(zh_tw_keys - zh_cn_keys):
    print(f'  {k}')

print('\n=== Keys in zh_TW but missing in en ===')
for k in sorted(zh_tw_keys - en_keys):
    print(f'  {k}')

print(f'\nTotal keys used in code: {len(keys_used)}')
print(f'zh_TW: {len(zh_tw_keys)}, zh_CN: {len(zh_cn_keys)}, en: {len(en_keys)}')
