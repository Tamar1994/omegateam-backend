"""
Rotas de Lutas (Geração de Chaves, Cronograma, Lutas)
"""
import math
import random
from fastapi import APIRouter, HTTPException, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime, timedelta
from bson.objectid import ObjectId
from models.luta import GerarChavesData, FinalizarLutaData, LateralReadyData
from models.campeonato import ConfigCronograma
from config.settings import POOMSAES_WT
from database.connection import get_db

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
                pares.append((atleta["nome"], "BYE (Avança Direto)"))
            
            # Lutas reais dos restantes
            for i in range(0, len(restantes), 2):
                if i + 1 < len(restantes):
                    pares.append((restantes[i]["nome"], restantes[i+1]["nome"]))
                else:
                    pares.append((restantes[i]["nome"], "BYE (Avança Direto)")) 

            # Salva os pares
            for vermelho, azul in pares:
                luta = {
                    "campeonato_id": camp_id, "categoria_id": cat_id, "modalidade": "Kyorugui",
                    "ordem_luta": ordem_geral, "atleta_vermelho": vermelho, "atleta_azul": azul,
                    "status": "Aguardando Chamada"
                }
                lutas_geradas.append(luta)
                ordem_geral += 1
                
        else:  # Poomsae
            for i, atleta in enumerate(atletas):
                apresentacao = {
                    "campeonato_id": camp_id, "categoria_id": cat_id, "modalidade": "Poomsae",
                    "ordem_luta": ordem_geral, "ordem_apresentacao": i + 1,
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
        categorias_dict[cat_id]["atletas"].append({"nome": mapa_usuarios.get(insc["atleta_email"], "Desconhecido"), "data": insc.get("data_inscricao", "")})

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
                    "atleta_vermelho": atletas[0]["nome"], "atleta_azul": "Sem Oponente (Ouro)",
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
                    "atleta_vermelho": atleta["nome"], "atleta_azul": "BYE (Avança Direto)",
                    "status": "Aguardando Chamada", "duracao_min": duracao
                })
            for i in range(0, len(restantes), 2):
                azul = restantes[i+1]["nome"] if i+1 < len(restantes) else "BYE (Avança Direto)"
                todas_as_lutas_geradas.append({
                    "campeonato_id": camp_id, "categoria_id": cat_id, "modalidade": "Kyorugui",
                    "atleta_vermelho": restantes[i]["nome"], "atleta_azul": azul,
                    "status": "Aguardando Chamada", "duracao_min": duracao
                })
        else:
            duracao = 8 if is_preta else 7
            for i, atleta in enumerate(atletas):
                todas_as_lutas_geradas.append({
                    "campeonato_id": camp_id, "categoria_id": cat_id, "modalidade": "Poomsae",
                    "ordem_apresentacao": i + 1, "atleta": atleta["nome"],
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
async def obter_luta_atual(camp_id: str, num_quadra: int, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Obtém a luta que está em andamento nesta quadra"""
    luta = await db.lutas.find_one({
        "campeonato_id": camp_id, 
        "quadra": num_quadra, 
        "status": "Em Andamento"
    })
    
    if not luta:
        raise HTTPException(status_code=404, detail="Nenhuma luta em andamento.")
        
    luta["_id"] = str(luta["_id"])
    return luta


@router.get("/campeonatos/{camp_id}/quadras/{num_quadra}/proxima-luta")
async def obter_proxima_luta(camp_id: str, num_quadra: int, db: AsyncIOMotorDatabase = Depends(get_db)):
    """
    Obtém a próxima luta para o mesário puxar.
    Retorna a primeira luta com status "Pendente" ou "Não Iniciada"
    """
    # Busca primeira luta sem status definido ou com status "Pendente"
    lutas_cursor = db.lutas.find({
        "campeonato_id": camp_id,
        "quadra": num_quadra,
        "$or": [
            {"status": {"$exists": False}},
            {"status": {"$in": ["Pendente", "Não Iniciada", None]}}
        ]
    }).sort("ordem_luta", 1).limit(1)  # Ordem cronológica
    
    lutas = await lutas_cursor.to_list(length=1)
    
    if not lutas:
        raise HTTPException(status_code=404, detail="Nenhuma luta pendente para esta quadra.")
    
    luta = lutas[0]
    luta["_id"] = str(luta["_id"])
    return luta


@router.put("/lutas/{luta_id}/finalizar")
async def finalizar_luta_banco(luta_id: str, dados: FinalizarLutaData):
    """Finaliza uma luta e salva os resultados"""
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
        
    return {"mensagem": "Luta encerrada salva no banco!"}


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
        
    return {"mensagem": f"Sorteio concluído! {atualizados} chaves atualizadas com os Poomsaes oficiais."}
