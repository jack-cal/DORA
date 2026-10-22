from . import __version__
"""Opt-in frozen-binary test. Refuses existing directories and uses regtest only."""
from pathlib import Path
import json,secrets,time
from .app import Application
from .orders import order_id
from .vault import Vault

def run(root,directory):
    directory=Path(directory)
    directory.mkdir(parents=True,exist_ok=False)
    password=secrets.token_urlsafe(32)
    report={'version':__version__,'network':'regtest-only','public_funds':False,'passed':False,'trades':[]}
    maker=taker=None
    try:
        maker=Application(root,directory/'maker');taker=Application(root,directory/'taker')
        original=taker.command('wallet_create',{'password':password})
        taker.command('wallet_backup',{'path':str(directory/'backup.smwvault')})
        taker.command('wallet_lock',{});assert taker.state()['wallet']['locked']
        try:taker.command('wallet_unlock',{'password':'deliberately-wrong-test-password'})
        except ValueError:pass
        else:raise AssertionError('Wrong password accepted')
        taker.command('wallet_unlock',{'password':password})
        restored=Vault(directory/'restored.vault')
        try:assert restored.restore(directory/'backup.smwvault',password)['addresses']==original['addresses']
        finally:restored.lock()
        report.update(encryption_backup_restore=True,wrong_password_rejected=True)
        for side,mode in [('buy','success'),('sell','refund')]:
            packet=maker.command('order',{'side':side,'smw':'4.12345678','btc':'0.00007654'})['order']
            taker.command('connect',{'port':maker.relay.address[1]})
            confirmation=taker.command('reserve',{'id':order_id(packet['body'])})['confirmation']
            session=confirmation['body']['session']
            taker.command('execute',{'session':session,'mode':mode})
            deadline=time.monotonic()+90
            while taker.state()['job']['running'] and time.monotonic()<deadline:time.sleep(.1)
            job=taker.state()['job']
            if not job.get('passed'):raise AssertionError(job.get('error','Execution did not finish'))
            result=job['result'];assert result['wallet_source']=='encrypted-local-test-vault'
            assert result['local_wallet_id']==original['wallet_id']
            if mode=='success':assert result['smw_received_atoms']==412345678 and result['btc_received_sats']==7654
            else:assert result['smw_refunded_atoms']==412345678 and result['btc_refunded_sats']==7654
            report['trades'].append({'mode':mode,'side':side,'session':session,'passed':True,'seconds':result['elapsed_seconds']})
        taker.close();taker=Application(root,directory/'taker')
        assert taker.state()['wallet']['locked'] and len(taker.state()['trades'])==2
        taker.command('wallet_unlock',{'password':password})
        assert taker.state()['wallet']['addresses']==original['addresses']
        report.update(restart_locked=True,same_addresses_after_restart=True,passed=True)
    except Exception as exc:report['error']=str(exc)
    finally:
        if maker:maker.close()
        if taker:taker.close()
        (directory/'wallet-check.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    return report
