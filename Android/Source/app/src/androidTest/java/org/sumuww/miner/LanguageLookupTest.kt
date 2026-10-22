package org.sumuww.miner

import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Test

/** Original Korean callers must continue resolving after display text edits. */
class LanguageLookupTest {
 @Test fun originalCallersResolveReviewedCatalogsInEveryLanguage() {
  val context=InstrumentationRegistry.getInstrumentation().targetContext
  fun asset(name:String)=JSONObject(context.assets.open(name).bufferedReader().use{it.readText()})
  val mobile=asset("mobile_ui.json")
  val sources=mobile.getJSONObject("source_keys")
  val overrides=mobile.getJSONObject("korean_overrides")
  val rows=mobile.getJSONObject("strings")
  val languages=mobile.getJSONArray("languages")
  val original=UiLanguage.code(context)
  try {
   for(code in UiLanguage.languages.keys) {
    UiLanguage.set(context,code)
    val translated=asset("locales/$code.json")
    val index=(0 until languages.length()).firstOrNull{languages.getString(it)==code}
    for(korean in sources.keys()) {
     val expected=when {
      code=="ko" -> overrides.optString(korean,korean)
      rows.has(korean) && index!=null -> rows.getJSONArray(korean).getString(index)
      else -> translated.getString(sources.getString(korean))
     }
     assertEquals("$code: $korean",expected,UiLanguage.text(context,korean))
    }
    if(code=="ko")for(korean in overrides.keys()) {
     assertEquals(overrides.getString(korean),UiLanguage.text(context,korean))
    }
   }
  } finally { UiLanguage.set(context,original) }
 }
}
