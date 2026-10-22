import asyncio, json, socket
import tempfile
from sumuww.peer import PeerNode
from pathlib import Path
from sumuww.dht_discovery import DhtDiscovery
from java import jclass

folder = str(jclass('androidx.test.platform.app.InstrumentationRegistry').getInstrumentation().getTargetContext().getExternalFilesDir(None))
targets = json.loads((Path(folder) / 'owned-internet-targets.json').read_text())
async def main():
    results=[]
    for host,port in targets:
        try:
            reader,writer=await asyncio.wait_for(asyncio.open_connection(host,port),5)
            writer.close()
            await writer.wait_closed()
            results.append({'host':host,'port':port,'connected':True})
        except Exception as error:
            results.append({'host':host,'port':port,'connected':False,'error':type(error).__name__+': '+str(error)})
    hints=[]
    handshakes=[]
    for host,port in targets:
        with tempfile.TemporaryDirectory() as directory:
            node=PeerNode(Path(directory)/'probe.sqlite',network='dora',allow_internet=True,discover_peers=False)
            try:
                await node.start()
                await node.connect(host,port)
                info=node.info()
                handshakes.append({'host':host,'port':port,'connected':True,'handshakes':info['stats']['handshakes']})
            except Exception as error:
                info=node.info()
                handshakes.append({'host':host,'port':port,'connected':False,'error':type(error).__name__+': '+str(error),'node_error':info.get('last_peer_error'),'stats':info.get('stats')})
            finally:
                await node.stop()
    dht=DhtDiscovery('dora',lambda values:hints.extend(values))
    try:
        await dht.start()
        await asyncio.sleep(25)
        return {'connections':results,'handshakes':handshakes,'discovery':dht.info(),'hints':hints}
    finally:
        await dht.stop()
report=json.dumps(asyncio.run(main()))
