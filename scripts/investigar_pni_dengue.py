"""Investiga a estrutura pública do PNI e identifica códigos candidatos da vacina dengue.

A rotina consulta amostras paginadas, produz somente agregações e nunca grava
registros individuais ou altera o banco do projeto.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import requests

API_BASE = "https://apidadosabertos.saude.gov.br"
ROTA = "/vacinacao/doses-aplicadas-pni-{ano}"
TIMEOUT = 45
USER_AGENT = "Projeto-Vacina-Dengue/1.0 (investigacao-pni)"

ALIASES = {
    "codigo_vacina": ("codigo_vacina", "co_vacina", "cod_vacina", "codigo_imunobiologico", "co_imunobiologico"),
    "descricao_vacina": ("descricao_vacina", "ds_vacina", "nome_vacina", "no_vacina", "descricao_imunobiologico"),
    "codigo_dose": ("codigo_dose_vacina", "co_dose_vacina", "cod_dose", "codigo_dose"),
    "descricao_dose": ("descricao_dose_vacina", "ds_dose_vacina", "nome_dose", "no_dose"),
    "data_aplicacao": ("data_vacina", "dt_vacina", "data_aplicacao", "dt_aplicacao", "data"),
    "idade": ("numero_idade_paciente", "nu_idade", "idade", "idade_paciente"),
    "sexo": ("tipo_sexo_paciente", "tp_sexo", "sexo", "sexo_paciente"),
    "municipio_paciente": ("codigo_municipio_paciente", "co_municipio_paciente", "id_mn_resi", "codigo_municipio_residencia"),
    "municipio_estabelecimento": ("codigo_municipio_estabelecimento", "co_municipio_estabelecimento", "id_municip", "codigo_municipio"),
}

CAMPOS_OBRIGATORIOS_PARA_ANALISE = (
    "codigo_vacina", "descricao_vacina", "codigo_dose", "data_aplicacao",
    "idade", "sexo", "municipio_paciente", "municipio_estabelecimento",
)


def extrair_registros(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list) and all(isinstance(item, dict) for item in payload):
        return payload
    if isinstance(payload, dict):
        for chave in ("data", "dados", "results", "resultados", "items", "registros"):
            valor = payload.get(chave)
            if isinstance(valor, list) and all(isinstance(item, dict) for item in valor):
                return valor
        listas = [valor for valor in payload.values() if isinstance(valor, list)]
        if len(listas) == 1 and all(isinstance(item, dict) for item in listas[0]):
            return listas[0]
    raise ValueError("Formato da resposta PNI não reconhecido.")


def _normalizar_chave(valor: str) -> str:
    return re.sub(r"[^a-z0-9]", "", valor.lower())


def obter_campo(registro: dict[str, Any], aliases: Iterable[str]) -> Any:
    mapa = {_normalizar_chave(str(chave)): valor for chave, valor in registro.items()}
    for alias in aliases:
        valor = mapa.get(_normalizar_chave(alias))
        if valor not in (None, ""):
            return valor
    return None


def resumir_contador(contador: Counter, limite: int = 50) -> list[dict[str, Any]]:
    return [
        {"valor": valor, "registros": quantidade}
        for valor, quantidade in sorted(contador.items(), key=lambda item: (-item[1], str(item[0])))[:limite]
    ]


def analisar_registros(registros: list[dict[str, Any]]) -> dict[str, Any]:
    presenca = Counter()
    codigos_vacina: Counter = Counter()
    catalogo_vacina: Counter = Counter()
    codigos_dose: Counter = Counter()
    descricoes_dose: Counter = Counter()
    sexos: Counter = Counter()
    idades: Counter = Counter()
    municipios_paciente: Counter = Counter()
    municipios_estabelecimento: Counter = Counter()
    datas: list[str] = []
    campos = sorted({str(chave) for registro in registros for chave in registro})

    for registro in registros:
        valores = {
            nome: obter_campo(registro, aliases)
            for nome, aliases in ALIASES.items()
        }
        for nome, valor in valores.items():
            if valor not in (None, ""):
                presenca[nome] += 1

        codigo = valores["codigo_vacina"]
        descricao = valores["descricao_vacina"]
        if codigo not in (None, ""):
            codigos_vacina[str(codigo)] += 1
            catalogo_vacina[(str(codigo), str(descricao or "SEM_DESCRICAO"))] += 1
        if valores["codigo_dose"] not in (None, ""):
            codigos_dose[str(valores["codigo_dose"])] += 1
        if valores["descricao_dose"] not in (None, ""):
            descricoes_dose[str(valores["descricao_dose"])] += 1
        if valores["sexo"] not in (None, ""):
            sexos[str(valores["sexo"])] += 1
        if valores["idade"] not in (None, ""):
            idades[str(valores["idade"])] += 1
        if valores["municipio_paciente"] not in (None, ""):
            municipios_paciente[str(valores["municipio_paciente"])] += 1
        if valores["municipio_estabelecimento"] not in (None, ""):
            municipios_estabelecimento[str(valores["municipio_estabelecimento"])] += 1
        if valores["data_aplicacao"] not in (None, ""):
            datas.append(str(valores["data_aplicacao"]))

    catalogo = [
        {"codigo_vacina": codigo, "descricao": descricao, "registros": quantidade,
         "descricao_menciona_dengue": "dengue" in descricao.lower()}
        for (codigo, descricao), quantidade in sorted(
            catalogo_vacina.items(), key=lambda item: (-item[1], item[0][0], item[0][1])
        )
    ]
    campos_presentes = {
        nome: {"registros_preenchidos": presenca[nome],
               "percentual_preenchido": round(presenca[nome] * 100 / len(registros), 2) if registros else 0.0}
        for nome in ALIASES
    }
    datas_ordenadas = sorted(datas)
    return {
        "registros_analisados": len(registros),
        "campos_retornados": campos,
        "campos_semanticos": campos_presentes,
        "codigos_vacina": resumir_contador(codigos_vacina),
        "catalogo_vacina_observado": catalogo,
        "codigos_dose": resumir_contador(codigos_dose),
        "descricoes_dose": resumir_contador(descricoes_dose),
        "sexo": resumir_contador(sexos),
        "idades_observadas": resumir_contador(idades, limite=100),
        "municipios_paciente": resumir_contador(municipios_paciente),
        "municipios_estabelecimento": resumir_contador(municipios_estabelecimento),
        "data_aplicacao_minima_observada": datas_ordenadas[0] if datas_ordenadas else None,
        "data_aplicacao_maxima_observada": datas_ordenadas[-1] if datas_ordenadas else None,
        "possiveis_codigos_dengue": [
            item for item in catalogo if item["descricao_menciona_dengue"]
        ],
        "campos_semanticos_ausentes": [
            nome for nome in CAMPOS_OBRIGATORIOS_PARA_ANALISE if presenca[nome] == 0
        ],
    }


def consultar_ano(
    ano: int, *, page_size: int = 1000, max_pages: int = 3,
    session: Any = requests,
) -> dict[str, Any]:
    if not 1 <= page_size <= 1000:
        raise ValueError("page_size deve estar entre 1 e 1000.")
    if max_pages < 1:
        raise ValueError("max_pages deve ser maior ou igual a 1.")

    registros: list[dict[str, Any]] = []
    paginas = 0
    for pagina in range(max_pages):
        response = session.get(
            f"{API_BASE}{ROTA.format(ano=ano)}",
            params={"limit": page_size, "offset": pagina},
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        lote = extrair_registros(response.json())
        paginas += 1
        registros.extend(lote)
        if len(lote) < page_size:
            break
    return {
        "ano_endpoint": ano,
        "paginas_consultadas": paginas,
        "limite_por_pagina": page_size,
        **analisar_registros(registros),
    }


def gerar_relatorio(
    anos: Iterable[int], *, page_size: int = 1000, max_pages: int = 3,
    session: Any = requests,
) -> dict[str, Any]:
    relatorio: dict[str, Any] = {
        "fonte": "API de Dados Abertos do SUS — PNI",
        "base_url": API_BASE,
        "gerado_em_utc": datetime.now(timezone.utc).isoformat(),
        "metodo": "amostragem paginada; agregações; sem persistência de registros individuais",
        "parametros": {"page_size": page_size, "max_pages_por_ano": max_pages},
        "anos": {},
        "erros": {},
        "observacoes": [
            "A amostra não comprova completude anual nem cobertura de todos os municípios.",
            "Código de vacina só será classificado como dengue após validação em dicionário oficial.",
            "Município do paciente e do estabelecimento são dimensões distintas.",
            "Idade observada não foi convertida em faixa etária porque a codificação precisa ser validada.",
        ],
    }
    for ano in anos:
        try:
            relatorio["anos"][str(ano)] = consultar_ano(
                ano, page_size=page_size, max_pages=max_pages, session=session
            )
        except Exception as exc:
            relatorio["erros"][str(ano)] = f"{type(exc).__name__}: {exc}"
    if not relatorio["anos"]:
        raise RuntimeError("Nenhum endpoint PNI pôde ser inspecionado: " + json.dumps(relatorio["erros"]))
    return relatorio


def main() -> int:
    parser = argparse.ArgumentParser(description="Investiga códigos e campos da API PNI sem carregar o banco.")
    parser.add_argument("--anos", default="2023,2024,2025,2026")
    parser.add_argument("--page-size", type=int, default=1000)
    parser.add_argument("--max-pages", type=int, default=3)
    parser.add_argument("--saida", default="reports/pni/inspecao_pni_dengue.json")
    args = parser.parse_args()
    anos = tuple(int(item.strip()) for item in args.anos.split(",") if item.strip())
    if not anos:
        parser.error("Informe pelo menos um ano.")
    relatorio = gerar_relatorio(anos, page_size=args.page_size, max_pages=args.max_pages)
    destino = Path(args.saida)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(relatorio, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
