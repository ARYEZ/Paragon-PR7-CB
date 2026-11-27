"""A stand-in Klipper for the tests: org.kde.klipper /klipper getClipboardHistoryMenu on the bus given, answering with
the lines of a file (newest first) that the test rewrites as "copies" happen. Its own process, as Klipper is.

    python standin_klipper.py BUS_ADDRESS HISTORY_FILE      prints READY once it owns the name"""
import sys

from PySide6.QtCore import ClassInfo, QCoreApplication, QObject, Slot
from PySide6.QtDBus import QDBusConnection

address, history = sys.argv[1], sys.argv[2]
app = QCoreApplication([])
bus = QDBusConnection.connectToBus(address, "klipper")


@ClassInfo({"D-Bus Interface": "org.kde.klipper.klipper"})
class Klipper(QObject):
    @Slot(result="QStringList")
    def getClipboardHistoryMenu(self):
        with open(history, encoding="utf-8") as fh:
            return [line.rstrip("\n").replace("\\n", "\n") for line in fh if line.strip()]


k = Klipper()
bus.registerObject("/klipper", k, QDBusConnection.RegisterOption.ExportAllSlots)
bus.registerService("org.kde.klipper")
print("READY", flush=True)
app.exec()
