import json,tempfile,time,tkinter as tk,unittest
from pathlib import Path
from unittest.mock import patch
from sumuww import updates
from sumuww.app import SumuwwApp
from sumuww.app_service import AppService

def manifest(version='0.57.26'):
    return json.dumps({'schema_version':1,'windows':{'version':version,'release_url':updates.RELEASES_URL+'/tag/test-version'}}).encode()

class ReleaseTests(unittest.TestCase):
    def test_numeric_comparison_and_candidates(self):
        for latest,expected in [('0.57.26',True),('0.57.25',False),('0.57.24',False),('0.58.0',True),('0.57.100',True)]:
            self.assertEqual(updates.parse_manifest(manifest(latest),'0.57.25-boundary9000-candidate')['available'],expected)
    def test_trusted_repository_only(self):
        self.assertEqual(updates.release_url(updates.RELEASES_URL),updates.RELEASES_URL)
        for url in ['http://github.com/jack-cal/SUMUWW/releases','https://github.com.evil.example/jack-cal/SUMUWW/releases',
                    'https://user@github.com/jack-cal/SUMUWW/releases','https://github.com/jack-cal/OTHER/releases',
                    updates.RELEASES_URL+'?redirect=evil',updates.RELEASES_URL+'#fake',updates.RELEASES_URL+'/tag/../evil']:
            with self.assertRaises(ValueError):updates.release_url(url)
    def test_malformed_bounded_and_duplicate_responses(self):
        for raw in [b'x'*65537,b'{}',b'{"schema_version":1,"schema_version":1}',manifest('x'),b'{"schema_version":true}']:
            with self.assertRaises((ValueError,KeyError,TypeError)):updates.parse_manifest(raw,'0.57.25')

class UpdateUiTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='owned-update-ui-');self.root=tk.Tk();self.root.withdraw()
        self.service=AppService(Path(self.temp.name)/'node',network='regtest',peers=[],bootstrap=False)
        self.app=SumuwwApp(self.root,self.service,language='ko',language_path=Path(self.temp.name)/'lang.json')
        self.errors=[];self.root.report_callback_exception=lambda *e:self.errors.append(e)
        self.wait(lambda:self.app._started)
    def wait(self,predicate):
        end=time.monotonic()+15
        while not predicate():
            self.root.update();time.sleep(.005)
            self.assertLess(time.monotonic(),end)
        self.root.update();self.assertFalse(self.errors)
    def tearDown(self):
        import gc
        self.service.stop().result(timeout=15);self.app._finish_close();self.app=None;self.root=None;gc.collect();self.temp.cleanup()
    def labels(self,view):
        result=[]
        for child in view.winfo_children():
            try:result.append(str(child.cget('textvariable') and child.getvar(child.cget('textvariable')) or child.cget('text')))
            except tk.TclError:pass
            result.append(self.labels(child))
        return '\n'.join(result)
    def test_real_button_background_result_download_and_close(self):
        with patch('sumuww.updates.check',return_value=updates.parse_manifest(manifest(),'0.57.25')) as check:
            check.assert_not_called();self.app.update_button.invoke()
            self.wait(lambda:self.app._update_dialog is not None and 'GitHub 0.57.26' in self.labels(self.app._update_dialog))
            check.assert_called_once()
            with patch('sumuww.app.webbrowser.open',return_value=True) as browser:
                self.app._open_github(updates.RELEASES_URL+'/tag/test-version');browser.assert_called_once_with(updates.RELEASES_URL+'/tag/test-version')
            self.app._update_dialog.destroy();self.assertIsNone(self.app._update_dialog)
            self.assertTrue(self.service.status().result(timeout=5)['node']['running'])
    def test_failed_request_has_github_fallback_and_no_late_reopen(self):
        with patch('sumuww.updates.check',side_effect=OSError('offline')):
            self.app.update_button.invoke();self.wait(lambda:not self.app._pending)
            self.assertIn('GitHub',self.labels(self.app._update_dialog))
            self.app._update_dialog.destroy();self.root.update();self.assertIsNone(self.app._update_dialog)
            self.assertTrue(self.service.status().result(timeout=5)['node']['running'])
