"""Rebuild aircraft-count sensitivity with the same frozen scenes and QC."""
import sys
from run_evaluation import main
if __name__=='__main__':
    if '--counts-only' not in sys.argv:sys.argv.append('--counts-only')
    main()
