"""python-for-android hook: after dist assets/java are laid out, patch WebView loader + PythonActivity."""

from pathlib import Path
import shutil


def after_apk_build(toolchain):
    root = Path(__file__).resolve().parent

    assets = Path("src/main/assets")
    if assets.is_dir():
        loader = root / "p4a_webview_loader"
        if loader.is_dir():
            for name in ("_load.html", "_loading_style.css"):
                src = loader / name
                if src.is_file():
                    shutil.copy2(src, assets / name)

    java_src = root / "p4a_python_activity" / "PythonActivity.java"
    java_dest = Path("src/main/java/org/kivy/android/PythonActivity.java")
    if java_src.is_file():
        java_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(java_src, java_dest)
