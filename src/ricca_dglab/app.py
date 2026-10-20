"""Entry point for the native Ricca × DG-LAB Control Center."""

from __future__ import annotations

import argparse
import ctypes
import os
from pathlib import Path
import sys

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QFont, QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickItem  # Registers QQuickItem* conversion for screenshots.


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true", help="use deterministic sample telemetry")
    parser.add_argument("--smoke-test", action="store_true", help="load the UI, then exit")
    parser.add_argument("--no-socket", action="store_true", help="do not start the local Socket server")
    parser.add_argument("--screenshot", type=Path, help="save one rendered frame, then exit")
    parser.add_argument("--page", type=int, default=0, help="initial navigation page index")
    parser.add_argument("--open-editor", action="store_true", help="open waveform editor on startup")
    parser.add_argument("--strategy", choices=("A", "B"), help="open a channel strategy for visual verification")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    from .single_instance import SingleInstance, show_existing_instance
    # Isolated --demo --no-socket visual checks cannot drive a real device.
    instance = SingleInstance()
    if not (args.demo and args.no_socket) and not instance.acquire():
        show_existing_instance()
        return 0
    root = _workspace_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from .backend import AppBackend, DemoReader
    from .hud import HudController
    if args.demo:
        reader = DemoReader()
    else:
        from ricca_hp_smoke_test import read_state
        reader = read_state

    if sys.platform == "win32":
        # Give the Qt window its own Windows taskbar identity instead of
        # inheriting pythonw.exe or an older launcher icon/group.
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "RiccaDGLab.ControlCenter.1"
        )

    app = QGuiApplication(sys.argv[:1])
    app.aboutToQuit.connect(instance.close)
    app.setApplicationName("Ricca × DG-LAB Control Center")
    app.setOrganizationName("Ricca x DG-LAB")
    app.setFont(QFont("Microsoft YaHei UI", 10))
    icon_path = (
        root / "src" / "ricca_dglab" / "assets" / "branding"
        / "ricca-app-icon-round.png"
    )
    app.setWindowIcon(QIcon(str(icon_path)))
    engine = QQmlApplicationEngine()
    backend = AppBackend(reader, demo=args.demo, start_bridge=not args.no_socket)
    engine.rootContext().setContextProperty("backend", backend)
    qml_path = Path(__file__).resolve().parent / "qml" / "ControlCenter.qml"
    engine.load(QUrl.fromLocalFile(str(qml_path)))
    if not engine.rootObjects():
        backend.shutdown()
        return 2
    main_window = engine.rootObjects()[0]
    engine.load(QUrl.fromLocalFile(str(qml_path.with_name("GameHud.qml"))))
    if len(engine.rootObjects()) != 2:
        backend.shutdown()
        return 2
    hud_window = engine.rootObjects()[1]
    hud_controller = HudController(backend, hud_window)
    hud_window.setProperty("controller", hud_controller)
    app.aboutToQuit.connect(hud_controller.shutdown)
    engine.rootObjects()[0].setProperty("pageIndex", max(0, min(7, args.page)))
    if args.open_editor:
        engine.rootObjects()[0].setProperty("editorOnStart", True)
    if args.strategy:
        engine.rootObjects()[0].setProperty("strategyOnStart", args.strategy)
    app.aboutToQuit.connect(backend.shutdown)
    if not args.demo and not backend.onboardingCompleted:
        main_window.setProperty("showOnboardingOnStart", True)
    if args.screenshot:
        destination = args.screenshot.expanduser().resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        def capture() -> None:
            window = engine.rootObjects()[0]
            window.grabWindow().save(str(destination))
            app.quit()

        QTimer.singleShot(900, capture)
    elif args.smoke_test:
        QTimer.singleShot(1200, app.quit)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
