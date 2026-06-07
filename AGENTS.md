# SEO Agent Pro

## Build/lint/test
- Tests: `python test_intel.py` (no-network intelligence layer tests)
- No lint/typecheck setup yet

## Conventions
- Intelligence layer is external (`seo_intelligence_layer/`) — never modify core files (`llm_router.py`, `modules.py`, `dynamic_writer.py`, `research_engine.py`)
- All SERP data cached in `cache_store/` — daily snapshots per keyword
- Rate limit: 2s between network requests
- API keys via env vars (see `.env.example`). Hardcoded fallbacks in `config.py` are deprecated.
- Run `python main.py --help` for all modes

## Key structure
- `seo_intelligence_layer/` — external SERP scrape + crawl + analyze + rewrite pipeline
- `seo/` — feedback loops, GSC, business mode, reporting
- `agent_core/` — resilience layer: relay (cache + circuit breaker), parallel execution, semantic validator, memory index, self-heal
- `pipeline_enhancer.py` — drop-in enhanced pipeline wrapper (parallel, auto-rewrite, validation)
- `main.py` — entry point with `--mode` dispatch (full, article, cluster, calendar, learn, optimize, intelligence, business, report, gsc-fetch, gsc-feedback)
- `config.py` — API keys (env vars), model definitions, GSC config
- `cache_store/` — on-disk SERP + LLM response cache

## Enhanced Pipeline (`--enhanced`)
Use `python main.py --mode full --keyword "..." --enhanced` to activate:
- **RelayRouter** — automatic retry, multi-provider fallback, disk cache, circuit breaker
- **Parallel execution** — cluster + calendar built concurrently with article generation
- **Auto-rewrite loop** — up to 2 retries when quality gate fails
- **Semantic validation** — Flesch-Kincaid, keyword relevance, schema completeness, dead-link sampling
- **Memory index** — searchable article history with trend analysis and duplicate detection

Batch mode: `python main.py --batch "kw1" "kw2" --model local`

## Distributed Execution (`--distributed`)
Use `python main.py --mode full --keyword "..." --distributed` to route tasks through Celery/Redis:
- **TaskQueue** — durable queue with in-process fallback when Redis is unavailable
- **RetryPolicy** — exponential backoff with jitter per task type
- **Structured telemetry** — task dispatch, completion, failure via MetricsCollector
- **Graceful shutdown** — drains in-flight tasks before exit
- **Worker entrypoint** — `python worker_entrypoint.py --concurrency 4 --health-port 8080`

### Starting the worker (requires Redis)
```bash
# Terminal 1: Start Celery worker
python worker_entrypoint.py --concurrency 4

# Terminal 2: Dispatch tasks
python main.py --mode full --keyword "best laptop" --model local --distributed
```

### In-process fallback (no Redis needed)
```bash
python worker_entrypoint.py --no-celery   # Health check only
python main.py --mode full --keyword "test" --distributed  # Uses in-process queue
```

### Task retry policies
| Task | Max Retries | Min Backoff | Max Backoff |
|------|-------------|-------------|-------------|
| analyze_competitors | 3 | 2s | 60s |
| write_article | 3 | 5s | 60s |
| full_pipeline | 2 | 10s | 60s |
| batch_articles | 1 | 5s | 60s |

## Production-Grade Content Rules (enforced in `_EEAT_SYSTEM` + `post_processor.py`)
- **No fabricated experience** — never claims "I tested" / "hands-on" unless real evidence exists
- **No hallucinated specs** — uncertain claims use approximate language (`[VERIFY]` placeholder)
- **Confidence-based claiming** — numerical claims downgrade to approximate when confidence < 0.75
- **Niche-aligned memory** — memory filtered by `_detect_niche()` to reject cross-domain contamination
- **Self-critique pass** — `_self_critique_article()` scans for unsupported claims, duplication, cross-niche terms, and template bleed after generation
- **Quality gate** — `validate_article_quality()` enforces 25+ checks (banned phrases, H1 count, FAQ count, external links, schema match, thin sections, word count)

## Post-processor (`post_processor.py`)
Applied after every article generation via `fix_article()`:
- `_wrap_bare_paragraphs()` — wraps bare text in `<p>` tags
- `_fix_duplicate_h1()` — removes extra H1 tags
- `_fix_duplicate_toc()` — removes ALL TOC blocks (formatter adds its own)
- `_fix_duplicate_meta()` — removes extra meta blocks
- `_fix_opener()` — replaces banned openers with vetted alternatives
- `_fix_vague_prices()` — flags "Varies" / "See site" in tables
- `_add_links()` — injects links from KNOWN_LINKS database
- `_ensure_link_attrs()` — ensures rel=nofollow target=_blank on all external links
- `_fix_faq_count()` — pads FAQ to 8 items (commercial) or 5 (other intents)
- `_fix_faq_schema()` — rebuilds FAQPage JSON-LD to exactly match FAQ items
- `_ensure_link_fallback()` — injects 3 authoritative links if article has <3
- `_ensure_qa_box()` — injects quick-answer-box if missing
- `_self_critique_article()` — final audit scan

## Generation Consensus Engine
- `generation_consensus_engine.py` — multi-model consensus pipeline (critique → fact-check → entropy → merge → confidence score)
- Wired into `modules.py` `write_article()` after repair loop via `run_consensus()`
- `CritiqueModel` — banned openers, H1 count, FAQ balance, keyword presence, bare paragraphs
- `FactModel` — price/percentage/year claim extraction with source-support detection
- `EntropyModel` — sentence variance, repetitive starts, AI pattern risk assessment
- `ConfidenceScorer` — adjusts per-claim confidence based on critique + support signals
- `ConsensusEngine` — merges all passes, tags `[VERIFY]` on rejected unsupported claims
- Only consensus-approved numerical claims survive. Low-confidence claims tagged.

## Evidence DAG
- `evidence_dag.py` — Directed Acyclic Graph of claims with full provenance lineage
- `ClaimNode` — id, text, type, confidence, source_url, temporal_freshness, effective_confidence, contradiction edges
- `EvidenceDAG` — cycle detection via DFS, support/contradiction edges, confidence propagation, consensus groups
- `DAGBuilder` — extracts prices/percentages/years/superlatives from article
- `DAGVerifier` — scans 10 contradiction pairs (best/worst, always/never, etc.), bidirectional contradiction edges
- `DAGConfidencePropagator` — iterative PageRank-style propagation (3 iterations, 0.85 damping)
- Wired into `modules.py` after consensus engine, logs contradictions

## Truth Infrastructure
- `truth_infrastructure.py` — persistent truth layer (JSONL-backed, zero dependencies)
- 6 pillars:
  1. `TruthNode` — every claim is a permanent, traceable, immutable node (persists across restarts)
  2. `CitationLineage` — full provenance: URL, domain, title, snippet, extraction timestamp, citation count
  3. `FreshnessScorer` — domain trust (.gov/.edu/.org decay hierarchy), age decay, freshness indicators
  4. `ContradictionHistory` — historical tracking with resolution (claim_a_wins/claim_b_wins/both_removed)
  5. `RepairRecord` — every repair stored as permanent learning (keyword, failure class, success/failure)
  6. `HallucinationSignal` — every detected hallucination stored as structured training signal
- `TruthStore` — central coordinator with `_upsert()` dedup by ID, `update_citation_freshness()` batch recompute
- Wired into `modules.py` — registers all DAG claims + contradictions on every article write

## Adaptive Trust Engine
- `adaptive_trust_engine.py` — probabilistic governance layer replacing hard rules with weighted risk scoring
- `TrustFactor` — single factor with name, weight, score, human-readable evidence
- `PublishRiskReport` — final verdict (publish/review/quarantine/block) with full factor breakdown
- `AdaptiveWeights` — per-niche weight profiles (health boosts hallucination_rate, finance boosts contradictions)
- `AdaptiveTrustEngine` — collects signals from DAG + consensus + truth store, computes `publish_risk = Σ(factor_weight × factor_score) / Σ(weights)`
- `learn()` — adjusts niche weights based on historical outcomes (which factors correctly predicted blocks)
- Thresholds: publish < 0.40, review < 0.65, quarantine < 0.80, block ≥ 0.80
- Wired into `modules.py` as final probabilistic gate before publish — logs verdict, risk score, and top factors

## Testing
- `test_multi_agent.py` — multi-agent orchestration tests (122 tests, no network required)
- `test_distributed.py` — distributed execution infrastructure (77 tests, no network required)
- `test_enhanced.py` — enhanced pipeline tests (no network required)
- `test_intel.py` — main intelligence layer test (no network required)
- `test_gsc_feedback.py` — GSC feedback loop tests (164 tests)
- `test_evaluation.py` — evaluation/scorer tests
- `test_system_hardening.py` — system hardening audit (39 tests)
- `test_seo_intelligence.py` — SEO intelligence layer (69 tests)
- `test_consensus.py` — generation consensus engine (26 tests)
- `test_evidence_dag.py` — evidence DAG (37 tests)
- `test_truth_infrastructure.py` — truth infrastructure (33 tests)
- `test_adaptive_trust.py` — adaptive trust engine (27 tests)
- Tests pass when: all assertions pass, `ALL TESTS PASSED` printed
- **Test mode**: Set `SEO_AGENT_TEST_MODE=1` env var to skip real module network calls.
  All test files do this automatically. Remove it to test with live SERP/LLM calls.

# ════════════════════════════════════════
# GRAND RAPIDS HOME SERVICES — SITE PROJECT
# ════════════════════════════════════════

## Project location
- Root: `projects/grand_rapids/`
- Generator script: `generate_articles.py` (root of repo, NOT inside project)
- Dev server: `http://localhost:3000`

## Site structure
- `/` — Home page with navbar + footer (Blog link added)
- `/blog.html` — Blog landing page (21 service category cards)
- `/hubs/{cat}-grand-rapids.html` — 21 hub pages (one per service)
- `/authority/` — About, Contact, Service Areas, Reviews, Financing, Warranty
- `/{directory}/{file}.html` — 1,311 article files across 6 directories

## The 21 Services (in `generate_articles.py` SERVICES dict)
Keys must match filename substrings for `detect_service()`. `cat` field matches the hub filename (without `-grand-rapids.html`).

| Key | Name (display) | cat (hub path) | Naming in filenames |
|-----|---------------|----------------|-------------------|
| plumbing | Plumbing | plumbing | plumbing |
| hvac | HVAC | hvac | hvac |
| electrical | Electrical | electrical | electrical |
| roofing | Roofing | roofing | roofing |
| landscaping | Landscaping | landscaping | landscaping |
| concrete | Concrete | concrete | concrete |
| fencing | Fencing | fencing | fencing |
| flooring | Flooring | flooring | flooring |
| painting | Painting | painting | painting |
| pest-control | Pest Control | pest-control | pest-control |
| siding | Siding | siding | siding |
| window-replacement | Window Replacement | window-replacement | window-replacement |
| deck-and-patio | Deck & Patio | deck-and-patio | deck-and-patio |
| kitchen-remodeling | Kitchen Remodeling | kitchen-remodeling | kitchen-remodeling |
| bathroom-remodeling | Bathroom Remodeling | bathroom-remodeling | bathroom-remodeling, shower-remodel |
| basement-remodel | Basement Remodeling | basement-remodeling | basement-remodel, basement-remodeling |
| garage-door | Garage Door | garage-door-services | garage-door-installation, garage-door-repair |
| tree-service | Tree Service | tree-service | tree-service |
| mold-remediation | Mold Remediation | mold-remediation | mold-remediation |
| water-damage-restoration | Water Damage Restoration | water-damage-restoration | water-damage-restoration |
| appliance-repair | Appliance Repair | appliance-repair | appliance-repair |

## Directory structure (6 directories, 1,311 files total)
| Directory | Files | Prefix | Geo-targets |
|-----------|-------|--------|-------------|
| `emergency/` | 184 | `emergency-{service}-{city}-mi.html` | 8 cities |
| `24_hour/` | 184 | `24-hour-{service}-{city}-mi.html` | 8 cities |
| `same_day/` | 184 | `same-day-{service}-{city}-mi.html` | 8 cities |
| `affordable/` | 184 | `affordable-{service}-{city}-mi.html` | 8 cities |
| `near_me/` | 184 | `near-me-{service}-{city}-mi.html` | 8 cities |
| `neighborhoods/` | 391 | `{service}-{neighborhood}-grand-rapids.html` (no prefix!) | 17 neighborhoods |

8 cities: grand-rapids, kentwood, wyoming, east-grand-rapids, walker, ada, cascade, rockford, jenison, hudsonville

## Article template rules (must follow for ALL generators)
- **Angi.com-style structure**: pricing tables, comparison tables, cost-saving tips, transparent data sources, additional repair costs
- **8 tables minimum**: Pricing, Emergency vs Standard, When You Need, Service Areas (10-city response), Emergency Checklist, Response Process, Additional Costs, Ways to Save
- **3 JSON-LD schemas**: Article, LocalBusiness, FAQPage (8 questions)
- **EEAT author**: Mike Vanderholt, license #MP-45728, 19+ years, 4,200+ calls
- **11+ external links**: LARA, EPA WaterSense, Angi, City of GR plus service-specific .gov/.org
- **No fabricated experience**: never claim "I tested" / "hands-on"
- **No hallucinated specs**: uncertain claims use `[VERIFY]`
- **Table of Contents**: professional card design — dark gradient header, numbered items with blue badge squares, responsive CSS grid, hover effects
- **`.section` padding removed**: no 80px top/bottom gap between hero image and TOC
- **Hero image**: max-width 800px centered (NOT full 1152px width)

## Image generation (`generate_image()`)
- Format: 1200×630 WebP (Google-preferred for Article rich results)
- Background: dark gradient (#0f0f0a → #1a1a2e), NOT blue (#1e293b rejected)
- Accent: indigo #3b5af6 for badge, stats, accent lines
- Elements: service badge pill tag, title, subtitle, 3 stats (4,200+ Calls, 19+ Yrs, 10 Cities)
- Diagonal line texture every 40px
- File path: `/assets/images/{dir_prefix}-{service_key}-{city_key}.webp`
- For neighborhoods (no dir_prefix): `/assets/images/{service_key}-{city_key}.webp`

## `detect_service()` rules
- `sk in name` check (substring match)
- Special aliases checked FIRST:
  - `"shower" in name` → `"bathroom-remodeling"`
- If no match, fallback: `"plumbing"`

## `detect_city()` rules
- Check longer city names FIRST (sorted by len, reverse) to prevent "grand-rapids" swallowing "east-grand-rapids"
- Fallback: `"grand-rapids"`

## Hub link resolution
- Template uses `sv["cat"]` for hub URLs, NOT the service key
- Because `garage-door` key needs to link to `/hubs/garage-door-services-grand-rapids`
- And `basement-remodel` key needs to link to `/hubs/basement-remodeling-grand-rapids`

## Batch generation strategy (weekly to avoid Google penalties)
- DO NOT upload all 1,311 articles at once — Google sees it as suspicious automated content
- Distribute across 7 weeks (~184/week, last week 391)
- Order by intent priority: emergency (highest conversion) → 24_hour → same_day → affordable → near_me → neighborhoods (lowest)
- Alternative: 3-week accelerated (552 + 552 + 391)

## Key files to NEVER modify
- `generate_articles.py` — the batch generation engine (modify SERVICES, CITIES, DIRS dicts only)
- `projects/grand_rapids/` — generated output (treat as read-only after generation)
- Existing `seo_intelligence_layer/` core files (listed at top of this file)
- `post_processor.py` rules apply to AI-written articles, NOT to generated HTML articles
