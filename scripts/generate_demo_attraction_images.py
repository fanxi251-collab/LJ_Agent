from pathlib import Path
import math

from PIL import Image, ImageDraw


WIDTH = 960
HEIGHT = 600
PALETTES = [
    ("#dcefe8", "#efd8a7", "#315f54", "#b77b35"),
    ("#dce8f1", "#f0d6b1", "#426b73", "#9f6b3c"),
    ("#e8e1f0", "#f1d8aa", "#665979", "#ad7435"),
    ("#d8ece5", "#e8c999", "#32685c", "#a76c2d"),
    ("#dcecf5", "#f2cfac", "#397184", "#bd7137"),
    ("#e8e6dc", "#eacb91", "#566b54", "#a66d2e"),
    ("#e1e6f0", "#ead1a5", "#4e6377", "#a06c3b"),
    ("#e8dfef", "#efcf9f", "#675a76", "#ab6f34"),
]


def generate(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for index, palette in enumerate(PALETTES, start=1):
        image = _draw_scene(index, palette)
        image.save(output_dir / f"seed-{index}.webp", "WEBP", quality=88, method=6)


def _draw_scene(index: int, palette: tuple[str, str, str, str]) -> Image.Image:
    sky, sun, mountain, accent = palette
    image = Image.new("RGB", (WIDTH, HEIGHT), sky)
    draw = ImageDraw.Draw(image)
    draw.ellipse((700, 70, 850, 220), fill=sun)
    draw.polygon([(0, 440), (180, 270), (320, 420), (500, 210), (690, 410), (820, 285), (960, 430), (960, 600), (0, 600)], fill=mountain)
    draw.polygon([(0, 500), (250, 360), (430, 490), (650, 330), (960, 480), (960, 600), (0, 600)], fill="#7fa596")
    if index in {1, 4}:
        _draw_gate(draw, accent, 355, 255)
    elif index == 2:
        _draw_bridge(draw, accent)
    elif index == 3:
        _draw_lotus(draw, accent)
    elif index == 5:
        _draw_fountain(draw, accent)
    elif index == 6:
        _draw_buddha(draw, accent)
    elif index == 7:
        _draw_palace(draw, accent)
    else:
        _draw_temple(draw, accent)
    return image


def _draw_gate(draw: ImageDraw.ImageDraw, color: str, x: int, y: int) -> None:
    draw.rectangle((x, y + 90, x + 250, y + 120), fill=color)
    for offset in (20, 90, 160, 230):
        draw.rectangle((x + offset, y + 100, x + offset + 16, y + 270), fill=color)
    draw.polygon([(x - 30, y + 90), (x + 125, y + 25), (x + 280, y + 90)], fill="#6a4a35")


def _draw_bridge(draw: ImageDraw.ImageDraw, color: str) -> None:
    draw.arc((270, 330, 690, 590), 190, 350, fill=color, width=30)
    draw.line((250, 390, 710, 390), fill="#f4e8d4", width=24)


def _draw_lotus(draw: ImageDraw.ImageDraw, color: str) -> None:
    center = (480, 395)
    for angle in range(0, 360, 45):
        dx = math.cos(math.radians(angle)) * 90
        dy = math.sin(math.radians(angle)) * 55
        draw.ellipse((center[0] + dx - 55, center[1] + dy - 28, center[0] + dx + 55, center[1] + dy + 28), fill=color)
    draw.ellipse((420, 340, 540, 460), fill="#e3b45f")


def _draw_fountain(draw: ImageDraw.ImageDraw, color: str) -> None:
    draw.ellipse((300, 430, 660, 520), fill="#72a8b7")
    for x in range(350, 651, 60):
        draw.arc((x - 35, 255, x + 35, 480), 180, 360, fill="#f5fbfd", width=8)
    draw.ellipse((430, 350, 530, 450), fill=color)


def _draw_buddha(draw: ImageDraw.ImageDraw, color: str) -> None:
    draw.ellipse((345, 150, 615, 420), fill="#efd18e")
    draw.ellipse((452, 215, 508, 271), fill="#9a6a2f")
    draw.ellipse((466, 199, 494, 225), fill="#9a6a2f")
    draw.polygon([(480, 265), (360, 445), (600, 445)], fill=color)
    draw.arc((395, 260, 565, 430), 200, 340, fill="#d7a655", width=18)
    draw.ellipse((335, 430, 625, 492), fill="#d7a655")
    draw.ellipse((385, 448, 575, 510), fill="#b87a34")


def _draw_palace(draw: ImageDraw.ImageDraw, color: str) -> None:
    draw.rectangle((280, 350, 680, 520), fill="#d9c8aa")
    draw.polygon([(235, 365), (480, 230), (725, 365)], fill=color)
    for x in range(320, 681, 72):
        draw.rectangle((x, 385, x + 24, 520), fill="#a77b4f")


def _draw_temple(draw: ImageDraw.ImageDraw, color: str) -> None:
    for level in range(4):
        y = 470 - level * 62
        width = 300 - level * 52
        left = 480 - width // 2
        draw.rectangle((left + 35, y, left + width - 35, y + 48), fill="#d7bd8f")
        draw.polygon([(left, y), (480, y - 32), (left + width, y)], fill=color)


if __name__ == "__main__":
    # 素材放在包内便于测试和首次启动复制，避免演示依赖外部图床。
    generate(Path(__file__).resolve().parents[1] / "src" / "lingjing_ai" / "assets" / "attractions")
