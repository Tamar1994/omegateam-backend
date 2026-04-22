"""
Serviço de Atletas de Poomsae (Conformidade WT)
"""
from datetime import date, datetime
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson.objectid import ObjectId
from fastapi import HTTPException
from models.poomsae_atleta import AtletaCreate, AtualizarAtleta, DivisaoEtaria


FORMAS_DISPONIVEIS_POR_DIVISAO = {
    # Artigo 8 - Designated Compulsory Poomsae
    "Cadet":    ["Taegeuk 4 Jang", "Taegeuk 5 Jang", "Taegeuk 6 Jang",
                 "Taegeuk 7 Jang", "Taegeuk 8 Jang", "Koryo", "Keumgang"],
    "Junior":   ["Taegeuk 4 Jang", "Taegeuk 5 Jang", "Taegeuk 6 Jang",
                 "Taegeuk 7 Jang", "Taegeuk 8 Jang", "Koryo", "Keumgang", "Taeback"],
    "Under 30": ["Taegeuk 6 Jang", "Taegeuk 7 Jang", "Taegeuk 8 Jang",
                 "Koryo", "Keumgang", "Taeback", "Pyongwon", "Shipjin"],
    "Under 40": ["Taegeuk 6 Jang", "Taegeuk 7 Jang", "Taegeuk 8 Jang",
                 "Koryo", "Keumgang", "Taeback", "Pyongwon", "Shipjin"],
    "Under 50": ["Taegeuk 8 Jang", "Koryo", "Keumgang", "Taeback",
                 "Pyongwon", "Shipjin", "Jitae", "Chonkwon"],
    "Under 60": ["Koryo", "Keumgang", "Taeback", "Pyongwon",
                 "Shipjin", "Jitae", "Chonkwon", "Hansu"],
    "Under 65": ["Koryo", "Keumgang", "Taeback", "Pyongwon",
                 "Shipjin", "Jitae", "Chonkwon", "Hansu"],
    "Over 65":  ["Koryo", "Keumgang", "Taeback", "Pyongwon",
                 "Shipjin", "Jitae", "Chonkwon", "Hansu"],
}


def calcular_divisao_etaria(data_nascimento: date, ano_competicao: int) -> DivisaoEtaria:
    """
    Calcula divisão etária baseado no ANO (não data exata).
    Artigo 4.1: A idade é baseada no ANO da competição.
    
    Exemplo: Se competição em 2026:
      - Cadet: nascido 2012-2013 (faz 12-14 em 2026)
      - Junior: nascido 2009-2011 (faz 15-17 em 2026)
    """
    idade = ano_competicao - data_nascimento.year

    if 12 <= idade <= 14:
        return DivisaoEtaria.CADET
    elif 15 <= idade <= 17:
        return DivisaoEtaria.JUNIOR
    elif 18 <= idade <= 30:
        return DivisaoEtaria.UNDER_30
    elif 31 <= idade <= 40:
        return DivisaoEtaria.UNDER_40
    elif 41 <= idade <= 50:
        return DivisaoEtaria.UNDER_50
    elif 51 <= idade <= 60:
        return DivisaoEtaria.UNDER_60
    elif 61 <= idade <= 65:
        return DivisaoEtaria.UNDER_65
    else:
        return DivisaoEtaria.OVER_65


def obter_formas_para_divisao(nome_divisao: str) -> list:
    """Retorna formas obrigatórias disponíveis para a divisão (Artigo 8)"""
    
    for key, formas in FORMAS_DISPONIVEIS_POR_DIVISAO.items():
        if key.lower() in nome_divisao.lower():
            return formas
    return []


def _serialize(doc: dict) -> dict:
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc


async def criar_atleta(db: AsyncIOMotorDatabase, dados: AtletaCreate) -> dict:
    """Cria novo atleta com divisão calculada automaticamente"""
    
    ano_atual = datetime.utcnow().year
    divisao = calcular_divisao_etaria(dados.data_nascimento, ano_atual)
    
    doc = dados.model_dump()
    doc["divisao_etaria"] = divisao
    doc["categoria_atual_ano"] = ano_atual
    doc["num_competicoes"] = 0
    doc["timestamp_criacao"] = datetime.utcnow()
    
    resultado = await db.poomsae_atletas.insert_one(doc)
    atleta = await db.poomsae_atletas.find_one({"_id": resultado.inserted_id})
    return _serialize(atleta)


async def listar_atletas(
    db: AsyncIOMotorDatabase,
    nacionalidade: Optional[str] = None,
    divisao: Optional[str] = None
) -> list:
    """Lista atletas com filtros"""
    
    filtro = {}
    if nacionalidade:
        filtro["nacionalidade"] = {"$regex": nacionalidade, "$options": "i"}
    if divisao:
        filtro["divisao_etaria"] = {"$regex": divisao, "$options": "i"}
    
    cursor = db.poomsae_atletas.find(filtro).sort("nome_completo", 1)
    atletas = await cursor.to_list(length=500)
    return [_serialize(a) for a in atletas]


async def obter_atleta(db: AsyncIOMotorDatabase, atleta_id: str) -> dict:
    """Obtém atleta por ID"""
    
    try:
        obj_id = ObjectId(atleta_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")
    
    atleta = await db.poomsae_atletas.find_one({"_id": obj_id})
    if not atleta:
        raise HTTPException(status_code=404, detail="Atleta não encontrado")
    
    return _serialize(atleta)


async def buscar_atleta_por_email(db: AsyncIOMotorDatabase, email: str) -> Optional[dict]:
    """Busca atleta por email"""
    atleta = await db.poomsae_atletas.find_one({"email": email.lower()})
    return _serialize(atleta) if atleta else None


async def atualizar_atleta(
    db: AsyncIOMotorDatabase,
    atleta_id: str,
    dados: AtualizarAtleta
) -> dict:
    """Atualiza atleta"""
    await obter_atleta(db, atleta_id)
    
    updates = dados.model_dump(exclude_none=True)
    await db.poomsae_atletas.update_one(
        {"_id": ObjectId(atleta_id)},
        {"$set": updates}
    )
    return await obter_atleta(db, atleta_id)


async def recalcular_divisao(db: AsyncIOMotorDatabase, atleta_id: str, ano_competicao: int) -> dict:
    """Recalcula divisão de atleta para um campeonato específico"""
    
    atleta = await obter_atleta(db, atleta_id)
    data_nasc = date.fromisoformat(str(atleta["data_nascimento"]))
    nova_divisao = calcular_divisao_etaria(data_nasc, ano_competicao)
    
    return {
        "atleta_id": atleta_id,
        "nome": atleta["nome_completo"],
        "data_nascimento": str(atleta["data_nascimento"]),
        "ano_competicao": ano_competicao,
        "divisao_calculada": nova_divisao,
        "formas_disponiveis": obter_formas_para_divisao(nova_divisao)
    }
