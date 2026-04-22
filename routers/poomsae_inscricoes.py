"""
Router de Inscrições de Poomsae
"""
from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional

from database.connection import get_db
from models.poomsae_inscricao import InscricaoCreate, AtualizarInscricao
import services.poomsae_inscricao_service as service

router = APIRouter(prefix="/api/poomsae/inscricoes", tags=["Poomsae - Inscrições"])


@router.post("/")
async def criar(dados: InscricaoCreate, db: AsyncIOMotorDatabase = Depends(get_db)):
    return await service.criar_inscricao(db, dados)


@router.get("/campeonato/{camp_id}")
async def listar(
    camp_id: str,
    categoria: Optional[str] = None,
    status: Optional[str] = None,
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    return await service.listar_inscricoes(db, camp_id, categoria, status)


@router.get("/{inscricao_id}")
async def obter(inscricao_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    return await service.obter_inscricao(db, inscricao_id)


@router.put("/{inscricao_id}")
async def atualizar(
    inscricao_id: str,
    dados: AtualizarInscricao,
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    return await service.atualizar_inscricao(db, inscricao_id, dados)


@router.post("/{inscricao_id}/chamada")
async def registrar_chamada(inscricao_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Registra chamada — após 3 chamadas sem resposta, marca como não compareceu (Artigo 9 WT)"""
    return await service.registrar_chamada(db, inscricao_id)


@router.post("/{inscricao_id}/confirmar-presenca")
async def confirmar_presenca(inscricao_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Confirma presença do atleta na competição"""
    return await service.confirmar_presenca(db, inscricao_id)
