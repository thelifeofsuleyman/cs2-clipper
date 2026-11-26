"""RoundLatch logo shared by the dashboard, tray and Windows packaging."""
from __future__ import annotations

INK = "#18201a"
LIME = "#d6f582"
_SIZE = 48
_SHAPES = (
    ((9, 21), (9, 9), (21, 9), (21, 13), (13, 13), (13, 21)),
    ((27, 35), (35, 35), (35, 27), (39, 27), (39, 39), (27, 39)),
    ((20, 15), (34, 24), (20, 33)),
)


def logo_svg() -> str:
    shapes = "".join(
        '<polygon points="' + " ".join(f"{x},{y}" for x, y in shape) + '"/>'
        for shape in _SHAPES
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_SIZE} {_SIZE}" '
        f'width="28" height="28" role="presentation" aria-hidden="true">'
        f'<rect width="{_SIZE}" height="{_SIZE}" rx="11" fill="{INK}"/>'
        f'<g fill="{LIME}">{shapes}</g></svg>'
    )


def logo_image(size: int):
    from PIL import Image, ImageDraw

    canvas = size * 3
    factor = canvas / _SIZE
    image = Image.new("RGBA", (canvas, canvas))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, canvas - 1, canvas - 1), radius=11 * factor, fill=INK)
    for shape in _SHAPES:
        draw.polygon([(x * factor, y * factor) for x, y in shape], fill=LIME)
    return image.resize((size, size), Image.Resampling.LANCZOS)
