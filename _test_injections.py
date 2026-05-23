"""Test memory injection output."""
import sys, json
sys.path.insert(0, '.')
from memory import build_prompt_injection, build_vector_memory_injection, build_strategy_evolution_injection

with open('seo_memory.json', encoding='utf-8') as f:
    mem = json.load(f)

articles = mem.get('articles_written', [])
print('Total articles:', len(articles))
for a in articles:
    print(f'  - {a.get("keyword","?")} (score={a.get("quality_score","?")}, wc={a.get("word_count","?")})')

print()
print('=== build_prompt_injection ===')
inj = build_prompt_injection(mem, 'best focus timer chrome extension 2026')
print(repr(inj[:400]) if inj else 'EMPTY')
print('Length:', len(inj))

print()
print('=== build_vector_memory_injection ===')
vmi = build_vector_memory_injection('best focus timer chrome extension 2026', mem)
print(repr(vmi[:400]) if vmi else 'EMPTY')
print('Length:', len(vmi))

print()
print('=== build_strategy_evolution_injection ===')
sei = build_strategy_evolution_injection()
print(repr(sei[:400]) if sei else 'EMPTY')
print('Length:', len(sei))
