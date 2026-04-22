"""
Modelos Pydantic para Atletas (Conformidade WT Poomsae)
"""
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, Literal
from datetime import datetime, date
from enum import Enum


class TipoElegibilidade(str, Enum):
    """Tipos de elegibilidade - Artigo 4.1"""
    NACIONALIDADE = "Nacionalidade do país"
    RECOMENDACAO = "Recomendação associação"
    DAN_POOM_WT = "Dan/Poom WT"
    DAN_POOM_KUKKIWON = "Dan/Poom Kukkiwon"
    GAL_WT = "WT Global Athlete Licence"


class DivisaoEtaria(str, Enum):
    """Divisões etárias - Artigo 6"""
    CADET = "12-14 (Cadet)"
    JUNIOR = "15-17 (Junior)"
    UNDER_30 = "18-30 (Under 30)"
    UNDER_40 = "31-40 (Under 40)"
    UNDER_50 = "41-50 (Under 50)"
    UNDER_60 = "51-60 (Under 60)"
    UNDER_65 = "61-65 (Under 65)"
    OVER_65 = "66+ (Over 65)"


class GeneroAtleta(str, Enum):
    MASCULINO = "M"
    FEMININO = "F"


class ClasseParataekwondo(str, Enum):
    """Classes para Para-Taekwondo - Artigo 23"""
    P11 = "P11"
    P12 = "P12"
    P13 = "P13"
    P20 = "P20"
    P31 = "P31"
    P32 = "P32"
    P33 = "P33"
    P34 = "P34"
    P50_PLUS = "P50+"
    P71 = "P71"
    P72 = "P72"
    P60 = "P60"  # Deaf


class AtletaCreate(BaseModel):
    """Criação de novo atleta"""
    nome_completo: str = Field(..., min_length=3)
    data_nascimento: date
    genero: GeneroAtleta
    nacionalidade: str
    email: EmailStr
    
    # Elegibilidade
    tipo_elegibilidade: TipoElegibilidade
    numero_documento: Optional[str] = None  # Dan/Poom número
    
    # Para-Taekwondo (opcional)
    classe_parataekwondo: Optional[ClasseParataekwondo] = None
    certificado_classe_wt: Optional[str] = None  # URL documento


class Atleta(AtletaCreate):
    """Modelo completo de atleta"""
    id: str = Field(alias="_id")
    
    # Calculadas automaticamente
    divisao_etaria: Optional[DivisaoEtaria] = None  # Calculada no backend
    categoria_atual_ano: int = Field(default=2026, description="Ano para cálculo de divisão")
    
    # Histórico
    num_competicoes: int = 0
    
    # Timestamps
    timestamp_criacao: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "nome_completo": "João Silva Santos",
                "data_nascimento": "2010-06-15",
                "genero": "M",
                "nacionalidade": "Brasil",
                "email": "joao@example.com",
                "tipo_elegibilidade": "Nacionalidade do país",
                "divisao_etaria": "12-14 (Cadet)",
                "num_competicoes": 3
            }
        }


class AtualizarAtleta(BaseModel):
    """Para updates parciais"""
    nome_completo: Optional[str] = None
    email: Optional[EmailStr] = None
    nacionalidade: Optional[str] = None
    tipo_elegibilidade: Optional[TipoElegibilidade] = None


class AtletaComHistorico(Atleta):
    """Atleta com histórico de competições"""
    competicoes_anteriores: list = Field(default_factory=list, description="IDs de competições")
    ranking_scores: dict = Field(default_factory=dict, description="{'divisao': 8.5, ...}")
