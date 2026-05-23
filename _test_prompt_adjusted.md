# Adjustments to make the test work with OUR codebase:

1. `from config import GSC_SITE_URL` → `from config import GSC_CONFIG`
   Then use `GSC_CONFIG["site_url"]` and `GSC_CONFIG["credentials_path"]`

2. `from core.gsc_client import GSCClient` → `from seo.gsc_client import GSCClient`

3. No `health_check()` method exists in our gsc_client.py.
   Alternative: check `gsc.use_simulation is False` + try a real fetch.

4. No `fetch_performance()` method.
   Use `fetch_top_queries(days=7, max_results=100)` instead,
   then filter results for "food morocco".

5. Remove Ollama/Local SQLite references — not relevant to this test.
