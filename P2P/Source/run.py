from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'vendor'))
sys.path.insert(0,str(ROOT))
if __name__=='__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    from smw_trade.app import main
    main(ROOT)
