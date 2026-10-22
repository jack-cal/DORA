package org.sumuww.wallet

import android.app.AlertDialog
import android.content.Intent
import android.view.View
import android.view.ViewGroup
import android.widget.CheckBox
import androidx.test.platform.app.InstrumentationRegistry
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import org.junit.Assert.*
import org.junit.Test
import java.io.File

class PrivacyHelpTest {
 @Test fun cancelRepeatSuppressAndSelectAgain(){
  val inst=InstrumentationRegistry.getInstrumentation();val context=inst.targetContext
  
  PrivacyRuntime.configure(context)
  if(!Python.isStarted())Python.start(AndroidPlatform(context))
  val builtins=Python.getInstance().getModule("builtins")
  val globals=builtins.callAttr("dict")
  fun exec(code:String){builtins.callAttr("exec",code,globals)}
  exec("""
import tempfile,json
from pathlib import Path
import wallet_runtime as bridge
from sumuww.app_service import AppService
owned=tempfile.TemporaryDirectory(prefix='owned-privacy-help-')
bridge.stop()
service=AppService(Path(owned.name)/'node',network='regtest',peers=[],bootstrap=False,allow_lan=False,allow_internet=False)
service.start().result(30)
bridge._service=service
saved_config=bridge._dispatch
calls=[]
def dispatch(method,args):
    if method=='privacy': calls.append(args[0]); return {}
    return saved_config(method,args)
bridge._dispatch=dispatch
""".trimIndent())
  val prefs=context.getSharedPreferences("wallet-ui",0)
  val saved=listOf("language","privacy-help-hidden-tor","privacy-help-hidden-i2p").associateWith{prefs.all[it]}
  prefs.edit().putString("language","en").remove("privacy-help-hidden-tor").remove("privacy-help-hidden-i2p").commit()
  val activity=inst.startActivitySync(Intent(context,MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) as MainActivity
  val confirm=MainActivity::class.java.getDeclaredMethod("confirmPrivacy",String::class.java).apply{isAccessible=true}
  val field=MainActivity::class.java.getDeclaredField("dialog").apply{isAccessible=true}
  fun current()=field.get(activity) as? AlertDialog
  fun views(v:View):List<View> = listOf(v)+if(v is ViewGroup)(0 until v.childCount).flatMap{views(v.getChildAt(it))}else emptyList()
  fun waitCalls(count:Int){
   val end=System.currentTimeMillis()+15000
   while(builtins.callAttr("eval","len(calls)",globals).toInt()!=count){assertTrue("Selection did not run",System.currentTimeMillis()<end);Thread.sleep(50)}
  }
  try{
   Thread.sleep(500)
   // Cancelling a checked box must not save the box or activate the mode.
   inst.runOnMainSync{
    confirm.invoke(activity,"tor");val d=current()!!;assertTrue(d.isShowing)
    views(d.window!!.decorView).filterIsInstance<CheckBox>().single().isChecked=true
    d.getButton(AlertDialog.BUTTON_NEGATIVE).performClick()
    assertFalse(prefs.getBoolean("privacy-help-hidden-tor",false))
   }
   assertEquals(0,builtins.callAttr("eval","len(calls)",globals).toInt())
   // Without the box, help must be shown for each selection.
   repeat(2){n->inst.runOnMainSync{
    confirm.invoke(activity,"tor");val d=current()!!;assertTrue(d.isShowing)
    assertFalse(views(d.window!!.decorView).filterIsInstance<CheckBox>().single().isChecked)
    d.getButton(AlertDialog.BUTTON_POSITIVE).performClick()
   };waitCalls(n+1)}
   // Run with the box selected, then the next selection executes immediately.
   inst.runOnMainSync{
    confirm.invoke(activity,"tor");val d=current()!!
    views(d.window!!.decorView).filterIsInstance<CheckBox>().single().isChecked=true
    d.getButton(AlertDialog.BUTTON_POSITIVE).performClick()
   };waitCalls(3)
   assertTrue(prefs.getBoolean("privacy-help-hidden-tor",false))
   inst.runOnMainSync{confirm.invoke(activity,"tor");assertTrue(current()?.isShowing!=true)};waitCalls(4)
   // Hiding Tor help does not hide I2P help.
   inst.runOnMainSync{confirm.invoke(activity,"i2p");assertTrue(current()!!.isShowing);current()!!.getButton(AlertDialog.BUTTON_NEGATIVE).performClick()}
   assertEquals(4,builtins.callAttr("eval","len(calls)",globals).toInt())
   File(context.getExternalFilesDir(null),"privacy-help-test.json").writeText("""{"passed":true,"cancel_keeps_mode":true,"unchecked_repeats":true,"checked_skips_and_runs":true,"per_mode":true}""")
  }finally{
   inst.runOnMainSync{current()?.dismiss();activity.finish()}
   exec("bridge._dispatch=saved_config\nservice.stop().result(30)\nbridge._service=None\nowned.cleanup()")
   val edit=prefs.edit();saved.forEach{(k,v)->when(v){is String->edit.putString(k,v);is Boolean->edit.putBoolean(k,v);else->edit.remove(k)}};edit.commit()
  }
 }

 @Test fun packagedNativeRoutersStartAndStop(){
  val inst=InstrumentationRegistry.getInstrumentation();val context=inst.targetContext
  PrivacyRuntime.configure(context)
  if(!Python.isStarted())Python.start(AndroidPlatform(context))
  val globals=Python.getInstance().getModule("builtins").callAttr("dict")
  Python.getInstance().getModule("builtins").callAttr("exec","""
import asyncio,json,tempfile,zipfile
from mobile_interfaces import install
install()
from sumuww.managed_privacy import ManagedRouter
from sumuww.privacy import Transport,settings
async def check():
    results={}
    with tempfile.TemporaryDirectory(prefix='owned-embedded-routers-') as folder:
        for mode in ('tor','i2p'):
            router=ManagedRouter(mode,folder)
            if mode=='i2p':
                # This test verifies the packaged local SAM protocol and owned
                # child lifecycle, not Internet reseeding. A clean router blocks
                # before SAM starts while unavailable public reseeds retry for
                # up to 180s. An empty valid ZIP supplies no router contacts;
                # this offline fixture cannot verify public I2P routing.
                empty_reseed=router.root/'local-protocol-only.zip'
                with zipfile.ZipFile(empty_reseed,'w'):pass
                actual_command=router._command
                router._command=lambda binary,kind: actual_command(binary,kind)+['--reseed.zipfile='+str(empty_reseed)]
            transport=None
            child=None
            try:
                port=await router.ensure_running()
                child=router.process
                assert await router.ensure_running()==port and router.process is child
                if mode=='i2p':
                    transport=Transport(settings(mode,port))
                    r,w=await asyncio.wait_for(transport._hello(),5)
                    w.close();await w.wait_closed()
                else:
                    r,w=await asyncio.open_connection('127.0.0.1',port)
                    w.write(b'\x05\x01\x00');await w.drain()
                    assert await asyncio.wait_for(r.readexactly(2),5)==b'\x05\x00'
                    w.close();await w.wait_closed()
                results[mode]={'native_start':True,'version':router.version,'local_protocol':True,'scope':'local_proxy_protocol_only','public_reseed_verified':False}
            finally:
                if transport is not None:await transport.stop()
                await router.stop()
                if child is not None:
                    assert child.poll() is not None
                    results[mode]['owned_child_stopped']=True
    return results
result=asyncio.run(check())
""".trimIndent(),globals)
  File(context.getExternalFilesDir(null),"embedded-native-test.json").writeText(Python.getInstance().getModule("builtins").callAttr("eval","json.dumps(result)",globals).toString())
 }
}
