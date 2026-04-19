"""
Modelos de Inscrição (Pydantic)
"""
from pydantic import BaseModel


class InscricaoData(BaseModel):
    campeonato_id: str
    atleta_email: str
    categoria_id: str
    modalidade: str  # Kyorugui ou Poomsae


class AtualizarStatusInscricao(BaseModel):
    status_pagamento: str  # "Confirmado", "Pendente" ou "Cancelado"
