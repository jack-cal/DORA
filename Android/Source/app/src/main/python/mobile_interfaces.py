"""Android interface adapter. Never infer a public NAT mapping from a local IP."""
import asyncio
import ipaddress
import json
import threading
import time

from sumuww import self_address

_slot = threading.BoundedSemaphore(1)


def network_identity():
    """Android sockets belong to a Network even when bound to 0.0.0.0.

    An opaque local identity is sufficient to replace discovery sockets when
    Wi-Fi/mobile routing or addresses change; it is never sent to a peer.
    """
    from java import jclass
    try:
        value = str(jclass('org.sumuww.miner.AndroidInterfaces').networkIdentity())
    except Exception as error:
        raise OSError('Android default network lookup failed') from error
    return value if value else None


def _read_android():
    from java import jclass
    rows = json.loads(str(jclass('org.sumuww.miner.AndroidInterfaces').read()))
    if not isinstance(rows, list) or len(rows) > self_address.MAX_UNICAST_ADDRESSES:
        raise OSError('Android IPv4 address count exceeds limit')
    return tuple(self_address.InterfaceAddress(str(ipaddress.ip_address(row['host'])), row['index'])
                 for row in rows)


def _begin():
    if not _slot.acquire(blocking=False):
        raise OSError('Android interface lookup is busy')
    done = threading.Event()
    result = []
    def worker():
        try:
            result.append((_read_android(), None))
        except Exception:
            result.append(((), OSError('Android interface lookup failed')))
        finally:
            _slot.release()
            done.set()
    try:
        threading.Thread(target=worker, name='sumuww-android-interfaces', daemon=True).start()
    except BaseException:
        _slot.release()
        raise
    return done, result


def _finish(result):
    values, error = result[0]
    if error is not None:
        raise error
    return values


def enumerate_ipv4_interfaces():
    done, result = _begin()
    if not done.wait(self_address.MAX_ENUMERATION_SECONDS):
        raise OSError('Android interface lookup timed out')
    return _finish(result)


async def async_enumerate_ipv4_interfaces():
    done, result = _begin()
    deadline = time.monotonic() + self_address.MAX_ENUMERATION_SECONDS
    while not done.is_set():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise OSError('Android interface lookup timed out')
        await asyncio.sleep(min(.01, remaining))
    return _finish(result)


def install():
    from sumuww.managed_privacy import install_android_paths
    from java import jclass
    install_android_paths(lambda: json.loads(str(jclass('org.sumuww.miner.PrivacyRuntime').paths())))
    # PeerNode imports an alias, so both consumers must use the platform adapter.
    from sumuww import peer
    self_address.enumerate_ipv4_interfaces = enumerate_ipv4_interfaces
    self_address.async_enumerate_ipv4_interfaces = async_enumerate_ipv4_interfaces
    peer.enumerate_ipv4_interfaces = async_enumerate_ipv4_interfaces
