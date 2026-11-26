"""Generate the RoundLatch executable icon and Inno Setup wizard artwork."""
from pathlib import Path
import sys

from PIL import Image, ImageDraw

PACKAGING = Path(__file__).resolve().parent
sys.path.insert(0, str(PACKAGING.parent))
from aegis.brand import logo_image


def main() -> None:
    icon = PACKAGING / "roundlatch.ico"
    logo_image(256).save(icon, sizes=[(size, size) for size in (16, 32, 48, 64, 128, 256)])
    print(f"wrote {icon}")

    vendor = PACKAGING / "vendor"
    vendor.mkdir(exist_ok=True)
    art = Image.new("RGB", (328, 628), "#151a18")
    draw = ImageDraw.Draw(art)
    for inset, color in ((24, "#273229"), (46, "#354432"), (68, "#4b5d3c")):
        draw.rounded_rectangle((inset, 150 + inset, 327 - inset, 477 - inset),
                               radius=22, outline=color, width=2)
    logo = logo_image(138)
    art.paste(logo, (95, 245), logo)
    art.save(vendor / "wizard-art.png")

    small = Image.new("RGB", (110, 110), "#151a18")
    logo = logo_image(96)
    small.paste(logo, (7, 7), logo)
    small.save(vendor / "wizard-mark.png")


if __name__ == "__main__":
    main()
