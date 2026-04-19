"""
Rotas de Quadras (Gestão de equipes e status)
"""
from fastapi import APIRouter, HTTPException, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson.objectid import ObjectId
from models.campeonato import EquipeQuadraData
from models.luta import LateralReadyData
from database.connection import get_db

router = APIRouter(prefix="/api", tags=["Quadras"])


@router.get("/campeonatos/{camp_id}/quadras")
async def listar_equipes_quadras(camp_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Lista todas as equipes das quadras de um campeonato"""
    cursor = db.quadras.find({"campeonato_id": camp_id})
    quadras = await cursor.to_list(length=20)
    for q in quadras:
        q["_id"] = str(q["_id"])
    return quadras


@router.post("/campeonatos/{camp_id}/quadras")
async def salvar_equipe_quadra(camp_id: str, dados: EquipeQuadraData, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Salva a equipe de uma quadra (Mesário, Central e Laterais)"""
    # Atualiza a quadra se existir, ou cria uma nova
    await db.quadras.update_one(
        {"campeonato_id": camp_id, "numero_quadra": dados.numero_quadra},
        {"$set": {
            "campeonato_id": camp_id,
            "numero_quadra": dados.numero_quadra,
            "mesario_email": dados.mesario_email,
            "central_email": dados.central_email,
            "lateral1_email": dados.lateral1_email,
            "lateral2_email": dados.lateral2_email,
            "lateral3_email": dados.lateral3_email,
            "lateral4_email": dados.lateral4_email,
            "lateral5_email": dados.lateral5_email
        }},
        upsert=True
    )
    return {"mensagem": f"Equipe da Quadra {dados.numero_quadra} salva com sucesso!"}


@router.put("/campeonatos/{camp_id}/quadras/{num_quadra}/ready")
async def atualizar_ready_lateral(camp_id: str, num_quadra: int, dados: LateralReadyData):
    """Atualiza o status de prontidão de um lateral (para o joystick)"""
    resultado = await db.quadras.update_one(
        {"campeonato_id": camp_id, "numero_quadra": num_quadra},
        {"$set": {f"{dados.lateral_slot}_ready": dados.is_ready}}
    )
    
    if resultado.matched_count == 0:
        raise HTTPException(status_code=404, detail="Quadra não encontrada.")
    
    return {"mensagem": "Status de prontidão atualizado!"}
