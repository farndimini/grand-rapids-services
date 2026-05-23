import re, sys
sys.path.insert(0, ".")
from modules import validate_article_quality
with open("output/final_2026_20260511_1915.md", encoding="utf-8") as f:
    article = f.read()
v = validate_article_quality(article, "final 2026")
print("Score: %d/100 — %s" % (v["score"], v["verdict"]))
for x in v["failures"]: print("  FAIL: %s" % x)
for x in v["warnings"]: print("  WARN: %s" % x)
wc = len(re.sub(r"<[^>]+>", "", article).split())
print("Word count: ~%d" % wc)
