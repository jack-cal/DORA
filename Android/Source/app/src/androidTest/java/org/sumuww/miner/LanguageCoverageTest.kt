package org.sumuww.miner

import android.content.Intent
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import java.io.File
import android.graphics.Bitmap

class LanguageCoverageTest {
 @Test fun catalogsAndAllScreenRoutesPreserveDrafts() {
  val inst=InstrumentationRegistry.getInstrumentation();val context=inst.targetContext
  assertEquals(34,UiLanguage.languages.size)
  val mobile=JSONObject(context.assets.open("mobile_ui.json").bufferedReader().use{it.readText()})
  val help=JSONObject(context.assets.open("sumuww_help.json").bufferedReader().use{it.readText()})
  val consent=JSONObject(context.assets.open("consent_ui.json").bufferedReader().use{it.readText()})
  val tour=JSONObject(context.assets.open("sumuww_tour.json").bufferedReader().use{it.readText()})
  val base=JSONObject(context.assets.open("locales/en.json").bufferedReader().use{it.readText()})
  for(code in UiLanguage.languages.keys){
   val catalog=JSONObject(context.assets.open("locales/$code.json").bufferedReader().use{it.readText()})
   assertEquals(base.length(),catalog.length())
   for(key in base.keys())assertTrue("$code: $key",catalog.getString(key).isNotBlank())
   assertTrue(help.has(code));assertTrue(consent.has(code));assertTrue(tour.has(code))
   if(code!="ko"){
    val index=(0 until mobile.getJSONArray("languages").length()).first{mobile.getJSONArray("languages").getString(it)==code}
    for(key in mobile.getJSONObject("strings").keys())assertTrue("$code mobile $key",mobile.getJSONObject("strings").getJSONArray(key).getString(index).isNotBlank())
   }
  }
  val original=UiLanguage.code(context);SumuwwConsent.accept(context)
  val activity=inst.startActivitySync(Intent(context,MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) as MainActivity
  // The first screen has an 800 ms splash overlay; audit the actual content.
  Thread.sleep(1000)
  inst.waitForIdleSync()
  val type=MainActivity::class.java
  val render=type.getDeclaredMethod("render").apply{isAccessible=true}
  val page=type.getDeclaredField("page").apply{isAccessible=true}
  val recipient=type.getDeclaredField("recipient").apply{isAccessible=true}
  val quantity=type.getDeclaredField("quantity").apply{isAccessible=true}
  val root=(type.getDeclaredField("screens").apply{isAccessible=true}.get(activity) as SumuwwScreens).appRoot
  // Kotlin mangles internal getters with the build variant's module name.
  // Resolve the same getter in both the compatible and published release APK.
  val contentFits=SumuwwVerticalTextView::class.java.declaredMethods.single{
   it.name.substringBefore('$')=="getContentFitsMeasuredBounds" && it.parameterCount==0
  }.apply{isAccessible=true}
  fun texts(v:View):List<String> = if(v is ViewGroup)(0 until v.childCount).flatMap{texts(v.getChildAt(it))} else if(v is TextView)listOf(v.text.toString())else emptyList()
  try{
   inst.runOnMainSync{recipient.set(activity,"dora1q-ui-language-fixture");quantity.set(activity,"1.25000000")}
   val captures=mutableSetOf<String>()
   val selected=InstrumentationRegistry.getArguments().getString("languageFilter")?.split(",")?:UiLanguage.languages.keys.toList()
   for(code in selected.flatMap{listOf(it,"en",it)} + selected.reversed()){
    inst.runOnMainSync{UiLanguage.set(context,code)}
     for(route in listOf(0,1,2,3,4,5,6,7,8,9,10,11,12,13,14)){
      inst.runOnMainSync{
      page.setInt(activity,route);render.invoke(activity)
      assertTrue("Empty screen $code/$route",texts(root).isNotEmpty())
      assertFalse("Untranslated Korean $code/$route",code!="ko"&&texts(root).any{it.any{c->c in '\uAC00'..'\uD7A3'}})
      }
      inst.waitForIdleSync()
      inst.runOnMainSync{
       fun check(view:View){
        if(view.visibility!=View.VISIBLE)return
        if(view is SumuwwVerticalTextView && view.usesVerticalMongolian && view.width>0 && view.height>0){
         assertTrue("Ink clipped $code/$route: ${view.text}; view=${view.width}x${view.height}; measured=${view.measuredWidth}x${view.measuredHeight}; pad=${view.paddingTop},${view.paddingBottom}; block=${SumuwwVerticalTextView::class.java.getDeclaredField("blockHeight").apply{isAccessible=true}.getFloat(view)}",contentFits.invoke(view) as Boolean)
         var child:View=view
         var parent=child.parent
         while(parent is ViewGroup && parent !is android.widget.ScrollView){
          assertTrue("Ancestor clips width $route: ${view.text}",child.left>=-1&&child.right<=parent.width+1)
          assertTrue("Ancestor clips height $route: ${view.text}; child=${child.top}..${child.bottom}; parent=${parent.javaClass.simpleName}/${parent.height}",child.top>=-1&&child.bottom<=parent.height+1)
          child=parent;parent=child.parent
         }
        }
        if(view is ViewGroup)for(i in 0 until view.childCount)check(view.getChildAt(i))
       }
       check(root)
       assertEquals("draft address after $code/$route","dora1q-ui-language-fixture",recipient.get(activity))
       assertEquals("draft amount after $code/$route","1.25000000",quantity.get(activity))
      }
      if(captures.add("$code/$route")){
       // Capture this activity's actual laid-out view tree. Display screenshots
       // can still contain the compositor's previous frame on a headless AVD.
       Thread.sleep(15)
       inst.waitForIdleSync()
       val folder=File(context.getExternalFilesDir(null),"language-ui-audit").apply{mkdirs()}
       lateinit var screenshot:Bitmap
       inst.runOnMainSync{
        assertTrue("Unlaid-out screen $code/$route",root.width>0&&root.height>0)
        // A status render may request layout between the previous idle wait and
        // this callback. Lay out this exact tree before drawing its bitmap.
        root.measure(View.MeasureSpec.makeMeasureSpec(root.width,View.MeasureSpec.EXACTLY),View.MeasureSpec.makeMeasureSpec(root.height,View.MeasureSpec.EXACTLY))
        root.layout(root.left,root.top,root.right,root.bottom)
        screenshot=Bitmap.createBitmap(root.width,root.height,Bitmap.Config.ARGB_8888)
        root.draw(android.graphics.Canvas(screenshot))
       }
       File(folder,"$code-$route.png").outputStream().use{screenshot.compress(Bitmap.CompressFormat.PNG,100,it)}
       screenshot.recycle()
       if(code=="mn-Mong"){
        val screens=type.getDeclaredField("screens").apply{isAccessible=true}.get(activity) as SumuwwScreens
        val actual=screens.content.getChildAt(0) as android.widget.ScrollView
        inst.runOnMainSync{actual.isSmoothScrollingEnabled=false;actual.scrollTo(0,actual.getChildAt(0).height)}
        inst.waitForIdleSync()
        inst.runOnMainSync{
         assertTrue("Last row unreachable $route: scroll=${actual.scrollY}, viewport=${actual.height}, page=${actual.getChildAt(0).height}",actual.scrollY+actual.height>=actual.getChildAt(0).height-actual.getChildAt(0).paddingBottom-1)
         screenshot=Bitmap.createBitmap(root.width,root.height,Bitmap.Config.ARGB_8888)
         root.draw(android.graphics.Canvas(screenshot))
        }
        File(folder,"$code-$route-bottom.png").outputStream().use{screenshot.compress(Bitmap.CompressFormat.PNG,100,it)}
        screenshot.recycle()
       }
      }
     }
    inst.runOnMainSync{
     assertEquals("dora1q-ui-language-fixture",recipient.get(activity))
     assertEquals("1.25000000",quantity.get(activity))
    }
   }
  }finally{inst.runOnMainSync{UiLanguage.set(context,original);activity.finish()}}
 }
}
