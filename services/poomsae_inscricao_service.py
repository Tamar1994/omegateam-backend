"""
Serviço de Inscrições de Poomsae (Conformidade WT)
"""
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson.objectid import ObjectId
from fastapi import HTTPException
from models.poomsae_inscricao import InscricaoCreate, AtualizarInscricao, TipoInscricao, StatusInscricao


MAX_CATEGORIAS_POR_ATLETA = 2  # Artigo 5.2

# Composição de grupos - Artigo 5.3
COMPOSICAO_DUPLA = {"min": 2, "max": 2}
COMPOSICAO_EQUIPE = {"min": 3, "max": 5}


def _serialize(doc: dict) -> dict:
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc


async def contar_categorias_atleta(db: AsyncIOMotorDatabase, atleta_id: str, campeonato_id: str) -> int:
    """Conta quantas categorias o atleta já está inscrito no campeonato"""
    return await db.poomsae_inscricoes.count_documents({
        "campeonato_id": campeonato_id,
        "atletas_ids": atleta_id,
        "status": {"$nin": [StatusInscricao.DESQUALIFICADO]}
    })


async def validar_max_2_categorias(
    db: AsyncIOMotorDatabase,
    atleta_ids: list,
    campeonato_id: str
) -> None:
    """Verifica que nenhum atleta excede 2 categorias - Artigo 5.2"""
    
    for atleta_id in atleta_ids:
        total = await contar_categorias_atleta(db, atleta_id, campeonato_id)
        if total >= MAX_CATEGORIAS_POR_ATLETA:
            raise HTTPException(
                status_code=400,
                detail=f"Atleta {atleta_id} já está inscrito em {total} categorias (máximo: {MAX_CATEGORIAS_POR_ATLETA} — Artigo 5.2 WT)"
            )


async def validar_composicao_grupo(
    tipo: TipoInscricao,
    atleta_ids: list,
    db: AsyncIOMotorDatabase
) -> None:
    """Valida número e condições dos membros do grupo - Artigo 5.3"""
    
    if tipo == TipoInscricao.INDIVIDUAL:
        if len(atleta_ids) != 1:
            raise HTTPException(status_code=400, detail="Individual deve ter exatamente 1 atleta")
    
    elif tipo == TipoInscricao.DUPLA:
        if len(atleta_ids) != COMPOSICAO_DUPLA["min"]:
            raise HTTPException(
                status_code=400,
                detail=f"Dupla deve ter exatamente {COMPOSICAO_DUPLA['min']} atletas"
            )
    
    elif tipo == TipoInscricao.EQUIPE:
        if not (COMPOSICAO_EQUIPE["min"] <= len(atleta_ids) <= COMPOSICAO_EQUIPE["max"]):
            raise HTTPException(
                status_code=400,
                detail=f"Equipe deve ter entre {COMPOSICAO_EQUIPE['min']} e {COMPOSICAO_EQUIPE['max']} atletas"
            )
    
    # Verificar duplicados na lista
    if len(set(atleta_ids)) != len(atleta_ids):
        raise HTTPException(status_code=400, detail="Atleta duplicado na composição do grupo")


async def criar_inscricao(db: AsyncIOMotorDatabase, dados: InscricaoCreate) -> dict:
    """Cria inscrição com todas as validações WT"""
    
    # Validar campeonato existe
    camp = await db.poomsae_campeonatos.find_one({"_id": ObjectId(dados.campeonato_id)})
    if not camp:
        raise HTTPException(status_code=404, detail="Campeonato não encontrado")
    
    # Validar status do campeonato (só pode inscrever em REGISTRATION)
    if camp.get("status") not in ["Planning", "Registration"]:
        raise HTTPException(
            status_code=400,
            detail=f"Campeonato com status '{camp.get('status')}' não aceita inscrições"
        )
    
    # Validar atletas existem
    for atleta_id in dados.atletas_ids:
        atleta = await db.poomsae_atletas.find_one({"_id": ObjectId(atleta_id)})
        if not atleta:
            raise HTTPException(status_code=404, detail=f"Atleta {atleta_id} não encontrado")
    
    # Validar composição do grupo
    await validar_composicao_grupo(dados.tipo_inscricao, dados.atletas_ids, db)
    
    # Validar max 2 categorias - Artigo 5.2
    await validar_max_2_categorias(db, dados.atletas_ids, dados.campeonato_id)
    
    # Verificar inscrição duplicada
    duplicada = await db.poomsae_inscricoes.find_one({
        "campeonato_id": dados.campeonato_id,
        "atletas_ids": {"$all": dados.atletas_ids, "$size": len(dados.atletas_ids)},
        "categoria": dados.categoria
    })
    if duplicada:
        raise HTTPException(
            status_code=409,
            detail="Já existe inscrição para estes atletas nesta categoria"
        )
    
    doc = dados.model_dump()
    doc["status"] = StatusInscricao.PENDENTE
    doc["numero_chamadas"] = 0
    doc["presente"] = False
    doc["uniforme_aprovado"] = None
    doc["timestamp_inscricao"] = datetime.utcnow()
    
    resultado = await db.poomsae_inscricoes.insert_one(doc)
    inscricao = await db.poomsae_inscricoes.find_one({"_id": resultado.inserted_id})
    return _serialize(inscricao)


async def listar_inscricoes(
    db: AsyncIOMotorDatabase,
    campeonato_id: str,
    categoria: str = None,
    status: str = None
) -> list:
    """Lista inscrições com filtros"""
    
    filtro = {"campeonato_id": campeonato_id}
    if categoria:
        filtro["categoria"] = {"$regex": categoria, "$options": "i"}
    if status:
        filtro["status"] = status
    
    cursor = db.poomsae_inscricoes.find(filtro).sort("timestamp_inscricao", -1)
    inscricoes = await cursor.to_list(length=500)
    return [_serialize(i) for i in inscricoes]


async def obter_inscricao(db: AsyncIOMotorDatabase, inscricao_id: str) -> dict:
    """Obtém inscrição por ID"""
    
    try:
        obj_id = ObjectId(inscricao_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")
    
    inscricao = await db.poomsae_inscricoes.find_one({"_id": obj_id})
    if not inscricao:
        raise HTTPException(status_code=404, detail="Inscrição não encontrada")
    
    return _serialize(inscricao)


async def registrar_chamada(db: AsyncIOMotorDatabase, inscricao_id: str) -> dict:
    """
    Registra chamada para inscrição.
    3 chamadas sem resposta = não comparecimento (Artigo 9)
    """
    inscricao = await obter_inscricao(db, inscricao_id)
    
    novas_chamadas = inscricao.get("numero_chamadas", 0) + 1
    updates = {"numero_chamadas": novas_chamadas}
    
    if novas_chamadas >= 3:
        updates["status"] = StatusInscricao.NAO_COMPARECEU
        updates["presente"] = False
    
    await db.poomsae_inscricoes.update_one(
        {"_id": ObjectId(inscricao_id)},
        {"$set": updates}
    )
    return await obter_inscricao(db, inscricao_id)


async def confirmar_presenca(db: AsyncIOMotorDatabase, inscricao_id: str) -> dict:
    """Confirma presença do atleta"""
    await obter_inscricao(db, inscricao_id)
    
    await db.poomsae_inscricoes.update_one(
        {"_id": ObjectId(inscricao_id)},
        {"$set": {"presente": True, "status": StatusInscricao.CONFIRMADO}}
    )
    return await obter_inscricao(db, inscricao_id)


async def atualizar_inscricao(
    db: AsyncIOMotorDatabase,
    inscricao_id: str,
    dados: AtualizarInscricao
) -> dict:
    """Atualiza inscrição"""
    await obter_inscricao(db, inscricao_id)
    
    updates = dados.model_dump(exclude_none=True)
    await db.poomsae_inscricoes.update_one(
        {"_id": ObjectId(inscricao_id)},
        {"$set": updates}
    )
    return await obter_inscricao(db, inscricao_id)
