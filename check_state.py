"""Check current project state"""
import os
root = r"projects/grand_rapids"
emergency = os.path.join(root, "emergency")
files = [f for f in os.listdir(emergency) if f.endswith(".html")]
print(f"Articles in emergency/: {len(files)}")
for f in sorted(files)[:5]:
    fp = os.path.join(emergency, f)
    print(f"  {f:60s} {os.path.getsize(fp)//1024:>4d} KB")
print("  ...")
img_dir = os.path.join(root, "assets", "images")
imgs = [f for f in os.listdir(img_dir) if f.endswith(".webp")]
print(f"Images in assets/images/: {len(imgs)}")
# Show first 5 images
for f in sorted(imgs)[:5]:
    fp = os.path.join(img_dir, f)
    print(f"  {f:55s} {os.path.getsize(fp)//1024:>4d} KB")
print("  ...")
