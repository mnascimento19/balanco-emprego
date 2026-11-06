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

-- Fatos: uma linha por movimentação (admissão ou desligamento).
-- O arquivo não tem identificador, e há linhas idênticas no mesmo mês, então a chave é
-- artificial. A idempotência vem da competência: recarregar um mês apaga e reinsere esse mês.
CREATE TABLE movimentacao (
    id              bigserial PRIMARY KEY,
    competencia     char(6)  NOT NULL,            -- AAAAMM do arquivo (competênciamov)
    regiao          smallint NOT NULL,            -- sem FK: existe o código 99
    uf              smallint NOT NULL REFERENCES uf(codigo),
    municipio       integer  NOT NULL,
    secao           char(1)  NOT NULL REFERENCES secao(codigo),
    subclasse       integer  NOT NULL,
    saldo           smallint NOT NULL CHECK (saldo IN (-1, 1)),
    cbo             integer,
    categoria       smallint REFERENCES categoria(codigo),
    grau_instrucao  smallint REFERENCES grau_instrucao(codigo),
    idade           smallint,                     -- 11 nulos em 2025-10
    horas_contratuais numeric(5,2),
    raca_cor        smallint REFERENCES raca_cor(codigo),
    sexo            smallint REFERENCES sexo(codigo),
    tipo_movimentacao smallint REFERENCES tipo_movimentacao(codigo),
    salario         numeric(12,2)                 -- no arquivo vem com vírgula decimal
);

CREATE INDEX ix_mov_competencia ON movimentacao (competencia);
