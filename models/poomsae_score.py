"""
Modelos de Match e Score para Poomsae (Conformidade WT)
Baseado em: Artigos 10-14 (Pontuação), Artigo 9 (Procedimento)
"""
from pydantic import BaseModel, Field, model_validator
from typing import List, Optional, Dict
from datetime import datetime
from enum import Enum


# ─────────────────────────────────────────────
#  Enums
# ─────────────────────────────────────────────

class TipoPoomsaeMatch(str, Enum):
    RECOGNIZED = "Recognized"
    FREESTYLE = "Freestyle"


class StatusMatch(str, Enum):
    AGENDADO = "Agendado"
    EM_ANDAMENTO = "Em Andamento"
    AGUARDANDO_SCORES = "Aguardando Scores"
    CALCULADO = "Calculado"
    CONCLUIDO = "Concluído"
    REMATCH = "Rematch"
    CANCELADO = "Cancelado"


class MotivoDQ(str, Enum):
    DOIS_KYEONG_GO = "2 Kyeong-go"         # Artigo 14.2
    SAIU_ZONA = "Saiu da Zona"             # Artigo 11.2c
    FORMA_ERRADA = "Forma Errada"          # Artigo 14.1
    UNIFORME = "Uniforme não Conforme"
    OUTROS = "Outros"


# ─────────────────────────────────────────────
#  Score de um juiz (Semana 5)
# ─────────────────────────────────────────────

class ScoreRecognized(BaseModel):
    """
    Pontuação Poomsae Recognized (Artigo 10.2):
      Acurácia: max 4.0 (cada subcritério: 0.1 incrementos)
      Apresentação: max 6.0
      Total: max 10.0
    """
    acuracia: float = Field(..., ge=0.0, le=4.0,
        description="Acurácia de movimentos: 0.0 ~ 4.0")
    apresentacao: float = Field(..., ge=0.0, le=6.0,
        description="Apresentação: 0.0 ~ 6.0")

    @model_validator(mode="after")
    def validar_incrementos(self):
        for campo, val in [("acuracia", self.acuracia), ("apresentacao", self.apresentacao)]:
            # WT usa incrementos de 0.1
            if round(val * 10) != val * 10:
                raise ValueError(f"{campo}: use incrementos de 0.1")
        return self

    @property
    def total(self) -> float:
        return round(self.acuracia + self.apresentacao, 2)


class ScoreFreestyle(BaseModel):
    """
    Pontuação Poomsae Freestyle (Artigo 10.3):
      Habilidade Técnica: max 6.0
      Apresentação: max 4.0
      Total: max 10.0
    """
    habilidade_tecnica: float = Field(..., ge=0.0, le=6.0,
        description="Habilidade técnica: 0.0 ~ 6.0")
    apresentacao: float = Field(..., ge=0.0, le=4.0,
        description="Apresentação: 0.0 ~ 4.0")

    @model_validator(mode="after")
    def validar_incrementos(self):
        for campo, val in [("habilidade_tecnica", self.habilidade_tecnica), ("apresentacao", self.apresentacao)]:
            if round(val * 10) != val * 10:
                raise ValueError(f"{campo}: use incrementos de 0.1")
        return self

    @property
    def total(self) -> float:
        return round(self.habilidade_tecnica + self.apresentacao, 2)


class ScoreJuiz(BaseModel):
    """Score submetido por um juiz para um match"""
    match_id: str
    juiz_id: str
    numero_juiz: int = Field(..., ge=1, le=7, description="Posição do juiz (1-7)")

    # Um dos dois tipos, dependendo do match
    score_recognized: Optional[ScoreRecognized] = None
    score_freestyle: Optional[ScoreFreestyle] = None

    # Penalidades aplicadas por este juiz (não por todos)
    # Nota: deduções de tempo/zona são aplicadas pelo Referee, não por juiz
    observacao: Optional[str] = None

    timestamp_submissao: Optional[datetime] = None
    editavel: bool = True  # False após prazo

    @model_validator(mode="after")
    def validar_tipo_score(self):
        if not self.score_recognized and not self.score_freestyle:
            raise ValueError("Forneça score_recognized OU score_freestyle")
        if self.score_recognized and self.score_freestyle:
            raise ValueError("Forneça apenas um tipo de score")
        return self


# ─────────────────────────────────────────────
#  Deduções (Artigo 11)
# ─────────────────────────────────────────────

class Deducoes(BaseModel):
    """
    Deduções aplicáveis (Artigo 11):
    - Saiu da zona de competição: -0.3
    - Fora do tempo permitido: -0.3 (Recognized ≤90s, Freestyle 90-100s)
    - Kyeong-go (advertência): 2 = DQ automático (Artigo 14.2)
    """
    saiu_zona: bool = False               # -0.3 (Artigo 11.2c)
    fora_do_tempo: bool = False           # -0.3 (Artigo 11.2a)
    num_kyeong_go: int = Field(default=0, ge=0, le=2)  # Artigo 14.2
    desqualificado: bool = False
    motivo_dq: Optional[MotivoDQ] = None

    @property
    def total_deducao(self) -> float:
        if self.desqualificado:
            return 0.0  # DQ remove pontuação inteira via status
        total = 0.0
        if self.saiu_zona:
            total += 0.3
        if self.fora_do_tempo:
            total += 0.3
        return round(total, 1)


# ─────────────────────────────────────────────
#  Match (uma execução de forma)
# ─────────────────────────────────────────────

class MatchCreate(BaseModel):
    """Criação de um match de poomsae"""
    campeonato_id: str

    # Campos opcionais para criação via MesarioPanel
    luta_id: Optional[str] = None
    atleta_id: Optional[str] = None
    inscricao_id: Optional[str] = None  # Usado em fluxo de Drawing of Lots

    rodada: int = Field(default=1, ge=1)
    numero_match: Optional[int] = None
    divisao: str = "Geral"
    categoria: Optional[str] = None

    # Aceita "tipo_poomsae" (padrão) ou "tipo" (enviado pelo MesarioPanel)
    tipo_poomsae: Optional[TipoPoomsaeMatch] = None
    tipo: Optional[str] = None

    forma_designada: str = "Poomsae"

    # Timing (Artigo 11)
    tempo_limite_seg: int = Field(default=90, description="90s Recognized, 100s Freestyle")
    tempo_executado_seg: Optional[int] = None

    # Juízes
    numero_juizes: Optional[int] = 5
    referee_id: Optional[str] = None
    juiz_ids: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalizar_tipo_poomsae(self):
        """Normaliza o campo tipo/tipo_poomsae para sempre ter tipo_poomsae definido"""
        if not self.tipo_poomsae and self.tipo:
            try:
                self.tipo_poomsae = TipoPoomsaeMatch(self.tipo)
            except ValueError:
                self.tipo_poomsae = TipoPoomsaeMatch.RECOGNIZED
        if not self.tipo_poomsae:
            self.tipo_poomsae = TipoPoomsaeMatch.RECOGNIZED
        return self


class Match(MatchCreate):
    """Match completo com resultado"""
    id: str = Field(alias="_id")

    status: StatusMatch = StatusMatch.AGENDADO
    deducoes: Deducoes = Field(default_factory=Deducoes)

    # Scores coletados (um por juiz)
    scores_juizes: List[str] = Field(default_factory=list,
        description="IDs dos ScoreJuiz submetidos")

    # Resultado calculado (preenchido após calcular_pontuacao_final)
    resultado: Optional["ResultadoMatch"] = None

    timestamp_criacao: datetime = Field(default_factory=datetime.utcnow)
    timestamp_inicio: Optional[datetime] = None
    timestamp_fim: Optional[datetime] = None

    class Config:
        populate_by_name = True


# ─────────────────────────────────────────────
#  Resultado calculado (Semana 6)
# ─────────────────────────────────────────────

class DetalheCalculo(BaseModel):
    """Detalhe do cálculo de pontuação para transparência"""
    scores_recebidos: List[float]         # Todos os scores do componente
    score_max: float                      # Removido
    score_min: float                      # Removido
    scores_validos: List[float]           # Após remover max e min
    media: float                          # Média dos válidos
    num_juizes: int


class ResultadoMatch(BaseModel):
    """
    Resultado final calculado conforme Artigo 13 WT.
    
    Recognized:
      - Acurácia média + Apresentação média = Total base
      - Total final = Total base - Deduções
    
    Freestyle:
      - Habilidade Técnica média + Apresentação média = Total base
      - Total final = Total base - Deduções
    """
    match_id: str

    # Recognized
    detalhe_acuracia: Optional[DetalheCalculo] = None
    detalhe_apresentacao: Optional[DetalheCalculo] = None

    # Freestyle
    detalhe_habilidade_tecnica: Optional[DetalheCalculo] = None

    pontuacao_base: float = 0.0          # Antes de deduções
    total_deducoes: float = 0.0
    pontuacao_final: float = 0.0         # Pontuação que entra no ranking

    # Totais brutos (para desempate critério 4)
    soma_total_scores: float = 0.0       # Soma de TODOS os scores (incl. max/min)

    desqualificado: bool = False
    num_juizes_computados: int = 0

    timestamp_calculo: datetime = Field(default_factory=datetime.utcnow)


# ─────────────────────────────────────────────
#  Desempate (Semana 7)
# ─────────────────────────────────────────────

class CriterioDesempate(str, Enum):
    APRESENTACAO = "Maior Apresentação"         # Recognized
    HABILIDADE_TECNICA = "Maior Hab. Técnica"  # Freestyle
    FREESTYLE_EM_MIXED = "Maior Score Freestyle"  # Mixed
    SOMA_TOTAL = "Maior Soma Total"             # Critério 4
    REMATCH = "Rematch Necessário"              # Critério 5


class ResultadoDesempate(BaseModel):
    """Resultado de resolução de desempate entre dois atletas/times"""
    match_id_1: str
    match_id_2: str
    criterio_aplicado: CriterioDesempate
    vencedor_match_id: Optional[str] = None  # None = REMATCH
    precisa_rematch: bool = False
    detalhes: str = ""
