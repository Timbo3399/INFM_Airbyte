"""
pytest-Konfiguration: macht die Skripte unter scripts/ importierbar, damit die
Tests deren reine Funktionen direkt ansprechen koennen.

Bewusst flache sys.path-Eintraege statt Pakete: die Skripte werden auch einzeln
per 'python scripts/<datei>.py' aufgerufen, und dabei liegt ihr eigenes
Verzeichnis auf sys.path. Ein Paket mit relativen Imports wuerde den direkten
Aufruf brechen.
"""
import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
for _unterordner in ("", "mapping", "images", "airbyte"):
    sys.path.insert(0, os.path.join(_ROOT, "scripts", _unterordner))
