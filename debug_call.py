import sys
sys.path.insert(0, ".")
import importlib
import llm_router
importlib.reload(llm_router)

from modules import _EEAT_SYSTEM, _E_EAT_USER_TEMPLATE
from datetime import datetime

user = _E_EAT_USER_TEMPLATE.format(
    keyword="chatgpt prompt templates chrome", intent="commercial", length=1500,
    angle="test", sections="Intro", elements="table",
    today=datetime.now().strftime("%B %d, %Y"),
    competitor_gaps="",
)

s_lower = (_EEAT_SYSTEM + " " + user).lower()

# Check the internal flags
import re
kw = llm_router._extract_keyword(user)
print(f"kw = {kw!r}")
print(f"'write a complete' in s_lower = {'write a complete' in s_lower}")
print(f"'return json' in s_lower = {'return json' in s_lower}")

is_article = "write a complete" in s_lower
is_json_request = any(x in s_lower for x in ["return only valid json", "return a json", "return json"])
is_json = is_json_request and not is_article
print(f"is_article = {is_article}")
print(f"is_json_request = {is_json_request}")
print(f"is_json = {is_json}")

if is_json:
    print("WILL ENTER JSON BLOCK -> early return")
elif is_article:
    print("WILL ENTER ARTICLE BLOCK")
else:
    print("WILL HIT FALLBACK -> None")

# Now actually call it
result = llm_router.call(_EEAT_SYSTEM, user, "local", stream=False)
print(f"Result = {type(result)}")
if result:
    print(f"Length = {len(result)} chars")
else:
    print("RESULT IS NONE - function returned None")
