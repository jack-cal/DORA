package org.sumuww.miner

import androidx.test.platform.app.InstrumentationRegistry
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import org.junit.Assume.assumeTrue
import org.junit.Test
import java.io.File

/** Optional public-chain fixture; never opens the production app's data. */
class HistoryNetworkAuditTest {
    @Test fun publicHistoryPrefixBenchmark() {
        val context=InstrumentationRegistry.getInstrumentation().targetContext
        check(context.packageName.endsWith(".audit"))
        val fixture=File(context.getExternalFilesDir(null),"history-fixture.sqlite")
        assumeTrue("Supply an isolated public chain snapshot",fixture.isFile)
        if(!Python.isStarted())Python.start(AndroidPlatform(context))
        val python=Python.getInstance();val globals=python.getModule("builtins").callAttr("dict")
        globals.callAttr("__setitem__","fixture_path",fixture.absolutePath)
        globals.callAttr("__setitem__","cache_path",context.cacheDir.absolutePath)
        python.getModule("builtins").callAttr("exec","""
            from pathlib import Path
            import collections,json,shutil,time
            from sumuww.chain import Chain
            from sumuww.link_crypto import producer
            target=Path(cache_path)/'history-benchmark.sqlite'
            shutil.copyfile(fixture_path,target)
            with Chain(target,network='sumuww') as chain:
                path=chain._path(chain.tip_hash)
                groups=collections.defaultdict(list)
                for row,block in path[9000:]:groups[producer(block)].append(block)
                results=[]
                for node_id,blocks in groups.items():
                    began=time.perf_counter()
                    for block in blocks:
                        chain.boundary.anchor(chain._path(block.header.previous_hash))
                    elapsed=time.perf_counter()-began
                    assert elapsed<1.0,(len(blocks),elapsed)
                    results.append({'producer':node_id,'blocks':len(blocks),'seconds':elapsed})
                report=json.dumps({'height':len(path)-1,'groups':results},indent=2)
        """.trimIndent(),globals)
        File(context.getExternalFilesDir(null),"history-benchmark.json").writeText(globals.callAttr("get","report").toString())
    }
}
