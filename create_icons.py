"""Generate application icons for ClearBudget."""

from PIL import Image, ImageDraw
from pathlib import Path


def create_icon(size: int) -> Image.Image:
    """Create a budget/money themed icon."""
    # Create image with dark background
    img = Image.new("RGBA", (size, size), color=(22, 24, 39, 255))
    draw = ImageDraw.Draw(img)

    # Draw a simple wallet/budget symbol
    padding = int(size * 0.1)
    inner_size = size - 2 * padding

    # Draw rounded rectangle for wallet
    box = [padding, padding, size - padding, size - padding]
    draw.rounded_rectangle(box, radius=int(size * 0.15), fill=(167, 139, 250, 255))

    # Draw coins/money symbol inside
    coin_y = padding + int(inner_size * 0.5)
    coin_radius = int(size * 0.08)

    # Coin 1
    coin1_x = padding + int(inner_size * 0.25)
    draw.ellipse(
        [
            coin1_x - coin_radius,
            coin_y - coin_radius,
            coin1_x + coin_radius,
            coin_y + coin_radius,
        ],
        fill=(52, 211, 153, 255),
    )

    # Coin 2
    coin2_x = padding + int(inner_size * 0.55)
    draw.ellipse(
        [
            coin2_x - coin_radius,
            coin_y - coin_radius,
            coin2_x + coin_radius,
            coin_y + coin_radius,
        ],
        fill=(96, 165, 250, 255),
    )

    # Coin 3
    coin3_x = padding + int(inner_size * 0.75)
    draw.ellipse(
        [
            coin3_x - coin_radius,
            coin_y - coin_radius,
            coin3_x + coin_radius,
            coin_y + coin_radius,
        ],
        fill=(251, 191, 36, 255),
    )

    return img


def main() -> int:
    """Create all icon sizes."""
    root = Path(__file__).parent
    sizes = [16, 32, 48, 64, 128, 256, 512]

    print("Generating icons...")

    for size in sizes:
        icon = create_icon(size)
        png_path = root / f"clearbudget_{size}.png"
        icon.save(png_path, "PNG")
        print(f"  [OK] {png_path.name}")

    # Create ICO from largest PNG
    icon_512 = Image.open(root / "clearbudget_512.png")

    # Create ICO with multiple sizes
    ico_sizes = []
    for size in [16, 32, 48, 64, 128, 256]:
        img_path = root / f"clearbudget_{size}.png"
        if img_path.exists():
            ico_sizes.append(Image.open(img_path))

    if ico_sizes:
        ico_path = root / "clearbudget.ico"
        ico_sizes[0].save(
            ico_path, "ICO", sizes=[(s.width, s.height) for s in ico_sizes]
        )
        print(f"  [OK] clearbudget.ico")

    print("Icon generation complete!")
    return 0


if __name__ == "__main__":
    exit(main())
