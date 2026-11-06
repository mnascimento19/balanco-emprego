"""Flow do Prefect: baixa, extrai e carrega os meses do Novo CAGED que ainda não estão no banco.

Seguro para rodar quantas vezes quiser: só processa meses sem MOV carregado, o download pula o
que já existe e a carga pula arquivos com o mesmo hash (ver pipeline/carga.py).
"""
from datetime import date
from pathlib import Path

from prefect import flow, get_run_logger, task

from pipeline.carga import carregar_arquivo
from pipeline.coleta import TIPOS, baixar, competencias_disponiveis, extrair
from pipeline.db import conectar

RAIZ = Path(__file__).resolve().parent.parent
RAW, EXTRAIDO = RAIZ / "data" / "raw", RAIZ / "data" / "extracted"
JANELA_MESES = 12  # o radar guarda os últimos 12 meses publicados


def _mes_anterior(c: str, n: int) -> str:
    ano, mes = int(c[:4]), int(c[4:])
    idx = ano * 12 + (mes - 1) - n
    return f"{idx // 12}{idx % 12 + 1:02d}"


@task(retries=3, retry_delay_seconds=[10, 60, 300])
def listar_pendentes() -> list[str]:
    """Últimos JANELA_MESES meses publicados no FTP que ainda não têm MOV no banco."""
    hoje = date.today()
    publicados = sorted(
        set(competencias_disponiveis(hoje.year - 1)) | set(competencias_disponiveis(hoje.year))
    )[-JANELA_MESES:]
    with conectar() as conn:
        feitos = {r[0] for r in conn.execute(
            "SELECT competencia_declaracao FROM carga_arquivo WHERE arquivo_tipo = 'MOV'")}
    return [c for c in publicados if c not in feitos]


@task(retries=3, retry_delay_seconds=[10, 60, 300], timeout_seconds=1800)
def baixar_e_extrair(tipo: str, competencia: str) -> str:
    return str(extrair(baixar(tipo, competencia, RAW), EXTRAIDO))


@task(retries=2, retry_delay_seconds=[30, 120], timeout_seconds=7200)
def carregar(caminho: str) -> str:
    with conectar() as conn:
        return carregar_arquivo(conn, caminho)


@task(retries=2, retry_delay_seconds=30)
def atualizar_indicadores() -> None:
    """Recalcula a view que alimenta o painel (CONCURRENTLY: o site segue lendo durante)."""
    with conectar() as conn:
        conn.autocommit = True  # REFRESH CONCURRENTLY não roda dentro de transação
        conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_indicadores")


@flow(name="carga-mensal-caged", log_prints=True)
def carga_mensal(competencias: list[str] | None = None) -> dict:
    """competencias=None processa os pendentes; ou passe ex.: ['202511'] para forçar meses."""
    log = get_run_logger()
    alvo = competencias or listar_pendentes()
    if not alvo:
        log.info("Nada pendente: banco em dia.")
        return {}
    log.info(f"Meses a processar: {alvo}")
    resultado = {}
    for comp in alvo:
        # EXC e FOR primeiro (pequenos); MOV por último, que é o grande
        for tipo in sorted(TIPOS, key=lambda t: t == "MOV"):
            txt = baixar_e_extrair(tipo, comp)
            resultado[f"{tipo}{comp}"] = carregar(txt)
            log.info(f"{tipo} {comp}: {resultado[f'{tipo}{comp}']}")
    atualizar_indicadores()
    return resultado


if __name__ == "__main__":
    # `python -m flows.carga_mensal` roda uma vez; para agendar, use `python -m flows.servir`
    carga_mensal()
