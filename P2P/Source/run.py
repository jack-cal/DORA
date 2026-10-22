from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'vendor'))
sys.path.insert(0,str(ROOT))
if __name__=='__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    if '--market-self-check' in sys.argv:
        # Windowed build checks must fail visibly in a log, not hang on a dialog.
        import traceback
        try:
            from smw_trade.app import main
            main(ROOT)
        except Exception:
            directory=Path(sys.argv[sys.argv.index('--data-dir')+1])
            directory.parent.mkdir(parents=True,exist_ok=True)
            directory.with_suffix('.error.log').write_text(traceback.format_exc(),encoding='utf8')
            raise SystemExit(1)
    else:
        from smw_trade.app import main
        main(ROOT)
