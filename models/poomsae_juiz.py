"""
Modelos Pydantic para Juízes (Conformidade WT Poomsae)
Baseado em: Artigos 20 e 22
"""
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
from datetime import datetime
from enum import Enum


class ClasseJuiz(str, Enum):
    """
    Classes de juízes - Artigo 20.3
    Class 1: Dan 8-9 ou Class2 5+ anos com 8+ eventos
    Class 2: Dan 6-7 ou Class3 3+ anos com 5+ eventos
    Class 3: Dan 4-5 + Seminar WT
    """
    CLASS_1 = "Class 1"
    CLASS_2 = "Class 2"
    CLASS_3 = "Class 3"


class TipoFuncaoJuiz(str, Enum):
    """Função do juiz durante a competição"""
    REFEREE = "Referee"   # Árbitro Principal (Class 1 obrigatório)
    JUDGE = "Judge"       # Árbitro de Apoio


class JuizCreate(BaseModel):
    """Criação de juiz"""
    nome_completo: str = Field(..., min_length=3)
    email: EmailStr
    nacionalidade: str
    
    # Qualificação - Artigo 20
    tipo_funcao: TipoFuncaoJuiz = TipoFuncaoJuiz.JUDGE
    classe: ClasseJuiz = ClasseJuiz.CLASS_3
    
    # Certificações
    numero_dan: int = Field(..., ge=1, le=9, description="Grau dan (1-9)")
    certificado_wt: bool = Field(default=False, description="Possui certificado WT")
    certificado_kukkiwon: bool = Field(default=False, description="Possui certificado Kukkiwon")
    passou_seminar_wt: bool = Field(default=False, description="Passou seminar WT")
    
    # Histórico
    num_eventos_supervisionados: int = 0


class Juiz(JuizCreate):
    """Modelo completo de juiz"""
    id: str = Field(alias="_id")
    
    ativo: bool = True
    timestamp_criacao: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "nome_completo": "Carlos Oliveira",
                "email": "carlos.juiz@example.com",
                "nacionalidade": "Brasil",
                "tipo_funcao": "Judge",
                "classe": "Class 2",
                "numero_dan": 7,
                "certificado_wt": True,
                "certificado_kukkiwon": False,
                "passou_seminar_wt": True,
                "num_eventos_supervisionados": 12
            }
        }


class ComposicaoJuizes(BaseModel):
    """Validação de composição de júri - Artigo 22"""
    referee_id: str
    judge_ids: List[str]  # 4 ou 6 juízes
    
    # Validações
    sistema_juizes: int = Field(default=7, ge=5, le=7, description="7 (padrão) ou 5")
    
    # Resultado da validação
    valido: bool = True
    mensagem_erro: Optional[str] = None


class ConflitosNacionalidade(BaseModel):
    """Resultado da verificação de conflito de nacionalidade - Artigo 22.2"""
    juiz_id: str
    atletas_conflito: List[str] = []
    tem_conflito: bool = False
    excecao_autorizada: bool = False  # Se exceção foi autorizada (se insuficientes)
    autorizado_por: Optional[str] = None
