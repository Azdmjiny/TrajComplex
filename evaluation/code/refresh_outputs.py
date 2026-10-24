"""Export current saved-statistics summary to an explicit NEW directory."""
import argparse
from pathlib import Path
from evaluation_runtime import RUNS,new_output

def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--runs',type=Path,default=RUNS)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args(argv)
    from build_report import build_report
    from make_figures import make_figures
    output=new_output(args.output)
    data=build_report(args.runs.resolve(),output)
    make_figures(data,output)
    print('Saved summary and figures in '+str(output))

if __name__=='__main__':main()
