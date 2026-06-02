"""Generate aegis.ico (shield + play) for the app/window/installer icon.

Run during the build (Pillow is a project dependency). Failure is non-fatal:
the spec falls back to the default icon if aegis.ico isn't produced. The shape
matches the in-app SVG logo: a shield ("Aegis") with a play triangle.
"""
import os

from PIL import Image, ImageDraw


def shield(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def pt(x, y):
        return (x / 48 * size, y / 48 * size)

    pts = [pt(24, 3), pt(41, 9), pt(41, 24), pt(33, 40),
           pt(24, 45), pt(15, 40), pt(7, 24), pt(7, 9)]
    d.polygon(pts, fill=(22, 27, 36, 255))
    d.line(pts + [pts[0]], fill=(255, 90, 60, 255),
           width=max(2, int(size * 0.055)), joint="curve")
    d.polygon([pt(20, 16), pt(33, 24), pt(20, 32)], fill=(255, 90, 60, 255))
    return img


def main() -> None:
    out = os.path.join(os.path.dirname(__file__), "aegis.ico")
    base = shield(256)
    base.save(out, sizes=[(s, s) for s in (16, 32, 48, 64, 128, 256)])
    print("wrote", out)


if __name__ == "__main__":
    main()
