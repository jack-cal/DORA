from . import __version__
"""Opt-in two-process check: each process owns only its own encrypted keys.

The parent fixture mines worthless regtest coins and observes public results.
It never receives private keys or vault passwords from either participant.
"""
import json
import multiprocessing
import os
import secrets
from pathlib import Path
from .app import Application
from .bitcoin import Bitcoin
from .research_node import ResearchNode
from .research_chain import SwapChain
from .orders import order_id
from .wallet_link import bitcoin_script
from sumuww.address import decode_address


def worker(connection,root,directory):
    app=None
    try:
        app=Application(root,directory)
        if not app.vault.state()['exists']:
            password=secrets.token_urlsafe(32)
            app.command('wallet_create',{'password':password})
            password=None
        connection.send({'ok':True,'result':{'pid':os.getpid(),'port':app.relay.address[1],
                                            'wallet':app.vault.state()}})
        while True:
            name,body=connection.recv()
            if name=='close':break
            try:
                value=app.state() if name=='state' else app.command(name,body)
                connection.send({'ok':True,'result':value})
            except Exception as exc:connection.send({'ok':False,'error':str(exc)})
    except Exception as exc:
        try:connection.send({'ok':False,'error':str(exc)})
        except (EOFError,BrokenPipeError,OSError):pass
    finally:
        if app:app.close()
        connection.close()


class Party:
    def __init__(self,root,directory):
        context=multiprocessing.get_context('spawn')
        self.parent,child=context.Pipe()
        self.process=context.Process(target=worker,args=(child,root,directory))
        self.process.start();child.close()
        self.initial=self.receive()
    def receive(self):
        if not self.parent.poll(90):raise RuntimeError('Independent participant did not respond')
        value=self.parent.recv()
        if not value['ok']:raise ValueError(value['error'])
        return value['result']
    def call(self,name,body=None):
        self.parent.send((name,body or {}));return self.receive()
    def close(self):
        if self.process.is_alive():
            try:self.parent.send(('close',{}))
            except (BrokenPipeError,OSError):pass
            self.process.join(12)
            if self.process.is_alive():self.process.terminate();self.process.join(5)
        self.parent.close()


def run(root,directory):
    root=Path(root);directory=Path(directory);directory.mkdir(parents=True,exist_ok=False)
    report={'version':__version__,'passed':False,'public_funds':False,'network':'regtest-only',
            'independent_processes':True,'private_keys_transmitted':False}
    a=b=node=btc=None
    try:
        btc=Bitcoin(root/'tools/bitcoin-31.1/bin/bitcoind.exe',directory/'bitcoin').start()
        node=ResearchNode(directory/'smw').start()
        config={'smw_url':f'http://127.0.0.1:{node.port}/rpc','smw_token':str(node.token_file),
                'btc_url':f'http://127.0.0.1:{btc.port}/','btc_cookie':str(btc.cookie)}
        a=Party(root,directory/'seller');b=Party(root,directory/'buyer')
        assert a.initial['pid']!=b.initial['pid'] and os.getpid() not in (a.initial['pid'],b.initial['pid'])
        report['party_pids']=[a.initial['pid'],b.initial['pid']]
        smw_address=a.initial['wallet']['addresses']['smw'];btc_address=b.initial['wallet']['addresses']['btc']
        miner=decode_address(smw_address,network='regtest')
        with node.lock,SwapChain(node.database) as chain:chain.mine(miner,103)
        btc.rpc('generatetoaddress',103,btc_address)
        for party in (a,b):party.call('swap_configure',config)
        a.call('connect',{'port':b.initial['port']});b.call('connect',{'port':a.initial['port']})
        links=[a.call('wallet_link',{'coin':'smw','url':config['smw_url'],'credential_file':config['smw_token'],'address':smw_address}),
               b.call('wallet_link',{'coin':'btc','url':config['btc_url'],'credential_file':config['btc_cookie'],'address':btc_address})]
        assert all(v['read_only'] and v['available_units']>0 for v in links)
        report['node_wallet_queries_passed']=True
        def mine(coin,count=1):
            if coin=='btc':btc.mine(count)
            else:
                with node.lock,SwapChain(node.database) as chain:chain.mine(miner,count)
        def locks():
            order=a.call('order',{'side':'sell','smw':'2.12345678','btc':'0.00007654'})['order']
            b.call('sync');session=b.call('reserve',{'id':order_id(order['body'])})['confirmation']['body']['session']
            for party in (a,b):party.call('peer_prepare',{'session':session})
            a.call('peer_sync',{'session':session})
            a.call('peer_fund',{'session':session});mine('smw');a.call('peer_sync',{'session':session})
            b.call('peer_fund',{'session':session});mine('btc');b.call('peer_sync',{'session':session})
            return session
        session=locks()
        a.call('peer_claim',{'session':session});mine('btc')
        # Seller sends no claim notification. Buyer must observe Bitcoin itself.
        b.call('peer_claim',{'session':session});mine('smw')
        assert all(p.call('peer_status',{'session':session})['received_confirmed'] for p in (a,b))
        with node.lock,SwapChain(node.database) as chain:
            buyer_script=decode_address(b.initial['wallet']['addresses']['smw'],network='regtest')
            assert chain.balance(buyer_script)==212345678
        report['claim_session']=session;report['claim_without_peer_notice_passed']=True
        session=locks()
        a.close();b.close();a=b=None
        # New independent processes, wallets locked, no old password retained.
        a=Party(root,directory/'seller');b=Party(root,directory/'buyer')
        assert a.initial['wallet']['locked'] and b.initial['wallet']['locked']
        mine('btc',16);mine('smw',41)
        a.call('peer_refund',{'session':session});mine('smw')
        b.call('peer_refund',{'session':session});mine('btc')
        assert all(p.call('peer_status',{'session':session})['refund_confirmed'] for p in (a,b))
        report.update(refund_session=session,restart_locked_refunds_passed=True,passed=True,
                      scope='Two processes on one PC, real TCP, actual chain validation; not a two-computer Internet/public-money test')
    except Exception as exc:report['error']=str(exc)
    finally:
        if a:a.close()
        if b:b.close()
        if node:node.close()
        if btc:btc.close()
        (directory/'peer-check.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    return report
