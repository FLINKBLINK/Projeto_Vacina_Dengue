import csv, io, sqlite3, zipfile
from scripts.auditar_snapshots_sinan import compare, read_snapshot

FIELDS=["ID_AGRAVO","ID_MN_RESI","DT_NOTIFIC","DT_SIN_PRI","CS_SEXO","NU_IDADE_N","SEM_PRI","CLASSI_FIN","CRITERIO","EVOLUCAO","OBS"]
def make_zip(path, rows):
    with zipfile.ZipFile(path,"w",zipfile.ZIP_DEFLATED) as z:
        buffer=io.StringIO(newline=""); writer=csv.DictWriter(buffer,fieldnames=FIELDS); writer.writeheader(); writer.writerows(rows)
        z.writestr("DENGBR.csv",buffer.getvalue().encode("utf-8"))
def row(**changes):
    result=dict(ID_AGRAVO="A90",ID_MN_RESI="350560",DT_NOTIFIC="2026-02-09",DT_SIN_PRI="2025-12-28",CS_SEXO="F",NU_IDADE_N="4050",SEM_PRI="202552",CLASSI_FIN="10",CRITERIO="1",EVOLUCAO="1",OBS="v1")
    result.update(changes); return result
def test_clinical_signature_matches_changed_snapshot_but_exact_does_not(tmp_path):
    paths={}
    for year,rows in {2024:[row(DT_NOTIFIC="2024-04-01",DT_SIN_PRI="2024-03-30")],2025:[row(OBS="v2")],2026:[row(OBS="v3"),row(OBS="v3")]}.items():
        paths[year]=tmp_path/f"{year}.zip"; make_zip(paths[year],rows)
    with sqlite3.connect(":memory:") as db:
        db.execute("CREATE TABLE fingerprints (ano INTEGER NOT NULL,tipo TEXT NOT NULL,hash TEXT NOT NULL,quantidade INTEGER NOT NULL DEFAULT 1,PRIMARY KEY(ano,tipo,hash))")
        for year in (2024,2025,2026): read_snapshot(db,year,paths[year])
        summary,details=compare(db,[2024,2025,2026])
    found={(x["ano_a"],x["ano_b"],x["tipo_comparacao"]):x for x in summary["comparacoes"]}
    assert found[(2025,2026,"assinatura_clinica")]["hashes_compartilhados"]==1
    assert found[(2025,2026,"assinatura_clinica")]["ocorrencias_correspondentes_minimas"]==1
    assert found[(2025,2026,"correspondencia_exata")]["hashes_compartilhados"]==0
    assert details
