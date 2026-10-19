#!/usr/bin/env python3
"""Build the preprint and a minimal, self-contained arXiv source archive."""
from pathlib import Path
import re
import shutil
import subprocess
import zipfile


ROOT = Path(__file__).resolve().parent


def main():
    build = ROOT / "build"
    build.mkdir(exist_ok=True)
    with (build / "latexmk-output.txt").open("w") as output:
        result = subprocess.run(
            ["latexmk", "-pdf", "-interaction=nonstopmode", "-halt-on-error",
             "-outdir=build", "paper.tex"],
            cwd=ROOT, stdout=output, stderr=subprocess.STDOUT,
        )
    if result.returncode:
        raise SystemExit("Build failed; see build/latexmk-output.txt")
    log = (build / "paper.log").read_text(errors="replace")
    if re.search(r"undefined references|Citation .* undefined|Reference .* undefined", log):
        raise SystemExit("Unresolved citations/references; see build/paper.log")
    source = (ROOT / "paper.tex").read_text()
    abstract = source.split(r"\begin{abstract}", 1)[1].split(r"\noindent", 1)[0]
    abstract = " ".join(abstract.replace(r"\%", "%").replace("--", "–").split())
    (ROOT / "ABSTRACT.txt").write_text(abstract + "\n")
    figures = re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", source)
    inputs = re.findall(r"\\input\{([^}]+)\}", source)
    names = ["paper.tex", "byod_preprint.sty", "fancyhdr.sty", "natbib.sty",
             "references.bib", "byod.bst", *inputs, *figures]
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    archive = dist / "arxiv-source.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as package:
        for name in sorted(set(names)):
            package.write(ROOT / name, name)
        package.write(build / "paper.bbl", "paper.bbl")
    shutil.copy2(build / "paper.pdf", ROOT / "paper.pdf")
    print(f"PDF: {ROOT / 'paper.pdf'}")
    print(f"Upload: {archive} ({archive.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
