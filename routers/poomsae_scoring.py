"""
Router de Matches e Scoring de Poomsae
"""
from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional
from pydantic import BaseModel

from database.connection import get_db
from models.poomsae_score import MatchCreate, ScoreJuiz, Deducoes
import services.poomsae_scoring_service as service

router = APIRouter(prefix="/api/poomsae", tags=["Poomsae - Scoring"])


class DesempateRequest(BaseModel):
    match_id_1: str
    match_id_2: str
    tipo_competicao: str = "Recognized"


# ── Matches ──────────────────────────────────

@router.post("/matches")
async def criar_match(dados: MatchCreate, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Cria um match (pode ser criado em batch pelo Drawing of Lots)"""
    return await service.criar_match(db, dados)


@router.get("/matches")
async def listar_matches(
    campeonato_id: Optional[str] = None,
    luta_id: Optional[str] = None,
    atleta_id: Optional[str] = None,
    divisao: Optional[str] = None,
    rodada: Optional[int] = None,
    status: Optional[str] = None,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    return await service.listar_matches(db, campeonato_id, luta_id, atleta_id, divisao, rodada, status)


@router.get("/matches/{match_id}")
async def obter_match(match_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    return await service.obter_match(db, match_id)


@router.post("/matches/{match_id}/iniciar")
async def iniciar_match(match_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Marca o match como em andamento"""
    return await service.iniciar_match(db, match_id)


# ── Scores ───────────────────────────────────

@router.post("/matches/{match_id}/scores")
async def submeter_score(
    match_id: str,
    dados: ScoreJuiz,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Juiz submete seu score para o match.
    Se todos os juízes submeteram, calcula automaticamente a pontuação.
    """
    dados.match_id = match_id
    return await service.submeter_score(db, dados)


@router.get("/matches/{match_id}/scores")
async def listar_scores(match_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Lista scores recebidos e pendentes para o match"""
    return await service.listar_scores_match(db, match_id)


@router.post("/matches/{match_id}/timer-iniciado")
async def marcar_timer_iniciado(match_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Registra o momento exato em que o mesário iniciou o cronômetro (usado pelo Scoreboard)"""
    return await service.marcar_timer_iniciado(db, match_id)


# ── Cálculo ──────────────────────────────────

@router.post("/matches/{match_id}/calcular")
async def calcular_pontuacao(match_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """
    Calcula pontuação final conforme Artigo 13 WT:
    - Remove MAIOR e MENOR score de cada componente
    - Calcula média dos restantes
    - Aplica deduções
    """
    return await service.calcular_pontuacao_final(db, match_id)


# ── Deduções ─────────────────────────────────

@router.post("/matches/{match_id}/deducoes")
async def aplicar_deducoes(
    match_id: str,
    deducoes: Deducoes,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Aplica deduções ao match (Artigo 11):
    - Saiu da zona: -0.3
    - Fora do tempo: -0.3
    - 2 Kyeong-go: DQ automático
    """
    return await service.aplicar_deducoes(db, match_id, deducoes)


# ── Desempate ─────────────────────────────────

@router.post("/desempate/resolver")
async def resolver_desempate(
    dados: DesempateRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Resolve desempate entre dois matches (Artigo 13.4):
    1. Recognized → maior apresentação
    2. Freestyle  → maior habilidade técnica
    3. Mixed      → maior score freestyle
    4. Maior soma total (incl. max/min)
    5. REMATCH
    """
    return await service.resolver_desempate(db, dados.match_id_1, dados.match_id_2, dados.tipo_competicao)


@router.post("/desempate/rematch")
async def criar_rematch(
    dados: DesempateRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Cria novos matches de rematch quando todos os critérios de desempate foram esgotados"""
    return await service.criar_rematch(db, dados.match_id_1, dados.match_id_2)
