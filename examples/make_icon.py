"""Draw the figure editor icon (plot_editor.ico, next to plot_editor.pyw): a plot on a white tile with black axes, two
curves and a text label selected with its handles. Drawn large and shrunk for each size, so the small sizes stay clean.

    python examples/make_icon.py
"""
import os
import struct

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "plot_editor.ico")
SIZES = [16, 24, 32, 48, 64]      # classic sizes: no 128/256 frames, which only exist as PNG
BIG = 1024


def draw():
    img = Image.new("RGBA", (BIG, BIG), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([40, 40, BIG - 40, BIG - 40], radius=190, fill="#ffffff", outline="#1a1a1a", width=40)
    d.line([(190, 190), (190, 834), (834, 834)], fill="#000000", width=52, joint="curve")
    for p in ((190, 190), (834, 834)):
        d.ellipse([p[0] - 26, p[1] - 26, p[0] + 26, p[1] + 26], fill="#000000")
    # two curves, stamped as round discs (PIL's wide lines come out serrated)
    for x in np.linspace(245, 800, 1400):
        for y, col in ((790 - 330 * np.exp(-((x - 430) / 150) ** 2), "#2d6cb5"),
                       (780 - 150 * (x - 245) / 555, "#f28c00")):
            d.ellipse([x - 30, y - 30, x + 30, y + 30], fill=col)
    # a text label selected for editing: box with four corner handles
    box = [430, 215, 800, 435]
    d.rectangle(box, fill="#ffffff", outline="#2d6cb5", width=20)
    try:
        font = ImageFont.truetype("arialbd.ttf", 190)
    except OSError:
        font = ImageFont.load_default()
    d.text(((box[0] + box[2]) / 2, (box[1] + box[3]) / 2), "Aa", font=font, fill="#000000", anchor="mm")
    for hx in (box[0], box[2]):
        for hy in (box[1], box[3]):
            d.rectangle([hx - 38, hy - 38, hx + 38, hy + 38], fill="#2d6cb5", outline="#ffffff", width=12)
    return img


def write_ico(path, images):
    """A classic .ico: every frame a 32-bit BMP (DIB) with alpha and an empty AND mask, smallest first. Pillow writes
    PNG-compressed frames, which Windows Vista and later read but older or simpler programs (a file manager's
    toolbar button, for one) do not."""
    entries, blobs, offset = [], [], 6 + 16 * len(images)
    for im in images:
        w, h = im.size
        px = np.asarray(im.convert("RGBA"))[::-1][..., [2, 1, 0, 3]]          # BGRA, bottom row first
        pixels = np.ascontiguousarray(px).tobytes()
        mask = bytes(((w + 31) // 32) * 4 * h)                                  # all zero: the alpha channel does the work
        header = struct.pack("<IiiHHIIiiII", 40, w, h * 2, 1, 32, 0, len(pixels) + len(mask), 0, 0, 0, 0)
        blob = header + pixels + mask
        entries.append(struct.pack("<BBBBHHII", w % 256, h % 256, 0, 0, 1, 32, len(blob), offset))
        blobs.append(blob)
        offset += len(blob)
    with open(path, "wb") as f:
        f.write(struct.pack("<HHH", 0, 1, len(images)) + b"".join(entries) + b"".join(blobs))


if __name__ == "__main__":
    big = draw()
    write_ico(OUT, [big.resize((s, s), Image.LANCZOS) for s in SIZES])
    big.resize((256, 256), Image.LANCZOS).save(os.path.join(os.environ.get("TEMP", HERE), "plot_editor_icon_preview.png"))
    print("written", os.path.abspath(OUT), os.path.getsize(OUT), "bytes")
