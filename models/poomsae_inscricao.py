"""
Modelos Pydantic para Inscrições (Conformidade WT Poomsae)
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime
from enum import Enum


class TipoInscricao(str, Enum):
    """Tipos de inscrição - Artigo 6"""
    INDIVIDUAL = "Individual"
    DUPLA = "Dupla/Pair"
    EQUIPE = "Equipe/Team"


class StatusInscricao(str, Enum):
    INSCRITA = "Inscrita"
    CONFIRMADA = "Confirmada"
    COMPETINDO = "Competindo"
    FINALIZADA = "Finalizada"
    RETIRADA = "Retirada"


class StatusInspecaoUniforme(str, Enum):
    PENDENTE = "Pendente"
    APROVADO = "Aprovado"
    REJEITADO = "Rejeitado"
    AJUSTE_NECESSARIO = "Ajuste Necessário"


class InscricaoCreate(BaseModel):
    """Criação de inscrição"""
    campeonato_id: str
    atleta_id: str  # ID do atleta principal ou primeiro membro
    
    pais_representado: str
    tipo_inscricao: TipoInscricao = TipoInscricao.INDIVIDUAL
    divisao: str = Field(..., description="Ex: 'Cadet', 'Junior', 'Under 30'")
    
    # Para Dupla/Equipe
    id_membros: Optional[List[str]] = None  # IDs dos outros atletas
    id_substituto: Optional[str] = None  # Para equipe mista (opcional)


class Inscricao(InscricaoCreate):
    """Modelo completo de inscrição"""
    id: str = Field(alias="_id")
    
    # Campos calculados
    categoria_etaria_calculada: str  # Calculado automaticamente
    numero_categorias_inscrito: int = Field(default=1, le=2)
    
    # Uniforme
    dobok_modelo: Optional[str] = None
    dobok_certificado_wt: bool = True
    status_inspecao: StatusInspecaoUniforme = StatusInspecaoUniforme.PENDENTE
    
    # Presença (Artigo 13)
    chamada_1_presenca: Optional[bool] = None  # 30 min antes
    chamada_2_presenca: Optional[bool] = None  # 15 min antes
    chamada_3_presenca: Optional[bool] = None  # 5 min antes
    status_presenca: Optional[str] = None  # "Presente", "Ausente/WO", "Retirado"
    
    # Status
    status: StatusInscricao = StatusInscricao.INSCRITA
    
    # Timestamps
    timestamp_inscricao: datetime = Field(default_factory=datetime.utcnow)
    timestamp_confirmacao: Optional[datetime] = None
    timestamp_atualizacao: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "campeonato_id": "507f1f77bcf86cd799439011",
                "atleta_id": "507f1f77bcf86cd799439012",
                "pais_representado": "Brasil",
                "tipo_inscricao": "Individual",
                "divisao": "Cadet",
                "categoria_etaria_calculada": "12-14 (Cadet)",
                "status": "Inscrita"
            }
        }


class AtualizarInscricao(BaseModel):
    """Para updates (só antes de Drawing of Lots)"""
    divisao: Optional[str] = None
    tipo_inscricao: Optional[TipoInscricao] = None
    id_membros: Optional[List[str]] = None
    dobok_modelo: Optional[str] = None
    status: Optional[StatusInscricao] = None


class ComposicaoGrupo(BaseModel):
    """Validação de composição de dupla/equipe"""
    tipo: TipoInscricao
    num_membros: int
    num_homens: Optional[int] = 0
    num_mulheres: Optional[int] = 0
    tem_substituto: bool = False
    
    # Validações
    valido: bool = True
    mensagem_erro: Optional[str] = None


class InscricaoComConfirmacao(Inscricao):
    """Inscrição com dados de confirmação"""
    confirmada: bool = False
    documentos_enviados: bool = False
    uniforme_aprovado: bool = False
