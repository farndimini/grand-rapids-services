import re
with open('js/data.js', 'r', encoding='utf-8') as f:
    content = f.read()
matches = re.findall(r"slug:\s+'([^']+)',\s+category:\s+'([^']+)',\s+title:\s+'([^']+)'", content)
print(f'{len(matches)} articles found:')
for i, (slug, cat, title) in enumerate(matches, 1):
    print(f'  {i:2d}. [{cat:12s}] {title}  ({slug})')
