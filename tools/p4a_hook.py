"""p4a hook: copy patched assets/java and inject extra Android components."""

from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

ANDROID_NS = "http://schemas.android.com/apk/res/android"
ET.register_namespace("android", ANDROID_NS)


def _an(name: str) -> str:
    return f"{{{ANDROID_NS}}}{name}"


def _has_component(app: ET.Element, tag: str, class_name: str) -> bool:
    for node in app.findall(tag):
        if node.get(_an("name")) == class_name:
            return True
    return False


def _ensure_boot_receiver(app: ET.Element) -> None:
    cls = "unofficial.tgws.tgwsproxy.BootCompletedReceiver"
    if _has_component(app, "receiver", cls):
        return
    receiver = ET.SubElement(
        app,
        "receiver",
        {
            _an("name"): cls,
            _an("enabled"): "true",
            _an("exported"): "true",
        },
    )
    filt = ET.SubElement(receiver, "intent-filter")
    ET.SubElement(filt, "action", {_an("name"): "android.intent.action.BOOT_COMPLETED"})
    ET.SubElement(filt, "action", {_an("name"): "android.intent.action.LOCKED_BOOT_COMPLETED"})
    ET.SubElement(filt, "action", {_an("name"): "android.intent.action.MY_PACKAGE_REPLACED"})


def _ensure_tile_service(app: ET.Element) -> None:
    cls = "unofficial.tgws.tgwsproxy.ProxyTileService"
    if _has_component(app, "service", cls):
        return
    svc = ET.SubElement(
        app,
        "service",
        {
            _an("name"): cls,
            _an("permission"): "android.permission.BIND_QUICK_SETTINGS_TILE",
            _an("exported"): "true",
            _an("label"): "TG WS Proxy",
            _an("icon"): "@mipmap/icon",
        },
    )
    filt = ET.SubElement(svc, "intent-filter")
    ET.SubElement(
        filt, "action", {_an("name"): "android.service.quicksettings.action.QS_TILE"}
    )


def _patch_manifest_components() -> None:
    manifest = Path("src/main/AndroidManifest.xml")
    if not manifest.is_file():
        return
    tree = ET.parse(manifest)
    root = tree.getroot()
    app = root.find("application")
    if app is None:
        return
    _ensure_boot_receiver(app)
    _ensure_tile_service(app)
    tree.write(manifest, encoding="utf-8", xml_declaration=True)


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

    extra_java = root / "p4a_android_java"
    if extra_java.is_dir():
        for src in extra_java.rglob("*.java"):
            rel = src.relative_to(extra_java)
            dest = Path("src/main/java") / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)

    _patch_manifest_components()
