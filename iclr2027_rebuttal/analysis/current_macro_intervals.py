"""Reproduce macro intervals from the recovered historical per-question outcomes."""
import runpy,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]/"evaluation"
sys.path.insert(0,str(root))
runpy.run_path(str(root/"historical_report.py"),run_name="__main__")
