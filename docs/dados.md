# Novo CAGED: o que foi confirmado (competência 2025-10)

Fonte: `ftp://ftp.mtps.gov.br/pdet/microdados/NOVO CAGED/<ano>/<AAAAMM>/`
Cada mês tem 3 arquivos `.7z`: `CAGEDMOV` (movimentações), `CAGEDFOR` (fora do prazo), `CAGEDEXC` (exclusões).
Só `CAGEDMOV202510` foi baixado e inspecionado.

## Formato
- `CAGEDMOV202510.7z`: 55 MB compactado, um `.txt` de 465 MB descompactado.
- Texto com separador `;`, **UTF-8**, decimal com **vírgula** (`1592,64`).
- 4.457.773 linhas e 28 colunas. Só `idade` tem nulos (11 linhas).
- `competênciamov` tem um único valor (`202510`), o mês do arquivo.
- `indicadordeforadoprazo` é `0` em todas as linhas, como esperado no arquivo de movimentações no prazo.

## Colunas
competênciamov, região, uf, município, seção, subclasse, saldomovimentação, cbo2002ocupação, categoria,
graudeinstrução, idade, horascontratuais, raçacor, sexo, tipoempregador, tipoestabelecimento,
tipomovimentação, tipodedeficiência, indtrabintermitente, indtrabparcial, salário, tamestabjan,
indicadoraprendiz, origemdainformação, competênciadec, indicadordeforadoprazo, unidadesaláriocódigo,
valorsaláriofixo

## Para o Radar
- `saldomovimentação` é `1` (admissão) ou `-1` (desligamento): 2.271.460 admissões e 2.186.313 desligamentos, saldo de +85.147 no mês.
- `seção` (22 valores) é a letra da CNAE e serve como "setor"; `subclasse` (1.301 valores) detalha.
- `uf` e `região` são códigos numéricos, `região` inclui `99` (521 linhas, provavelmente não identificado).
- `salário` e `valorsaláriofixo` são texto com vírgula e precisam de conversão na carga.

## Pendências
- Os códigos (uf, seção, tipomovimentação, categoria etc.) ainda precisam do dicionário oficial,
  que está no `Layout Não-identificado Novo Caged Movimentação.xlsx` na raiz do FTP. Ainda não li esse arquivo.
- Ver como `CAGEDFOR` e `CAGEDEXC` entram no saldo antes de decidir se a carga os inclui.
