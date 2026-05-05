"""p4a hook: copy patched assets/java and inject extra Android components."""

from __future__ import annotations

from pathlib import Path
import re
import shutil
import xml.etree.ElementTree as ET
from typing import Optional

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


def _manifest_package(manifest_root: ET.Element):
    pkg = manifest_root.get("package")
    if pkg:
        return pkg
    return manifest_root.get(_an("package"))


def _manifest_has_send_queries(manifest_root: ET.Element) -> bool:
    """Package visibility (API 30+): need SEND intents or share chooser may fail on some devices."""
    for q in manifest_root.findall("queries"):
        for intent in q.findall("intent"):
            for action in intent.findall("action"):
                if action.get(_an("name")) == "android.intent.action.SEND":
                    return True
    return False


def _ensure_share_queries(manifest_root: ET.Element) -> None:
    if _manifest_has_send_queries(manifest_root):
        return
    queries = ET.SubElement(manifest_root, "queries")
    for mime in ("text/plain", "image/jpeg"):
        intent = ET.SubElement(queries, "intent")
        ET.SubElement(intent, "action", {_an("name"): "android.intent.action.SEND"})
        ET.SubElement(intent, "data", {_an("mimeType"): mime})


def _has_tgws_share_provider(app: ET.Element) -> bool:
    cls = "unofficial.tgws.tgwsproxy.TgwsShareFileProvider"
    for node in app.findall("provider"):
        if node.get(_an("name")) == cls:
            return True
    return False


def _ensure_file_provider(app: ET.Element, manifest_root: ET.Element) -> None:
    """Share cover.jpg via FileProvider (content:// URI + app chooser)."""
    if _has_tgws_share_provider(app):
        return
    pkg = _manifest_package(manifest_root)
    if not pkg:
        return
    authority = f"{pkg}.tgws.share"
    provider = ET.SubElement(
        app,
        "provider",
        {
            _an("name"): "unofficial.tgws.tgwsproxy.TgwsShareFileProvider",
            _an("authorities"): authority,
            _an("exported"): "false",
            _an("grantUriPermissions"): "true",
        },
    )
    ET.SubElement(
        provider,
        "meta-data",
        {
            _an("name"): "android.support.FILE_PROVIDER_PATHS",
            _an("resource"): "@xml/tgws_file_paths",
        },
    )


def _ensure_loopback_network_security(app: ET.Element) -> None:
    """Разрешить HTTP к 127.0.0.1 для загрузки cover при шаринге (не трогаем уже заданный config)."""
    if app.get(_an("networkSecurityConfig")):
        return
    app.set(_an("networkSecurityConfig"), "@xml/network_security_config")


def _ensure_python_service_foreground_type(app: ET.Element) -> None:
    """API 34+: foreground service должен объявить тип (см. FOREGROUND_SERVICE_DATA_SYNC в buildozer.spec)."""
    for svc in app.findall("service"):
        name = svc.get(_an("name")) or ""
        if "ServiceProxy" not in name:
            continue
        existing = (svc.get(_an("foregroundServiceType")) or "").strip()
        if existing:
            continue
        svc.set(_an("foregroundServiceType"), "dataSync")


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


def _patch_manifest_components(dist: Path) -> None:
    manifest = dist / "src" / "main" / "AndroidManifest.xml"
    if not manifest.is_file():
        return
    tree = ET.parse(manifest)
    root = tree.getroot()
    app = root.find("application")
    if app is None:
        return
    _ensure_share_queries(root)
    _ensure_boot_receiver(app)
    _ensure_tile_service(app)
    _ensure_file_provider(app, root)
    _ensure_loopback_network_security(app)
    _ensure_python_service_foreground_type(app)
    tree.write(manifest, encoding="utf-8", xml_declaration=True)


def _patch_gradle_compile_sdk(dist: Path, min_sdk: int = 34) -> None:
    """p4a шаблон часто фиксирует compileSdk 33; androidx.core:1.12+ требует compileSdk >= 34 (checkReleaseAarMetadata)."""
    bg = dist / "build.gradle"
    if not bg.is_file():
        return
    text = bg.read_text(encoding="utf-8")
    orig = text

    def _bump_compile_eq(m: re.Match) -> str:
        key, ver = m.group(1), int(m.group(2))
        if ver < min_sdk:
            return f"{key} = {min_sdk}"
        return m.group(0)

    def _bump_compile_sp(m: re.Match) -> str:
        key, ver = m.group(1), int(m.group(2))
        if ver < min_sdk:
            return f"{key} {min_sdk}"
        return m.group(0)

    text = re.sub(
        r"(compileSdkVersion)\s*=\s*(\d+)\b",
        _bump_compile_eq,
        text,
    )
    text = re.sub(
        r"(compileSdk)\s*=\s*(\d+)\b",
        _bump_compile_eq,
        text,
    )
    text = re.sub(
        r"(compileSdkVersion)\s+(\d+)\b",
        _bump_compile_sp,
        text,
    )
    text = re.sub(
        r"(compileSdk)\s+(\d+)\b",
        _bump_compile_sp,
        text,
    )
    if text != orig:
        bg.write_text(text, encoding="utf-8")


def _find_dist_dir() -> Optional[Path]:
    """Каталог Gradle-dist с `src/main/AndroidManifest.xml`.

    На этапе `toolchain create` каталога dist ещё нет — нельзя подставлять cwd (корень
    репозитория): оверлей писал бы в hostcwd/src/... и ломал сборку.
    """
    cwd = Path.cwd()
    if (cwd / "src" / "main" / "AndroidManifest.xml").is_file():
        return cwd

    project_root = Path(__file__).resolve().parent.parent
    manifests = list(
        project_root.glob(
            ".buildozer/android/platform/*/dists/*/src/main/AndroidManifest.xml"
        )
    )
    if manifests:
        # AndroidManifest.xml → src/main → src → dist_dir
        return manifests[0].parent.parent.parent

    return None


def _apply_tgws_build_overlay():
    """Копирует Java/res и правит манифест. Дважды: после build.py и сразу перед gradle assemble (p4a toolchain)."""
    root = Path(__file__).resolve().parent
    dist = _find_dist_dir()
    if dist is None:
        print(
            f"[tgws-hook] skip overlay: dist not ready yet (cwd={Path.cwd()})",
            flush=True,
        )
        return

    print(f"[tgws-hook] dist_dir={dist}  cwd={Path.cwd()}", flush=True)

    assets = dist / "src" / "main" / "assets"
    if assets.is_dir():
        loader = root / "p4a_webview_loader"
        if loader.is_dir():
            for name in ("_load.html", "_loading_style.css"):
                src = loader / name
                if src.is_file():
                    shutil.copy2(src, assets / name)

    java_src = root / "p4a_python_activity" / "PythonActivity.java"
    java_dest = dist / "src/main/java/org/kivy/android/PythonActivity.java"
    if java_src.is_file():
        java_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(java_src, java_dest)
        java_dest.touch()

    extra_java = root / "p4a_android_java"
    if extra_java.is_dir():
        for src in extra_java.rglob("*.java"):
            rel = src.relative_to(extra_java)
            dest = dist / "src" / "main" / "java" / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            dest.touch()
            print(f"[tgws-hook] copied java: {dest}", flush=True)

    extra_res = root / "p4a_android_res"
    if extra_res.is_dir():
        for src in extra_res.rglob("*"):
            if src.is_file():
                rel = src.relative_to(extra_res)
                dest = dist / "src" / "main" / "res" / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)

    _patch_manifest_components(dist)
    _patch_gradle_compile_sdk(dist)


def before_apk_build(toolchain):
    """Самый ранний хук: гарантирует, что кастомные Java-файлы присутствуют до любого шага сборки."""
    _apply_tgws_build_overlay()


def after_apk_build(toolchain):
    _apply_tgws_build_overlay()


def before_apk_assemble(toolchain):
    """Страховка: manifest/res попадают в APK независимо от порядка шагов p4a."""
    _apply_tgws_build_overlay()
