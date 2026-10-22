package org.sumuww.wallet

import android.content.Context
import android.graphics.Typeface

/** A bundled Arabic face keeps readable glyph weight independent of OEM fallback fonts. */
internal object SumuwwArabicTypography {
    private val faces=mutableMapOf<Boolean,Typeface>()
    @Synchronized fun face(context:Context,bold:Boolean):Typeface = faces.getOrPut(bold) {
        val weight=if(bold)600 else 500
        Typeface.Builder(context.assets,"fonts/NotoSansArabic.ttf").setWeight(weight)
            .setFontVariationSettings("'wght' $weight, 'wdth' 100").setItalic(false).build()
    }
}
