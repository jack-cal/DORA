package org.sumuww.miner

import android.app.Activity
import android.graphics.*
import android.graphics.drawable.Drawable
import android.view.View
import android.util.LruCache

/** Native materials, never a raster screenshot of a functional screen. */
internal class SumuwwFinishDrawable(
    private val palette: SumuwwTheme.Palette, private val dark: Boolean,
    private val radius: Float, private val kind: Kind
) : Drawable() {
    enum class Kind { KEY, BUTTON, ACTION, SOFT, SURFACE }
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG)
    private val shape = Path()
    override fun draw(canvas: Canvas) {
        val rect = RectF(bounds)
        if (rect.isEmpty) return
        val c = SumuwwTheme.config(palette)
        val surface = SumuwwTheme.surface(palette, dark)
        val accent = SumuwwTheme.foregroundAccent(palette, dark)
        val key = kind == Kind.KEY
        val filled = key || kind == Kind.BUTTON || (kind == Kind.ACTION && palette.id == "default")
        val colors = if (key) intArrayOf(c.gradientStart, SumuwwTheme.mix(c.gradientStart, c.gradientEnd, .44f), c.gradientEnd)
            else if(filled) intArrayOf(SumuwwTheme.mix(c.accent,Color.BLACK,.03f),c.accent,SumuwwTheme.mix(c.accent,Color.BLACK,.03f))
            else if (kind == Kind.ACTION) intArrayOf(SumuwwTheme.mix(surface, accent, if (dark) .23f else .08f), SumuwwTheme.mix(surface, accent, if (dark) .11f else .13f), surface)
            else if (kind == Kind.SOFT) intArrayOf(SumuwwTheme.mix(surface, accent, if (dark) .13f else .075f), SumuwwTheme.mix(surface, accent, if (dark) .045f else .035f), surface)
            else intArrayOf(if (dark) SumuwwTheme.mix(surface, Color.WHITE, .03f) else Color.WHITE, surface, surface)
        paint.style = Paint.Style.FILL
        paint.shader = LinearGradient(rect.left, rect.top, rect.right, rect.bottom, colors, floatArrayOf(0f, .28f, 1f), Shader.TileMode.CLAMP)
        canvas.drawRoundRect(rect, radius, radius, paint)
        val saved = canvas.save()
        shape.reset(); shape.addRoundRect(rect, radius, radius, Path.Direction.CW)
        canvas.clipPath(shape)
        // A bright crown and narrow reflections, rather than a large dark material field.
        paint.shader = LinearGradient(0f,rect.top,0f,rect.top+rect.height()*.10f,
            intArrayOf(withAlpha(Color.WHITE,if(filled)100 else if(dark)30 else 180),withAlpha(Color.WHITE,0)),null,Shader.TileMode.CLAMP)
        canvas.drawRect(rect,paint)
        if (filled) {
            val highlight=canvas.save()
            canvas.translate(rect.right-rect.width()*.03f,rect.top-rect.height()*.06f)
            canvas.scale(1f,if(key).20f else .12f)
            val lightRadius=rect.width()*(if(key).46f else .34f)
            paint.shader = RadialGradient(0f,0f,lightRadius,
                intArrayOf(withAlpha(Color.WHITE,105),withAlpha(palette.secondary,75),withAlpha(palette.secondary,0)),floatArrayOf(0f,.30f,1f),Shader.TileMode.CLAMP)
            canvas.drawCircle(0f,0f,lightRadius,paint)
            canvas.restoreToCount(highlight)
        }
        if(key) {
            paint.shader=LinearGradient(rect.right-rect.width()*.48f,rect.bottom,rect.right,rect.top,
                intArrayOf(withAlpha(Color.WHITE,0),withAlpha(Color.WHITE,28),withAlpha(Color.WHITE,155)),floatArrayOf(0f,.58f,1f),Shader.TileMode.CLAMP)
            paint.style=Paint.Style.STROKE;paint.strokeWidth=1.2f
            for(offset in listOf(0f,.05f)) {
                shape.reset();shape.moveTo(rect.right,rect.top+rect.height()*(.10f+offset))
                shape.cubicTo(rect.right-rect.width()*.02f,rect.top+rect.height()*.38f,rect.right-rect.width()*.04f,rect.top+rect.height()*.84f,rect.right-rect.width()*.42f,rect.bottom)
                canvas.drawPath(shape,paint)
            }
            paint.shader=null;paint.style=Paint.Style.FILL
            val x=rect.right-rect.width()*.08f;val y=rect.top+rect.height()*.06f
            val size=minOf(rect.width(),rect.height())*.018f
            paint.color=withAlpha(Color.WHITE,180)
            shape.reset();shape.moveTo(x,y-size*2);shape.quadTo(x+size*.25f,y-size*.25f,x+size*2,y)
            shape.quadTo(x+size*.25f,y+size*.25f,x,y+size*2);shape.quadTo(x-size*.25f,y+size*.25f,x-size*2,y)
            shape.quadTo(x-size*.25f,y-size*.25f,x,y-size*2);canvas.drawPath(shape,paint)
        }
        canvas.restoreToCount(saved)
        paint.shader = null; paint.style = Paint.Style.STROKE; paint.strokeWidth = 1f
        paint.shader=LinearGradient(rect.left,rect.top,rect.right,rect.bottom,
            intArrayOf(withAlpha(Color.WHITE,if(filled)175 else if(dark)45 else 225),withAlpha(Color.WHITE,if(filled)30 else 0),withAlpha(accent,if(dark)45 else 22)),floatArrayOf(0f,.45f,1f),Shader.TileMode.CLAMP)
        rect.inset(.5f,.5f); canvas.drawRoundRect(rect,radius,radius,paint)
        paint.style = Paint.Style.FILL;paint.shader=null
    }
    override fun getOutline(outline: Outline) { outline.setRoundRect(bounds, radius) }
    override fun setAlpha(alpha: Int) { }
    override fun setColorFilter(filter: ColorFilter?) { }
    @Deprecated("Deprecated in Java") override fun getOpacity() = PixelFormat.TRANSLUCENT
}

private fun withAlpha(color: Int, alpha: Int) = (color and 0x00ffffff) or (alpha.coerceIn(0,255) shl 24)

/** Calm vertical screen gradient, with the accent confined to a faint upper wash. */
internal class SumuwwScreenBackground(private val palette: SumuwwTheme.Palette, private val dark: Boolean) : Drawable() {
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG)
    override fun draw(canvas: Canvas) {
        val r = RectF(bounds); if (r.isEmpty) return
        val base = SumuwwTheme.background(palette,dark)
        paint.shader = LinearGradient(0f,r.top,0f,r.bottom, if(dark) SumuwwTheme.mix(base,Color.BLACK,.16f) else Color.WHITE, base, Shader.TileMode.CLAMP)
        canvas.drawRect(r,paint)
        paint.shader = RadialGradient(r.right,r.top,r.width()*1.2f,intArrayOf(withAlpha(palette.primary,if(dark) 9 else 7),withAlpha(palette.primary,0)),null,Shader.TileMode.CLAMP)
        canvas.drawRect(r,paint); paint.shader=null
    }
    override fun setAlpha(alpha: Int) { }
    override fun setColorFilter(filter: ColorFilter?) { }
    @Deprecated("Deprecated in Java") override fun getOpacity() = PixelFormat.OPAQUE
}

internal object SumuwwSceneArt {
    private val cache = LruCache<String, Bitmap>(2)
    @Synchronized fun bitmap(activity: Activity, id: String): Bitmap = cache.get(id) ?: activity.assets.open("theme_backgrounds/$id.png").use {
        BitmapFactory.decodeStream(it, null, BitmapFactory.Options().apply { inScaled = false })
            ?: error("Missing SMW scene $id")
    }.also { cache.put(id,it) }
}

/** Splash scenery is separate from the official logo, words and native controls. */
internal class SumuwwSplashBackground(private val activity: Activity, private val palette: SumuwwTheme.Palette, private val dark: Boolean) : View(activity) {
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG or Paint.FILTER_BITMAP_FLAG)
    private val path = Path()
    private val scene = if (palette.id in setOf("spring","summer","autumn","winter")) SumuwwSceneArt.bitmap(activity,palette.id) else null
    override fun onDraw(canvas: Canvas) {
        val w=width.toFloat(); val h=height.toFloat(); if(w==0f||h==0f)return
        val image=scene
        if(image!=null) {
            val half=image.width/2f
            val panelLeft=if(dark)half else 0f
            val panelRatio=half/image.height
            val targetRatio=w/h
            val cropW=if(targetRatio<panelRatio)image.height*targetRatio else half
            val cropH=if(targetRatio<panelRatio)image.height.toFloat() else half/targetRatio
            val x=panelLeft+(half-cropW)/2
            val y=(image.height-cropH)/2
            canvas.drawBitmap(image,Rect(x.toInt(),y.toInt(),(x+cropW).toInt(),(y+cropH).toInt()),RectF(0f,0f,w,h),paint)
            return
        }
        val base=SumuwwTheme.background(palette,dark)
        paint.shader=LinearGradient(0f,0f,w,h,if(dark)Color.parseColor("#080D12") else Color.WHITE,base,Shader.TileMode.CLAMP)
        canvas.drawRect(0f,0f,w,h,paint)
        if(palette.id=="default") {
            paint.shader=LinearGradient(0f,h*.65f,w,h,intArrayOf(SumuwwTheme.mix(base,palette.primary,if(dark).38f else .16f),SumuwwTheme.mix(base,palette.secondary,if(dark).42f else .10f)),null,Shader.TileMode.CLAMP)
            path.reset();path.moveTo(0f,h*.64f);path.cubicTo(w*.45f,h*.67f,w*.63f,h*.90f,w,h*.91f);path.lineTo(w,h);path.lineTo(0f,h);path.close();canvas.drawPath(path,paint)
            paint.shader=LinearGradient(w,h*.65f,0f,h,SumuwwTheme.mix(base,palette.secondary,if(dark).44f else .15f),SumuwwTheme.mix(base,palette.primary,if(dark).56f else .10f),Shader.TileMode.CLAMP)
            path.reset();path.moveTo(w,h*.65f);path.cubicTo(w*.53f,h*.72f,w*.41f,h*.85f,0f,h*.91f);path.lineTo(0f,h);path.lineTo(w,h);path.close();canvas.drawPath(path,paint)
        } else {
            // Silk ribbons in the supplied color boards, rather than tiny decorations at the bottom.
            for(i in 0..1) {
                val y=if(i==0)h*.13f else h*.70f
                val strength=if(dark).35f else .13f
                paint.shader=LinearGradient(0f,y,w,y+h*.33f,intArrayOf(SumuwwTheme.mix(base,palette.primary,strength),SumuwwTheme.mix(base,palette.secondary,strength*1.2f),base),floatArrayOf(0f,.52f,1f),Shader.TileMode.CLAMP)
                path.reset();path.moveTo(-w*.1f,y);path.cubicTo(w*.50f,y-h*.18f,w*.80f,y+h*.25f,w*1.12f,y+h*.32f)
                path.lineTo(w*1.12f,y+h*.47f);path.cubicTo(w*.57f,y+h*.24f,w*.27f,y+h*.11f,-w*.1f,y+h*.32f);path.close();canvas.drawPath(path,paint)
                paint.shader=null;paint.style=Paint.Style.STROKE;paint.strokeWidth=resources.displayMetrics.density*(if(dark)1.2f else .8f)
                paint.color=withAlpha(if(dark)palette.secondary else Color.WHITE,if(dark)150 else 245)
                path.reset();path.moveTo(-w*.03f,y+h*.20f);path.cubicTo(w*.40f,y-h*.01f,w*.52f,y+h*.29f,w*1.04f,y+h*.35f);canvas.drawPath(path,paint);paint.style=Paint.Style.FILL
            }
        }
        paint.shader=null
    }
}

/** Use the official alpha silhouette and aspect ratio, with the selected theme's gradient. */
internal class SumuwwBrandMark(activity: Activity, palette: SumuwwTheme.Palette, dark: Boolean) : View(activity) {
    private val localized = LocaleBrand.isLocalized(activity)
    private val art = brand(activity)
    private val bitmap = art.first
    private val source = art.second
    private val paint=Paint(Paint.ANTI_ALIAS_FLAG or Paint.FILTER_BITMAP_FLAG)
    private val colors = if (palette.id == "default" || LocaleBrand.isLocalized(activity)) null else SumuwwTheme.brandColors(palette, dark)
    private val tintMode = PorterDuffXfermode(PorterDuff.Mode.SRC_IN)
    private var displayArt: Bitmap? = null
    companion object {
        private val cached = mutableMapOf<Int, Pair<Bitmap,Rect>>()
        @Synchronized private fun brand(activity: Activity): Pair<Bitmap,Rect> {
            val resource = LocaleBrand.artwork(activity)
            return cached.getOrPut(resource) {
            val bitmap=BitmapFactory.decodeResource(activity.resources,resource,BitmapFactory.Options().apply{inScaled=false})
            var l=bitmap.width;var t=bitmap.height;var r=0;var b=0
            for(y in 0 until bitmap.height)for(x in 0 until bitmap.width)if(Color.alpha(bitmap.getPixel(x,y))>4){l=minOf(l,x);t=minOf(t,y);r=maxOf(r,x);b=maxOf(b,y)}
            bitmap to if(r>=l&&b>=t)Rect(l,t,r+1,b+1)else Rect(0,0,bitmap.width,bitmap.height)
            }
        }
    }
    override fun onSizeChanged(w:Int,h:Int,oldw:Int,oldh:Int) {
        super.onSizeChanged(w,h,oldw,oldh)
        if(!localized || w<=0 || h<=0)return
        val scale=minOf(w/source.width().toFloat(),h/source.height().toFloat())
        val targetWidth=maxOf(1,(source.width()*scale).toInt())
        val targetHeight=maxOf(1,(source.height()*scale).toInt())
        var sampled=Bitmap.createBitmap(bitmap,source.left,source.top,source.width(),source.height())
        // Reduce by at most two per pass so thin gold details are averaged
        // instead of being skipped by a single bilinear sample of the master.
        while(sampled.width>targetWidth*2 && sampled.height>targetHeight*2) {
            val smaller=Bitmap.createScaledBitmap(sampled,maxOf(targetWidth,sampled.width/2),maxOf(targetHeight,sampled.height/2),true)
            if(sampled!==bitmap && sampled!==smaller)sampled.recycle()
            sampled=smaller
        }
        val final=Bitmap.createScaledBitmap(sampled,targetWidth,targetHeight,true)
        if(sampled!==bitmap && sampled!==final)sampled.recycle()
        displayArt?.takeIf{it!==bitmap && it!==final}?.recycle()
        displayArt=final
    }
    override fun onDraw(canvas: Canvas) {
        val scale=minOf(width/source.width().toFloat(),height/source.height().toFloat())
        val w=source.width()*scale;val h=source.height()*scale
        val target=RectF((width-w)/2,(height-h)/2,(width+w)/2,(height+h)/2)
        val tint=colors
        if(tint==null) {
            val display=displayArt
            if(display!=null)canvas.drawBitmap(display,null,target,paint)
            else canvas.drawBitmap(bitmap,source,target,paint)
        } else {
            val layer=canvas.saveLayer(0f,0f,width.toFloat(),height.toFloat(),null)
            canvas.drawBitmap(bitmap,source,target,paint)
            paint.shader=LinearGradient(target.left,target.top,target.right,target.bottom,tint,floatArrayOf(0f,.12f,.35f,.78f,1f),Shader.TileMode.CLAMP)
            paint.xfermode=tintMode
            canvas.drawRect(0f,0f,width.toFloat(),height.toFloat(),paint)
            paint.shader=null;paint.xfermode=null
            canvas.restoreToCount(layer)
        }
    }
}
