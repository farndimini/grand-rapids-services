import sys, re
sys.path.insert(0, ".")
import importlib
import llm_router
importlib.reload(llm_router)

# Monkey-patch _call_local to inject tracing
original = llm_router._call_local
src = original.__code__
print(f"_call_local defined at line {src.co_firstlineno}")

# Read the source to count how many lines
import inspect
source_lines = inspect.getsource(original).split('\n')
print(f"_call_local has {len(source_lines)} lines of source")

# Now let's directly check what happens inside
from modules import _EEAT_SYSTEM, _E_EAT_USER_TEMPLATE
from datetime import datetime

user = _E_EAT_USER_TEMPLATE.format(
    keyword="chatgpt prompt templates chrome", intent="commercial", length=1500,
    angle="test", sections="Intro", elements="table",
    today=datetime.now().strftime("%B %d, %Y"),
    competitor_gaps="",
)

s_lower = (_EEAT_SYSTEM + " " + user).lower()
kw = llm_router._extract_keyword(user)

# Manually duplicate the flag logic
is_article_check = "write a complete" in s_lower
print(f"Pre-call: is_article = {is_article_check}")
print(f"Pre-call: kw = {kw!r}")

# Now let's use exec to add print tracing
# Create a debug version
traced_code = original.__code__.replace(
    co_consts=original.__code__.co_consts + ("TRACED",)
)
print(f"co_consts has {len(original.__code__.co_consts)} items")

# Instead of monkey-patching, let's just run with more instrumentation
# by patching the call function
orig_call = llm_router.call
def debug_call(system, user, model_name, stream=True):
    if model_name == "local":
        # Patch _call_local
        orig_local = llm_router._call_local
        def traced_local(system, user, stream):
            result = orig_local(system, user, stream)
            import traceback
            print(f"\n_call_local returned: {type(result)}", flush=True)
            if result is None:
                traceback.print_stack()
            return result
        llm_router._call_local = traced_local
    
    result = orig_call(system, user, model_name, stream)
    llm_router._call_local = orig_local
    return result

# Temporarily replace, doesn't work well... let me just compile manually
# Actually, let's just create our own local that wraps original
import types

@types.coroutine
async def noop():
    pass

# Hmm, let's take a different approach. Let's add a print at the start of call_local
# by reading the source and compiling a modified version
source = inspect.getsource(original)
# Add a print at the very beginning
modified_source = source.replace(
    "def _call_local(system: str, user: str, stream: bool) -> str:",
    "def _call_local(system: str, user: str, stream: bool) -> str:\n    import traceback; traceback.print_stack(limit=5); print(f'\\n>>> _call_local START: kw={{_extract_keyword(user)}}, is_article={{\"write a complete\" in (system+\" \"+user).lower()}}')",
    1
)
try:
    exec(modified_source, llm_router.__dict__)
    print("Patched _call_local successfully")
except SyntaxError as e:
    print(f"Syntax error in patch: {e}")
    print("Falling back to original")
    llm_router._call_local = original

# Call
try:
    result = llm_router.call(_EEAT_SYSTEM, user, "local", stream=False)
    print(f"\nRESULT: {type(result)}")
except Exception as e:
    import traceback
    print(f"\nERROR: {e}")
    traceback.print_exc()
