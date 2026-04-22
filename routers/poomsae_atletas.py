"""
Router de Atletas de Poomsae
"""
from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional

from database.connection import get_db
from models.poomsae_atleta import AtletaCreate, AtualizarAtleta
import services.poomsae_atleta_service as service

router = APIRouter(prefix="/api/poomsae/atletas", tags=["Poomsae - Atletas"])


@router.post("/")
async def criar(dados: AtletaCreate, db: AsyncIOMotorDatabase = Depends(get_db)):
    return await service.criar_atleta(db, dados)


@router.get("/")
async def listar(
    nacionalidade: Optional[str] = None,
    divisao: Optional[str] = None,
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    return await service.listar_atletas(db, nacionalidade, divisao)


@router.get("/{atleta_id}")
async def obter(atleta_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    return await service.obter_atleta(db, atleta_id)


@router.put("/{atleta_id}")
async def atualizar(
    atleta_id: str,
    dados: AtualizarAtleta,
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    return await service.atualizar_atleta(db, atleta_id, dados)


@router.get("/{atleta_id}/divisao")
async def calcular_divisao(
    atleta_id: str,
    ano_competicao: int,
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Recalcula divisão etária do atleta para um ano específico (lógica por ANO — Artigo 4.1 WT)"""
    return await service.recalcular_divisao(db, atleta_id, ano_competicao)
