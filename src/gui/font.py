import logging
import numpy
from OpenGL.GL import *
from gui.fontdata import FONT_BITMAPS

def _edt(bin_img):
    h,w=bin_img.shape
    f=numpy.where(bin_img,0,1e10).astype(numpy.float32)
    for y in range(h):
        if y>0:
            f[y]=numpy.minimum(f[y],f[y-1]+1)
    for y in range(h-2,-1,-1):
        f[y]=numpy.minimum(f[y],f[y+1]+1)
    for x in range(w):
        if x>0:
            f[:,x]=numpy.minimum(f[:,x],f[:,x-1]+1)
    for x in range(w-2,-1,-1):
        f[:,x]=numpy.minimum(f[:,x],f[:,x+1]+1)
    return f

def _sdf_glyph(bitmap, upscale, spread):
    src=8
    dst=src*upscale
    bin_img=numpy.zeros((dst,dst),dtype=numpy.uint8)
    for y in range(src):
        byte=bitmap[y]
        for x in range(src):
            if (byte>>(7-x))&1:
                bin_img[y*upscale:(y+1)*upscale,x*upscale:(x+1)*upscale]=1
    inside=_edt(bin_img)
    outside=_edt(1-bin_img)
    sdf=(outside-inside)/upscale
    sdf=numpy.clip(sdf,-spread,spread)
    return sdf.astype(numpy.float32)

class SDFFontAtlas:
    def __init__(self, glyph_size=128, spread=1.2, chars=None):
        self.spread=spread
        self.glyph_size=glyph_size
        self.pixel_height=glyph_size
        if chars is None:
            chars=[chr(c) for c in range(32,127)]
        self.chars=chars
        cols=16
        rows=6
        atlas_w=cols*glyph_size
        atlas_h=rows*glyph_size
        sdf_data=numpy.zeros((atlas_h,atlas_w),dtype=numpy.float32)
        self.glyphs={}
        upscale=glyph_size//8
        for code in range(32,128):
            ch=chr(code)
            if ch not in chars:
                continue
            bitmap=FONT_BITMAPS.get(code,[0]*8)
            sdf=_sdf_glyph(bitmap,upscale,spread)
            idx=code-32
            row=idx//cols
            col=idx%cols
            y0=row*glyph_size
            x0=col*glyph_size
            sdf_data[y0:y0+glyph_size,x0:x0+glyph_size]=sdf
            u0=(x0+1)/atlas_w
            v0=(y0+1)/atlas_h
            u1=(x0+glyph_size-1)/atlas_w
            v1=(y0+glyph_size-1)/atlas_h
            self.glyphs[ch]=(glyph_size,glyph_size,glyph_size,u0,v0,u1,v1)
        sdf_data=(sdf_data/spread)*0.5+0.5
        sdf_data=numpy.clip(sdf_data,0.0,1.0)
        sdf_tex=(sdf_data*255).astype(numpy.uint8)
        self.tex_id=glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D,self.tex_id)
        glTexImage2D(GL_TEXTURE_2D,0,GL_R8,atlas_w,atlas_h,0,GL_RED,GL_UNSIGNED_BYTE,sdf_tex)
        glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MAG_FILTER,GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_S,GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_T,GL_CLAMP_TO_EDGE)
        glBindTexture(GL_TEXTURE_2D,0)

    def get_glyph(self,char):
        return self.glyphs.get(char)

    def cleanup(self):
        pass

class BitmapFontAtlas:
    def __init__(self, pixel_height=32, chars=None):
        self.pixel_height=8
        self.tex_id=self._create_texture()
        if chars is None:
            chars=[chr(c) for c in range(32,127)]
        self.chars=chars
        self.default_advance=8
        self.glyphs={}
        cols=16
        rows=8
        for code in range(32,128):
            ch=chr(code)
            row=(code-32)//cols
            col=(code-32)%cols
            u0=col/cols
            v0=row/rows
            u1=(col+1)/cols
            v1=(row+1)/rows
            self.glyphs[ch]=(8,8,self.default_advance,u0,v0,u1,v1)

    def _create_texture(self):
        cols=16
        rows=8
        cell_w=8
        cell_h=8
        tex_w=cols*cell_w
        tex_h=rows*cell_h
        texture_data=numpy.zeros((tex_h,tex_w,4),dtype=numpy.uint8)
        for code in range(32,128):
            row=(code-32)//cols
            col=(code-32)%cols
            bitmap=FONT_BITMAPS.get(code,[0]*8)
            for y in range(cell_h):
                row_bits=bitmap[y] if y<len(bitmap) else 0
                for x in range(cell_w):
                    if (row_bits>>(7-x))&1:
                        texture_data[row*cell_h+y,col*cell_w+x]=[255,255,255,255]
                    else:
                        texture_data[row*cell_h+y,col*cell_w+x]=[0,0,0,0]
        tex_id=glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D,tex_id)
        glTexImage2D(GL_TEXTURE_2D,0,GL_RGBA,tex_w,tex_h,0,GL_RGBA,GL_UNSIGNED_BYTE,texture_data)
        glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,GL_LINEAR_MIPMAP_LINEAR)
        glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MAG_FILTER,GL_LINEAR)
        glGenerateMipmap(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D,0)
        return tex_id

    def get_glyph(self,char):
        return self.glyphs.get(char)

    def cleanup(self):
        pass

def create_font_atlas(size=128, spread=1.2, chars=None):
    #logging.debug(f"Creating SDF atlas: size={size}, spread={spread}")
    try:
        return SDFFontAtlas(size, spread, chars)
    except Exception as e:
        logging.warning(f"SDF failed: {e}. Using bitmap.")
        return BitmapFontAtlas(size, chars)
