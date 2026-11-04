#!/usr/bin/env python3
"""Render a captured, unedited BYOD Gradio trajectory as a square GIF."""
from __future__ import annotations

import argparse
import colorsys
import json
import re
from pathlib import Path

from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont


def font(size, bold=False):
    names = [
        '/System/Library/Fonts/Supplemental/Arial Bold.ttf' if bold else '/System/Library/Fonts/Supplemental/Arial.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    ]
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    raise RuntimeError('Install Arial or DejaVu Sans to render the animation.')


def probability_color(value):
    return tuple(round(v * 255) for v in colorsys.hls_to_rgb(int(value * 120) / 360, .30, .90))


def tokens(html):
    soup = BeautifulSoup(html, 'html.parser')
    result = []
    for span in soup.find_all('span'):
        title = span.get('title', '')
        if 'token position' not in title:
            continue
        masked = 'masked at iteration' in title
        match = re.search(r'sampling probability ([\d.]+)%', title)
        probability = float(match[1]) / 100 if match else 0
        # Parse the original CSS hue instead of deriving it from rounded tooltips.
        hue = re.search(r'color:hsl\((\d+),90%,30%\)', span.get('style', ''))
        color = tuple(round(v * 255) for v in colorsys.hls_to_rgb(int(hue[1]) / 360, .3, .9)) if hue else probability_color(probability)
        result.append(dict(text=span.get_text(), masked=masked, color=color, bold='font-weight:600' in span.get('style', '')))
    return result


def draw_answer(draw, items, size):
    regular, bold = font(size), font(size, True)
    chars = []
    for item in items:
        for char in ('\ufffc' if item['masked'] else item['text']):
            chars.append((char, item))
    text = ''.join(char for char, _ in chars)
    mask_font = font(17, True)
    mask_width = draw.textlength('MASK', font=mask_font) + 16
    x, y, right, line = 64., 340., 1016., size * 1.58
    for match in re.finditer(r'\ufffc|\n|[^\S\n]+|[^\s\ufffc]+', text):
        group = chars[match.start():match.end()]
        word = match[0]
        if word == '\n':
            x, y = 64., y + line
            continue
        width = mask_width + 4 if word == '\ufffc' else sum(draw.textlength(ch, font=bold if item['bold'] else regular) for ch, item in group)
        if x + width > right and x > 64:
            x, y = 64., y + line
            if word.isspace():
                continue
        if word == '\ufffc':
            draw.rounded_rectangle((x, y + 7, x + mask_width, y + 32), radius=4, fill='#e3e6ed', outline='#cbd1dc')
            draw.text((x + 8, y + 11), 'MASK', font=mask_font, fill='#66718a')
            x += width
        else:
            for ch, item in group:
                face = bold if item['bold'] else regular
                draw.text((x, y), ch, font=face, fill=item['color'])
                x += draw.textlength(ch, font=face)
    return y + line


def render_frame(html, size, system_guided=False, is_final=False):
    image = Image.new('RGB', (1080, 1080), '#f4f5f9')
    d = ImageDraw.Draw(image)
    d.text((42, 38), 'BYOD: Build Your Own DLM', font=font(44, True), fill='#182237')
    d.text((42, 119), 'What do you know about', font=font(36), fill='#172238')
    d.text((42, 165), 'Diffusion Language Models?', font=font(36), fill='#172238')
    d.rounded_rectangle((32, 240, 1048, 934), radius=22, fill='white', outline='#dce1eb', width=2)
    step = re.search(r'Denoising step (\d+)/(\d+)', html)
    current, total = map(int, step.groups())
    items = tokens(html)
    count = sum(not token['masked'] for token in items)
    label = 'Complete' if is_final else 'Denoising'
    d.text((64, 265), f'{label} · step {current:02d} / {total}', font=font(23, True), fill='#245dc8')
    count_text = f'{count} text tokens'
    d.text((1016 - d.textlength(count_text, font=font(20)), 268), count_text, font=font(20), fill='#66718a')
    d.rounded_rectangle((64, 308, 1016, 315), radius=3, fill='#e6eaf2')
    d.rounded_rectangle((64, 308, 64 + 952 * current / total, 315), radius=3, fill='#6c4bc1')
    bottom = draw_answer(d, items, size)
    if bottom > 917:
        raise ValueError(f'Text overflows at font size {size}: {bottom}')
    d.text((44, 956), 'Prediction probability', font=font(20, True), fill='#29364d')
    d.text((44, 991), 'Lower', font=font(18), fill='#66718a')
    for offset in range(180):
        d.line((112 + offset, 995, 112 + offset, 1010), fill=probability_color(offset / 179), width=1)
    d.text((303, 991), 'Higher', font=font(18), fill='#66718a')
    d.rounded_rectangle((443, 989, 506, 1015), radius=4, fill='#e3e6ed', outline='#cbd1dc')
    d.text((451, 994), 'MASK', font=font(16, True), fill='#66718a')
    d.text((520, 991), 'Masked', font=font(18), fill='#66718a')
    footer = 'System-guided model output' if system_guided else 'Recorded model output'
    d.text((44, 1042), footer + ' · playback slowed for readability', font=font(16), fill='#788298')
    return image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path)
    parser.add_argument('--output', type=Path, default=Path('artifacts/byod_daily_gif/byod-gemma-denoising.gif'))
    parser.add_argument('--sidecars', action='store_true', help='Also export PNG, text, and rendering metadata')
    args = parser.parse_args()
    capture = json.loads(args.capture.read_text())
    frames = capture['frames']
    system_guided = capture.get('settings', {}).get('system_prompt', 'You are a helpful assistant.') != 'You are a helpful assistant.'
    for size in [32, 31, 30, 29, 28, 27, 26, 25, 24, 23, 22]:
        try:
            images = [render_frame(frame[1], size, system_guided, index == len(frames) - 1)
                      for index, frame in enumerate(frames)]
            break
        except ValueError:
            if size == 22:
                raise
    # A common palette avoids flickering and keeps the GIF compact.
    sheet = Image.new('RGB', (1024, 1024), 'white')
    for index, frame in enumerate(images):
        sheet.paste(frame.resize((128, 128)), ((index % 8) * 128, (index // 8) * 128))
    # Reserve exact colors for the UI and all 121 probability hues. Thumbnail
    # quantization alone can drop small colored glyphs and distort confidence.
    ui_colors = ['ffffff', 'f4f5f9', '182237', '566178', 'e8e2fa', '6942a4',
                 '66718a', '172238', 'dce1eb', '245dc8', 'e6eaf2', '6c4bc1',
                 '29364d', 'e3e6ed', 'cbd1dc', '788298']
    optimized = sheet.quantize(colors=119, method=Image.Quantize.MEDIANCUT).getpalette()[:119 * 3]
    colors = optimized + [value for hue in range(121)
                          for value in tuple(round(v * 255) for v in colorsys.hls_to_rgb(hue / 360, .3, .9))]
    colors += [int(color[offset:offset + 2], 16) for color in ui_colors for offset in (0, 2, 4)]
    palette = Image.new('P', (1, 1))
    palette.putpalette(colors)
    converted = [frame.quantize(palette=palette, dither=Image.Dither.NONE) for frame in images]
    durations = [120] * len(images)
    durations[0], durations[-1] = 800, 5000
    args.output.parent.mkdir(parents=True, exist_ok=True)
    converted[0].save(args.output, save_all=True, append_images=converted[1:], duration=durations, loop=0, optimize=True, disposal=1)
    report = dict(capture=str(args.capture), seed=capture['seed'], visible_tokens=capture['visible_tokens'], frames=len(images), dimensions=[1080, 1080], font_size=size, duration_ms=sum(durations), system_guided=system_guided, settings=capture.get('settings'), unedited_answer=capture['answer'])
    if args.sidecars:
        images[-1].save(args.output.with_suffix('.png'))
        args.output.with_suffix('.txt').write_text(capture['answer'] + '\n')
        args.output.with_suffix('.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
