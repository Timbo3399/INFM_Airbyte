"""Tests fuer scripts/images/export_images.py (keine DB noetig).

Auch hier lief frueher alles beim Import: Datenbankverbindung aufbauen, Dateien
schreiben. Ein Import in einem Test haette also echte Dateien angelegt.
"""
import export_images as ex


def test_dateiname_folgt_der_ext_id():
    # Die Aufgabenstellung verlangt <ID>.png als Dateinamen.
    pfad = ex.ziel_pfad("/tmp/bilder", "42")
    assert pfad.endswith("42.png")


def test_schreibt_die_bytes_unveraendert(tmp_path):
    ziel = tmp_path / "7.png"
    ex.schreibe_bild(str(ziel), b"\x89PNG-Testdaten")
    assert ziel.read_bytes() == b"\x89PNG-Testdaten"


def test_memoryview_aus_psycopg2_wird_korrekt_geschrieben(tmp_path):
    # psycopg2 liefert BYTEA als memoryview, nicht als bytes.
    ziel = tmp_path / "8.png"
    ex.schreibe_bild(str(ziel), memoryview(b"binaerdaten"))
    assert ziel.read_bytes() == b"binaerdaten"


def test_batches_liest_in_haeppchen_statt_alles_auf_einmal():
    class FakeCursor:
        def __init__(self, zeilen, groesse):
            self.zeilen, self.groesse, self.aufrufe = list(zeilen), groesse, 0

        def fetchmany(self, n):
            self.aufrufe += 1
            haeppchen, self.zeilen = self.zeilen[:n], self.zeilen[n:]
            return haeppchen

    cur = FakeCursor([("1", b"a"), ("2", b"b"), ("3", b"c")], 2)
    alles = list(ex.batches(cur, groesse=2))
    assert alles == [("1", b"a"), ("2", b"b"), ("3", b"c")]
    assert cur.aufrufe == 3        # zwei volle Haeppchen, dann das leere Ende
