"""Packaged offline smoke check: owned disposable profiles and native widgets."""
import json,tkinter as tk
from pathlib import Path
from .application import MarketApplication
from .desktop import MarketDesktop
from . import VERSION
from .amounts import QUOTES
from .vault import COINS

def run(root,directory,flavor='full'):
    directory=Path(directory)
    if directory.exists():raise ValueError('Self-check requires a new directory.')
    a=MarketApplication(root,directory/'a','test',flavor=flavor);b=MarketApplication(root,directory/'b','test',flavor=flavor);ui=None
    try:
        a.vault.create('disposable-build-check-password');b.vault.create('disposable-build-check-password')
        a.connect('127.0.0.1',b.relay.address[1]);b.connect('127.0.0.1',a.relay.address[1])
        for coin in QUOTES:
            # Offline smoke checks must not fake funded application orders.
            try:a.create(side='sell',coin=coin,quantity='10',price='0.5')
            except ValueError:pass
            else:raise AssertionError('Unfunded posting was accepted')
            assert not a.store.listing()
        root_window=tk.Tk();root_window.withdraw();ui=MarketDesktop(a,root_window)
        for code,name in ui.localization.languages.items():
            ui.language.set(name);ui.change_language();root_window.update()
            assert tuple(ui.pair_select['values'])==QUOTES
            assert tuple(ui.node_select['values'])==COINS
            assert 'contract' not in ui.vars
        assert set(a.vault.state()['addresses'])==set(COINS)=={'SMW','BTC'}
        report={'passed':True,'version':VERSION,'edition':flavor,'languages':len(ui.extra),'pairs':len(QUOTES),'assets':list(QUOTES),'native_window':True,'unfunded_posting_rejected':True,'funded_trade_test':False,'contract_deployment_required':False,'public_funds_used':False}
        (directory/'report.json').write_text(json.dumps(report,indent=2))
        return report
    finally:
        if ui:ui.close()
        a.close();b.close()
