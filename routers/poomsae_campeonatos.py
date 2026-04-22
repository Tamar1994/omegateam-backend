"""
Router de Campeonatos de Poomsae
"""
from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional

from database.connection import get_db
from models.poomsae_campeonato import CampeonatoPoomsaeCreate, AtualizarCampeonatoPoomsae
import services.poomsae_campeonato_service as service

router = APIRouter(prefix="/api/poomsae/campeonatos", tags=["Poomsae - Campeonatos"])


@router.post("/")
async def criar(dados: CampeonatoPoomsaeCreate, db: AsyncIOMotorDatabase = Depends(get_db)):
    return await service.criar_campeonato_poomsae(db, dados)


@router.get("/")
async def listar(
    status: Optional[str] = None,
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    return await service.listar_campeonatos_poomsae(db, status)


@router.get("/{camp_id}")
async def obter(camp_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    return await service.obter_campeonato_poomsae(db, camp_id)


@router.put("/{camp_id}")
async def atualizar(
    camp_id: str,
    dados: AtualizarCampeonatoPoomsae,
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    return await service.atualizar_campeonato_poomsae(db, camp_id, dados)


@router.get("/{camp_id}/conformidade")
async def verificar_conformidade(camp_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Relatório de conformidade WT para o campeonato"""
    return await service.verificar_conformidade(db, camp_id)


@router.get("/{camp_id}/pode-iniciar")
async def pode_iniciar(camp_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Verifica se competição atende todos os requisitos para iniciar"""
    return await service.pode_iniciar_competicao(db, camp_id)
