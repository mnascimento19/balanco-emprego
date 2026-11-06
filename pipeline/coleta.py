"""Download e extração dos arquivos do Novo CAGED (FTP do Ministério do Trabalho).

Idempotente: não baixa de novo um arquivo que já existe com o mesmo tamanho do servidor, e não
extrai de novo um .txt que já existe.
"""
import ftplib
import shutil
import tempfile
from pathlib import Path

import py7zr

HOST = "ftp.mtps.gov.br"
BASE = "/pdet/microdados/NOVO CAGED"
TIPOS = ("MOV", "FOR", "EXC")


def _ftp() -> ftplib.FTP:
    ftp = ftplib.FTP(HOST, timeout=120, encoding="latin-1")  # nomes de arquivo com acentos
    ftp.login()
    ftp.voidcmd("TYPE I")
    return ftp


def competencias_disponiveis(ano: int) -> list[str]:
    ftp = _ftp()
    try:
        return sorted(p.split("/")[-1] for p in ftp.nlst(f"{BASE}/{ano}"))
    finally:
        ftp.quit()


def baixar(tipo: str, competencia: str, pasta_raw: Path) -> Path:
    """Baixa CAGED<tipo><competencia>.7z. Pula se já existir com o mesmo tamanho."""
    nome = f"CAGED{tipo}{competencia}.7z"
    remoto = f"{BASE}/{competencia[:4]}/{competencia}/{nome}"
    destino = pasta_raw / nome
    pasta_raw.mkdir(parents=True, exist_ok=True)
    ftp = _ftp()
    try:
        tamanho = ftp.size(remoto)
        if destino.exists() and destino.stat().st_size == tamanho:
            return destino
        parcial = destino.with_suffix(".7z.part")
        with open(parcial, "wb") as f:
            ftp.retrbinary(f"RETR {remoto}", f.write, blocksize=1 << 20)
        if parcial.stat().st_size != tamanho:
            raise IOError(f"{nome}: baixou {parcial.stat().st_size} de {tamanho} bytes")
        parcial.replace(destino)  # só aparece com o nome final se completo
        return destino
    finally:
        ftp.quit()


def extrair(arquivo_7z: Path, pasta_saida: Path) -> Path:
    """Extrai o .txt do .7z, de forma atômica.

    Extrai para uma pasta temporária e só move para o nome final se o resultado estiver íntegro.
    Assim, uma falha no meio (ex.: MemoryError) nunca deixa um .txt incompleto no lugar do final,
    que seria reaproveitado na próxima tentativa. Um .txt final vazio é tratado como inexistente.
    """
    pasta_saida.mkdir(parents=True, exist_ok=True)
    txt = pasta_saida / (arquivo_7z.stem + ".txt")
    if txt.exists() and txt.stat().st_size > 0:
        return txt
    txt.unlink(missing_ok=True)  # vazio/corrompido de uma tentativa anterior

    tmp = Path(tempfile.mkdtemp(prefix=arquivo_7z.stem + "_", dir=pasta_saida))
    try:
        with py7zr.SevenZipFile(arquivo_7z) as z:
            z.extractall(path=tmp)
        saida = tmp / txt.name
        if not saida.exists() or saida.stat().st_size == 0:
            raise FileNotFoundError(f"{txt.name} veio vazio ou ausente ao extrair {arquivo_7z.name}")
        saida.replace(txt)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return txt
