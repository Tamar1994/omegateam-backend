"""
Modelos Pydantic para Campeonato de Poomsae (Conformidade WT)
Baseado em: World Taekwondo Poomsae Competition Rules & Interpretation
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime
from enum import Enum


class TipoPoomsae(str, Enum):
    """Tipos de Poomsae conforme WT"""
    RECOGNIZED = "Recognized"
    FREESTYLE = "Freestyle"
    MIXED = "Mixed"


class SistemaCompeticao(str, Enum):
    """Sistemas de competição conforme WT Artigo 7"""
    SINGLE_ELIMINATION = "Single Elimination"
    ROUND_ROBIN = "Round Robin"
    CUT_OFF = "Cut Off"
    COMBINATION = "Combination"


class StatusCampeonato(str, Enum):
    """Status do campeonato"""
    PLANNING = "Planning"
    REGISTRATION = "Registration"
    DRAWING = "Drawing"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"


class RequisitosConformidade(BaseModel):
    """Requisitos mínimos WT - Artigo 7"""
    min_6_paises: bool = False
    min_6_atletas_por_divisao: bool = False
    venue_conforme: bool = False
    td_designado: bool = False
    juizes_qualificados: bool = False


class EspecificacoesVenue(BaseModel):
    """Especificações do venue - Artigo 3"""
    capacidade_minima_assentos: int = Field(default=2000, ge=2000, description="Mínimo WT")
    piso_minimo_m2: float = Field(default=1500, ge=1500, description="30m × 50m mínimo")
    altura_minima_teto: float = Field(default=10, ge=10, description="Metros")
    iluminacao_lux_min: int = Field(default=1500, ge=1500, description="Lux")
    iluminacao_lux_max: int = Field(default=1800, le=1800, description="Lux")
    numero_cortes: int = Field(default=1, ge=1, le=3, description="Cortes de competição")
    tipo_superfice: str = Field(default="Tatame elástico", description="Material da quadra")
    altura_plataforma_m: Optional[float] = Field(default=None, ge=0.5, le=0.6, description="Opcional")


class CampeonatoPoomsaeCreate(BaseModel):
    """Criação de novo campeonato Poomsae"""
    nome: str = Field(..., min_length=3, description="Nome do campeonato")
    data_inicio: datetime
    data_fim: datetime
    localizacao: str
    organizador: str
    
    tipo: TipoPoomsae = TipoPoomsae.RECOGNIZED
    sistema_competicao: SistemaCompeticao = SistemaCompeticao.CUT_OFF
    
    technical_delegate_email: str
    
    # Especificações do venue
    venue_specs: EspecificacoesVenue = Field(default_factory=EspecificacoesVenue)
    
    # Descrição/notas
    descricao: Optional[str] = None


class CampeonatoPoomsae(CampeonatoPoomsaeCreate):
    """Modelo completo de campeonato Poomsae (com ID e timestamps)"""
    id: str = Field(alias="_id")
    status: StatusCampeonato = StatusCampeonato.PLANNING
    
    # Conformidade WT
    requisitos: RequisitosConformidade = Field(default_factory=RequisitosConformidade)
    
    # Drawing of Lots
    data_drawing_lots: Optional[datetime] = None
    formas_designadas: dict = Field(default_factory=dict, description="{'divisao': ['forma1', 'forma2']}")
    
    # Timestamps
    timestamp_criacao: datetime = Field(default_factory=datetime.utcnow)
    timestamp_atualizacao: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "nome": "Campeonato Estadual de Poomsae 2026",
                "data_inicio": "2026-05-15T08:00:00",
                "data_fim": "2026-05-15T18:00:00",
                "localizacao": "São Paulo - SP",
                "organizador": "Confederação de Taekwondo",
                "tipo": "Recognized",
                "sistema_competicao": "Cut Off",
                "technical_delegate_email": "td@example.com",
                "status": "Planning",
                "requisitos": {
                    "min_6_paises": False,
                    "min_6_atletas_por_divisao": False,
                    "venue_conforme": True,
                    "td_designado": True,
                    "juizes_qualificados": False
                }
            }
        }


class AtualizarCampeonatoPoomsae(BaseModel):
    """Para updates parciais"""
    nome: Optional[str] = None
    data_inicio: Optional[datetime] = None
    data_fim: Optional[datetime] = None
    localizacao: Optional[str] = None
    status: Optional[StatusCampeonato] = None
    sistema_competicao: Optional[SistemaCompeticao] = None
    venue_specs: Optional[EspecificacoesVenue] = None
