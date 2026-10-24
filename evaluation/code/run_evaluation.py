"""Explicit current workflows; never run hidden variants or overwrite results."""
import argparse
import importlib
import sys

COMMANDS={
    'vectoring':'evaluate_saved_vectoring',
    'holding-control':'evaluate_holding_control',
    'holding-common-cutoff':'analyze_common_cutoff',
    'vectoring-fixed-scales':'diagnose_fixed_scales',
}

def main(argv=None):
    argv=list(sys.argv[1:] if argv is None else argv)
    parser=argparse.ArgumentParser(description=__doc__,epilog='Use COMMAND --help for inputs. No command runs by default.')
    parser.add_argument('command',choices=COMMANDS)
    args=parser.parse_args(argv[:1])
    rest=argv[1:]
    importlib.import_module(COMMANDS[args.command]).cli(rest)

if __name__=='__main__':main()
