"""Tests fuer die reinen Funktionen in scripts/airbyte_run_sync.py."""
import airbyte_run_sync as r


def test_laufende_jobs_sind_nicht_fertig():
    assert r.ist_fertig("running") is False
    assert r.ist_fertig("pending") is False
    assert r.ist_fertig("incomplete") is False


def test_endzustaende_sind_fertig():
    for status in ("succeeded", "failed", "cancelled"):
        assert r.ist_fertig(status) is True


def test_zusammenfassung_nennt_status_zeilen_und_dauer():
    text = r.summarize_job({
        "status": "succeeded", "jobId": 7,
        "rowsSynced": 5922, "duration": "PT41S",
    })
    assert "succeeded" in text
    assert "5922" in text
    assert "PT41S" in text


def test_zusammenfassung_kommt_auch_ohne_kennzahlen_klar():
    text = r.summarize_job({"status": "failed", "jobId": 8})
    assert "failed" in text
    assert "8" in text


# --- schon laufende Syncs ------------------------------------------------------
# Airbyte laesst pro Connection nur einen Sync zu und antwortet sonst mit
# HTTP 409. Das wollen wir vorher erkennen, statt in einen Traceback zu laufen.

def test_findet_laufenden_job_der_connection():
    jobs = [{"jobId": 1, "status": "incomplete", "connectionId": "c-1"}]
    assert r.laufender_job(jobs, "c-1")["jobId"] == 1


def test_abgeschlossene_jobs_blockieren_nicht():
    jobs = [{"jobId": 1, "status": "succeeded", "connectionId": "c-1"},
            {"jobId": 2, "status": "failed", "connectionId": "c-1"}]
    assert r.laufender_job(jobs, "c-1") is None


def test_laufender_job_einer_anderen_connection_blockiert_nicht():
    jobs = [{"jobId": 1, "status": "running", "connectionId": "c-2"}]
    assert r.laufender_job(jobs, "c-1") is None
