"""Restructure llm_router.py: move _wrap_professional_article before _call_local."""
import shutil
import os

filepath = r"C:\Users\pc\Desktop\2026\AGENT 2\llm_router.py"
backup = filepath + ".bak"

# Read the file
with open(filepath, "r", encoding="utf-8") as f:
    lines = f.readlines()

print(f"Total lines: {len(lines)}")

# --- Identify boundaries ---

# _call_local starts at line 1084 (0-indexed: 1083)
call_local_start_idx = None
for i, line in enumerate(lines):
    if line.startswith("def _call_local(system: str, user: str, stream: bool) -> str:"):
        call_local_start_idx = i
        break

# _wrap_professional_article starts at line 1369 (0-indexed: 1368)
wrap_start_idx = None
for i, line in enumerate(lines):
    if line.startswith("def _wrap_professional_article"):
        wrap_start_idx = i
        break

# Find end of _wrap_professional_article: the line with </html>""" (its return string close)
wrap_end_idx = None
for i in range(wrap_start_idx, len(lines)):
    stripped = lines[i].rstrip()
    if "</html>\"\"\"" in stripped or stripped == "</html>\"\"\"":
        wrap_end_idx = i
        break

# Find the end of inner function defs inside _call_local
# It's the last indent=4 or higher line before _wrap_professional_article
# Actually: inner functions end at line 1366 (index 1365), which is the </script>""" line
# that closes _build_json_ld's return string.
# After that: lines 1367-1368 are blank, then _wrap_professional_article at 1369
# So the inner-function-block ends at wrap_start_idx - 1 (or wrap_start_idx - 2 excluding blanks)

# The code that should be inside _call_local but is currently after _wrap_professional_article
# starts at wrap_end_idx + 2 (line 1486, 0-indexed 1485)
# and extends to line 2757 (0-indexed 2756), which is the last indent=4 line before public API

# Find public API section start (line 2759/2760 area, 0-indexed 2758+)
# Lines after 2757 are public API (indent=0)
pub_api_start_idx = None
for i in range(len(lines) - 1, -1, -1):
    stripped = lines[i].rstrip()
    if stripped and not stripped.startswith(" "):
        # This is a top-level line
        pub_api_start_idx = i
        break
# But we need the start of public API, which is after _call_local ends
# Let's find the last non-blank indent=4 line before the public API section
# That's line 2757 (return fallback)

# Actually, let me just find where the indent=0 code resumes after the indent=4 block
# that follows _wrap_professional_article
call_local_body_end_idx = None
for i in range(wrap_end_idx + 1, len(lines)):
    stripped = lines[i].rstrip()
    if stripped and not stripped.startswith(" "):
        call_local_body_end_idx = i - 1
        break
# The line before the first indent=0 line after the indent=4 block
# This would be the last line of _call_local's body

print(f"_call_local start: line {call_local_start_idx + 1}")
print(f"_wrap_professional_article: lines {wrap_start_idx + 1} - {wrap_end_idx + 1}")
print(f"    body is {wrap_end_idx - wrap_start_idx + 1} lines")

# Now identify the blocks
# Block A: lines 0 to call_local_start_idx - 1 (before _call_local)
block_a = lines[:call_local_start_idx]

# Block W: _wrap_professional_article (lines wrap_start_idx..wrap_end_idx inclusive)
block_w = lines[wrap_start_idx:wrap_end_idx + 1]

# Block B: _call_local header + inner function defs (from call_local_start_idx to wrap_start_idx - 1)
block_b = lines[call_local_start_idx:wrap_start_idx]

# Block C: rest of _call_local body (from wrap_end_idx + 1 to call_local_body_end_idx)
block_c = lines[wrap_end_idx + 1:call_local_body_end_idx + 1] if call_local_body_end_idx else []

# Block D: public API section (from call_local_body_end_idx + 1 to end)
block_d = lines[call_local_body_end_idx + 1:] if call_local_body_end_idx else []

print(f"\nBlock A (before _call_local): {len(block_a)} lines")
print(f"Block W (_wrap_professional_article): {len(block_w)} lines")
print(f"Block B (_call_local header + inner defs): {len(block_b)} lines")
print(f"Block C (rest of _call_local body): {len(block_c)} lines")
print(f"Block D (public API): {len(block_d)} lines")

# Verify we didn't lose any lines
total = len(block_a) + len(block_w) + len(block_b) + len(block_c) + len(block_d)
print(f"\nTotal restructured lines: {total} (original: {len(lines)})")
assert total == len(lines), f"Line count mismatch! Lost {len(lines) - total} lines"

# Create backup
shutil.copy2(filepath, backup)
print(f"\nBackup saved to: {backup}")

# Write restructured file
new_lines = block_a + block_w + block_b + block_c + block_d
with open(filepath, "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print(f"Written {len(new_lines)} lines to {filepath}")

# Verify syntax
source = "".join(new_lines)
try:
    compile(source, filepath, "exec")
    print("\n✓ Syntax check PASSED — valid Python")
except SyntaxError as e:
    print(f"\n✗ Syntax error: {e}")
    # Restore backup
    print("Restoring backup...")
    shutil.copy2(backup, filepath)

# Report new structure
print("\n=== New Structure ===")
print(f"  Lines 1-{len(block_a)}: (preamble before _call_local)")
print(f"  Lines {len(block_a) + 1}-{len(block_a) + len(block_w)}: _wrap_professional_article")
print(f"  Lines {len(block_a) + len(block_w) + 1}-{len(block_a) + len(block_w) + len(block_b)}: _call_local (header + inner function defs)")
print(f"  Lines {len(block_a) + len(block_w) + len(block_b) + 1}-{len(block_a) + len(block_w) + len(block_b) + len(block_c)}: _call_local (main body — BAN_PHRASES, _audit_paragraphs, _self_evaluate, article generation)")
print(f"  Lines {len(block_a) + len(block_w) + len(block_b) + len(block_c) + 1}-{total}: Public API (call, call_json, list_models)")
