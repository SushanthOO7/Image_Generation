from io import BytesIO
from textwrap import wrap

from PIL import Image, ImageDraw, ImageFont


def render_placeholder_image(prompt: str, size: tuple[int, int] = (1024, 1024)) -> bytes:
    width, height = size
    image = Image.new("RGB", size, color=(16, 20, 22))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()

    clean_prompt = prompt.encode("ascii", "replace").decode("ascii")
    title = "FLUX.2 mock generation"
    lines = [title, "", *wrap(clean_prompt, width=42)]

    y = 96
    for index, line in enumerate(lines[:16]):
        fill = (143, 213, 197) if index == 0 else (244, 240, 232)
        draw.text((80, y), line, fill=fill, font=font)
        y += 36

    draw.rectangle((80, height - 180, width - 80, height - 80), outline=(143, 213, 197), width=3)
    draw.text((104, height - 144), "Storage stage: MinIO object uploaded", fill=(215, 208, 196), font=font)

    output = BytesIO()
    image.save(output, format="WEBP", quality=92)
    return output.getvalue()


def render_thumbnail(image_bytes: bytes, size: tuple[int, int] = (320, 320)) -> bytes:
    with Image.open(BytesIO(image_bytes)) as image:
        image.thumbnail(size)
        output = BytesIO()
        image.save(output, format="WEBP", quality=85)
        return output.getvalue()
