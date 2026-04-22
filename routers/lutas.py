"""
Rotas de Lutas (Geração de Chaves, Cronograma, Lutas)
"""
import math
import random
from fastapi import APIRouter, HTTPException, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime, timedelta
from bson.objectid import ObjectId
from models.luta import GerarChavesData, FinalizarLutaData, LateralReadyData
from models.campeonato import ConfigCronograma
from config.settings import POOMSAES_WT
from database.connection import get_db
from routers.joystick import manager  # Import para notificar Live

router = APIRouter(prefix="/api", tags=["Lutas"])


@router.post("/campeonatos/{camp_id}/gerar-chaves")
async def gerar_chaves(camp_id: str, dados: GerarChavesData, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Gera as chaves e fila de lutas para uma modalidade"""
    # Limpa chaves anteriores
    await db.lutas.delete_many({"campeonato_id": camp_id, "modalidade": dados.modalidade})

    campeonato = await db.campeonatos.find_one({"_id": ObjectId(camp_id)})
    nivel_camp = campeonato.get("nivel", "Estadual") if campeonato else "Estadual"

    # Busca inscrições pagas ORDENADAS por data
    inscricoes_cursor = db.inscricoes.find({
        "campeonato_id": camp_id,
        "modalidade": dados.modalidade,
        "status_pagamento": "Confirmado"
    }).sort("data_inscricao", 1)
    
    inscricoes = await inscricoes_cursor.to_list(length=2000)

    if not inscricoes:
        raise HTTPException(status_code=400, detail=f"Nenhum atleta confirmado em {dados.modalidade}.")

    emails = [i["atleta_email"] for i in inscricoes]
    usuarios_cursor = db.users.find({"email": {"$in": emails}})
    
    mapa_usuarios = {}
    for u in await usuarios_cursor.to_list(length=2000):
        nome_base = f"{u.get('nome', '')} {u.get('sobrenome', '')}"
        complemento = ""
        
        if nivel_camp == "Estadual":
            complemento = u.get("equipe", "")
        elif nivel_camp == "Nacional":
            complemento = u.get("estado", "")
        elif nivel_camp == "Internacional":
            complemento = u.get("pais", "")
            
        mapa_usuarios[u["email"]] = f"{nome_base} ({complemento})" if complemento else nome_base

    categorias_dict = {}
    for insc in inscricoes:
        cat_id = insc["categoria_id"]
        if cat_id not in categorias_dict:
            categorias_dict[cat_id] = []
        
        atleta_nome = mapa_usuarios.get(insc["atleta_email"], "Atleta Desconhecido")
        categorias_dict[cat_id].append({
            "inscricao_id": str(insc["_id"]), 
            "email": insc["atleta_email"],  # ← ADD: Store athlete email
            "nome": atleta_nome,
            "data": insc.get("data_inscricao", "")
        })

    lutas_geradas = []
    ordem_geral = 1

    for cat_id, atletas in categorias_dict.items():
        atletas.sort(key=lambda x: x["data"])

        if dados.modalidade == "Kyorugui":
            N = len(atletas)
            
            # Caso raro: Apenas 1 atleta (Ouro direto)
            if N == 1:
                luta = {
                    "campeonato_id": camp_id, "categoria_id": cat_id, "modalidade": "Kyorugui",
                    "ordem_luta": ordem_geral, "atleta_vermelho": atletas[0]["nome"],
                    "atleta_azul": "Sem Oponente (Ouro)", "status": "Encerrado"
                }
                lutas_geradas.append(luta)
                ordem_geral += 1
                continue
            
            # Matemática: próxima potência de 2
            next_power_of_2 = 2 ** math.ceil(math.log2(N))
            num_byes = next_power_of_2 - N
            
            cabecas_de_chave = atletas[:num_byes]
            restantes = atletas[num_byes:]

            pares = []
            
            # Cabeças de chave ganham BYE
            for atleta in cabecas_de_chave:
                pares.append((atleta, "BYE"))
            
            # Lutas reais dos restantes
            for i in range(0, len(restantes), 2):
                if i + 1 < len(restantes):
                    pares.append((restantes[i], restantes[i+1]))
                else:
                    pares.append((restantes[i], {"nome": "BYE (Avança Direto)", "email": None})) 

            # Salva os pares
            for vermelho, azul in pares:
                # Handle BYE case
                if vermelho == "BYE":
                    vermelho_nome = "BYE (Avança Direto)"
                    vermelho_email = None
                else:
                    vermelho_nome = vermelho["nome"]
                    vermelho_email = vermelho["email"]
                
                if isinstance(azul, dict) and azul.get("nome") == "BYE (Avança Direto)":
                    azul_nome = "BYE (Avança Direto)"
                    azul_email = None
                else:
                    azul_nome = azul["nome"]
                    azul_email = azul["email"]
                
                luta = {
                    "campeonato_id": camp_id, "categoria_id": cat_id, "modalidade": "Kyorugui",
                    "ordem_luta": ordem_geral, 
                    "atleta_vermelho_email": vermelho_email,  # ← NEW
                    "atleta_vermelho": vermelho_nome,  # Keep for backward compatibility
                    "atleta_azul_email": azul_email,  # ← NEW
                    "atleta_azul": azul_nome,  # Keep for backward compatibility
                    "status": "Aguardando Chamada"
                }
                lutas_geradas.append(luta)
                ordem_geral += 1
                
        else:  # Poomsae
            for i, atleta in enumerate(atletas):
                apresentacao = {
                    "campeonato_id": camp_id, "categoria_id": cat_id, "modalidade": "Poomsae",
                    "ordem_luta": ordem_geral, "ordem_apresentacao": i + 1,
                    "atleta_email": atleta["email"],  # ← NEW
                    "atleta": atleta["nome"], "status": "Aguardando Chamada"
                }
                lutas_geradas.append(apresentacao)
                ordem_geral += 1

    if lutas_geradas:
        await db.lutas.insert_many(lutas_geradas)

    for l in lutas_geradas:
        if "_id" in l: l["_id"] = str(l["_id"])

    return {"mensagem": f"Chaves e Fila de {dados.modalidade} geradas com sucesso!", "lutas": lutas_geradas}


@router.get("/campeonatos/{camp_id}/lutas")
async def listar_lutas(camp_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Lista todas as lutas de um campeonato ordenadas"""
    cursor = db.lutas.find({"campeonato_id": camp_id}).sort("ordem_luta", 1)
    lutas = await cursor.to_list(length=2000)
    
    for l in lutas:
        l["_id"] = str(l["_id"])
        
    return lutas


@router.post("/campeonatos/{camp_id}/gerar-cronograma")
async def gerar_cronograma(camp_id: str, config: ConfigCronograma, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Gera o cronograma completo com distribuição nas quadras"""
    await db.lutas.delete_many({"campeonato_id": camp_id})

    inscricoes_cursor = db.inscricoes.find({"campeonato_id": camp_id, "status_pagamento": "Confirmado"}).sort("data_inscricao", 1)
    inscricoes = await inscricoes_cursor.to_list(length=3000)

    if not inscricoes:
        raise HTTPException(status_code=400, detail="Nenhum atleta confirmado.")

    campeonato = await db.campeonatos.find_one({"_id": ObjectId(camp_id)})
    nivel_camp = campeonato.get("nivel", "Estadual") if campeonato else "Estadual"

    emails = [i["atleta_email"] for i in inscricoes]
    usuarios_cursor = db.users.find({"email": {"$in": emails}})
    mapa_usuarios = {}
    for u in await usuarios_cursor.to_list(length=3000):
        nome_base = f"{u.get('nome', '')} {u.get('sobrenome', '')}"
        comp = u.get("equipe", "") if nivel_camp == "Estadual" else u.get("estado", "") if nivel_camp == "Nacional" else u.get("pais", "")
        mapa_usuarios[u["email"]] = f"{nome_base} ({comp})" if comp else nome_base

    # Agrupa por categoria
    categorias_dict = {}
    for insc in inscricoes:
        cat_id = insc["categoria_id"]
        if cat_id not in categorias_dict:
            categorias_dict[cat_id] = {"atletas": [], "modalidade": insc["modalidade"]}
        categorias_dict[cat_id]["atletas"].append({
            "email": insc["atleta_email"],  # ← NEW
            "nome": mapa_usuarios.get(insc["atleta_email"], "Desconhecido"), 
            "data": insc.get("data_inscricao", "")
        })

    todas_as_lutas_geradas = []

    # Gera as lutas e apresentações
    for cat_id, info in categorias_dict.items():
        atletas = info["atletas"]
        modalidade = info["modalidade"]
        atletas.sort(key=lambda x: x["data"])

        cat_detalhes = next((c for c in campeonato["categorias"] if c["id"] == cat_id), None)
        is_preta = "Preta" in cat_detalhes["graduacao"] if cat_detalhes else False
        is_adulto = "Adulto" in cat_detalhes["idade_genero"] or "Sub 21" in cat_detalhes["idade_genero"] if cat_detalhes else False

        if modalidade == "Kyorugui":
            if is_adulto and is_preta: duracao = 10
            elif is_preta: duracao = 9
            else: duracao = 8

            N = len(atletas)
            if N == 1:
                todas_as_lutas_geradas.append({
                    "campeonato_id": camp_id, "categoria_id": cat_id, "modalidade": "Kyorugui",
                    "atleta_vermelho_email": atletas[0]["email"],  # ← NEW
                    "atleta_vermelho": atletas[0]["nome"], 
                    "atleta_azul_email": None,  # ← NEW
                    "atleta_azul": "Sem Oponente (Ouro)",
                    "status": "Encerrado", "duracao_min": duracao
                })
                continue
            
            next_power_of_2 = 2 ** math.ceil(math.log2(N))
            num_byes = next_power_of_2 - N
            cabecas_de_chave = atletas[:num_byes]
            restantes = atletas[num_byes:]
            
            for atleta in cabecas_de_chave:
                todas_as_lutas_geradas.append({
                    "campeonato_id": camp_id, "categoria_id": cat_id, "modalidade": "Kyorugui",
                    "atleta_vermelho_email": atleta["email"],  # ← NEW
                    "atleta_vermelho": atleta["nome"], 
                    "atleta_azul_email": None,  # ← NEW
                    "atleta_azul": "BYE (Avança Direto)",
                    "status": "Aguardando Chamada", "duracao_min": duracao
                })
            for i in range(0, len(restantes), 2):
                azul_atleta = restantes[i+1] if i+1 < len(restantes) else None
                azul_nome = azul_atleta["nome"] if azul_atleta else "BYE (Avança Direto)"
                azul_email = azul_atleta["email"] if azul_atleta else None
                
                todas_as_lutas_geradas.append({
                    "campeonato_id": camp_id, "categoria_id": cat_id, "modalidade": "Kyorugui",
                    "atleta_vermelho_email": restantes[i]["email"],  # ← NEW
                    "atleta_vermelho": restantes[i]["nome"], 
                    "atleta_azul_email": azul_email,  # ← NEW
                    "atleta_azul": azul_nome,
                    "status": "Aguardando Chamada", "duracao_min": duracao
                })
        else:  # ✅ POOMSAE - Criar chaves 1v1 (Chong vs Hong)
            duracao = 8 if is_preta else 7
            
            # Criar pares de apresentações (Chong vs Hong)
            N = len(atletas)
            for i in range(0, N, 2):
                if i + 1 < N:
                    # Par completo: Chong e Hong
                    todas_as_lutas_geradas.append({
                        "campeonato_id": camp_id, "categoria_id": cat_id, "modalidade": "Poomsae",
                        "atleta_vermelho_email": atletas[i]["email"],  # ← NEW
                        "atleta_vermelho": atletas[i]["nome"],      # Chong (Vermelho)
                        "atleta_azul_email": atletas[i+1]["email"],  # ← NEW
                        "atleta_azul": atletas[i+1]["nome"],        # Hong (Azul)
                        "status": "Aguardando Chamada", "duracao_min": duracao
                    })
                else:
                    # Atleta impar (só apresenta, sem oponente)
                    todas_as_lutas_geradas.append({
                        "campeonato_id": camp_id, "categoria_id": cat_id, "modalidade": "Poomsae",
                        "atleta_vermelho_email": atletas[i]["email"],  # ← NEW
                        "atleta_vermelho": atletas[i]["nome"],
                        "atleta_azul_email": None,  # ← NEW
                        "atleta_azul": "BYE (Avança Direto)",
                        "status": "Aguardando Chamada", "duracao_min": duracao
                    })

    # Distribui nas quadras
    hora_inicio_dt = datetime.strptime(config.horario_inicio, "%H:%M")
    quadras = [{"id": i+1, "tempo_atual": hora_inicio_dt, "tipo": "Mista"} for i in range(config.num_quadras)]
    
    if config.isolar_poomsae and config.num_quadras > 1:
        quadras[0]["tipo"] = "Poomsae"
        for i in range(1, config.num_quadras):
            quadras[i]["tipo"] = "Kyorugui"

    ordem_geral = 1
    todas_as_lutas_geradas.sort(key=lambda x: (x["modalidade"] == "Kyorugui", x["categoria_id"]))

    for luta in todas_as_lutas_geradas:
        luta["ordem_luta"] = ordem_geral
        ordem_geral += 1
        
        quadras_compativeis = [q for q in quadras if q["tipo"] == "Mista" or q["tipo"] == luta["modalidade"]]
        if not quadras_compativeis:
            quadras_compativeis = quadras
        
        quadra_escolhida = min(quadras_compativeis, key=lambda q: q["tempo_atual"])
        
        luta["quadra"] = quadra_escolhida["id"]
        luta["horario_previsto"] = quadra_escolhida["tempo_atual"].strftime("%H:%M")
        
        quadra_escolhida["tempo_atual"] += timedelta(minutes=luta["duracao_min"])

    if todas_as_lutas_geradas:
        await db.lutas.insert_many(todas_as_lutas_geradas)

    for l in todas_as_lutas_geradas:
        if "_id" in l: l["_id"] = str(l["_id"])

    return {"mensagem": "Cronograma Oficial Gerado com Sucesso!", "lutas": todas_as_lutas_geradas}


@router.get("/campeonatos/{camp_id}/quadras/{num_quadra}/luta-atual")
async def obter_luta_atual(camp_id: str, num_quadra: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Obtém a luta que está em andamento nesta quadra"""
    try:
        num_quadra_int = int(num_quadra)
    except ValueError:
        raise HTTPException(status_code=400, detail="Número da quadra inválido")
    
    luta = await db.lutas.find_one({
        "campeonato_id": camp_id, 
        "quadra": num_quadra_int, 
        "status": "Em Andamento"
    })
    
    if not luta:
        raise HTTPException(status_code=404, detail="Nenhuma luta em andamento.")
        
    luta["_id"] = str(luta["_id"])
    return luta


@router.get("/campeonatos/{camp_id}/quadras/{num_quadra}/proxima-luta")
async def obter_proxima_luta(camp_id: str, num_quadra: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """
    Obtém a próxima luta para o mesário puxar.
    Retorna a primeira luta com status "Aguardando Chamada" (ainda não foi puxada)
    """
    try:
        num_quadra_int = int(num_quadra)
    except ValueError:
        raise HTTPException(status_code=400, detail="Número da quadra inválido")
    
    # Busca primeira luta DESTE CAMPEONATO ainda não puxada
    # Status "Aguardando Chamada" = nunca foi puxada
    lutas_cursor = db.lutas.find({
        "campeonato_id": camp_id,
        "status": "Aguardando Chamada"
    }).sort("ordem_luta", 1).limit(1)
    
    lutas = await lutas_cursor.to_list(length=1)
    
    if not lutas:
        raise HTTPException(status_code=404, detail="Nenhuma luta pendente para esta quadra.")
    
    luta = lutas[0]
    
    # ✅ IMPORTANTE: Marcar que foi puxada e qual é a quadra
    await db.lutas.update_one(
        {"_id": luta["_id"]},
        {"$set": {
            "quadra": num_quadra_int,
            "status": "Em Andamento"  # Agora está sendo disputada
        }}
    )
    
    # Buscar novamente para retornar com dados atualizados
    luta_atualizada = await db.lutas.find_one({"_id": luta["_id"]})
    luta_atualizada["_id"] = str(luta_atualizada["_id"])
    return luta_atualizada


@router.get("/campeonatos/{camp_id}/quadras/{num_quadra}/luta-em-andamento")
async def obter_luta_em_andamento(camp_id: str, num_quadra: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """
    Retorna a luta que já está Em Andamento nesta quadra.
    Usado pelo mesário para reconectar sem puxar uma nova luta.
    """
    try:
        num_quadra_int = int(num_quadra)
    except ValueError:
        raise HTTPException(status_code=400, detail="Número da quadra inválido")

    luta = await db.lutas.find_one({
        "campeonato_id": camp_id,
        "quadra": num_quadra_int,
        "status": "Em Andamento"
    })

    if not luta:
        raise HTTPException(status_code=404, detail="Nenhuma luta em andamento nesta quadra.")

    luta["_id"] = str(luta["_id"])
    return luta


@router.get("/scoreboard/access/{token}")
async def validar_token_scoreboard(token: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """
    Valida token de acesso ao Scoreboard.
    Token é permanente por quadra (não single-use).
    Retorna numero_quadra e campeonato_id.
    """
    # Procurar quadra pelo token
    quadra = await db.quadras.find_one({"token_scoreboard": token})
    
    if not quadra:
        raise HTTPException(status_code=401, detail="Token inválido")
    
    return {
        "acesso_autorizado": True,
        "campeonato_id": quadra["campeonato_id"],
        "numero_quadra": quadra["numero_quadra"],
        "mensagem": "Acesso autorizado ao Scoreboard da Quadra"
    }


@router.get("/lutas/{luta_id}/luta-atual")
async def obter_luta_atual(luta_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """
    Obtém dados da luta atual para o Scoreboard.
    Usa o endpoint já existente em campeonatos.
    """
    try:
        luta = await db.lutas.find_one({
            "_id": ObjectId(luta_id),
            "status": "Em Andamento"
        })
    except:
        luta = await db.lutas.find_one({
            "_id": luta_id,
            "status": "Em Andamento"
        })
    
    if not luta:
        raise HTTPException(status_code=404, detail="Luta não encontrada")
    
    luta["_id"] = str(luta["_id"])
    return luta
async def finalizar_luta_banco(luta_id: str, dados: FinalizarLutaData, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Finaliza uma luta e salva os resultados"""
    
    # Buscar dados atuais da luta para fazer broadcast
    luta_atual = await db.lutas.find_one({"_id": ObjectId(luta_id)})
    if not luta_atual:
        raise HTTPException(status_code=404, detail="Luta não encontrada.")
    
    resultado = await db.lutas.update_one(
        {"_id": ObjectId(luta_id)},
        {"$set": {
            "status": "Encerrada",
            "vencedor": dados.vencedor,
            "placar_red": dados.placar_red,
            "placar_blue": dados.placar_blue,
            "faltas_red": dados.faltas_red,
            "faltas_blue": dados.faltas_blue
        }}
    )
    
    if resultado.matched_count == 0:
        raise HTTPException(status_code=404, detail="Luta não encontrada.")
    
    # ✅ CRIAR REGISTRO NO resultados (Phase 1 - Athlete Identification)
    if luta_atual.get("atleta_vermelho_email") or luta_atual.get("atleta_azul_email"):
        # Determinar vencedor e perdedor
        if dados.vencedor == "red":
            vencedor_email = luta_atual.get("atleta_vermelho_email")
            vencedor_nome = luta_atual.get("atleta_vermelho")
            perdedor_email = luta_atual.get("atleta_azul_email")
            perdedor_nome = luta_atual.get("atleta_azul")
            placar_vencedor = dados.placar_red
            placar_perdedor = dados.placar_blue
        else:
            vencedor_email = luta_atual.get("atleta_azul_email")
            vencedor_nome = luta_atual.get("atleta_azul")
            perdedor_email = luta_atual.get("atleta_vermelho_email")
            perdedor_nome = luta_atual.get("atleta_vermelho")
            placar_vencedor = dados.placar_blue
            placar_perdedor = dados.placar_red
        
        # Inserir resultado para o vencedor
        if vencedor_email:
            resultado_vencedor = {
                "campeonato_id": luta_atual.get("campeonato_id"),
                "luta_id": str(luta_id),
                "atleta_email": vencedor_email,
                "atleta_nome": vencedor_nome,
                "categoria_id": luta_atual.get("categoria_id"),
                "modalidade": luta_atual.get("modalidade"),
                "adversario_email": perdedor_email,
                "adversario_nome": perdedor_nome,
                "medalha": "participacao",  # Will be updated when medal determination happens
                "placar_final": placar_vencedor,
                "placar_adversario": placar_perdedor,
                "venceu": True,
                "data_luta": datetime.utcnow(),
                "timestamp_criacao": datetime.utcnow()
            }
            await db.resultados.insert_one(resultado_vencedor)
        
        # Inserir resultado para o perdedor (se não for BYE)
        if perdedor_email:
            resultado_perdedor = {
                "campeonato_id": luta_atual.get("campeonato_id"),
                "luta_id": str(luta_id),
                "atleta_email": perdedor_email,
                "atleta_nome": perdedor_nome,
                "categoria_id": luta_atual.get("categoria_id"),
                "modalidade": luta_atual.get("modalidade"),
                "adversario_email": vencedor_email,
                "adversario_nome": vencedor_nome,
                "medalha": "participacao",
                "placar_final": placar_perdedor,
                "placar_adversario": placar_vencedor,
                "venceu": False,
                "data_luta": datetime.utcnow(),
                "timestamp_criacao": datetime.utcnow()
            }
            await db.resultados.insert_one(resultado_perdedor)
    
    # 📺 NOTIFICAR LIVE QUE LUTA FOI ENCERRADA
    campeonato_id = luta_atual.get("campeonato_id")
    if campeonato_id:
        luta_atualizada = await db.lutas.find_one({"_id": ObjectId(luta_id)})
        await manager.broadcast_luta_update(campeonato_id, luta_atualizada)
        print(f"📺 Live notificado: Luta {luta_id} encerrada")
        
    return {"mensagem": "Luta encerrada salva no banco!"}


@router.put("/lutas/{luta_id}/atualizar-turno-poomsae")
async def atualizar_turno_poomsae(luta_id: str, dados: dict, db: AsyncIOMotorDatabase = Depends(get_db)):
    """
    Atualiza qual Poomsae está sendo executado (turno_poomsae).
    
    Esperado: {
        "turno_poomsae": "chong_p1" | "chong_p2" | "hong_p1" | "hong_p2"
    }
    """
    turno = dados.get("turno_poomsae")
    
    if turno not in ["chong_p1", "chong_p2", "hong_p1", "hong_p2"]:
        raise HTTPException(status_code=400, detail="Turno inválido")
    
    resultado = await db.lutas.update_one(
        {"_id": ObjectId(luta_id)},
        {"$set": {"turno_poomsae": turno}}
    )
    
    if resultado.matched_count == 0:
        raise HTTPException(status_code=404, detail="Luta não encontrada.")
    
    return {"mensagem": f"Turno Poomsae atualizado para: {turno}"}


@router.post("/campeonatos/{camp_id}/sortear-poomsaes")
async def sortear_poomsaes_campeonato(camp_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Sorteia os Poomsaes oficiais para as categorias de Faixa Preta"""
    lutas_poomsae = await db.lutas.find({"campeonato_id": camp_id, "modalidade": "Poomsae"}).to_list(length=1000)
    
    atualizados = 0
    for luta in lutas_poomsae:
        if "freestyle" in luta.get("nome_categoria", "").lower():
            await db.lutas.update_one({"_id": luta["_id"]}, {"$set": {"poomsae_1": "Poomsae Free Style", "poomsae_2": None}})
            continue
            
        if "colorida" in luta.get("nome_categoria", "").lower() or "gub" in luta.get("nome_categoria", "").lower():
            await db.lutas.update_one({"_id": luta["_id"]}, {"$set": {"poomsae_1": "Poomsae da Faixa Atual", "poomsae_2": None}})
            continue

        cat_nome = luta.get("nome_categoria", "")
        grupo = "Adulto"
        if "Cadete" in cat_nome: grupo = "Cadete"
        elif "Juvenil" in cat_nome or "Sub 17" in cat_nome: grupo = "Juvenil"
        elif "Sub 30" in cat_nome: grupo = "Sub 30"
        elif "Sub 40" in cat_nome: grupo = "Sub 40"
        elif "Sub 50" in cat_nome: grupo = "Sub 50"
        elif "Sub 60" in cat_nome or "Master" in cat_nome: grupo = "Master"

        pool = POOMSAES_WT.get(grupo, POOMSAES_WT["Sub 30"])
        sorteados = random.sample(pool, 2)
        
        await db.lutas.update_one({"_id": luta["_id"]}, {"$set": {"poomsae_1": sorteados[0], "poomsae_2": sorteados[1]}})
        atualizados += 1
    
    # Criar notícia do sorteio
    from datetime import datetime
    noticia_sorteio = {
        "titulo": f"🎲 Sorteio de Poomsaes Realizado",
        "conteudo": f"{atualizados} chaves foram atualizadas com os Poomsaes oficiais. Os atletas devem consultar seu quadro de apresentações.",
        "campeonato_id": camp_id,
        "tipo": "sortear_poomsae",
        "data_criacao": datetime.utcnow().isoformat(),
        "ativa": True
    }
    
    try:
        await db.noticias.insert_one(noticia_sorteio)
    except Exception as e:
        print(f"Aviso: Não foi possível criar notícia do sorteio: {str(e)}")
        
    return {"mensagem": f"Sorteio concluído! {atualizados} chaves atualizadas com os Poomsaes oficiais."}



@router.get("/scoreboard/luta-atual")
async def obter_luta_atual_por_token(token: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """
    Obtém a luta atual de uma quadra usando o token.
    Token é validado e extrai campeonato_id + numero_quadra.
    """
    # Procurar quadra pelo token
    quadra = await db.quadras.find_one({"token_scoreboard": token})
    
    if not quadra:
        raise HTTPException(status_code=401, detail="Token inválido")
    
    numero_quadra = quadra["numero_quadra"]
    
    try:
        luta = await db.lutas.find_one({
            "quadra": numero_quadra,
            "status": "Em Andamento"
        })
        
        if not luta:
            return {
                "luta": None,
                "numero_quadra": numero_quadra,
                "campeonato_id": quadra["campeonato_id"],
                "mensagem": "Aguardando próxima luta"
            }
        
        luta["_id"] = str(luta["_id"])
        return {
            "luta": luta,
            "numero_quadra": numero_quadra,
            "campeonato_id": quadra["campeonato_id"],
            "mensagem": "Luta em andamento"
        }
    except Exception as e:
        return {
            "luta": None,
            "numero_quadra": numero_quadra,
            "campeonato_id": quadra["campeonato_id"],
            "mensagem": f"Erro ao buscar luta: {str(e)}"
        }


# ✅ PHASE 1: ATHLETE ENDPOINTS (Athlete Identification)

@router.get("/meu-perfil/minhas-lutas")
async def minhas_lutas(email: str = Query(..., description="Athlete email"), db: AsyncIOMotorDatabase = Depends(get_db)):
    """
    Retorna todas as lutas do atleta (Kyorugui, Poomsae).
    Query parameter: email=user@example.com
    
    Resposta inclui:
    - Próximas lutas (status != Encerrada)
    - Lutas concluídas (status == Encerrada)
    - Resultado final se luta terminou
    """
    try:
        # Buscar todas as lutas onde o atleta participou (Kyorugui)
        lutas_kyorugui = await db.lutas.find({
            "$or": [
                {"atleta_vermelho_email": email},
                {"atleta_azul_email": email}
            ],
            "modalidade": "Kyorugui"
        }).sort("ordem_luta", 1).to_list(length=500)
        
        # Buscar todas as lutas Poomsae onde o atleta participou
        lutas_poomsae = await db.lutas.find({
            "atleta_vermelho_email": email,
            "modalidade": "Poomsae"
        }).sort("ordem_luta", 1).to_list(length=500)
        
        resultado = []
        
        # Processar Kyorugui
        for luta in lutas_kyorugui:
            sou_vermelho = luta.get("atleta_vermelho_email") == email
            resultado.append({
                "luta_id": str(luta["_id"]),
                "campeonato_id": luta.get("campeonato_id"),
                "categoria": luta.get("nome_categoria", "N/A"),
                "modalidade": "Kyorugui",
                "meu_lado": "vermelho" if sou_vermelho else "azul",
                "meu_nome": luta.get("atleta_vermelho") if sou_vermelho else luta.get("atleta_azul"),
                "adversario_nome": luta.get("atleta_azul") if sou_vermelho else luta.get("atleta_vermelho"),
                "adversario_email": luta.get("atleta_azul_email") if sou_vermelho else luta.get("atleta_vermelho_email"),
                "status": luta.get("status"),
                "quadra": luta.get("quadra", "N/A"),
                "ordem_luta": luta.get("ordem_luta"),
                "resultado": {
                    "vencedor": luta.get("vencedor"),
                    "placar_meu": luta.get("placar_red") if sou_vermelho else luta.get("placar_blue"),
                    "placar_adversario": luta.get("placar_blue") if sou_vermelho else luta.get("placar_red"),
                    "faltas_minhas": luta.get("faltas_red") if sou_vermelho else luta.get("faltas_blue"),
                    "faltas_adversario": luta.get("faltas_blue") if sou_vermelho else luta.get("faltas_red"),
                } if luta.get("status") == "Encerrada" else None
            })
        
        # Processar Poomsae
        for luta in lutas_poomsae:
            resultado.append({
                "luta_id": str(luta["_id"]),
                "campeonato_id": luta.get("campeonato_id"),
                "categoria": luta.get("nome_categoria", "N/A"),
                "modalidade": "Poomsae",
                "meu_lado": "vermelho",
                "meu_nome": luta.get("atleta_vermelho"),
                "adversario_nome": luta.get("atleta_azul"),
                "adversario_email": luta.get("atleta_azul_email"),
                "status": luta.get("status"),
                "quadra": luta.get("quadra", "N/A"),
                "ordem_luta": luta.get("ordem_luta"),
                "turno_poomsae": luta.get("turno_poomsae"),
                "resultado": {
                    "placar_meu": luta.get("placar_red"),
                    "placar_adversario": luta.get("placar_blue"),
                } if luta.get("status") == "Encerrada" else None
            })
        
        # Ordenar por ordem_luta
        resultado.sort(key=lambda x: x.get("ordem_luta", 999))
        
        return {
            "email_atleta": email,
            "total_lutas": len(resultado),
            "lutas": resultado
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar lutas: {str(e)}")


@router.get("/lutas/{luta_id}/resultado")
async def obter_resultado_luta(luta_id: str, email: str = Query(...), db: AsyncIOMotorDatabase = Depends(get_db)):
    """
    Retorna resultado de uma luta específica para o atleta.
    Valida que o email pertence a um dos atletas da luta.
    
    Query: /api/lutas/507f1f77bcf86cd799439011/resultado?email=athlete@example.com
    """
    try:
        # Buscar a luta
        luta = await db.lutas.find_one({"_id": ObjectId(luta_id)})
        
        if not luta:
            raise HTTPException(status_code=404, detail="Luta não encontrada")
        
        # Verificar se email está na luta (Kyorugui e Poomsae)
        sou_vermelho = luta.get("atleta_vermelho_email") == email
        sou_azul = luta.get("atleta_azul_email") == email
        
        if not sou_vermelho and not sou_azul:
            raise HTTPException(status_code=403, detail="Acesso negado - você não participa desta luta")
        
        # Se luta ainda não encerrou, retornar status apenas
        if luta.get("status") != "Encerrada":
            return {
                "luta_id": str(luta["_id"]),
                "campeonato_id": luta.get("campeonato_id"),
                "categoria": luta.get("nome_categoria", "N/A"),
                "modalidade": luta.get("modalidade"),
                "meu_lado": "vermelho" if sou_vermelho else "azul",
                "meu_nome": luta.get("atleta_vermelho") if sou_vermelho else luta.get("atleta_azul"),
                "adversario_nome": luta.get("atleta_azul") if sou_vermelho else luta.get("atleta_vermelho"),
                "adversario_email": luta.get("atleta_azul_email") if sou_vermelho else luta.get("atleta_vermelho_email"),
                "status": luta.get("status"),
                "quadra": luta.get("quadra", "N/A"),
                "resultado": None
            }
        
        # Buscar resultado na coleção resultados
        resultado_doc = await db.resultados.find_one({"luta_id": str(luta_id), "atleta_email": email})
        
        meu_placar = luta.get("placar_red") if sou_vermelho else luta.get("placar_blue")
        placar_adversario = luta.get("placar_blue") if sou_vermelho else luta.get("placar_red")
        faltas_minhas = luta.get("faltas_red") if sou_vermelho else luta.get("faltas_blue")
        faltas_adversario = luta.get("faltas_blue") if sou_vermelho else luta.get("faltas_red")
        
        return {
            "luta_id": str(luta["_id"]),
            "campeonato_id": luta.get("campeonato_id"),
            "categoria": luta.get("nome_categoria", "N/A"),
            "modalidade": luta.get("modalidade"),
            "meu_lado": "vermelho" if sou_vermelho else "azul",
            "meu_nome": luta.get("atleta_vermelho") if sou_vermelho else luta.get("atleta_azul"),
            "adversario_nome": luta.get("atleta_azul") if sou_vermelho else luta.get("atleta_vermelho"),
            "adversario_email": luta.get("atleta_azul_email") if sou_vermelho else luta.get("atleta_vermelho_email"),
            "status": "Encerrada",
            "quadra": luta.get("quadra", "N/A"),
            "resultado": {
                "vencedor": luta.get("vencedor"),
                "venci": resultado_doc.get("venceu") if resultado_doc else (luta.get("vencedor") == ("red" if sou_vermelho else "blue")),
                "meu_placar": meu_placar,
                "placar_adversario": placar_adversario,
                "minhas_faltas": faltas_minhas,
                "faltas_adversario": faltas_adversario,
                "medalha": resultado_doc.get("medalha") if resultado_doc else "participacao"
            }
        }
    
    except ObjectId as e:
        raise HTTPException(status_code=400, detail="ID da luta inválido")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar resultado: {str(e)}")
