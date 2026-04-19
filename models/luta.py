"""
Modelos de Luta (Pydantic)
"""
from pydantic import BaseModel


class GerarChavesData(BaseModel):
    modalidade: str  # 'Kyorugui' ou 'Poomsae'


class LateralReadyData(BaseModel):
    lateral_slot: str  # Ex: "lateral1", "lateral2", etc.
    is_ready: bool


class FinalizarLutaData(BaseModel):
    vencedor: str  # 'red' ou 'blue'
    placar_red: int
    placar_blue: int
    faltas_red: int
    faltas_blue: int
