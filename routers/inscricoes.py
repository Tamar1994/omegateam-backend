"""
Rotas de Inscrições
"""
from fastapi import APIRouter, HTTPException, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime
from bson.objectid import ObjectId
from models.inscricao import InscricaoData, AtualizarStatusInscricao
from database.connection import get_db

router = APIRouter(prefix="/api", tags=["Inscrições"])


@router.post("/inscricoes")
async def realizar_inscricao(dados: InscricaoData, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Realiza uma inscrição em um campeonato"""
    nova_inscricao = dados.dict()
    nova_inscricao["data_inscricao"] = datetime.utcnow().isoformat()
    nova_inscricao["status_pagamento"] = "Pendente"
    
    # Verifica se já está inscrito nessa modalidade neste evento
    existe = await db.inscricoes.find_one({
        "campeonato_id": dados.campeonato_id, 
        "atleta_email": dados.atleta_email,
        "modalidade": dados.modalidade
    })
    
    if existe:
        raise HTTPException(status_code=400, detail="Você já está inscrito nesta modalidade.")

    resultado = await db.inscricoes.insert_one(nova_inscricao)
    return {"mensagem": "Inscrição realizada com sucesso!", "inscricao_id": str(resultado.inserted_id)}


@router.get("/campeonatos/{camp_id}/inscricoes")
async def listar_inscricoes_campeonato(camp_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Lista todas as inscrições de um campeonato"""
    # Busca todas as inscrições daquele evento
    inscricoes_cursor = db.inscricoes.find({"campeonato_id": camp_id})
    inscricoes = await inscricoes_cursor.to_list(length=1000)
    
    # Busca os dados dos usuários para pegar Nome e Sobrenome
    emails = [i["atleta_email"] for i in inscricoes]
    usuarios_cursor = db.users.find({"email": {"$in": emails}})
    usuarios = await usuarios_cursor.to_list(length=1000)
    
    # Cria um dicionário para cruzar os dados
    mapa_usuarios = {u["email"]: f"{u.get('nome', '')} {u.get('sobrenome', '')}" for u in usuarios}
    
    # Monta a lista final com o nome do atleta incluído
    for insc in inscricoes:
        insc["_id"] = str(insc["_id"])
        insc["atleta_nome"] = mapa_usuarios.get(insc["atleta_email"], "Atleta Desconhecido")
        
    return inscricoes


@router.put("/inscricoes/{inscricao_id}/status")
async def atualizar_status_inscricao(inscricao_id: str, dados: AtualizarStatusInscricao, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Atualiza o status de pagamento de uma inscrição"""
    resultado = await db.inscricoes.update_one(
        {"_id": ObjectId(inscricao_id)},
        {"$set": {"status_pagamento": dados.status_pagamento}}
    )
    
    if resultado.matched_count == 0:
        raise HTTPException(status_code=404, detail="Inscrição não encontrada.")
        
    return {"mensagem": "Status atualizado com sucesso!"}
