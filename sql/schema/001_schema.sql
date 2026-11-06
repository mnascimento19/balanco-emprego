-- Dimensões: tradução dos códigos do dicionário oficial (layout .xlsx do CAGED).
-- Carregadas pelo pipeline a partir das abas do dicionário.
CREATE TABLE regiao      (codigo smallint PRIMARY KEY, descricao text NOT NULL);
CREATE TABLE uf          (codigo smallint PRIMARY KEY, descricao text NOT NULL);
CREATE TABLE secao       (codigo char(1)  PRIMARY KEY, descricao text NOT NULL);
CREATE TABLE tipo_movimentacao (codigo smallint PRIMARY KEY, descricao text NOT NULL);
CREATE TABLE grau_instrucao    (codigo smallint PRIMARY KEY, descricao text NOT NULL);
CREATE TABLE raca_cor    (codigo smallint PRIMARY KEY, descricao text NOT NULL);
CREATE TABLE sexo        (codigo smallint PRIMARY KEY, descricao text NOT NULL);
CREATE TABLE categoria   (codigo smallint PRIMARY KEY, descricao text NOT NULL);

-- Município, subclasse e CBO ficam sem chave estrangeira: o arquivo traz códigos
-- que não estão no dicionário (município 510183, subclasse 8630505, ~31 CBOs).
CREATE TABLE municipio   (codigo integer PRIMARY KEY, descricao text NOT NULL);
CREATE TABLE subclasse   (codigo integer PRIMARY KEY, descricao text NOT NULL);
CREATE TABLE cbo         (codigo integer PRIMARY KEY, descricao text NOT NULL);

-- Controle de carga: um registro por arquivo do governo (tipo + mês da declaração).
-- É a unidade de idempotência. Se o hash do arquivo não mudou, a carga é pulada; se mudou
-- (o governo republica arquivos), apaga as linhas daquele arquivo e reinsere, numa transação.
CREATE TABLE carga_arquivo (
    arquivo_tipo           text    NOT NULL CHECK (arquivo_tipo IN ('MOV', 'FOR', 'EXC')),
    competencia_declaracao char(6) NOT NULL,       -- AAAAMM do nome do arquivo
    sha256                 text    NOT NULL,
    tamanho_bytes          bigint  NOT NULL,
    linhas                 integer NOT NULL,
    carregado_em           timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (arquivo_tipo, competencia_declaracao)
);

-- Fatos: uma linha por movimentação (admissão ou desligamento) de um arquivo.
-- O arquivo não tem identificador, e há linhas idênticas (121 mil grupos em 2025-10, em geral
-- de 2 a 6 linhas), que não são removidas: são tratadas como eventos distintos.
-- A chave é artificial e a deduplicação acontece por arquivo, via carga_arquivo.
-- Sem FKs para as dimensões de propósito: a checagem linha a linha custava ~90% do tempo
-- da carga (94 s contra 3 s para 500 mil linhas). O pipeline valida os códigos contra as
-- dimensões de uma vez só, antes de inserir (pipeline/carga.py, DIMENSOES_VALIDADAS).
CREATE TABLE movimentacao (
    id              bigserial PRIMARY KEY,
    arquivo_tipo    text     NOT NULL,
    competencia_declaracao char(6) NOT NULL,      -- mês do arquivo (competênciadec)
    competencia_evento     char(6) NOT NULL,      -- mês em que ocorreu (competênciamov)
    FOREIGN KEY (arquivo_tipo, competencia_declaracao)
        REFERENCES carga_arquivo (arquivo_tipo, competencia_declaracao) ON DELETE CASCADE,
    regiao          smallint NOT NULL,            -- sem FK: existe o código 99
    uf              smallint NOT NULL,
    municipio       integer  NOT NULL,
    secao           char(1)  NOT NULL,
    subclasse       integer  NOT NULL,
    saldo           smallint NOT NULL CHECK (saldo IN (-1, 1)),
    cbo             integer,
    categoria       smallint,
    grau_instrucao  smallint,
    idade           smallint,                     -- 11 nulos em 2025-10
    horas_contratuais numeric(5,2),
    raca_cor        smallint,
    sexo            smallint,
    tipo_movimentacao smallint,
    salario         numeric(12,2),                -- no arquivo vem com vírgula decimal
    -- Efeito no saldo de empregos: uma exclusão cancela o evento, com efeito inverso
    -- (Leia-me do CAGED). Esta é a coluna que as análises devem somar.
    saldo_efetivo   smallint GENERATED ALWAYS AS
                    (CASE WHEN arquivo_tipo = 'EXC' THEN -saldo ELSE saldo END) STORED
);

CREATE INDEX ix_mov_arquivo ON movimentacao (arquivo_tipo, competencia_declaracao);
CREATE INDEX ix_mov_evento  ON movimentacao (competencia_evento);
