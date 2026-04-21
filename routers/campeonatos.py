"""
Rotas de Campeonatos (CRUD)
"""
from fastapi import APIRouter, HTTPException, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime
from bson.objectid import ObjectId
from models.campeonato import CampeonatoData, AtualizarCategoriasData
from database.connection import get_db
from services.email_service import enviar_notificacao_torneio_encerrado

router = APIRouter(prefix="/api", tags=["Campeonatos"])


@router.post("/campeonatos")
async def criar_campeonato(dados: CampeonatoData, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Cria um novo campeonato"""
    novo_campeonato = dados.dict()
    novo_campeonato["data_criacao"] = datetime.utcnow().isoformat()
    
    resultado = await db.campeonatos.insert_one(novo_campeonato)
    novo_campeonato["_id"] = str(resultado.inserted_id)
    
    return {"mensagem": "Campeonato criado com sucesso!", "campeonato": novo_campeonato}


@router.get("/campeonatos")
async def listar_campeonatos(db: AsyncIOMotorDatabase = Depends(get_db)):
    """Lista todos os campeonatos"""
    campeonatos_cursor = db.campeonatos.find().sort("data_criacao", -1)
    campeonatos = await campeonatos_cursor.to_list(length=100)
    for camp in campeonatos:
        camp["_id"] = str(camp["_id"])
    return campeonatos


@router.get("/campeonatos/{camp_id}")
async def obter_campeonato(camp_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Obtém os detalhes de um campeonato"""
    camp = await db.campeonatos.find_one({"_id": ObjectId(camp_id)})
    if not camp:
        raise HTTPException(status_code=404, detail="Campeonato não encontrado")
    camp["_id"] = str(camp["_id"])
    return camp


@router.put("/campeonatos/{camp_id}/categorias")
async def atualizar_categorias(camp_id: str, dados: AtualizarCategoriasData, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Atualiza as categorias de um campeonato"""
    resultado = await db.campeonatos.update_one(
        {"_id": ObjectId(camp_id)},
        {"$set": {"categorias": [c.dict() for c in dados.categorias]}}
    )
    
    if resultado.matched_count == 0:
        raise HTTPException(status_code=404, detail="Campeonato não encontrado.")
        
    return {"mensagem": "Categorias atualizadas com sucesso!"}


# ✅ PHASE 2: TOURNAMENT FINISH WITH NOTIFICATIONS

@router.post("/campeonatos/{camp_id}/encerrar")
async def encerrar_torneio(camp_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """
    Encerra o torneio e envia notificações a todos os atletas com suas medalhas.
    
    Procedimento:
    1. Marcar campeonato como "Encerrado"
    2. Para cada atleta, buscar resultados finais
    3. Enviar email com medalha conquistada
    """
    try:
        # Buscar campeonato
        campeonato = await db.campeonatos.find_one({"_id": ObjectId(camp_id)})
        if not campeonato:
            raise HTTPException(status_code=404, detail="Campeonato não encontrado")
        
        # Buscar todos os atletas que participaram (via resultados)
        atletas_unicos = await db.resultados.distinct(
            "atleta_email",
            {"campeonato_id": camp_id}
        )
        
        if not atletas_unicos:
            # Se não há resultados, buscar de inscricoes
            atletas_unicos = await db.inscricoes.distinct(
                "email",
                {"campeonato_id": camp_id}
            )
        
        # Atualizar status do campeonato
        await db.campeonatos.update_one(
            {"_id": ObjectId(camp_id)},
            {"$set": {
                "status": "Encerrado",
                "data_encerramento": datetime.utcnow().isoformat()
            }}
        )
        
        # Contador de notificações enviadas
        notificacoes_enviadas = 0
        erros_email = []
        
        # Enviar notificações para cada atleta
        for atleta_email in atletas_unicos:
            try:
                # Buscar melhor resultado do atleta
                resultado_atleta = await db.resultados.find_one(
                    {
                        "campeonato_id": camp_id,
                        "atleta_email": atleta_email,
                        "venceu": True
                    },
                    sort=[("medalha", -1)]  # Priorizar medallhas: ouro > prata > bronze > participacao
                )
                
                # Se não tem vitória, buscar qualquer resultado
                if not resultado_atleta:
                    resultado_atleta = await db.resultados.find_one(
                        {
                            "campeonato_id": camp_id,
                            "atleta_email": atleta_email
                        }
                    )
                
                medalha = resultado_atleta.get("medalha", "participacao") if resultado_atleta else "participacao"
                atleta_nome = resultado_atleta.get("atleta_nome", "Atleta") if resultado_atleta else "Atleta"
                
                # Enviar email
                await enviar_notificacao_torneio_encerrado(
                    atleta_email=atleta_email,
                    atleta_nome=atleta_nome,
                    campeonato_nome=campeonato.get("nome", "Campeonato"),
                    medalha=medalha
                )
                notificacoes_enviadas += 1
                print(f"✅ Email enviado para {atleta_email} - Medalha: {medalha}")
                
            except Exception as e:
                erro_msg = f"Erro ao notificar {atleta_email}: {str(e)}"
                print(f"❌ {erro_msg}")
                erros_email.append(erro_msg)
        
        # Retornar resultado
        resultado = {
            "mensagem": "Torneio encerrado com sucesso",
            "campeonato_id": camp_id,
            "status": "Encerrado",
            "notificacoes_enviadas": notificacoes_enviadas,
            "total_atletas": len(atletas_unicos),
            "erros": erros_email if erros_email else None
        }
        
        return resultado
        
    except ObjectId as e:
        raise HTTPException(status_code=400, detail="ID do campeonato inválido")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao encerrar torneio: {str(e)}")
