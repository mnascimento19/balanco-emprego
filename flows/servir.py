"""Deixa o flow agendado: roda todo dia às 08:00 e só carrega o que for novo.

O governo publica o mês anterior perto do fim do mês seguinte, então consultar todo dia é simples
e robusto: se não houver nada novo o flow termina em segundos.
"""
from .carga_mensal import carga_mensal

if __name__ == "__main__":
    carga_mensal.serve(name="carga-diaria", cron="0 8 * * *")
