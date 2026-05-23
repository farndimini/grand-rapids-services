"""
deploy.py — Regenerate all pages and assets for production deployment.

Usage:
    set SEO_AGENT_SITE_URL=https://yourdomain.com
    python deploy.py

Then:
    git add projects/grand_rapids/ vercel.json
    git commit -m "deploy"
    git push
"""

import os
import sys

os.environ["SEO_AGENT_TEST_MODE"] = "1"
SITE_URL = os.environ.get("SEO_AGENT_SITE_URL", "https://yoursite.com")

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

print(f"Deploying with SITE_URL={SITE_URL}")
print("=" * 50)

# 1. Generate all service pages
print("\n[1/5] Generating service pages (1840)...")
from programmatic_expander import build_matrix, generate_batch, PROJECT_ROOT

matrix = build_matrix()
print(f"  Matrix: {len(matrix)} total combinations")

# Generate in batches
batch_size = 200
all_pages = []
for i in range(0, len(matrix), batch_size):
    batch = matrix[i:i + batch_size]
    from programmatic_expander import generate_batch as gb

    # Override limit for this batch
    import programmatic_expander as pe
    pages = []
    # We generate directly since generate_batch is simpler
    pages = generate_batch(limit=len(batch))
    all_pages.extend(pages)
    print(f"  Batch {i // batch_size + 1}/{(len(matrix) + batch_size - 1) // batch_size}: {len(pages)} pages")

# 2. Generate neighborhood pages
print("\n[2/5] Generating neighborhood pages (391)...")
from programmatic_expander import generate_neighborhood_pages
neighborhood_pages = generate_neighborhood_pages(limit=0)
print(f"  {len(neighborhood_pages)} pages")

# 3. Generate hub pages
print("\n[3/5] Building hub pages...")
from programmatic_expander import build_hubs
hubs = build_hubs()
print(f"  {len(hubs)} hub pages")

# 4. Generate authority pages
print("\n[4/5] Generating authority pages...")
from authority_pages import generate_authority_pages
auth = generate_authority_pages()
print(f"  {len(auth)} authority pages")

# 5. Generate segmented sitemaps
print("\n[5/5] Generating segmented sitemaps...")
from programmatic_expander import generate_segmented_sitemaps
segs = generate_segmented_sitemaps(
    all_pages,
    include_neighborhoods=True,
    include_hubs=True,
    include_authority=True,
)
print(f"  {len(segs)} sitemap segments")

# Generate homepage
print("\n  Generating homepage...")
from generate_homepage import build_homepage
html = build_homepage()
out_path = os.path.join(BASE, "projects", "grand_rapids", "index.html")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(html)
print(f"  Homepage: {out_path} ({len(html)} bytes)")

print("\n" + "=" * 50)
print("Deployment ready!")
print(f"  Total service pages: {len(all_pages)}")
print(f"  Neighborhood pages: {len(neighborhood_pages)}")
print(f"  Hub pages: {len(hubs)}")
print(f"  Authority pages: {len(auth)}")
print(f"  Sitemap segments: {len(segs)}")
print(f"  SITE_URL: {SITE_URL}")
print()
print("Next steps:")
print(f"  1. git add projects/grand_rapids/ vercel.json .gitignore")
print(f"  2. git commit -m 'deploy: regenerate all pages'")
print(f"  3. git push")
