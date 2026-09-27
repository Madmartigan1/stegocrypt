from PIL import Image, ImageDraw, ImageFont

# Windows .ico sizes (rendered at 256). macOS .icns is rendered at 1024 so the
# Retina sizes (512@2x = 1024) stay sharp; the design is identical at both scales.
ico_sizes = [(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)]

def render(S=256):
    k = S / 256  # all coordinates below are in 256px units
    im = Image.new("RGBA", (S,S), (0,0,0,0))
    d = ImageDraw.Draw(im)
    p = lambda *xs: tuple(round(x * k) for x in xs)

    # Colors
    bg = (18, 18, 22, 255)        # dark card
    accent = (21, 101, 192, 255)  # blue
    accent2 = (30, 125, 50, 255)  # green

    # Background rounded card
    d.rounded_rectangle(p(16,16, 256-16, 256-16), radius=round(40*k), fill=bg)

    # Padlock body
    d.rounded_rectangle(p(72,120, 256-72, 256-56), radius=round(28*k), fill=accent)
    # Shackle
    d.arc(p(72,40, 256-72, 200), start=210, end=-30, fill=accent, width=round(16*k))

    # Keyhole
    d.ellipse(p(128-10, 160, 128+10, 180), fill=(230,230,230,255))
    d.rectangle(p(128-4, 178, 128+4, 198), fill=(230,230,230,255))

    # "SC" text (fallback font if arial isn't available)
    try:
        f = ImageFont.truetype("arial.ttf", round(64*k))
    except Exception:
        f = ImageFont.load_default()
    tw, th = d.textbbox((0,0), "SC", font=f)[2:]
    d.text(((S-tw)//2, S-round(24*k)-th), "SC", font=f, fill=accent2)
    return im

render(256).save("assets/stegocrypt.ico", sizes=ico_sizes)
print("Wrote assets/stegocrypt.ico")
render(1024).save("assets/stegocrypt.icns")
print("Wrote assets/stegocrypt.icns")
