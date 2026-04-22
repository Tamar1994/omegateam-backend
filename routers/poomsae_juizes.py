"""
Router de Juízes de Poomsae
"""
from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List, Optional
from pydantic import BaseModel

from database.connection import get_db
from models.poomsae_juiz import JuizCreate
import services.poomsae_juiz_service as service

router = APIRouter(prefix="/api/poomsae/juizes", tags=["Poomsae - Juízes"])


class ValidarComposicaoRequest(BaseModel):
    referee_id: str
    judge_ids: List[str]


class ConflitosRequest(BaseModel):
    juiz_id: str
    atleta_ids: List[str]


@router.post("/")
async def criar(dados: JuizCreate, db: AsyncIOMotorDatabase = Depends(get_db)):
    return await service.criar_juiz(db, dados)


@router.get("/")
async def listar(
    classe: Optional[str] = None,
    tipo_funcao: Optional[str] = None,
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    return await service.listar_juizes(db, classe, tipo_funcao)


@router.get("/{juiz_id}")
async def obter(juiz_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    return await service.obter_juiz(db, juiz_id)


@router.post("/validar-composicao")
async def validar_composicao(
    dados: ValidarComposicaoRequest,
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """
    Valida composição do júri: 1 Referee Class 1 + 4 ou 6 Judges.
    Sistema de 5 ou 7 juízes (Artigo 22 WT).
    """
    return await service.validar_composicao_juizes(db, dados.referee_id, dados.judge_ids)


@router.post("/verificar-conflito")
async def verificar_conflito(
    dados: ConflitosRequest,
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """
    Verifica conflito de nacionalidade entre juiz e atletas.
    Artigo 22.2: juiz não pode julgar atleta da mesma nação.
    """
    return await service.verificar_conflito_nacionalidade(db, dados.juiz_id, dados.atleta_ids)
