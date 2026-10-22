"""Native desktop service. No web signing endpoint or unattended payments."""
import base64, json, secrets, sqlite3, tempfile, threading
from contextlib import closing
from pathlib import Path
from ..instance import DirectoryLock
from ..orders import canonical
from ..vault import _write_new
from .board import Board,identifier
from .relay import BoardRelay
from .vault import TradeVault
from .engine import Engine,adapters,POLICY


def active_connections(config):
    # Retain old settings in backups, but never instantiate retired adapters.
    return {coin:value for coin,value in config.items() if coin not in ('ETH','BNB','XRP')}

class MarketApplication:
    def __init__(self,root,directory,network='mainnet',flavor='full'):
        if flavor not in ('full','light'):raise ValueError('Unknown application edition.')
        self.flavor=flavor;self.header_progress=None
        self.root=Path(root);self.data_lock=DirectoryLock(directory);self.mutex=threading.RLock()
        self.relay=None;self.closing=False
        try:
            self.store=Board(directory,network);self.vault=TradeVault(self.store.directory/'trading-wallet.vault',network)
            self.config_path=self.store.directory/'market-connections.json'
            self.config=json.loads(self.config_path.read_text()) if self.config_path.exists() else {'nodes':{},'listen':{'host':'127.0.0.1','port':0},'peers':[]}
            self.config['nodes']=self.edition_connections(self.config['nodes'])
            self.engine=Engine(self.store,self.vault,self.make_nodes(self.config['nodes']))
            self.relay=BoardRelay(self.store,**self.config['listen']).start();self.relay.swap_handler=self.engine.receive
            for peer in self.config['peers']:self.relay.peers.add(tuple(peer))
        except BaseException:
            if self.relay:self.relay.close()
            self.data_lock.close();raise

    def edition_connections(self,config):
        result=config.copy()
        btc=result.get('BTC')
        if self.flavor=='light':
            from .light_network import DEFAULT_SERVERS
            policy={k:btc[k] for k in ('fee_units','confirmations','block_seconds') if btc and k in btc}
            result['BTC']=btc if btc and btc.get('mode')=='light' else {'mode':'light','servers':list(DEFAULT_SERVERS),**policy}
        elif btc and btc.get('mode')=='light':result.pop('BTC')
        return result

    def progress(self,height,total):self.header_progress=(height,total)
    def make_nodes(self,config):return adapters(active_connections(config),self.store.network,self.store.directory/'light',self.progress)
    def close_nodes(self):
        for node in self.engine.nodes.values():
            if hasattr(node,'close'):node.close()

    def _save_config(self):
        temp=self.config_path.with_suffix('.'+secrets.token_hex(6)+'.tmp')
        _write_new(temp,canonical(self.config));temp.replace(self.config_path)

    def configure(self,coin,values):
        with self.mutex:
            if coin not in ('SMW','BTC'):raise ValueError('Unknown coin connection.')
            if coin=='BTC' and (values.get('mode')=='light')!=(self.flavor=='light'):raise ValueError('Use the Bitcoin connection type for this application edition.')
            node=self.make_nodes({coin:values})[coin]
            try:info=node.info()
            except BaseException:
                if hasattr(node,'close'):node.close()
                raise
            with self.store.connect() as c:states=[json.loads(r[0]) for r in c.execute('SELECT state FROM swaps')]
            for state in states:
                expected=state['offer']['chains'].get(coin)
                if expected and expected!={k:info[k] for k in POLICY}:
                    if hasattr(node,'close'):node.close()
                    raise ValueError('Prepared trades require the same chain identity, fees and confirmation policy.')
            old=self.engine.nodes.get(coin)
            if old and hasattr(old,'close'):old.close()
            self.config['nodes'][coin]=values;self._save_config();self.engine.nodes[coin]=node
            return info

    def listen(self,host,port):
        with self.mutex:
            new=BoardRelay(self.store,host,port).start();new.swap_handler=self.engine.receive
            old=self.relay
            with old.lock:new.peers.update(old.peers);new.routes.update(old.routes)
            self.relay=new;old.close();self.config['listen']={'host':host,'port':new.address[1]};self._save_config()
            return self.relay.address

    def connect(self,host,port):
        n=self.relay.connect(host,port)
        self.config['peers']=[list(p) for p in self.relay.peers];self._save_config();return n

    def sync(self):
        results=[]
        for host,port in tuple(self.relay.peers):
            try:self.relay.connect(host,port);results.append({'host':host,'port':port,'ok':True})
            except (OSError,ValueError):results.append({'host':host,'port':port,'ok':False})
        return results

    def create(self,**values):
        p=self.store.create(**values);delivery=self.relay.publish(p)
        return {'id':identifier(p['body']),'delivery':delivery}

    def cancel_post(self,oid):
        packet=self.store.cancel(oid);return self.relay.publish(packet)

    def route(self,identity):
        endpoint=self.relay.routes.get(identity)
        if endpoint is None:self.sync();endpoint=self.relay.routes.get(identity)
        if endpoint is None:raise ValueError('Connect directly to the author or counterparty to reserve and exchange trade details.')
        return endpoint

    def reserve(self,oid):return self.relay.reserve(self.route(self.store.post(oid)['maker']),oid)

    def sync_trade(self,session):
        t=self.store.terms(session);other=t['buyer'] if self.engine.selling(t) else t['seller']
        return self.relay.sync_swap(self.route(other),self.engine.snapshot(session))

    def cancel_trade(self,session):
        self.engine.cancel(session)
        try:self.sync_trade(session)
        except (OSError,ValueError):pass  # Local cancellation is already durable.
        return self.engine.status(session)

    def state(self):
        with self.store.connect() as c:prepared={r[0] for r in c.execute('SELECT id FROM swaps')}
        return {'network':self.store.network,'wallet':self.vault.state(),'orders':self.store.listing(),
                'sessions':[{**t,'prepared':t['session'] in prepared} for t in self.store.sessions()],
                'listener':self.relay.address,'configured':list(self.engine.nodes),'peers':list(self.relay.peers)}

    def backup(self,destination):
        with self.mutex,self.engine.lock,tempfile.TemporaryDirectory() as tmp:
            database=Path(tmp)/'market.sqlite'
            with self.store.connect() as source,closing(sqlite3.connect(database)) as target:source.backup(target)
            payload={'database':base64.b64encode(database.read_bytes()).decode(),'identity':base64.b64encode((self.store.directory/'market-identity.key').read_bytes()).decode(),'config':self.config}
            envelope={'format':'sumuww-market-recovery-v2','network':self.store.network,'wallet':base64.b64encode(self.vault.path.read_bytes()).decode(),'records':self.vault.seal('recovery-v2',payload)}
            _write_new(destination,canonical(envelope));return {'encrypted_backup':True}

    def restore_backup(self,source,password):
        with self.mutex,self.engine.lock:
            if self.vault.path.exists() or self.store.listing():raise ValueError('Restore into a new, empty profile only.')
            path=Path(source)
            if path.stat().st_size>256*1024*1024:raise ValueError('Recovery archive exceeds the size limit.')
            data=json.loads(path.read_text(encoding='utf8'))
            if set(data)!={'format','network','wallet','records'} or data['format']!='sumuww-market-recovery-v2' or data['network']!=self.store.network:raise ValueError('Wrong recovery archive or network.')
            # Validate everything in an isolated temporary profile before replacing files.
            with tempfile.TemporaryDirectory() as tmp:
                temp=Path(tmp);wallet=temp/'trading-wallet.vault';wallet.write_bytes(base64.b64decode(data['wallet'],validate=True))
                recovered=TradeVault(wallet,self.store.network);recovered.unlock(password);payload=recovered.unseal('recovery-v2',data['records'])
                (temp/'market.sqlite').write_bytes(base64.b64decode(payload['database'],validate=True));(temp/'market-identity.key').write_bytes(base64.b64decode(payload['identity'],validate=True))
                test=Board(temp,self.store.network)
                with test.connect() as c:
                    if c.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Recovery database is damaged.')
                    c.execute('PRAGMA wal_checkpoint(TRUNCATE)')
                test.listing()
                restored_config=payload['config'].copy();restored_config['nodes']=self.edition_connections(restored_config['nodes'])
                self.close_nodes()
                self.relay.close()
                with self.store.connect() as c:c.execute('PRAGMA wal_checkpoint(TRUNCATE)')
                for name in ('market.sqlite','market-identity.key','trading-wallet.vault'):
                    target=self.store.directory/name;staged=target.with_suffix('.restore.tmp');staged.write_bytes((temp/name).read_bytes());staged.replace(target)
                self.store=Board(self.store.directory,self.store.network);self.vault=TradeVault(self.vault.path,self.store.network);self.vault.unlock(password)
                self.config=restored_config;self._save_config();self.engine=Engine(self.store,self.vault,self.make_nodes(self.config['nodes']))
                self.relay=BoardRelay(self.store,'127.0.0.1',0).start();self.relay.swap_handler=self.engine.receive
                for peer in self.config['peers']:self.relay.peers.add(tuple(peer))
            return {'restored':True}

    def close(self):
        if self.closing:return
        self.closing=True
        if self.relay:self.relay.close()
        self.close_nodes()
        self.vault.lock();self.data_lock.close()
