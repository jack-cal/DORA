"""Per-frame bounds without selecting a fixed-size prefix of respondents.

Research candidate only. Old v4 peers cannot accept oversized certificates
or bpart; a coordinated upgrade is required before public deployment.
"""
from hashlib import sha256
import secrets
import struct
import tempfile
import time

PART_BYTES=256*1024
MAX_TRANSFER_BYTES=16*1024*1024
MAX_PENDING_BYTES=64*1024*1024
MAX_TRANSFER_SECONDS=120
PART_HEADER=struct.Struct('<12s16sQQ32s')
PART_FRAME_BYTES=PART_HEADER.size+PART_BYTES
COMMANDS=frozenset(('bquery','bresponse','bcall','bblock'))

def fragments(command,payload,*,transfer_id=None):
    if command not in COMMANDS or not payload:raise ValueError('Invalid boundary multipart command')
    if len(payload)>MAX_TRANSFER_BYTES:raise ValueError('Boundary transfer exceeds total byte budget')
    transfer_id=secrets.token_bytes(16) if transfer_id is None else transfer_id
    if len(transfer_id)!=16:raise ValueError('Invalid boundary transfer ID')
    name=command.encode('ascii').ljust(12,b'\0');digest=sha256(payload).digest()
    for offset in range(0,len(payload),PART_BYTES):
        yield PART_HEADER.pack(name,transfer_id,len(payload),offset,digest)+payload[offset:offset+PART_BYTES]

async def send_parts(node,session,command,payload):
    async with session.boundary_part_send_lock:
        for part in fragments(command,payload):await node._send(session,'bpart',part)

class PartReceiver:
    def __init__(self):self.pending={}

    def discard(self,session):
        row=self.pending.pop(session,None)
        if row is not None:row['file'].close()

    def receive(self,session,part):
        try:
            if not PART_HEADER.size<len(part)<=PART_FRAME_BYTES:raise ValueError('Boundary part size')
            name,transfer,total,offset,expected=PART_HEADER.unpack_from(part)
            command=name.rstrip(b'\0').decode('ascii')
            if command not in COMMANDS or name!=command.encode().ljust(12,b'\0'):raise ValueError('Boundary part command')
            data=part[PART_HEADER.size:]
            if not total or offset+len(data)>total:raise ValueError('Boundary part extent')
            if total>MAX_TRANSFER_BYTES:raise ValueError('Boundary transfer exceeds total byte budget')
            row=self.pending.get(session);identity=(command,transfer,total,expected)
            if row is None:
                if offset!=0:raise ValueError('Boundary part missing beginning')
                if sum(r['identity'][2] for r in self.pending.values())+total>MAX_PENDING_BYTES:
                    raise ValueError('Boundary pending transfers exceed total byte budget')
                now=time.monotonic()
                row={'identity':identity,'file':tempfile.TemporaryFile(),'offset':0,'hash':sha256(),'updated':now,'started':now}
                self.pending[session]=row
            if row['identity']!=identity or row['offset']!=offset:raise ValueError('Boundary part context or ordering')
            if time.monotonic()-row['started']>MAX_TRANSFER_SECONDS:raise ValueError('Boundary total transfer deadline')
            row['file'].write(data);row['hash'].update(data);row['offset']+=len(data);row['updated']=time.monotonic()
            if row['offset']!=total:return None
            if row['hash'].digest()!=expected:raise ValueError('Boundary transfer digest')
            row['file'].seek(0);payload=row['file'].read();self.discard(session)
            return command,payload
        except BaseException:
            self.discard(session)
            raise

    def expire(self,idle_seconds):
        now=time.monotonic()
        for session,row in tuple(self.pending.items()):
            if session.writer.is_closing() or now-row['updated']>idle_seconds or now-row['started']>MAX_TRANSFER_SECONDS:self.discard(session)

    def close(self):
        for session in tuple(self.pending):self.discard(session)
