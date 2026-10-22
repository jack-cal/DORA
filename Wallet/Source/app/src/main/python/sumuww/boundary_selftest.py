"""Explicit, disposable runtime diagnostic; never opens the user's node/wallet."""
import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from .chain import Chain
from .peer import PeerNode
from .wallet import RegtestKey
from .boundary_crypto import NodeKeys,BLS,split_signature,verify_split,vrf_verify,canonical

class _LoopbackPeer(PeerNode):
    async def _open_target(self,target):
        return await asyncio.open_connection(*target,local_addr=(self.address[0],0))

async def _until(predicate):
    async with asyncio.timeout(180):
        while not predicate():await asyncio.sleep(.03)

async def _network(root):
    pay=RegtestKey.from_int(1).script_pubkey;seed=[];nodes=[]
    with Chain(root/'seed.sqlite') as chain:
        for _ in range(2):
            block=chain.make_block(pay);chain.accept_block(block);seed.append(block)
    try:
        for i in range(3):
            database=root/str(i)/'node.sqlite'
            with Chain(database) as chain:
                for block in seed:chain.accept_block(block)
            node=_LoopbackPeer(database,network='regtest',boundary_activation=3,host=f'127.0.0.{i+1}',port=0,
                discover_peers=False,dht_enabled=False,poll_interval=.1,timeout=30)
            await node.start();nodes.append(node)
        # A path, not a full mesh: the first node must receive the third
        # responder and signature through an actual relay.
        for i in range(2):await nodes[i].add_peer(*nodes[i+1].address)
        await _until(lambda:sum(len(n.boundary_runtime.sessions()) for n in nodes)==4)
        signed=0;ordinary=0
        for attempt in range(200):
            node=nodes[signed%3];block=node.chain.make_block(pay)
            height=node.chain._row(block.header.previous_hash)[2]+1
            required=node.chain.boundary.required(height,block.header.previous_hash)
            before=node.chain.tip_hash
            if required:
                try:node.chain.accept_block(block)
                except ValueError:pass
                else:raise AssertionError('Unsigned selected block accepted')
                assert node.chain.tip_hash==before
                proof=await asyncio.wait_for(node.boundary_runtime.complete(block),180)
                signed+=1
            else:proof=None;ordinary+=1
            assert node.chain.accept_block(block,boundary_envelope=proof)
            await _until(lambda:all(n.chain.tip_hash==block.block_hash() for n in nodes))
            assert all(n.chain.boundary.proof(block.block_hash())==proof for n in nodes)
            if signed>=2 and ordinary:break
        assert signed>=2 and ordinary
        final_height=height
        assert all(n._stats['internal_errors']==0 for n in nodes)
    finally:await asyncio.gather(*(n.stop() for n in nodes))
    for i in range(3):
        with Chain(root/str(i)/'node.sqlite',boundary_activation=3) as chain:
            assert chain.info()['height']==final_height
    return ['real_tcp_relay_discovery_three_distinct_socket_ips','unsigned_selected_block_rejected',
            'ordinary_unselected_pow_blocks_accepted',
            'three_real_signatures_and_binary_block_sync','completed_aggregate_split_and_next_block_sync','persisted_proof_restart']

def run():
    checks=[]
    with TemporaryDirectory(prefix='sumuww-boundary-runtime-') as tmp:
        root=Path(tmp)
        with Chain(root/'public-profile.sqlite',network='dora') as chain:
            assert chain.boundary.activation==9000
        checks.append('public_activation_9000')
        keys=NodeKeys(root/'diagnostic-keys.sqlite','disposable-regtest')
        try:
            message=canonical({'domain':'sumuww-disposable-selftest-v1'})
            ticket=keys.ticket(message)
            assert vrf_verify(bytes.fromhex(keys.node_id),bytes.fromhex(ticket['proof']),message).hex()==ticket['output']
            signature=keys.sign_once('disposable',message)
            assert BLS.Verify(keys.public_key,message,signature)
            a,b=split_signature(signature);assert verify_split(signature,a,b)
            assert not BLS.Verify(keys.public_key,message+b'!',signature)
            assert not verify_split(signature,a,a)
            from py_ecc.bls.g2_primitives import G2_to_signature
            from py_ecc.optimized_bls12_381 import Z2
            identity=G2_to_signature(Z2)
            assert not verify_split(signature,signature,identity)
            assert not verify_split(signature,identity,signature)
            checks+=['real_ecvrf','real_bls_and_tamper_rejection','real_group_signature_split']
        finally:keys.close()
        checks+=asyncio.run(_network(root))
    return {'passed':True,'scope':'isolated_loopback_runtime_not_public_network','activation_height':9000,'checks':checks}

def run_json():return json.dumps(run())
