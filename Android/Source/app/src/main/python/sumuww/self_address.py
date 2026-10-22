"""Local IP listener addresses from OS interfaces, with no public-IP service.

Addresses are runtime contact hints. A locally assigned global IP does not
prove firewall, routing, or external reachability. No router/firewall writes,
DNS queries, adapter identifiers or hardware identifiers are used.
"""
from __future__ import annotations

import asyncio
import ctypes
from dataclasses import dataclass
import ipaddress
import os
import socket
import threading

from .peer_discovery import discovery_endpoint


DEFAULT_PORT = 18444
REFRESH_INTERVAL = 30
MAX_OWN_ADDRESSES = 32
MAX_ADAPTERS = 64
MAX_UNICAST_ADDRESSES = 128
MAX_BUFFER_BYTES = 256 * 1024
MAX_ENUMERATION_SECONDS = .5
_ENUMERATION_SLOT = threading.BoundedSemaphore(1)
_LAN = tuple(ipaddress.IPv4Network(value) for value in ('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16'))


@dataclass(frozen=True)
class InterfaceAddress:
    host: str
    if_index: int = 0
    metric: int = 0

    def __post_init__(self):
        if not isinstance(self.host,str) or '%' in self.host:raise ValueError('Interface address must be unscoped numeric IP')
        object.__setattr__(self,'host',str(ipaddress.ip_address(self.host)))
        for value in (self.if_index,self.metric):
            if type(value) is not int or not 0<=value<=0xFFFFFFFF:
                raise ValueError('Invalid interface index or metric')


@dataclass(frozen=True)
class SelfAddressState:
    own_addresses: tuple = ()
    advertised_endpoint: tuple | None = None
    status: str = 'not_running'
    external_reachability: str = 'not_verified'


class _Header(ctypes.Structure):
    _fields_=[('length',ctypes.c_uint32),('if_index',ctypes.c_uint32)]


class _HeaderUnion(ctypes.Union):
    _anonymous_=('head',)
    _fields_=[('alignment',ctypes.c_uint64),('head',_Header)]


class _SocketAddress(ctypes.Structure):
    _fields_=[('address',ctypes.c_void_p),('length',ctypes.c_int32)]


class _Adapter(ctypes.Structure):
    _anonymous_=('head',)
    _fields_=[('head',_HeaderUnion),('next',ctypes.c_void_p),('name',ctypes.c_void_p),
              ('unicast',ctypes.c_void_p),('anycast',ctypes.c_void_p),('multicast',ctypes.c_void_p),
              ('dns_servers',ctypes.c_void_p),('dns_suffix',ctypes.c_void_p),('description',ctypes.c_void_p),
              ('friendly_name',ctypes.c_void_p),('physical_address',ctypes.c_uint8*8),
              ('physical_length',ctypes.c_uint32),('flags',ctypes.c_uint32),('mtu',ctypes.c_uint32),
              ('if_type',ctypes.c_uint32),('oper_status',ctypes.c_uint32),('ipv6_index',ctypes.c_uint32),
              ('zones',ctypes.c_uint32*16),('prefix',ctypes.c_void_p),
              ('transmit_speed',ctypes.c_uint64),('receive_speed',ctypes.c_uint64),
              ('wins',ctypes.c_void_p),('gateway',ctypes.c_void_p),('metric',ctypes.c_uint32)]


class _Unicast(ctypes.Structure):
    _anonymous_=('head',)
    _fields_=[('head',_HeaderUnion),('next',ctypes.c_void_p),('socket_address',_SocketAddress),
              ('prefix_origin',ctypes.c_uint32),('suffix_origin',ctypes.c_uint32),
              ('dad_state',ctypes.c_uint32)]


def _parse_windows_buffer(buffer):
    start=ctypes.addressof(buffer);end=start+ctypes.sizeof(buffer)
    def checked(pointer,size):
        if type(pointer) is not int or not start<=pointer<=end-size:
            raise OSError('Invalid OS interface buffer')
    result=[];adapters=set();unicast_seen=set();pointer=start
    while pointer and len(adapters)<MAX_ADAPTERS and len(result)<MAX_OWN_ADDRESSES:
        if pointer in adapters:raise OSError('Cyclic OS interface buffer')
        adapters.add(pointer);checked(pointer,_Adapter.oper_status.offset+4)
        adapter=_Adapter.from_address(pointer)
        if adapter.length<_Adapter.oper_status.offset+4:
            raise OSError('Truncated OS interface record')
        metric=0xFFFFFFFF
        if adapter.length>=_Adapter.metric.offset+4:
            checked(pointer,_Adapter.metric.offset+4);metric=int(adapter.metric)
        item=adapter.unicast if adapter.oper_status==1 else None
        while item and len(unicast_seen)<MAX_UNICAST_ADDRESSES and len(result)<MAX_OWN_ADDRESSES:
            if item in unicast_seen:raise OSError('Cyclic OS interface address list')
            unicast_seen.add(item);checked(item,_Unicast.dad_state.offset+4)
            address=_Unicast.from_address(item)
            if address.length<_Unicast.dad_state.offset+4:
                raise OSError('Truncated OS unicast record')
            endpoint=address.socket_address
            if address.dad_state==4 and 16<=endpoint.length<=128:
                checked(endpoint.address,16)
                raw=ctypes.string_at(endpoint.address,16)
                if int.from_bytes(raw[:2],'little')==socket.AF_INET:
                    host=socket.inet_ntoa(raw[4:8])
                    candidate=InterfaceAddress(host,int(adapter.if_index),metric)
                    if candidate not in result:result.append(candidate)
                elif int.from_bytes(raw[:2],'little')==socket.AF_INET6 and endpoint.length>=28:
                    checked(endpoint.address,28)
                    raw6=ctypes.string_at(endpoint.address,28)
                    if int.from_bytes(raw6[24:28], 'little') == 0:
                        candidate=InterfaceAddress(socket.inet_ntop(socket.AF_INET6,raw6[8:24]),int(adapter.ipv6_index),metric)
                        if candidate not in result:result.append(candidate)
            item=address.next
        pointer=adapter.next
    return tuple(sorted(result,key=lambda value:(value.metric,value.if_index,int(ipaddress.ip_address(value.host)))))


def _windows_interfaces():
    api=ctypes.WinDLL('iphlpapi').GetAdaptersAddresses
    api.argtypes=[ctypes.c_uint32,ctypes.c_uint32,ctypes.c_void_p,ctypes.c_void_p,
                  ctypes.POINTER(ctypes.c_uint32)]
    api.restype=ctypes.c_uint32
    size=15000
    for _ in range(3):
        if not 1<=size<=MAX_BUFFER_BYTES:raise OSError('OS interface buffer exceeds its limit')
        buffer=ctypes.create_string_buffer(size);length=ctypes.c_uint32(size)
        # Keep unicast IP addresses; skip names, DNS and multicast data.
        code=api(socket.AF_UNSPEC,0x0002|0x0004|0x0008|0x0020,None,buffer,ctypes.byref(length))
        if code==0:return _parse_windows_buffer(buffer)
        if code==232:return ()  # ERROR_NO_DATA
        if code!=111:raise OSError('OS interface enumeration failed')  # ERROR_BUFFER_OVERFLOW
        size=int(length.value)
    raise OSError('OS interface buffer kept changing')


def _begin_enumeration():
    slot=_ENUMERATION_SLOT
    if not slot.acquire(blocking=False):raise OSError('OS interface lookup is busy')
    completed=threading.Event();result=[]
    def worker():
        try:result.append((_windows_interfaces(),None))
        except Exception:result.append(((),OSError('OS interface enumeration failed')))
        finally:slot.release();completed.set()
    try:
        threading.Thread(target=worker,name='sumuww-interface-enumeration',daemon=True).start()
    except Exception:
        slot.release();raise OSError('OS interface worker could not start')
    return completed,result


def _enumeration_result(result):
    values,error=result[0]
    if error is not None:raise error
    return values


def enumerate_ipv4_interfaces():
    """Read Windows interfaces with bounded memory, work and wait time.

    A synchronous OS call may outlive its deadline. Only one daemon worker
    may be in that call; later attempts fail promptly instead of accumulating
    workers. The node remains usable and reports the failed local lookup.
    """
    if os.name!='nt':return ()
    completed,result=_begin_enumeration()
    if not completed.wait(MAX_ENUMERATION_SECONDS):raise OSError('OS interface lookup timed out')
    return _enumeration_result(result)


async def async_enumerate_ipv4_interfaces():
    """Wait for the same bounded OS job without blocking a peer actor."""
    if os.name!='nt':return ()
    completed,result=_begin_enumeration()
    loop=asyncio.get_running_loop();deadline=loop.time()+MAX_ENUMERATION_SECONDS
    while not completed.is_set():
        remaining=deadline-loop.time()
        if remaining<=0:raise OSError('OS interface lookup timed out')
        await asyncio.sleep(min(.01,remaining))
    return _enumeration_result(result)


def _own_endpoint(host,port,*,allow_internet,allow_lan):
    if type(port) is not int or not 1<=port<=65535:raise ValueError('Own address needs the actual bound port')
    if not isinstance(host,str):raise ValueError('Own address must be numeric IP')
    address=ipaddress.ip_address(host)
    if address.version == 6 and ('%' in host or address.ipv4_mapped is not None or address.is_link_local):
        raise ValueError('Scoped, mapped or link-local IPv6 is not a public contact')
    if address.is_loopback:return str(address),port
    if (allow_internet or allow_lan) and address.version == 6 and address in ipaddress.IPv6Network('fc00::/7'):
        return str(address),port
    if (allow_internet or allow_lan) and any(address in block for block in _LAN):return str(address),port
    if allow_internet:return discovery_endpoint(str(address),port)
    raise ValueError('Own address is outside the permitted local scope')


def resolve_self_address(bound_endpoint,*,allow_internet=False,allow_lan=False,automatic=False,
                         manual_endpoint=None,interfaces=None,include_ipv6=False):
    for value in (allow_internet,allow_lan,automatic):
        if type(value) is not bool:raise ValueError('Own-address permission flags must be bools')
    if not isinstance(bound_endpoint,(tuple,list)) or len(bound_endpoint)!=2:
        raise ValueError('Own address needs an IP host and actual port')
    host,port=bound_endpoint
    if not isinstance(host,str):raise ValueError('Own address must be numeric IP')
    address=ipaddress.ip_address(host)
    own=[];public=[]
    if address.is_unspecified:
        if host not in ('0.0.0.0', '::') or not (allow_internet or allow_lan):raise ValueError('Wildcard own listener requires Internet or LAN permission')
        own.append(_own_endpoint('::1' if address.version == 6 else '127.0.0.1',port,allow_internet=allow_internet,allow_lan=allow_lan))
        if automatic:
            if interfaces is None:interfaces=enumerate_ipv4_interfaces()
            if not isinstance(interfaces,(tuple,list)):raise ValueError('Invalid local interface list')
            bounded=interfaces[:MAX_UNICAST_ADDRESSES]
            if any(not isinstance(item,InterfaceAddress) for item in bounded):
                raise ValueError('Invalid local interface record')
            ordered=sorted(bounded,
                           key=lambda item:(item.metric,item.if_index,int(ipaddress.ip_address(item.host))))
            for item in ordered:
                if ipaddress.ip_address(item.host).version != address.version and not include_ipv6:
                    continue
                try:target=_own_endpoint(item.host,port,allow_internet=allow_internet,allow_lan=allow_lan)
                except ValueError:continue
                if target not in own and len(own)<MAX_OWN_ADDRESSES:own.append(target)
                try:
                    if target not in public:public.append(discovery_endpoint(*target))
                except ValueError:pass
    else:
        target=_own_endpoint(host,port,allow_internet=allow_internet,allow_lan=allow_lan)
        own.append(target)
        if automatic:
            try:public.append(discovery_endpoint(*target))
            except ValueError:pass
    selected=None;status='local_interface' if any(not ipaddress.ip_address(item[0]).is_loopback for item in own) else 'loopback_only'
    if manual_endpoint is not None:
        if not isinstance(manual_endpoint,(tuple,list)) or len(manual_endpoint)!=2:
            raise ValueError('Manual contact needs numeric IP and port')
        selected=_own_endpoint(*manual_endpoint,allow_internet=allow_internet,allow_lan=allow_lan)
        status='manual_contact'
    elif automatic and public:
        selected=public[0];status='direct_public_interface'
        if selected not in own:
            # The selected listener remains visible even with many private
            # interfaces; every reported address still fits the same bound.
            own[-1]=selected
    return SelfAddressState(tuple(own),selected,status)
