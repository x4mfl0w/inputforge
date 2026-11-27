# -*- mode: python ; coding: utf-8 -*-
# PyInstaller-Build für InputForge.
#
#   pyinstaller packaging/inputforge.spec --noconfirm
#
# Umgebungsvariablen:
#   INPUTFORGE_ONEFILE=1   → einzelne .exe statt Ordner (langsamerer Start, mehr AV-Fehlalarme)
#   INPUTFORGE_UAC_ADMIN=1 → .exe fordert immer Adminrechte an (nötig, wenn das Spiel als
#                            Admin läuft – sonst blockiert Windows (UIPI) Hooks und SendInput)
import os
import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent
sys.path.insert(0, str(ROOT / "src"))
from inputforge import __version__  # noqa: E402

ONEFILE = os.environ.get("INPUTFORGE_ONEFILE") == "1"
UAC_ADMIN = os.environ.get("INPUTFORGE_UAC_ADMIN") == "1"

# Ungenutzte Qt-Module ausschließen → deutlich kleineres Paket.
QT_EXCLUDES = [
    f"PySide6.{m}"
    for m in (
        "Qt3DAnimation Qt3DCore Qt3DExtras Qt3DInput Qt3DLogic Qt3DRender QtBluetooth "
        "QtCharts QtDataVisualization QtDesigner QtHelp QtLocation QtMultimedia "
        "QtMultimediaWidgets QtNfc QtOpenGL QtOpenGLWidgets QtPdf QtPdfWidgets "
        "QtPositioning QtQml QtQuick QtQuick3D QtQuickControls2 QtQuickWidgets "
        "QtRemoteObjects QtScxml QtSensors QtSerialPort QtSpatialAudio QtSql QtSvg "
        "QtSvgWidgets QtTest QtTextToSpeech QtUiTools QtWebChannel QtWebEngineCore "
        "QtWebEngineQuick QtWebEngineWidgets QtWebSockets QtXml"
    ).split()
]

a = Analysis(
    [str(ROOT / "packaging" / "entry_gui.py")],
    pathex=[str(ROOT / "src")],
    datas=[(str(ROOT / "examples"), "examples")],
    hiddenimports=["inputforge.platform.win32", "inputforge.platform.x11"],
    excludes=["tkinter", "matplotlib", *QT_EXCLUDES],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe_kwargs = dict(
    name="InputForge",
    console=False,
    uac_admin=UAC_ADMIN,
    upx=False,  # UPX erhöht AV-Fehlalarme deutlich
    version=None,
)

if ONEFILE:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], **exe_kwargs)
else:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, **exe_kwargs)
    coll = COLLECT(exe, a.binaries, a.datas, name=f"InputForge-{__version__}", upx=False)
