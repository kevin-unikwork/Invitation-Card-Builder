#!/usr/bin/env python3
"""
System health check - verify all components are working
"""

import sys
import os
from pathlib import Path

def check_requirement(name, check_func, required=True):
    """Check a single requirement."""
    try:
        result = check_func()
        status = "✅" if result else "⚠️"
        print(f"{status} {name}")
        return result or not required
    except Exception as e:
        status = "❌" if required else "⚠️"
        print(f"{status} {name}: {str(e)[:50]}")
        return not required

def main():
    print("\n" + "=" * 70)
    print("SYSTEM HEALTH CHECK - Video Generation")
    print("=" * 70 + "\n")

    all_ok = True
    
    # 1. Check Python version
    all_ok &= check_requirement(
        "Python 3.12+",
        lambda: sys.version_info >= (3, 12)
    )

    # 2. Check required packages
    def check_pillow():
        from PIL import Image, ImageDraw
        return True
    all_ok &= check_requirement("Pillow/PIL", check_pillow)

    def check_ffmpeg():
        import subprocess
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        return True
    all_ok &= check_requirement("FFmpeg", check_ffmpeg)

    def check_fastapi():
        import fastapi
        return True
    all_ok &= check_requirement("FastAPI", check_fastapi)

    # 3. Check optional but nice-to-have
    def check_pango():
        try:
            import gi
            gi.require_version("Pango", "1.0")
            from gi.repository import Pango
            return True
        except:
            return False
    pango_ok = check_requirement(
        "Pango/Cairo (optional, for multilingual)",
        check_pango,
        required=False
    )

    # 4. Check file structure
    print("\nFile Structure:")
    
    paths = [
        ("Template directory", "static/template"),
        ("Fonts directory", "static/fonts"),
        ("Template media", "static/template_media"),
        ("Output directory", "static/output"),
    ]
    
    for name, path in paths:
        exists = Path(path).exists()
        status = "✅" if exists else "❌"
        print(f"{status} {name}: {path}")
        all_ok &= exists

    # 5. Check key files
    print("\nKey Files:")
    
    files = [
        "main.py",
        "video_processing.py",
        "user_templates.py",
        "requirements.txt",
        "VIDEO_FIX_GUIDE.md",
        "QUICK_START.md",
    ]
    
    for fname in files:
        exists = Path(fname).exists()
        status = "✅" if exists else "⚠️"
        print(f"{status} {fname}")
        all_ok &= exists

    # 6. Check module imports
    print("\nModule Health:")
    
    def check_video_processing():
        import video_processing
        has_pango = video_processing._PANGO_AVAILABLE
        has_pil = video_processing._PIL_AVAILABLE
        return has_pil
    
    vp_ok = check_requirement("video_processing module", check_video_processing)

    def check_user_templates():
        import user_templates
        return hasattr(user_templates, 'router')
    
    ut_ok = check_requirement("user_templates module", check_user_templates)

    # 7. Template count
    print("\nTemplates Available:")
    template_dir = Path("static/template")
    if template_dir.exists():
        templates = list(template_dir.glob("*.json"))
        print(f"✅ {len(templates)} templates found")
        for t in sorted(templates)[:5]:
            print(f"   - {t.name}")
    
    # 8. Font count
    print("\nFonts Available:")
    font_dir = Path("static/fonts")
    if font_dir.exists():
        fonts = list(font_dir.glob("*.ttf"))
        print(f"✅ {len(fonts)} font files found")

    # Summary
    print("\n" + "=" * 70)
    if all_ok and vp_ok and ut_ok:
        print("✅ SYSTEM STATUS: READY")
        print("\nYour video generation system is fully operational!")
        print("\nTo start: python3 main.py")
        print("Then test with: QUICK_START.md")
        return 0
    else:
        print("⚠️ SYSTEM STATUS: NEEDS ATTENTION")
        if not pango_ok:
            print("\nNote: Pango not available - using Pillow fallback (still works)")
        return 1
    print("=" * 70 + "\n")

if __name__ == "__main__":
    sys.exit(main())
