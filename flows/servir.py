"""Deixa o flow agendado: roda todo dia às 08:00 e só carrega o que for novo.

O agendamento do Prefect precisa de um servidor local (gratuito, sem conta). Sem ele o Prefect
só avisa "Cannot schedule flows on an ephemeral server" e nunca dispara nada, por isso este
script se recusa a rodar sem ele. Em dois terminais:

    prefect server start
    PREFECT_API_URL=http://127.0.0.1:4200/api python -m flows.servir

Vale enquanto os dois processos estiverem rodando nesta máquina; não é um agendador na nuvem.
O governo publica o mês anterior perto do fim do mês seguinte, então consultar todo dia é simples e
robusto: se não houver nada novo o flow termina em segundos.
"""
import sys

from prefect.settings import PREFECT_API_URL

from .carga_mensal import carga_mensal

AVISO = (
    "Sem servidor do Prefect não há agendamento. Em outro terminal rode `prefect server start` e "
    "depois defina PREFECT_API_URL=http://127.0.0.1:4200/api antes de rodar este comando."
)


def main() -> int:
    if not PREFECT_API_URL.value():
        print(AVISO, file=sys.stderr)
        return 1
    carga_mensal.serve(name="carga-diaria", cron="0 8 * * *")
    return 0


if __name__ == "__main__":
    sys.exit(main())
