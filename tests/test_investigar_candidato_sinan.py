import csv
import io
import zipfile

from scripts.auditar_snapshots_sinan import digest_fields
from scripts.investigar_candidato_sinan import compare_target, row_hash

FIELDS = [
    "ID_AGRAVO", "ID_MN_RESI", "DT_NOTIFIC", "DT_SIN_PRI", "CS_SEXO",
    "NU_IDADE_N", "SEM_PRI", "CLASSI_FIN", "CRITERIO", "EVOLUCAO", "OBS", "NU_ANO",
]


def make_zip(path, rows):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
        archive.writestr("DENGBR.csv", buffer.getvalue().encode("utf-8"))


def base_row(**changes):
    row = {
        "ID_AGRAVO": "A90", "ID_MN_RESI": "354340",
        "DT_NOTIFIC": "2026-02-09", "DT_SIN_PRI": "2026-02-01",
        "CS_SEXO": "F", "NU_IDADE_N": "4050", "SEM_PRI": "202605",
        "CLASSI_FIN": "10", "CRITERIO": "1", "EVOLUCAO": "1",
        "OBS": "versao-a", "NU_ANO": "2026",
    }
    row.update(changes)
    return row


def test_targeted_audit_exports_hashes_and_field_equality_not_raw_values(tmp_path):
    target = base_row(OBS="snapshot-2025")
    candidate = base_row(
        OBS="snapshot-2026", DT_NOTIFIC="2026-02-18", DT_SIN_PRI="2026-02-12"
    )
    p2025 = tmp_path / "2025.zip"
    p2026 = tmp_path / "2026.zip"
    make_zip(p2025, [target])
    make_zip(p2026, [candidate])

    prefix = row_hash(target)[:12]
    summary, details = compare_target(p2025, p2026, prefix)

    assert summary["alvo_hash"].startswith(prefix)
    assert summary["candidatos_por_camada"]["meses_sexo_idade_classificacao_desfecho"]["quantidade"] == 1
    assert len(details) == 3
    strongest = next(
        item for item in details
        if item["camada_correspondencia"] == "meses_sexo_idade_classificacao_desfecho"
    )
    assert strongest["DT_NOTIFIC_igual"] is False
    assert strongest["CLASSI_FIN_igual"] is True
    assert "DT_NOTIFIC" not in strongest
    assert "OBS" not in strongest


def test_targeted_audit_rejects_non_unique_prefix(tmp_path):
    row = base_row()
    p2025 = tmp_path / "2025.zip"
    p2026 = tmp_path / "2026.zip"
    make_zip(p2025, [row, row])
    make_zip(p2026, [row])
    try:
        compare_target(p2025, p2026, row_hash(row)[:12])
    except ValueError as exc:
        assert "exatamente um alvo" in str(exc)
    else:
        raise AssertionError("Deveria rejeitar prefixo que identifica mais de um alvo")
