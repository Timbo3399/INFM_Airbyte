"""
pytest-Konfiguration: macht die Loader-Module unter scripts/ importierbar,
damit die Tests deren reine Funktionen direkt ansprechen koennen.
"""
import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_ROOT, "scripts"))
sys.path.insert(0, os.path.join(_ROOT, "scripts", "mapping"))
