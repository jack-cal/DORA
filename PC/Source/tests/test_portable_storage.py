"""Exclusive encrypted-file publication on ordinary temporary directories.

Windows tests run the real no-replace rename primitive on the local filesystem.
They do not claim removable FAT32/exFAT hardware or power-loss verification.
"""

from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from sumuww.keystore import WalletError, _publish_exclusively, _publish_no_replace, backup_wallet, create_wallet, load_wallet, restore_wallet

PASSWORD = "portable-test-password-only"
PUBLICATION_PRIMITIVE = "sumuww.keystore.os.rename" if os.name == "nt" else "sumuww.keystore.os.link"


class PortableStorageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="sumuww-portable-storage-", dir=os.environ.get("SUMUWW_TEST_WORKDIR"))
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.destination = self.root / "wallet.json"

    def assert_clean(self):
        self.assertEqual(list(self.root.rglob(".sumuww-wallet-*.tmp")), [])

    @unittest.skipUnless(os.name == "nt", "Windows no-replace rename semantics")
    def test_create_backup_restore_work_when_hard_links_are_unavailable(self):
        backup = self.root / "usb-like-destination" / "backup.json"
        restored = self.root / "restored" / "wallet.json"
        # The directory simulates an unsupported hard-link primitive, not a FAT
        # volume. The actual file writes, rename, encryption and unlock are real.
        with patch("sumuww.keystore.os.link", side_effect=OSError("hard links unavailable")) as hard_link:
            original = create_wallet(self.destination, PASSWORD, network="dora")
            raw = self.destination.read_bytes()
            self.assertEqual(backup_wallet(self.destination, backup, PASSWORD, network="dora").address, original.address)
            self.assertEqual(restore_wallet(backup, restored, PASSWORD, network="dora").address, original.address)
            self.assertEqual(load_wallet(restored, PASSWORD, network="dora").pubkey, original.pubkey)
            hard_link.assert_not_called()
        for path in (self.destination, backup, restored):
            self.assertEqual(path.read_bytes(), raw)
        self.assert_clean()

    def test_publication_follows_complete_write_flush_fsync_and_close(self):
        raw = b"complete encrypted envelope test bytes"
        events = []
        fdopen, fsync = os.fdopen, os.fsync
        publish = os.rename if os.name == "nt" else os.link
        test = self

        class RecordingFile:
            def __init__(self, descriptor, mode):
                self.output = fdopen(descriptor, mode)
            def __enter__(self):
                return self
            def write(self, value):
                events.append("write")
                return self.output.write(value)
            def flush(self):
                events.append("flush")
                self.output.flush()
            def fileno(self):
                return self.output.fileno()
            def __exit__(self, *ignored):
                self.output.close()
                events.append("close")

        def synced(descriptor):
            fsync(descriptor)
            events.append("fsync")

        def published(source, destination):
            test.assertEqual(events, ["write", "flush", "fsync", "close"])
            test.assertEqual(Path(source).parent, Path(destination).parent)
            test.assertEqual(Path(source).read_bytes(), raw)
            publish(source, destination)
            events.append("publish")

        with patch("sumuww.keystore.os.fdopen", side_effect=RecordingFile), patch("sumuww.keystore.os.fsync", side_effect=synced), patch(PUBLICATION_PRIMITIVE, side_effect=published):
            _publish_exclusively(self.destination, raw)
        self.assertEqual(self.destination.read_bytes(), raw)
        self.assertEqual(events[-1], "publish")
        self.assert_clean()

    def test_short_write_write_error_and_flush_error_never_publish(self):
        fdopen = os.fdopen
        raw = b"complete encrypted envelope test bytes"

        for failure in ("short-write", "write-error", "flush-error"):
            class FailingFile:
                def __init__(self, descriptor, mode):
                    self.output = fdopen(descriptor, mode)
                def __enter__(self):
                    return self
                def write(self, value):
                    if failure == "short-write":
                        return self.output.write(value[:-1])
                    if failure == "write-error":
                        self.output.write(value[:5])
                        raise OSError("injected write error")
                    return self.output.write(value)
                def flush(self):
                    raise OSError("injected flush error")
                def fileno(self):
                    return self.output.fileno()
                def __exit__(self, *ignored):
                    self.output.close()

            with self.subTest(failure=failure), patch("sumuww.keystore.os.fdopen", side_effect=FailingFile), patch(PUBLICATION_PRIMITIVE) as publish:
                with self.assertRaises(OSError):
                    _publish_exclusively(self.destination, raw)
                publish.assert_not_called()
            self.assertFalse(self.destination.exists())
            self.assert_clean()

    def test_fdopen_error_closes_descriptor_and_removes_temporary(self):
        close = os.close
        descriptors = []

        def closed(descriptor):
            close(descriptor)
            descriptors.append(descriptor)

        with patch("sumuww.keystore.os.fdopen", side_effect=OSError("injected fdopen error")), patch("sumuww.keystore.os.close", side_effect=closed):
            with self.assertRaises(OSError):
                _publish_exclusively(self.destination, b"encrypted test bytes")
        self.assertEqual(len(descriptors), 1)
        with self.assertRaises(OSError):
            os.fstat(descriptors[0])
        self.assertFalse(self.destination.exists())
        self.assert_clean()

    def test_descriptor_close_error_still_removes_temporary(self):
        close = os.close

        def closed_with_error(descriptor):
            close(descriptor)
            raise OSError("injected descriptor close error")

        with patch("sumuww.keystore.os.fdopen", side_effect=OSError("injected fdopen error")), patch("sumuww.keystore.os.close", side_effect=closed_with_error):
            with self.assertRaises(OSError):
                _publish_exclusively(self.destination, b"encrypted test bytes")
        self.assertFalse(self.destination.exists())
        self.assert_clean()

    def test_two_publishers_preserve_one_complete_winner(self):
        gate = threading.Barrier(2)
        publish = os.rename if os.name == "nt" else os.link
        candidates = (b"complete encrypted candidate A", b"complete encrypted candidate B")

        def competing_publication(source, destination):
            gate.wait(timeout=10)
            publish(source, destination)

        def writer(raw):
            try:
                _publish_exclusively(self.destination, raw)
                return True
            except WalletError:
                return False

        with patch(PUBLICATION_PRIMITIVE, side_effect=competing_publication), ThreadPoolExecutor(max_workers=2) as workers:
            futures = [workers.submit(writer, candidate) for candidate in candidates]
            results = [future.result(timeout=15) for future in futures]
        self.assertEqual(sum(results), 1)
        self.assertEqual(self.destination.read_bytes(), candidates[results.index(True)])
        self.assert_clean()

    def test_non_windows_branch_keeps_exclusive_link_instead_of_rename(self):
        source = self.root / "complete.tmp"
        source.write_bytes(b"complete encrypted test bytes")
        self.destination.write_bytes(b"existing destination")
        link = os.link
        # Preconstructed paths avoid changing pathlib's host path selection.
        with patch("sumuww.keystore.os.name", "posix"), patch("sumuww.keystore.os.rename") as rename, patch("sumuww.keystore.os.link", wraps=link) as linked:
            with self.assertRaises(FileExistsError):
                _publish_no_replace(source, self.destination)
            linked.assert_called_once_with(source, self.destination)
            rename.assert_not_called()
        self.assertEqual(self.destination.read_bytes(), b"existing destination")
        self.assertEqual(source.read_bytes(), b"complete encrypted test bytes")


if __name__ == "__main__":
    unittest.main()
