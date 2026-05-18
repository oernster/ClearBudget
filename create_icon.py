"""Create multi-resolution ICO file from PNG images."""

from pathlib import Path
from PIL import Image

PROJECT_ROOT = Path(__file__).parent

# PNG sizes in order of preference
png_files = [
    "clearbudget_256.png",
    "clearbudget_128.png",
    "clearbudget_64.png",
    "clearbudget_48.png",
    "clearbudget_32.png",
    "clearbudget_16.png",
]

images = []
for png_name in png_files:
    png_path = PROJECT_ROOT / png_name
    if png_path.exists():
        try:
            img = Image.open(png_path)
            # Convert to RGB if needed (ICO format)
            if img.mode in ("RGBA", "LA"):
                # Keep alpha channel for ICO
                images.append(img)
            else:
                images.append(img.convert("RGBA"))
            print(f"Loaded: {png_name} ({img.width}x{img.height})")
        except Exception as e:
            print(f"Failed to load {png_name}: {e}")

if images:
    ico_path = PROJECT_ROOT / "ClearBudget.ico"
    images[0].save(
        ico_path,
        format="ICO",
        sizes=[(img.width, img.height) for img in images],
        append_images=images[1:] if len(images) > 1 else [],
    )
    print(f"\nCreated: {ico_path}")
    print(f"File size: {ico_path.stat().st_size} bytes")
else:
    print("No PNG files found")
