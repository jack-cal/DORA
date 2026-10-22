package org.sumuww.miner

import android.app.Activity
import android.graphics.Color
import android.graphics.Typeface
import android.view.Gravity
import android.view.View
import android.widget.FrameLayout

/** Scene art is a background only. Logo, typography and footer are real native Views. */
internal fun sumuwwSplash(activity: Activity, palette: SumuwwTheme.Palette, dark: Boolean): FrameLayout {
    val ui = SumuwwUiComponents(activity, palette, dark)
    val root = FrameLayout(activity).apply { isClickable = true }
    root.addView(SumuwwSplashBackground(activity,palette,dark),FrameLayout.LayoutParams(-1,-1))
    val brand = ui.column().apply { gravity=Gravity.CENTER; setPadding(ui.dp(24),ui.dp(24),ui.dp(24),ui.dp(24)) }
    brand.addView(ui.logo(),ui.params(ui.dp(if(LocaleBrand.isLocalized(activity))224 else 164),ui.dp(if(LocaleBrand.isLocalized(activity))128 else 90)))
    brand.addView(ui.label(UiLanguage.text(activity,"SUMUWW"),28f,ui.ink,true).apply { gravity=Gravity.CENTER;letterSpacing=.12f;typeface=Typeface.create("sans-serif",Typeface.BOLD) },ui.params(top=22))
    brand.addView(ui.label("Open Connections\nGreater Tomorrow.",15f,ui.ink).apply { gravity=Gravity.CENTER;setLineSpacing(ui.dp(3).toFloat(),1f) },ui.params(top=16))
    root.addView(brand,FrameLayout.LayoutParams(-1,-2,Gravity.CENTER))
    val footer=ui.column().apply { gravity=Gravity.CENTER;setPadding(ui.dp(24),0,ui.dp(24),ui.dp(64)) }
    footer.addView(ui.label(UiLanguage.text(activity,"더 나은 연결이 만드는 더 큰 내일을 위해"),12f,ui.ink).apply{gravity=Gravity.CENTER})
    val track=FrameLayout(activity).apply { background=ui.rounded(if(dark)Color.parseColor("#33404E") else Color.parseColor("#D5DFED"),2) }
    track.addView(View(activity).apply{background=ui.rounded(ui.accent,2)},FrameLayout.LayoutParams(ui.dp(44),ui.dp(3)))
    footer.addView(track,ui.params(ui.dp(92),ui.dp(3),top=20).apply{gravity=Gravity.CENTER})
    root.addView(footer,FrameLayout.LayoutParams(-1,-2,Gravity.BOTTOM))
    return root
}
