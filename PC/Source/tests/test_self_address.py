"""Local-address selection and bounded OS enumeration; no external service."""
import ctypes
import ipaddress
import os
import socket
import threading
import time
import unittest
from unittest.mock import patch

from sumuww import self_address as own


class AddressSelectionTests(unittest.TestCase):
    def resolve(self, interfaces, **options):
        return own.resolve_self_address(('0.0.0.0', 24680), allow_internet=True,
                                        automatic=True, interfaces=interfaces, **options)

    def test_private_interfaces_use_actual_port_without_public_claim(self):
        state=self.resolve([own.InterfaceAddress('192.168.7.8'),own.InterfaceAddress('10.5.6.7')])
        self.assertEqual((('127.0.0.1',24680),('10.5.6.7',24680),('192.168.7.8',24680)),state.own_addresses)
        self.assertEqual('local_interface',state.status)
        self.assertIsNone(state.advertised_endpoint)
        self.assertEqual('not_verified',state.external_reachability)

    def test_only_assigned_global_interface_is_selected_deterministically(self):
        state=self.resolve([own.InterfaceAddress('8.8.4.4',7,20),own.InterfaceAddress('1.1.1.1',9,10),
                            own.InterfaceAddress('8.8.8.8',8,10)])
        self.assertEqual(('8.8.8.8',24680),state.advertised_endpoint)
        self.assertEqual('direct_public_interface',state.status)
        self.assertEqual('not_verified',state.external_reachability)

    def test_reserved_cgnat_linklocal_unspecified_and_multicast_not_contacts(self):
        state=self.resolve([own.InterfaceAddress(host) for host in
                            ('0.0.0.0','100.64.1.2','169.254.3.4','192.0.2.1','224.1.2.3','240.1.2.3')])
        self.assertEqual((('127.0.0.1',24680),),state.own_addresses)
        self.assertIsNone(state.advertised_endpoint)

    def test_internet_optout_never_enumerates_or_adds_global_address(self):
        with patch.object(own,'enumerate_ipv4_interfaces') as enumeration:
            state=own.resolve_self_address(('127.0.0.1',12345),automatic=True)
        enumeration.assert_not_called()
        self.assertEqual((('127.0.0.1',12345),),state.own_addresses)
        self.assertIsNone(state.advertised_endpoint)
        with self.assertRaises(ValueError):own.resolve_self_address(('0.0.0.0',12345),automatic=True)
        with self.assertRaises(ValueError):own.resolve_self_address(('8.8.8.8',12345),automatic=True)

    def test_bound_numeric_listener_does_not_claim_other_interfaces(self):
        with patch.object(own,'enumerate_ipv4_interfaces') as enumeration:
            state=own.resolve_self_address(('8.8.8.8',12345),allow_internet=True,automatic=True,
                                           interfaces=[own.InterfaceAddress('1.1.1.1')])
        enumeration.assert_not_called()
        self.assertEqual((('8.8.8.8',12345),),state.own_addresses)
        self.assertEqual(('8.8.8.8',12345),state.advertised_endpoint)

    def test_manual_contact_precedes_global_interface(self):
        state=self.resolve([own.InterfaceAddress('8.8.8.8')],manual_endpoint=('1.1.1.1',12345))
        self.assertEqual(('1.1.1.1',12345),state.advertised_endpoint)
        self.assertEqual('manual_contact',state.status)

    def test_address_bounds_duplicates_and_selected_public_visibility(self):
        values=[own.InterfaceAddress('10.0.0.'+str(i),i,0) for i in range(1,60)]
        values+=[own.InterfaceAddress('8.8.8.8',60,1)]*5
        state=self.resolve(values)
        self.assertEqual(32,len(state.own_addresses))
        self.assertEqual(32,len(set(state.own_addresses)))
        self.assertIn(state.advertised_endpoint,state.own_addresses)
        self.assertEqual(('8.8.8.8',24680),state.advertised_endpoint)

    def test_invalid_types_flags_ports_hosts_and_records_rejected(self):
        for endpoint in (('127.0.0.1',0),('127.0.0.1',True),('127.0.0.1',65536),
                         ('localhost',12345),(2130706433,12345),('fe80::1',12345)):
            with self.subTest(endpoint=endpoint),self.assertRaises(ValueError):
                own.resolve_self_address(endpoint)
        for key in ('allow_internet','allow_lan','automatic'):
            with self.subTest(flag=key),self.assertRaises(ValueError):
                own.resolve_self_address(('127.0.0.1',12345),**{key:1})
        for interfaces in ({},[{}],[('8.8.8.8',1,1)]):
            with self.subTest(records=interfaces),self.assertRaises(ValueError):self.resolve(interfaces)
        with self.assertRaises(ValueError):self.resolve([],manual_endpoint=(134744072,12345))

    def test_interface_values_require_numeric_ipv4_and_valid_metrics(self):
        for arguments in (('localhost',),('fe80::1%7',),('1.1.1.1',True),('1.1.1.1',1,-1),('1.1.1.1',1,2**32)):
            with self.subTest(arguments=arguments),self.assertRaises(ValueError):own.InterfaceAddress(*arguments)

    def test_nonautomatic_mode_does_no_interface_lookup(self):
        with patch.object(own,'enumerate_ipv4_interfaces') as enumeration:
            state=own.resolve_self_address(('0.0.0.0',12345),allow_internet=True)
        enumeration.assert_not_called()
        self.assertIsNone(state.advertised_endpoint)
        self.assertEqual((('127.0.0.1',12345),),state.own_addresses)


class WindowsBufferTests(unittest.TestCase):
    def fixture(self):
        buffer=ctypes.create_string_buffer(2048);base=ctypes.addressof(buffer)
        adapter=own._Adapter.from_buffer(buffer,0)
        adapter.length=ctypes.sizeof(own._Adapter);adapter.if_index=7;adapter.metric=12
        adapter.oper_status=1;adapter.unicast=base+512
        unicast=own._Unicast.from_buffer(buffer,512)
        unicast.length=ctypes.sizeof(own._Unicast);unicast.dad_state=4
        unicast.socket_address.address=base+1024;unicast.socket_address.length=16
        raw=socket.AF_INET.to_bytes(2,'little')+b'\x00\x00'+socket.inet_aton('192.168.5.6')+b'\x00'*8
        ctypes.memmove(base+1024,raw,16)
        return buffer,adapter,unicast

    def test_native_buffer_keeps_only_host_index_metric(self):
        buffer,adapter,unicast=self.fixture()
        adapter.name=123  # Names and hardware identifiers are never read.
        adapter.physical_address[:]=[255]*8
        self.assertEqual((own.InterfaceAddress('192.168.5.6',7,12),),own._parse_windows_buffer(buffer))

    def test_down_and_tentative_addresses_are_ignored(self):
        for field,value in (('oper_status',2),('dad_state',1)):
            buffer,adapter,unicast=self.fixture()
            setattr(adapter if field=='oper_status' else unicast,field,value)
            self.assertEqual((),own._parse_windows_buffer(buffer))

    def test_bad_pointer_and_truncated_record_rejected(self):
        for case in ('adapter','unicast','socket','adapter_length','unicast_length'):
            buffer,adapter,unicast=self.fixture()
            if case=='adapter':adapter.next=123
            elif case=='unicast':adapter.unicast=123
            elif case=='socket':unicast.socket_address.address=123
            elif case=='adapter_length':adapter.length=1
            else:unicast.length=1
            with self.subTest(case=case),self.assertRaises(OSError):own._parse_windows_buffer(buffer)

    def test_cyclic_adapter_or_unicast_list_rejected(self):
        for field in ('adapter','unicast'):
            buffer,adapter,unicast=self.fixture()
            if field=='adapter':adapter.next=ctypes.addressof(buffer)
            else:unicast.next=ctypes.addressof(buffer)+512
            with self.subTest(field=field),self.assertRaises(OSError):own._parse_windows_buffer(buffer)

    def test_os_buffer_growth_is_bounded(self):
        calls=[]
        def oversized(family,flags,reserved,buffer,length):
            calls.append(len(buffer));length._obj.value=own.MAX_BUFFER_BYTES+1;return 111
        class Api:
            GetAdaptersAddresses=staticmethod(oversized)
        with patch.object(own.ctypes,'WinDLL',return_value=Api(),create=True):
            with self.assertRaises(OSError):own._windows_interfaces()
        self.assertEqual([15000],calls)

    def test_os_no_data_and_error_are_distinct(self):
        for code in (232,5):
            class Api:
                GetAdaptersAddresses=staticmethod(lambda *args:code)
            with patch.object(own.ctypes,'WinDLL',return_value=Api(),create=True):
                if code==232:self.assertEqual((),own._windows_interfaces())
                else:
                    with self.assertRaises(OSError):own._windows_interfaces()


class EnumerationWorkerTests(unittest.TestCase):
    def test_blocked_os_call_has_finite_wait_and_one_daemon_worker(self):
        entered,release,finished=threading.Event(),threading.Event(),threading.Event()
        def blocked():
            entered.set()
            try:release.wait(2);return ()
            finally:finished.set()
        try:
            with patch.object(own.os,'name','nt'),patch.object(own,'_ENUMERATION_SLOT',threading.BoundedSemaphore(1)),\
                 patch.object(own,'MAX_ENUMERATION_SECONDS',.03),patch.object(own,'_windows_interfaces',side_effect=blocked) as lookup:
                start=time.monotonic()
                with self.assertRaises(OSError):own.enumerate_ipv4_interfaces()
                self.assertLess(time.monotonic()-start,.25)
                self.assertTrue(entered.is_set());self.assertFalse(finished.is_set())
                with self.assertRaises(OSError):own.enumerate_ipv4_interfaces()
                self.assertEqual(1,lookup.call_count)
                workers=[thread for thread in threading.enumerate() if thread.name=='sumuww-interface-enumeration']
                self.assertEqual(1,len(workers));self.assertTrue(workers[0].daemon)
                release.set();self.assertTrue(finished.wait(1))
        finally:release.set();finished.wait(1)

    def test_real_windows_enumeration_is_local_and_bounded(self):
        if os.name!='nt':
            self.assertEqual((),own.enumerate_ipv4_interfaces());return
        with patch.object(own.socket,'getaddrinfo',side_effect=AssertionError('Unexpected DNS')):
            values=own.enumerate_ipv4_interfaces()
        self.assertLessEqual(len(values),32)
        self.assertTrue(all(isinstance(item,own.InterfaceAddress) for item in values))


if __name__=='__main__':unittest.main()
