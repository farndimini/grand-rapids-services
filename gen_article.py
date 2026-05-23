import sys, re
sys.path.insert(0, '.')
from llm_router import call

system = 'You are an SEO content writer. Write a complete article about the keyword. This is about finding free ebooks on Amazon Kindle store - a guide for readers looking for free books on Amazon.'
user = 'Write a complete article about: best free ebooks on Amazon Kindle store'
article = call(system, user, 'local', stream=False)

with open('ebook_amazon_free.html', 'w', encoding='utf-8') as f:
    f.write(article)
print('Saved to ebook_amazon_free.html')

words = len(article.split())
print(f'Word count: ~{words}')

headings = re.findall(r'<h[23][^>]*>(.*?)</h[23]>', article, re.DOTALL)
for h in headings:
    clean = re.sub(r'<[^>]+>', '', h).strip()
    print(f'  Section: {clean}')

intent_m = re.search(r'Intent: (\w+)', article)
if intent_m:
    print(f'Intent: {intent_m.group(1)}')
