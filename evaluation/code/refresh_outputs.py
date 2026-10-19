"""Update canonical summaries, Matplotlib figures and the Markdown report."""
import runpy
from pathlib import Path

def main():
    for name in ['run_analysis.py','make_figures.py','build_report.py']:
        runpy.run_path(str(Path(__file__).with_name(name)),run_name='__main__')
if __name__=='__main__':main()
