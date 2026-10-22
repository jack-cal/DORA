"""Local wire bounds and adversarial-stream tests, independent of P2P policy."""

import asyncio
import dataclasses
import struct
import unittest

from sumuww.primitives import Header, encode_compact_size, sha256d
from sumuww.wire import (
    FRAME_HEADER_SIZE, INV_BLOCK, INV_TRANSACTION, MAX_HEADERS, MAX_INV,
    MAX_LOCATOR, MAX_PAYLOAD, NETWORK_MAGIC, PROTOCOL_VERSION, Frame,
    Inventory, PeerDisconnected, ProtocolError, Version, decode_getheaders, decode_headers,
    decode_inventory, decode_ping, decode_version, encode_frame,
    encode_getheaders, encode_headers, encode_inventory, encode_ping,
    encode_version, read_frame, write_frame,
)


HASH_A = bytes(range(32))
HASH_B = bytes(reversed(range(32)))
HEADER = Header(4, HASH_A, HASH_B, 1_700_000_001, 0x207FFFFF, 42)
VERSION = Version(PROTOCOL_VERSION, HASH_A, 0x0102030405060708,
                  "dora-local-regtest-v0.8-p2wpkh", HASH_B)


def damaged(raw, offset, value):
    return raw[:offset] + value + raw[offset + len(value):]


class CodecTests(unittest.TestCase):
    def reject_truncations(self, decoder, raw):
        for length in range(len(raw)):
            with self.subTest(length=length):
                with self.assertRaises(ProtocolError):
                    decoder(raw[:length])
        with self.assertRaises(ProtocolError):
            decoder(raw + b"\x00")

    def test_frame_known_layout_and_checksum(self):
        raw = encode_frame("ping", bytes.fromhex("0807060504030201"))
        self.assertEqual(raw[:4], bytes.fromhex("d0524709"))
        self.assertEqual(raw[4:16], b"ping" + bytes(8))
        self.assertEqual(raw[16:20], b"\x08\x00\x00\x00")
        self.assertEqual(raw[20:24], sha256d(raw[24:])[:4])
        self.assertEqual(len(raw), FRAME_HEADER_SIZE + 8)

    def test_frame_zero_and_maximum_payload(self):
        self.assertEqual(encode_frame("verack", b"")[16:20], bytes(4))
        raw = encode_frame("block", bytes(MAX_PAYLOAD))
        self.assertEqual(len(raw), MAX_PAYLOAD + FRAME_HEADER_SIZE)
        with self.assertRaises(ProtocolError):
            encode_frame("block", bytes(MAX_PAYLOAD + 1))

    def test_frame_rejects_bad_commands(self):
        for command in ("", "Version", "ab cd", "a-b", "a\x00", '\ud55c\uae00', "1inv",
                        "abcdefghijklz", b"ping", None):
            with self.subTest(command=command), self.assertRaises(ProtocolError):
                encode_frame(command, b"")
        self.assertEqual(encode_frame("abcdefghijkl", b"")[4:16], b"abcdefghijkl")
        self.assertEqual(encode_frame("v2", b"")[4:16], b"v2" + bytes(10))

    def test_frame_rejects_bad_payload_and_magic(self):
        for payload in ("text", bytearray(), memoryview(b""), None):
            with self.subTest(payload=type(payload)), self.assertRaises(ProtocolError):
                encode_frame("ping", payload)
        for magic in (b"", b"abc", b"abcde", "dora", None):
            with self.subTest(magic=magic), self.assertRaises(ProtocolError):
                encode_frame("ping", b"", magic)
        self.assertEqual(encode_frame("ping", b"", b"abcd")[:4], b"abcd")

    def test_frame_is_frozen_and_validated(self):
        frame = Frame("tx", b"value")
        with self.assertRaises(dataclasses.FrozenInstanceError):
            frame.payload = b"change"
        with self.assertRaises(ProtocolError):
            Frame("TX", b"")
        with self.assertRaises(ProtocolError):
            Frame("tx", bytearray())

    def test_version_known_layout_and_roundtrip(self):
        raw = encode_version(VERSION)
        profile = VERSION.profile.encode("utf-8")
        self.assertEqual(raw[:4], b"\x01\x00\x00\x00")
        self.assertEqual(raw[4:36], HASH_A)
        self.assertEqual(raw[36:44], bytes.fromhex("0807060504030201"))
        self.assertEqual(raw[44:], bytes([len(profile)]) + profile + HASH_B)
        self.assertEqual(decode_version(raw), VERSION)

    def test_version_integer_boundaries(self):
        for protocol, nonce in ((0, 0), (0xFFFFFFFF, 0xFFFFFFFFFFFFFFFF)):
            value = Version(protocol, HASH_A, nonce, "x", HASH_B)
            self.assertEqual(decode_version(encode_version(value)), value)
        for protocol, nonce in ((True, 0), (-1, 0), (0x100000000, 0),
                                (1, True), (1, -1), (1, 0x10000000000000000)):
            with self.subTest(protocol=protocol, nonce=nonce), self.assertRaises(ProtocolError):
                Version(protocol, HASH_A, nonce, "x", HASH_B)

    def test_version_profile_utf8_boundaries(self):
        for profile in ("x", "x" * 64, '\ud55c' * 21):
            value = dataclasses.replace(VERSION, profile=profile)
            self.assertEqual(decode_version(encode_version(value)), value)
        for profile in ("", "x" * 65, '\ud55c' * 22, "\ud800", None, b"x"):
            with self.subTest(profile=repr(profile)), self.assertRaises(ProtocolError):
                dataclasses.replace(VERSION, profile=profile)

    def test_version_hash_lengths_and_types(self):
        for digest in (bytes(31), bytes(33), bytearray(32), "0" * 32):
            for field in ("genesis", "tip"):
                with self.subTest(field=field, digest=type(digest)), self.assertRaises(ProtocolError):
                    dataclasses.replace(VERSION, **{field: digest})
        with self.assertRaises(ProtocolError):
            encode_version({"protocol": 1})

    def test_version_truncations_and_trailing_bytes(self):
        self.reject_truncations(decode_version, encode_version(VERSION))

    def test_version_rejects_invalid_utf8(self):
        prefix = encode_version(VERSION)[:44]
        for invalid in (b"\xff", b"\xc0\xaf", b"\xed\xa0\x80", b"\xc2"):
            with self.subTest(invalid=invalid), self.assertRaises(ProtocolError):
                decode_version(prefix + bytes([len(invalid)]) + invalid + HASH_B)

    def test_version_rejects_noncanonical_and_oversized_profile(self):
        prefix = encode_version(VERSION)[:44]
        for size in (b"\xfd\x01\x00", b"\xfe\x01\x00\x00\x00",
                     b"\xff" + struct.pack("<Q", 1), b"\x00", b"\x41"):
            with self.subTest(size=size), self.assertRaises(ProtocolError):
                decode_version(prefix + size + b"x" + HASH_B)

    def test_inventory_known_layout_and_roundtrip(self):
        value = (Inventory(INV_TRANSACTION, HASH_A), Inventory(INV_BLOCK, HASH_B))
        raw = b"\x02\x01\x00\x00\x00" + HASH_A + b"\x02\x00\x00\x00" + HASH_B
        self.assertEqual(encode_inventory(value), raw)
        self.assertEqual(decode_inventory(raw), value)

    def test_inventory_count_boundaries(self):
        for count in (0, 1, 252, 253, MAX_INV):
            value = (Inventory(INV_BLOCK, HASH_A),) * count
            self.assertEqual(decode_inventory(encode_inventory(value)), value)
        with self.assertRaises(ProtocolError):
            encode_inventory((Inventory(INV_BLOCK, HASH_A),) * (MAX_INV + 1))
        with self.assertRaises(ProtocolError):
            decode_inventory(encode_compact_size(MAX_INV + 1))

    def test_inventory_rejects_noncanonical_size(self):
        for size in (b"\xfd\x00\x00", b"\xfe\x01\x00\x00\x00",
                     b"\xff" + struct.pack("<Q", 256)):
            with self.subTest(size=size), self.assertRaises(ProtocolError):
                decode_inventory(size)

    def test_inventory_rejects_unknown_or_invalid_kinds(self):
        for kind in (0, 3, 0xFFFFFFFF, True, -1, 0x100000000, "1"):
            with self.subTest(kind=kind), self.assertRaises(ProtocolError):
                Inventory(kind, HASH_A)
        for kind in (0, 3, 0xFFFFFFFF):
            with self.subTest(wire_kind=kind), self.assertRaises(ProtocolError):
                decode_inventory(b"\x01" + struct.pack("<I", kind) + HASH_A)

    def test_inventory_rejects_wrong_container_and_digest(self):
        for items in ([], [Inventory(1, HASH_A)], (HASH_A,), None):
            with self.subTest(items=items), self.assertRaises(ProtocolError):
                encode_inventory(items)
        for digest in (bytes(31), bytes(33), bytearray(32), None):
            with self.subTest(digest=type(digest)), self.assertRaises(ProtocolError):
                Inventory(1, digest)

    def test_inventory_truncations_and_trailing_bytes(self):
        self.reject_truncations(decode_inventory, encode_inventory((Inventory(1, HASH_A), Inventory(2, HASH_B))))

    def test_getheaders_known_layout_and_roundtrip(self):
        locator = (HASH_A, HASH_B)
        self.assertEqual(encode_getheaders(locator), b"\x02" + HASH_A + HASH_B + bytes(32))
        self.assertEqual(decode_getheaders(encode_getheaders(locator, HASH_B)), (locator, HASH_B))

    def test_getheaders_count_boundaries(self):
        for count in (1, MAX_LOCATOR):
            value = (HASH_A,) * count
            self.assertEqual(decode_getheaders(encode_getheaders(value)), (value, bytes(32)))
        for locator in ((), (HASH_A,) * (MAX_LOCATOR + 1), [HASH_A], None):
            with self.subTest(locator=type(locator)), self.assertRaises(ProtocolError):
                encode_getheaders(locator)
        for raw in (b"\x00" + bytes(32), encode_compact_size(MAX_LOCATOR + 1)):
            with self.subTest(raw=raw), self.assertRaises(ProtocolError):
                decode_getheaders(raw)

    def test_getheaders_rejects_digest_lengths_and_types(self):
        for digest in (bytes(31), bytes(33), bytearray(32), None):
            with self.subTest(digest=type(digest)):
                with self.assertRaises(ProtocolError):
                    encode_getheaders((digest,))
                with self.assertRaises(ProtocolError):
                    encode_getheaders((HASH_A,), digest)

    def test_getheaders_rejects_noncanonical_size(self):
        for size in (b"\xfd\x01\x00", b"\xfe\x01\x00\x00\x00",
                     b"\xff" + struct.pack("<Q", 1)):
            with self.subTest(size=size), self.assertRaises(ProtocolError):
                decode_getheaders(size + HASH_A + bytes(32))

    def test_getheaders_truncations_and_trailing_bytes(self):
        self.reject_truncations(decode_getheaders, encode_getheaders((HASH_A, HASH_B)))

    def test_headers_known_layout_and_roundtrip(self):
        value = (HEADER, dataclasses.replace(HEADER, nonce=43))
        self.assertEqual(encode_headers(value), b"\x02" + value[0].serialize() + value[1].serialize())
        self.assertEqual(decode_headers(encode_headers(value)), value)

    def test_headers_count_boundaries(self):
        for count in (0, 1, MAX_HEADERS):
            value = (HEADER,) * count
            self.assertEqual(decode_headers(encode_headers(value)), value)
        with self.assertRaises(ProtocolError):
            encode_headers((HEADER,) * (MAX_HEADERS + 1))
        with self.assertRaises(ProtocolError):
            decode_headers(encode_compact_size(MAX_HEADERS + 1))

    def test_headers_rejects_noncanonical_and_bitcoin_txcount_encoding(self):
        for raw in (b"\xfd\x00\x00", b"\xfd\x01\x00" + HEADER.serialize(),
                    b"\x01" + HEADER.serialize() + b"\x00"):
            with self.subTest(raw_length=len(raw)), self.assertRaises(ProtocolError):
                decode_headers(raw)

    def test_headers_rejects_wrong_container_and_malformed_object(self):
        for value in ([HEADER], (HEADER.serialize(),), None):
            with self.subTest(value=type(value)), self.assertRaises(ProtocolError):
                encode_headers(value)
        with self.assertRaises(ProtocolError):
            encode_headers((dataclasses.replace(HEADER, nonce=True),))
        with self.assertRaises(ProtocolError):
            encode_headers((dataclasses.replace(HEADER, previous_hash=bytes(31)),))

    def test_headers_truncations_and_trailing_bytes(self):
        self.reject_truncations(decode_headers, encode_headers((HEADER, HEADER)))

    def test_ping_known_layout_and_roundtrip(self):
        self.assertEqual(encode_ping(0x0102030405060708), bytes.fromhex("0807060504030201"))
        for value in (0, 0x0102030405060708, 0xFFFFFFFFFFFFFFFF):
            self.assertEqual(decode_ping(encode_ping(value)), value)

    def test_ping_rejects_type_range_and_length(self):
        for value in (-1, 0x10000000000000000, True, 1.0, "1", None):
            with self.subTest(value=value), self.assertRaises(ProtocolError):
                encode_ping(value)
        for raw in (b"", bytes(7), bytes(9), bytearray(8), "x" * 8):
            with self.subTest(raw=type(raw)), self.assertRaises(ProtocolError):
                decode_ping(raw)

    def test_decoders_require_bytes(self):
        for decoder in (decode_version, decode_inventory, decode_getheaders, decode_headers):
            for raw in (None, bytearray(), memoryview(b""), ""):
                with self.subTest(decoder=decoder.__name__, raw=type(raw)), self.assertRaises(ProtocolError):
                    decoder(raw)


class HeaderOnlyReader:
    """Fail if an invalid header triggers a payload read/allocation request."""

    def __init__(self, raw):
        self.raw = raw
        self.requests = []

    async def readexactly(self, size):
        self.requests.append(size)
        if len(self.requests) > 1:
            raise AssertionError("Body read before rejecting invalid header")
        return self.raw


class FakeWriter:
    def __init__(self, *, hang=False):
        self.writes = []
        self.drains = 0
        self.hang = hang

    def write(self, raw):
        self.writes.append(raw)

    async def drain(self):
        self.drains += 1
        if self.hang:
            await asyncio.Event().wait()


class AsyncWireTests(unittest.IsolatedAsyncioTestCase):
    async def test_fragmented_header_and_payload(self):
        encoded = encode_frame("version", encode_version(VERSION))
        reader = asyncio.StreamReader()

        async def feed():
            for byte in encoded:
                reader.feed_data(bytes([byte]))
                await asyncio.sleep(0)

        feeder = asyncio.create_task(feed())
        self.assertEqual(await read_frame(reader, timeout=1), Frame("version", encode_version(VERSION)))
        await feeder

    async def test_consecutive_frames_keep_stream_boundaries(self):
        reader = asyncio.StreamReader()
        reader.feed_data(encode_frame("verack", b"") + encode_frame("ping", encode_ping(123)))
        self.assertEqual(await read_frame(reader), Frame("verack", b""))
        self.assertEqual(await read_frame(reader), Frame("ping", encode_ping(123)))

    async def test_reads_maximum_payload(self):
        reader = asyncio.StreamReader()
        reader.feed_data(encode_frame("block", bytes(MAX_PAYLOAD)))
        frame = await read_frame(reader)
        self.assertEqual(frame.command, "block")
        self.assertEqual(len(frame.payload), MAX_PAYLOAD)

    async def test_oversized_length_rejected_before_body_read(self):
        for size in (MAX_PAYLOAD + 1, 0xFFFFFFFF):
            reader = HeaderOnlyReader(damaged(encode_frame("block", b""), 16, struct.pack("<I", size)))
            with self.subTest(size=size), self.assertRaises(ProtocolError):
                await read_frame(reader)
            self.assertEqual(reader.requests, [FRAME_HEADER_SIZE])

    async def test_wrong_magic_rejected_before_body_read(self):
        reader = HeaderOnlyReader(encode_frame("version", b"", b"btc!"))
        with self.assertRaisesRegex(ProtocolError, "magic"):
            await read_frame(reader)
        self.assertEqual(reader.requests, [FRAME_HEADER_SIZE])

    async def test_bad_command_padding_rejected_before_body_read(self):
        for command in (b"ping\x00x" + bytes(6), b"Ping" + bytes(8),
                        bytes(12), b"a\xff" + bytes(10), b"a b" + bytes(9)):
            reader = HeaderOnlyReader(damaged(encode_frame("ping", b""), 4, command))
            with self.subTest(command=command), self.assertRaises(ProtocolError):
                await read_frame(reader)
            self.assertEqual(reader.requests, [FRAME_HEADER_SIZE])

    async def test_unpadded_twelve_byte_command(self):
        reader = asyncio.StreamReader()
        reader.feed_data(encode_frame("abcdefghijkl", b""))
        self.assertEqual(await read_frame(reader), Frame("abcdefghijkl", b""))

    async def test_payload_checksum_rejects_corruption(self):
        for raw in (damaged(encode_frame("tx", b"abc"), 24, b"z"),
                    damaged(encode_frame("verack", b""), 20, bytes(4))):
            reader = asyncio.StreamReader()
            reader.feed_data(raw)
            with self.assertRaisesRegex(ProtocolError, "checksum"):
                await read_frame(reader)

    async def test_truncated_header_and_payload(self):
        encoded = encode_frame("tx", b"transaction")
        for length in (1, 23, 24, len(encoded) - 1):
            reader = asyncio.StreamReader()
            reader.feed_data(encoded[:length])
            reader.feed_eof()
            with self.subTest(length=length), self.assertRaisesRegex(ProtocolError, "Truncated"):
                await read_frame(reader)

    async def test_clean_frame_boundary_eof_is_a_disconnect(self):
        reader = asyncio.StreamReader()
        reader.feed_eof()
        with self.assertRaises(PeerDisconnected):
            await read_frame(reader)
        self.assertTrue(issubclass(PeerDisconnected, ProtocolError))

    async def test_idle_and_body_stall_timeouts(self):
        for raw in (b"", encode_frame("tx", b"wait")[:24]):
            reader = asyncio.StreamReader()
            reader.feed_data(raw)
            with self.subTest(raw=raw), self.assertRaisesRegex(ProtocolError, "timed out"):
                await read_frame(reader, timeout=0.02)

    async def test_timeout_applies_to_entire_frame(self):
        reader = asyncio.StreamReader()
        encoded = encode_frame("tx", b"body")

        async def feed():
            await asyncio.sleep(0.06)
            reader.feed_data(encoded[:24])
            await asyncio.sleep(0.06)
            reader.feed_data(encoded[24:])

        feeder = asyncio.create_task(feed())
        with self.assertRaisesRegex(ProtocolError, "Whole-frame"):
            await read_frame(reader, timeout=0.1)
        await feeder

    async def test_read_cancellation_propagates(self):
        reader = asyncio.StreamReader()
        task = asyncio.create_task(read_frame(reader))
        await asyncio.sleep(0)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task

    async def test_write_serializes_and_drains_once(self):
        writer = FakeWriter()
        await write_frame(writer, "ping", encode_ping(8))
        self.assertEqual(writer.writes, [encode_frame("ping", encode_ping(8))])
        self.assertEqual(writer.drains, 1)

    async def test_write_timeout_bounds_drain(self):
        writer = FakeWriter(hang=True)
        with self.assertRaisesRegex(ProtocolError, "drain timed out"):
            await write_frame(writer, "ping", b"", timeout=0.02)
        self.assertEqual(writer.drains, 1)

    async def test_write_invalid_message_does_not_write(self):
        writer = FakeWriter()
        for command, payload in (("Ping", b""), ("tx", "not bytes"),
                                 ("block", bytes(MAX_PAYLOAD + 1))):
            with self.subTest(command=command), self.assertRaises(ProtocolError):
                await write_frame(writer, command, payload)
        self.assertEqual(writer.writes, [])
        self.assertEqual(writer.drains, 0)

    async def test_read_and_write_validate_timeout(self):
        for timeout in (0, -1, True, None, "5", float("nan"), float("inf"), 10 ** 1000):
            writer = FakeWriter()
            with self.subTest(timeout_type=type(timeout)):
                with self.assertRaises(ProtocolError):
                    await read_frame(asyncio.StreamReader(), timeout=timeout)
                with self.assertRaises(ProtocolError):
                    await write_frame(writer, "verack", b"", timeout=timeout)
            self.assertEqual(writer.writes, [])


if __name__ == "__main__":
    unittest.main()
