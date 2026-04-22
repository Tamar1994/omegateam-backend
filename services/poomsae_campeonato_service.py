"""
Serviço de Campeonato de Poomsae (Conformidade WT)
"""
from datetime import datetime
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson.objectid import ObjectId
from fastapi import HTTPException
from models.poomsae_campeonato import (
    CampeonatoPoomsaeCreate, AtualizarCampeonatoPoomsae,
    RequisitosConformidade, StatusCampeonato
)


def _serialize(doc: dict) -> dict:
    """Converte ObjectId para string"""
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc


async def criar_campeonato_poomsae(db: AsyncIOMotorDatabase, dados: CampeonatoPoomsaeCreate) -> dict:
    """Cria novo campeonato de Poomsae com validações WT"""
    
    if dados.data_fim < dados.data_inicio:
        raise HTTPException(status_code=400, detail="Data fim deve ser após data início")
    
    doc = dados.model_dump()
    doc["status"] = StatusCampeonato.PLANNING
    doc["requisitos"] = RequisitosConformidade().model_dump()
    doc["formas_designadas"] = {}
    doc["timestamp_criacao"] = datetime.utcnow()
    doc["timestamp_atualizacao"] = datetime.utcnow()
    
    resultado = await db.poomsae_campeonatos.insert_one(doc)
    camp = await db.poomsae_campeonatos.find_one({"_id": resultado.inserted_id})
    return _serialize(camp)


async def listar_campeonatos_poomsae(db: AsyncIOMotorDatabase, status: Optional[str] = None) -> list:
    """Lista campeonatos de Poomsae com filtros opcionais"""
    
    filtro = {}
    if status:
        filtro["status"] = status
    
    cursor = db.poomsae_campeonatos.find(filtro).sort("timestamp_criacao", -1)
    camps = await cursor.to_list(length=100)
    return [_serialize(c) for c in camps]


async def obter_campeonato_poomsae(db: AsyncIOMotorDatabase, camp_id: str) -> dict:
    """Obtém campeonato por ID"""
    
    try:
        obj_id = ObjectId(camp_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")
    
    camp = await db.poomsae_campeonatos.find_one({"_id": obj_id})
    if not camp:
        raise HTTPException(status_code=404, detail="Campeonato não encontrado")
    
    return _serialize(camp)


async def atualizar_campeonato_poomsae(
    db: AsyncIOMotorDatabase,
    camp_id: str,
    dados: AtualizarCampeonatoPoomsae
) -> dict:
    """Atualiza campeonato (bloqueado após Drawing)"""
    
    camp = await obter_campeonato_poomsae(db, camp_id)
    
    # Bloquear edições críticas após drawing
    if camp["status"] in [StatusCampeonato.IN_PROGRESS, StatusCampeonato.COMPLETED]:
        campos_bloqueados = {"sistema_competicao", "tipo"}
        campos_enviados = {k for k, v in dados.model_dump(exclude_none=True).items()}
        if campos_bloqueados & campos_enviados:
            raise HTTPException(
                status_code=400,
                detail="Não é possível editar sistema/tipo após campeonato iniciar"
            )
    
    updates = dados.model_dump(exclude_none=True)
    updates["timestamp_atualizacao"] = datetime.utcnow()
    
    await db.poomsae_campeonatos.update_one(
        {"_id": ObjectId(camp_id)},
        {"$set": updates}
    )
    return await obter_campeonato_poomsae(db, camp_id)


async def verificar_conformidade(db: AsyncIOMotorDatabase, camp_id: str) -> dict:
    """
    Verifica se campeonato atende requisitos mínimos WT (Artigo 7)
    Retorna relatório de conformidade
    """
    camp = await obter_campeonato_poomsae(db, camp_id)
    obj_id = ObjectId(camp_id)
    
    relatorio = {
        "campeonato_id": camp_id,
        "nome": camp["nome"],
        "requisitos": {},
        "conforme": True,
        "pendencias": []
    }
    
    # 1. Mínimo 6 países
    paises_cursor = db.poomsae_inscricoes.distinct("pais_representado", {"campeonato_id": camp_id})
    paises = await paises_cursor
    min_6_paises = len(paises) >= 6
    relatorio["requisitos"]["min_6_paises"] = {
        "atinge": min_6_paises,
        "atual": len(paises),
        "minimo": 6
    }
    if not min_6_paises:
        relatorio["pendencias"].append(f"Apenas {len(paises)} países inscritos (mínimo: 6)")
    
    # 2. Mínimo 6 atletas/equipes por divisão
    pipeline = [
        {"$match": {"campeonato_id": camp_id}},
        {"$group": {"_id": "$divisao", "total": {"$sum": 1}}}
    ]
    divisoes = await db.poomsae_inscricoes.aggregate(pipeline).to_list(length=100)
    divisoes_abaixo = [d for d in divisoes if d["total"] < 6]
    min_atletas = len(divisoes_abaixo) == 0
    relatorio["requisitos"]["min_6_atletas_por_divisao"] = {
        "atinge": min_atletas,
        "divisoes_insuficientes": [d["_id"] for d in divisoes_abaixo]
    }
    if not min_atletas:
        relatorio["pendencias"].append(
            f"{len(divisoes_abaixo)} divisão(ões) com menos de 6 inscritos"
        )
    
    # 3. Technical Delegate designado
    td_designado = bool(camp.get("technical_delegate_email"))
    relatorio["requisitos"]["td_designado"] = {
        "atinge": td_designado,
        "td_email": camp.get("technical_delegate_email")
    }
    if not td_designado:
        relatorio["pendencias"].append("Technical Delegate não designado")
    
    # 4. Venue conforme (Artigo 3)
    venue = camp.get("venue_specs", {})
    venue_conforme = (
        venue.get("capacidade_minima_assentos", 0) >= 2000 and
        venue.get("piso_minimo_m2", 0) >= 1500 and
        venue.get("altura_minima_teto", 0) >= 10
    )
    relatorio["requisitos"]["venue_conforme"] = {
        "atinge": venue_conforme,
        "specs": venue
    }
    if not venue_conforme:
        relatorio["pendencias"].append("Venue não atende especificações mínimas WT")
    
    # 5. Juízes qualificados
    juizes_count = await db.poomsae_juizes_campeonato.count_documents({"campeonato_id": camp_id})
    juizes_qualificados = juizes_count >= 5  # mínimo 1 referee + 4 juízes
    relatorio["requisitos"]["juizes_qualificados"] = {
        "atinge": juizes_qualificados,
        "total_juizes": juizes_count,
        "minimo": 5
    }
    if not juizes_qualificados:
        relatorio["pendencias"].append(f"Apenas {juizes_count} juízes (mínimo: 5)")
    
    # Resultado geral
    relatorio["conforme"] = len(relatorio["pendencias"]) == 0
    
    # Atualizar requisitos no banco
    await db.poomsae_campeonatos.update_one(
        {"_id": obj_id},
        {"$set": {
            "requisitos.min_6_paises": min_6_paises,
            "requisitos.min_6_atletas_por_divisao": min_atletas,
            "requisitos.td_designado": td_designado,
            "requisitos.venue_conforme": venue_conforme,
            "requisitos.juizes_qualificados": juizes_qualificados,
        }}
    )
    
    return relatorio


async def pode_iniciar_competicao(db: AsyncIOMotorDatabase, camp_id: str) -> dict:
    """Verifica se competição pode começar"""
    relatorio = await verificar_conformidade(db, camp_id)
    return {
        "pode_iniciar": relatorio["conforme"],
        "pendencias": relatorio["pendencias"],
        "relatorio_completo": relatorio
    }
