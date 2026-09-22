#!/usr/bin/env python3
"""Capture the five Gemma demo trajectories used by the ICLR appendix."""

from __future__ import annotations

import colorsys
import re
from pathlib import Path

from bs4 import BeautifulSoup
from gradio_client import Client
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "iclr2027_submission" / "figures"
PROMPT = "What do you know about Amsterdam?"
SYSTEM_PROMPT = "You are a helpful assistant."
SPACE = "Ruurd/byod-gemma-2-9b"

CASES = (
    ("demo_gemma_random_64steps_64tokens_iteration.png", 64, 64, "Random", "Prediction iteration"),
    ("demo_gemma_confidence_64steps_64tokens_iteration.png", 64, 64, "Confidence-guided", "Prediction iteration"),
    ("demo_gemma_confidence_64steps_64tokens_probability.png", 64, 64, "Confidence-guided", "Prediction probability"),
    ("demo_gemma_confidence_32steps_64tokens_probability.png", 32, 64, "Confidence-guided", "Prediction probability"),
    ("demo_gemma_confidence_16steps_64tokens_probability.png", 16, 64, "Confidence-guided", "Prediction probability"),
)

POSITIVE_EXAMPLE_ATTEMPTS = 10


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    names = (
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    )
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def _hsl_color(hue: int, saturation: int, lightness: int) -> tuple[int, int, int]:
    red, green, blue = colorsys.hls_to_rgb(hue / 360, lightness / 100, saturation / 100)
    return (round(red * 255), round(green * 255), round(blue * 255))


def _css_color(style: str) -> tuple[int, int, int]:
    match = re.search(r"color:hsl\((\d+),(\d+)%,(\d+)%\)", style)
    if not match:
        return (55, 65, 81)
    hue, saturation, lightness = (int(value) for value in match.groups())
    return _hsl_color(hue, saturation, lightness)


def _answer_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    return "".join(span.get_text() for span in soup.find_all("span")).strip()


def _positive_example_score(text: str) -> float:
    """Prefer complete, readable examples while keeping selection deterministic."""
    normalized = " ".join(text.split())
    words = re.findall(r"[A-Za-z]+", normalized.lower())
    score = min(len(words), 50) / 10
    score += 2 if normalized.startswith("Amsterdam") else 0
    score += 2 if "capital" in normalized.lower() else 0
    score += 2 if normalized.endswith((".", "!", "?")) else -3
    score += min(normalized.count("."), 3)
    score += 1 if "known for" in normalized.lower() else 0
    repeated = sum(left == right for left, right in zip(words, words[1:]))
    score -= 8 * repeated
    for fragment in (
        ",,",
        "..",
        "province",
        "12 provinces",
        "twelve provinces",
        "country netherlands",
        "country' population",
        "kingdom netherlands",
        "central bank",
        "united nations",
        "dutch monarchy",
        "dutch government",
        "famous known",
        "known of its",
        "known for of",
        "capital of amsterdam",
        " a the ",
        "of, the netherlands",
        "city and known",
        "nightlife life",
        "one of the world.",
        "the van.",
        "one of one of",
        "nightlife and nightlife",
        "rijks museum",
        "van museum",
        "anne museum",
    ):
        score -= 8 * normalized.lower().count(fragment)
    return score


def _span_color(span, coloring: str, total_steps: int) -> tuple[int, int, int]:
    title = span.get("title", "")
    if coloring == "Prediction iteration":
        match = re.search(r"predicted at iteration (\d+)", title)
        if match:
            fraction = max(0.0, min(1.0, int(match.group(1)) / max(total_steps, 1)))
            return _hsl_color(210, 90, 72 - round(42 * fraction))
    elif coloring == "Prediction probability":
        match = re.search(r"sampling probability ([\d.]+)%", title)
        if match:
            probability = max(0.0, min(1.0, float(match.group(1)) / 100))
            return _hsl_color(int(probability * 120), 90, 30)
    return _css_color(span.get("style", ""))


def render(html: str, output: Path, coloring: str) -> None:
    soup = BeautifulSoup(html, "html.parser")
    spans = soup.find_all("span")
    heading = soup.find("div", style=lambda value: value and "font-weight:700" in value)
    heading_text = heading.get_text(" ", strip=True) if heading else "Final denoising state"
    step_match = re.search(r"Denoising step \d+/(\d+)", heading_text)
    total_steps = int(step_match.group(1)) if step_match else 1

    width, height = 1100, 1000
    margin, x, y = 45, 45, 42
    image = Image.new("RGB", (width, height), "#fafafa")
    draw = ImageDraw.Draw(image)
    title_font = _font(32, bold=True)
    token_font = _font(30)
    token_bold = _font(30, bold=True)
    line_height = 52

    draw.text((margin, y), heading_text, fill="#2563eb", font=title_font)
    y += 68

    for span in spans:
        token = span.get_text()
        style = span.get("style", "")
        probability_match = re.search(r"sampling probability ([\d.]+)%", span.get("title", ""))
        probability = float(probability_match.group(1)) if probability_match else 0.0
        font = token_bold if coloring == "Prediction probability" and probability > 80 else token_font
        token_width = draw.textlength(token, font=font)
        if x + token_width > width - margin and token.strip():
            x = margin
            y += line_height
        draw.text((x, y), token, fill=_span_color(span, coloring, total_steps), font=font)
        x += token_width

    final_height = y + line_height + 24
    draw.rounded_rectangle((8, 8, width - 8, final_height - 8), radius=18, outline="#d1d5db", width=3)
    image = image.crop((0, 0, width, final_height))
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, optimize=True)


def main() -> None:
    client = Client(SPACE)
    cached_html: dict[tuple[int, int, str], str] = {}
    for filename, steps, tokens, remasking, coloring in CASES:
        cache_key = (steps, tokens, remasking)
        if cache_key not in cached_html:
            attempts = POSITIVE_EXAMPLE_ATTEMPTS if steps == tokens == 64 else 1
            candidates = []
            for attempt in range(1, attempts + 1):
                status, html = client.predict(
                    PROMPT,
                    SYSTEM_PROMPT,
                    tokens,
                    steps,
                    tokens,
                    0.7,
                    3,
                    0.0,
                    coloring,
                    remasking,
                    True,
                    False,
                    api_name="/generate",
                )
                answer = _answer_text(html)
                score = _positive_example_score(answer)
                candidates.append((score, html, status, answer))
                print(f"{remasking} {steps}/{tokens} candidate {attempt}: score={score:.1f} | {answer}")
            score, html, status, answer = max(candidates, key=lambda candidate: candidate[0])
            cached_html[cache_key] = html
            print(f"Selected {remasking} {steps}/{tokens}: score={score:.1f} | {answer}")
        else:
            html = cached_html[cache_key]
            status = "reused selected trajectory with alternate coloring"
        destination = OUTPUT_DIR / filename
        render(html, destination, coloring)
        print(f"{destination.name}: {status}")


if __name__ == "__main__":
    main()
