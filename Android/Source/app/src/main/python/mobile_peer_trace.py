"""Temporary on-device execution trace. Metadata only, Android logcat only.

Does not enable RPC, alter protocol traffic or read wallet/transaction bodies.
Instrumentation expires after 30 minutes and is bounded to 80 events/second.
"""
import asyncio
import ctypes
import functools
import itertools
import json
import os
import time
import traceback

_sink = None
_until = 0
_window = 0
_count = 0
_installed = False
_sequence = itertools.count(1)

def emit(event, **fields):
    global _window, _count
    now = time.monotonic()
    if _sink is None or now > _until:
        return
    second = int(now)
    if second != _window:
        _window, _count = second, 0
    _count += 1
    if _count > 80:
        return
    try:
        raw = json.dumps(dict(t=now, pid=os.getpid(), event=event, **fields), separators=(',', ':'), default=str)
        _sink(4, b'SMWPeerTrace', raw[:3800].encode())
    except Exception:
        pass

def identity(session):
    return dict(sid=getattr(session, '_trace_id', None),
                target=session.outgoing, peer=f'{session.nonce:016x}' if session.nonce is not None else None,
                stage=session.handshake_stage, ready=session.ready, synchronized=session.synchronized,
                attempted_protocol=session.attempted_protocol,
                initial_discovery_deferred=getattr(session, 'initial_discovery_deferred', False))

def install():
    global _sink, _until, _installed
    if _installed:
        return
    lib = ctypes.CDLL('liblog.so')
    _sink = lib.__android_log_write
    _sink.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_char_p]
    _sink.restype = ctypes.c_int
    _until = time.monotonic() + 1800
    _installed = True
    from sumuww.peer import PeerNode
    from sumuww.peer_discovery import PeerAddressBook
    from sumuww.dht_discovery import DhtDiscovery
    emit('trace_installed', python=__import__('sys').version.split()[0])

    reserve = PeerNode._reserve
    def traced_reserve(self, reader, writer, outgoing=None):
        session = reserve(self, reader, writer, outgoing)
        if session is None:
            emit('reserve_rejected', target=outgoing, remote=writer.get_extra_info('peername'))
            return None
        session._trace_id = f'{os.getpid()}:{next(_sequence)}'
        emit('tcp_reserved', **identity(session), local=writer.get_extra_info('sockname'),
             remote=writer.get_extra_info('peername'))
        close = writer.close
        def traced_close():
            if not writer.is_closing():
                emit('local_close', **identity(session), reason=session.local_close_reason,
                     stack=[f'{f.name}:{f.lineno}' for f in traceback.extract_stack(limit=7)[:-1]])
            return close()
        writer.close = traced_close
        protocol = writer.transport.get_protocol()
        eof = protocol.eof_received
        def traced_eof():
            emit('transport_eof', **identity(session), closing=writer.is_closing())
            return eof()
        protocol.eof_received = traced_eof
        lost = protocol.connection_lost
        def traced_lost(exc):
            emit('transport_lost', **identity(session), error=type(exc).__name__ if exc else None,
                 errno=getattr(exc, 'errno', None), closing=writer.is_closing())
            return lost(exc)
        protocol.connection_lost = traced_lost
        return session
    PeerNode._reserve = traced_reserve

    def wrap_async(name):
        original = getattr(PeerNode, name)
        @functools.wraps(original)
        async def wrapped(self, session, *args, **kwargs):
            if name == '_send':
                emit('send_begin', **identity(session), command=args[0], size=len(args[1]) if len(args)>1 else 0)
            elif name == '_handshake':
                emit('handshake_begin', **identity(session))
            try:
                result = await original(self, session, *args, **kwargs)
            except BaseException as exc:
                emit('call_exception', **identity(session), function=name,
                     exception=type(exc).__name__, detail=str(exc)[:180])
                raise
            if name == '_read':
                emit('frame_received', **identity(session), command=result.command, size=len(result.payload))
                if result.command == 'version':
                    from sumuww.wire import decode_version
                    try:
                        remote=decode_version(result.payload)
                        emit('remote_version', **identity(session), protocol=remote.protocol,
                             remote_nonce=f'{remote.nonce:016x}', requested=session.attempted_protocol)
                    except Exception:
                        pass
            elif name == '_send':
                emit('frame_sent', **identity(session), command=args[0])
            elif name == '_handshake':
                emit('handshake_end', **identity(session), protocol=session.protocol)
            elif name == '_poll_session':
                now=time.monotonic()
                if now-getattr(session, '_trace_heartbeat', 0)>=10:
                    session._trace_heartbeat=now
                    emit('live_connection', **identity(session), tip=self.chain.tip_hash.hex(),
                         closing=session.writer.is_closing(), eof=session.reader.at_eof())
            elif name == '_run_session':
                emit('session_end', **identity(session), reason=session.local_close_reason,
                     retry_discovery_pending=session.outgoing in getattr(self, '_short_session_grace', {}))
            return result
        setattr(PeerNode, name, wrapped)
    for name in ('_send', '_read', '_handshake', '_run_session', '_poll_session', '_handle'):
        wrap_async(name)

    open_target=PeerNode._open_target
    async def traced_open(self, target):
        emit('dial_begin', target=target)
        try:
            value=await open_target(self, target)
        except BaseException as exc:
            emit('dial_exception', target=target, exception=type(exc).__name__, detail=str(exc)[:160])
            raise
        emit('dial_connected', target=target)
        return value
    PeerNode._open_target=traced_open

    hints=PeerNode._received_dht_hints
    def traced_hints(self, endpoints):
        emit('automatic_dht_hints', endpoints=endpoints)
        return hints(self, endpoints)
    PeerNode._received_dht_hints=traced_hints
    addresses=PeerNode._received_addresses
    def traced_addresses(self, session, payload):
        value=addresses(self, session, payload)
        emit('address_response_handled', **identity(session), endpoints=session.last_address_response)
        return value
    PeerNode._received_addresses=traced_addresses

    candidate=PeerAddressBook.candidate
    def traced_candidate(self, excluded=(), **kwargs):
        target=candidate(self, excluded, **kwargs)
        now=time.monotonic()
        if target is not None or now-getattr(self, '_trace_candidate_at', 0)>=10:
            self._trace_candidate_at=now
            emit('candidate_selected', target=target, entries=len(self._entries),
                 excluded=len(excluded), retry_cap=kwargs.get('retry_cap'))
        return target
    PeerAddressBook.candidate=traced_candidate

    lookup=DhtDiscovery._lookup
    async def traced_lookup(self):
        emit('dht_lookup_begin', family=self.family)
        result=await lookup(self)
        emit('dht_lookup_end', family=self.family, hints=result, result=self._last_lookup_result)
        return result
    DhtDiscovery._lookup=traced_lookup

    query=DhtDiscovery._query
    async def traced_query(self, endpoint, method, arguments):
        result=await query(self, endpoint, method, arguments)
        nodes=[]
        if method == b'get_peers' and result and result.get(b'y') == b'r':
            try:
                hints, contacts, _=self._parse_contacts(result[b'r'])
                nodes=[dict(endpoint=address, distance=f'{int.from_bytes(node_id,"big") ^ int.from_bytes(self.key,"big"):040x}')
                       for node_id,address in contacts]
            except Exception:
                pass
        emit('dht_query_reply', family=self.family, endpoint=endpoint, method=method.decode(),
             responded=result is not None, nodes=nodes[:16])
        return result
    DhtDiscovery._query=traced_query

    retain=DhtDiscovery._retain_referral
    def traced_retain(self, frontier, visited, initial, node_id, target):
        before=dict(frontier)
        replaced=self._stats['routing_replacements']
        result=retain(self,frontier,visited,initial,node_id,target)
        if self._stats['routing_replacements']>replaced:
            removed=next(endpoint for endpoint in before if endpoint not in frontier)
            emit('dht_route_replaced',family=self.family,endpoint=target,removed=removed,
                 distance=f'{int.from_bytes(node_id,"big") ^ int.from_bytes(self.key,"big"):040x}',
                 removed_distance=f'{int.from_bytes(before[removed],"big") ^ int.from_bytes(self.key,"big"):040x}',
                 tracked=len(frontier)+len(visited))
        return result
    DhtDiscovery._retain_referral=traced_retain

    task_done=PeerNode._task_done
    def traced_task_done(self, task):
        if not task.cancelled() and task.exception() is not None:
            emit('node_task_failed', task=task.get_name(), exception=type(task.exception()).__name__, detail=str(task.exception())[:180])
        return task_done(self, task)
    PeerNode._task_done=traced_task_done

