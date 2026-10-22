package org.sumuww.wallet

import androidx.test.platform.app.InstrumentationRegistry
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.io.File
import org.junit.Test

/** Explicit diagnostic only; not counted as a functional pass. */
class NativeRouterDiagnosis {
    @Test fun captureNativeStartupOutput() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        PrivacyRuntime.configure(context)
        if (!Python.isStarted()) Python.start(AndroidPlatform(context))
        val scope = Python.getInstance().getModule("builtins").callAttr("dict")
        Python.getInstance().getModule("builtins").callAttr("exec", """
import json,tempfile,time,os,socket
from pathlib import Path
from java import jclass
from mobile_interfaces import install
install()
from sumuww.managed_privacy import ManagedRouter
report={'cwd':os.getcwd(),'routers':{}}
with tempfile.TemporaryDirectory(prefix='wallet-router-diagnostic-') as folder:
    for mode in ('tor','i2p'):
        router=ManagedRouter(mode,folder)
        binary,kind=router._binary()
        command=router._command(binary,kind)
        if mode=='i2p':command+=['--log=stdout','--loglevel=debug']
        args=jclass('java.util.ArrayList')()
        for arg in command:args.add(str(arg))
        output=Path(folder)/(mode+'-output.txt')
        builder=jclass('java.lang.ProcessBuilder')(args)
        builder.redirectErrorStream(True)
        builder.redirectOutput(jclass('java.io.File')(str(output)))
        process=builder.start()
        try:
            started=time.monotonic();ready=False
            while time.monotonic()-started<45 and process.isAlive():
                try:
                    with socket.create_connection(('127.0.0.1',router.port),timeout=.3):ready=True
                    break
                except OSError:time.sleep(.2)
            report['routers'][mode]={'alive':process.isAlive(),'local_port_ready':ready,'seconds':time.monotonic()-started,'output':output.read_text(errors='replace')[-16000:]}
        finally:
            process.destroy()
            if not process.waitFor(3,jclass('java.util.concurrent.TimeUnit').SECONDS):process.destroyForcibly()
report=json.dumps(report)
""".trimIndent(), scope)
        File(context.getExternalFilesDir(null), "native-router-diagnosis.json").writeText(scope.callAttr("get", "report").toString())
    }
}
