package org.sumuww.wallet

import androidx.test.platform.app.InstrumentationRegistry
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.io.File
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class WalletUpgradeTest {
    private fun python(code: String): JSONObject {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        if (!Python.isStarted()) Python.start(AndroidPlatform(context))
        val scope = Python.getInstance().getModule("builtins").callAttr("dict")
        scope.callAttr("__setitem__", "fixture_root", File(context.filesDir, "wallet-upgrade-regression").absolutePath)
        Python.getInstance().getModule("builtins").callAttr("exec", code, scope)
        return JSONObject(scope.callAttr("get", "report").toString())
    }
    @Test fun createLegacyFixture() {
        val result = python("""
import json,hashlib,tempfile
from pathlib import Path
import wallet_runtime
from dora import keystore
from dora.chain import Chain
from sumuww.__main__ import create_payment
from dora.wallet import RegtestKey
keystore._publish_no_replace=wallet_runtime._publish_android
root=Path(fixture_root);root.mkdir(exist_ok=True)
password='disposable-upgrade-test-password'
files={}
for name,hd,network in [('legacy-hd.json',True,'dora'),('legacy-single.json',False,'dora'),('regtest.json',True,'regtest')]:
    path=root/name
    key=(keystore.create_hd_wallet if hd else keystore.create_wallet)(path,password,network=network)
    files[name]={'address':key.address,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
sender=keystore.load_wallet(root/'regtest.json',password,network='regtest')
with Chain(root/'node.sqlite',network='regtest') as chain:
    chain.mine(sender.script_pubkey,100)
    payment=create_payment(chain,sender,RegtestKey.from_int(2).script_pubkey,250000000,0)
    chain.submit_transaction(payment)
    ledger={'height':chain.info()['height'],'balance':chain.balance(sender.script_pubkey),'utxo':chain.info()['utxo_commitment'],'pending':payment.txid().hex()}
(root/'expected.json').write_text(json.dumps({'files':files,'ledger':ledger}))
report=json.dumps({'passed':True,'created_with':'installed_pre_update','wallets':len(files)})
""".trimIndent())
        assertTrue(result.getBoolean("passed"))
    }
    @Test fun verifyPreservedWalletAfterUpdate() {
        val result = python("""
import json,hashlib,tempfile
from pathlib import Path
import wallet_runtime
from dora import keystore
from dora.chain import Chain
keystore._publish_no_replace=wallet_runtime._publish_android
root=Path(fixture_root);expected=json.loads((root/'expected.json').read_text())
password='disposable-upgrade-test-password'
for name,identity in expected['files'].items():
    path=root/name;network='regtest' if name=='regtest.json' else 'dora'
    key=keystore.load_wallet(path,password,network=network)
    assert key.address==identity['address']
    assert hashlib.sha256(path.read_bytes()).hexdigest()==identity['sha256']
    if key.is_hd:
        phrase=keystore.export_mnemonic(path,password,network=network)
        with tempfile.TemporaryDirectory(dir=root) as recovered_dir:
            recovered=keystore.recover_hd_wallet(Path(recovered_dir)/name,password,phrase,network=network)
            assert recovered.address==identity['address']
sender=keystore.load_wallet(root/'regtest.json',password,network='regtest')
with Chain(root/'node.sqlite',network='regtest') as chain:
    assert chain.info()['height']==expected['ledger']['height']
    assert chain.balance(sender.script_pubkey)==expected['ledger']['balance']
    assert chain.info()['utxo_commitment']==expected['ledger']['utxo']
    assert [tx.txid().hex() for tx in chain.mempool_transactions()]==[expected['ledger']['pending']]
with Chain(root/'public-activation.sqlite',network='dora') as chain:
    assert chain.boundary.activation==9000
    assert chain.htlc_activation==9100
report=json.dumps({'passed':True,'wallet_files_unchanged':3,'recovered_hd_addresses_unchanged':2,'ledger_and_pending_preserved':True,'activation_height':9000,'htlc_activation_height':9100})
""".trimIndent())
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        File(context.getExternalFilesDir(null), "wallet-upgrade-validation.json").writeText(result.toString(2))
        assertTrue(result.getBoolean("passed"))
        assertEquals(3, result.getInt("wallet_files_unchanged"))
    }
}
