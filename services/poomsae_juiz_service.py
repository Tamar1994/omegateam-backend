"""
Serviço de Juízes de Poomsae (Conformidade WT)
"""
from datetime import datetime
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson.objectid import ObjectId
from fastapi import HTTPException
from models.poomsae_juiz import JuizCreate, ClasseJuiz, TipoFuncaoJuiz


def _serialize(doc: dict) -> dict:
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc


async def criar_juiz(db: AsyncIOMotorDatabase, dados: JuizCreate) -> dict:
    """Cria juiz com validações WT"""
    
    # Validar: Referee deve ser Class 1 - Artigo 20.3
    if dados.tipo_funcao == TipoFuncaoJuiz.REFEREE and dados.classe != ClasseJuiz.CLASS_1:
        raise HTTPException(
            status_code=400,
            detail="Referee (Árbitro Principal) deve ser Class 1 — Artigo 20.3 WT"
        )
    
    # Validar classe vs dan
    if dados.classe == ClasseJuiz.CLASS_1 and dados.numero_dan < 8:
        raise HTTPException(
            status_code=400,
            detail="Class 1 requer Dan 8 ou 9"
        )
    elif dados.classe == ClasseJuiz.CLASS_2 and dados.numero_dan < 6:
        raise HTTPException(
            status_code=400,
            detail="Class 2 requer Dan 6 ou 7"
        )
    elif dados.classe == ClasseJuiz.CLASS_3 and dados.numero_dan < 4:
        raise HTTPException(
            status_code=400,
            detail="Class 3 requer Dan 4 ou 5"
        )
    
    # Verificar email duplicado
    existente = await db.poomsae_juizes.find_one({"email": dados.email})
    if existente:
        raise HTTPException(status_code=409, detail="Juiz com este email já cadastrado")
    
    doc = dados.model_dump()
    doc["ativo"] = True
    doc["timestamp_criacao"] = datetime.utcnow()
    
    resultado = await db.poomsae_juizes.insert_one(doc)
    juiz = await db.poomsae_juizes.find_one({"_id": resultado.inserted_id})
    return _serialize(juiz)


async def listar_juizes(
    db: AsyncIOMotorDatabase,
    classe: Optional[str] = None,
    tipo_funcao: Optional[str] = None
) -> list:
    """Lista juízes com filtros"""
    
    filtro = {"ativo": True}
    if classe:
        filtro["classe"] = classe
    if tipo_funcao:
        filtro["tipo_funcao"] = tipo_funcao
    
    cursor = db.poomsae_juizes.find(filtro).sort("nome_completo", 1)
    juizes = await cursor.to_list(length=100)
    return [_serialize(j) for j in juizes]


async def obter_juiz(db: AsyncIOMotorDatabase, juiz_id: str) -> dict:
    """Obtém juiz por ID"""
    
    try:
        obj_id = ObjectId(juiz_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")
    
    juiz = await db.poomsae_juizes.find_one({"_id": obj_id})
    if not juiz:
        raise HTTPException(status_code=404, detail="Juiz não encontrado")
    
    return _serialize(juiz)


async def validar_composicao_juizes(
    db: AsyncIOMotorDatabase,
    referee_id: str,
    judge_ids: list
) -> dict:
    """
    Valida composição do júri.
    Sistema de 7 juízes: 1 Referee + 6 Judges (padrão WT)
    Sistema de 5 juízes: 1 Referee + 4 Judges
    Artigo 22
    """
    erros = []
    
    # Verificar total válido (5 ou 7)
    total = 1 + len(judge_ids)
    if total not in [5, 7]:
        erros.append(f"Total de {total} juízes inválido — deve ser 5 ou 7 (Artigo 22)")
    
    # Verificar Referee
    try:
        referee = await obter_juiz(db, referee_id)
        if referee["tipo_funcao"] != TipoFuncaoJuiz.REFEREE:
            erros.append(f"Juiz {referee['nome_completo']} não é Referee")
        if referee["classe"] != ClasseJuiz.CLASS_1:
            erros.append(f"Referee {referee['nome_completo']} deve ser Class 1")
    except HTTPException:
        erros.append(f"Referee ID '{referee_id}' não encontrado")
    
    # Verificar Judges
    for jid in judge_ids:
        try:
            juiz = await obter_juiz(db, jid)
        except HTTPException:
            erros.append(f"Judge ID '{jid}' não encontrado")
    
    # Verificar duplicados
    all_ids = [referee_id] + judge_ids
    if len(set(all_ids)) != len(all_ids):
        erros.append("Juiz duplicado na composição")
    
    return {
        "valido": len(erros) == 0,
        "erros": erros,
        "sistema_juizes": total,
        "referee_id": referee_id,
        "judge_ids": judge_ids
    }


async def verificar_conflito_nacionalidade(
    db: AsyncIOMotorDatabase,
    juiz_id: str,
    atleta_ids: list
) -> dict:
    """
    Verifica se juiz tem mesma nacionalidade de algum atleta.
    Artigo 22.2 - juiz não pode julgar atleta da mesma nação.
    """
    juiz = await obter_juiz(db, juiz_id)
    
    conflitos = []
    for atleta_id in atleta_ids:
        atleta = await db.poomsae_atletas.find_one({"_id": ObjectId(atleta_id)})
        if atleta and atleta.get("nacionalidade") == juiz["nacionalidade"]:
            conflitos.append({
                "atleta_id": atleta_id,
                "nome_atleta": atleta.get("nome_completo"),
                "nacionalidade": atleta.get("nacionalidade")
            })
    
    return {
        "juiz_id": juiz_id,
        "nome_juiz": juiz["nome_completo"],
        "tem_conflito": len(conflitos) > 0,
        "conflitos": conflitos
    }
