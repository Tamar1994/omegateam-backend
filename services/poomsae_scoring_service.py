"""
Serviço de Scoring de Poomsae — Conformidade WT
Artigos 10-14 (Pontuação, Deduções, Desempate)

ALGORITMO CENTRAL (Artigo 13):
  1. Coletar scores de todos os 7 (ou 5) juízes
  2. Para CADA componente (acurácia, apresentação, habilidade técnica):
     a. Encontrar valor MÁXIMO → remover
     b. Encontrar valor MÍNIMO → remover
     c. Calcular MÉDIA dos restantes
  3. Total = soma das médias por componente
  4. Total Final = Total − Deduções
"""
from typing import List, Optional
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson.objectid import ObjectId
from fastapi import HTTPException

from models.poomsae_score import (
    ScoreJuiz, Match, MatchCreate, ResultadoMatch, DetalheCalculo,
    Deducoes, StatusMatch, TipoPoomsaeMatch,
    ResultadoDesempate, CriterioDesempate, MotivoDQ
)


# ─────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────

def _serialize(doc: dict) -> dict:
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc


def _calcular_componente(scores: List[float]) -> DetalheCalculo:
    """
    Remove o MAIOR e o MENOR score, calcula a média dos restantes.
    Com 3+ juízes aplica trimming WT. Com 1-2 juízes usa a média direta.
    """
    n = len(scores)
    if n == 0:
        raise ValueError("Nenhum score recebido")

    score_max = max(scores)
    score_min = min(scores)
    scores_copia = scores.copy()

    if n >= 4:
        # Com 4+ juízes: descarta maior e menor, média das intermediárias
        scores_copia.remove(score_max)
        scores_copia.remove(score_min)
    # Com 1-3 juízes: média direta (sem descarte)

    media = round(sum(scores_copia) / len(scores_copia), 2)

    return DetalheCalculo(
        scores_recebidos=scores,
        score_max=score_max,
        score_min=score_min,
        scores_validos=scores_copia,
        media=media,
        num_juizes=n,
    )


# ─────────────────────────────────────────────
#  Matches
# ─────────────────────────────────────────────

async def criar_match(db: AsyncIOMotorDatabase, dados: MatchCreate) -> dict:
    """Cria um match de poomsae"""
    doc = dados.model_dump(exclude={"tipo"})  # remove campo alias
    doc["status"] = StatusMatch.AGENDADO
    doc["deducoes"] = Deducoes().model_dump()
    doc["scores_juizes"] = []
    doc["resultado"] = None
    doc["timestamp_criacao"] = datetime.utcnow()

    resultado = await db.poomsae_matches.insert_one(doc)
    match = await db.poomsae_matches.find_one({"_id": resultado.inserted_id})
    return _serialize(match)


async def listar_matches(
    db: AsyncIOMotorDatabase,
    campeonato_id: Optional[str] = None,
    luta_id: Optional[str] = None,
    atleta_id: Optional[str] = None,
    divisao: Optional[str] = None,
    rodada: Optional[int] = None,
    status: Optional[str] = None,
) -> list:
    filtro: dict = {}
    if campeonato_id:
        filtro["campeonato_id"] = campeonato_id
    if luta_id:
        filtro["luta_id"] = luta_id
    if atleta_id:
        filtro["atleta_id"] = atleta_id
    if divisao:
        filtro["divisao"] = {"$regex": divisao, "$options": "i"}
    if rodada:
        filtro["rodada"] = rodada
    if status:
        filtro["status"] = status

    cursor = db.poomsae_matches.find(filtro).sort([("rodada", 1), ("timestamp_criacao", 1)])
    matches = await cursor.to_list(length=500)
    return [_serialize(m) for m in matches]


async def obter_match(db: AsyncIOMotorDatabase, match_id: str) -> dict:
    try:
        obj_id = ObjectId(match_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")

    match = await db.poomsae_matches.find_one({"_id": obj_id})
    if not match:
        raise HTTPException(status_code=404, detail="Match não encontrado")
    return _serialize(match)


async def iniciar_match(db: AsyncIOMotorDatabase, match_id: str) -> dict:
    """Marca match como em andamento"""
    match = await obter_match(db, match_id)
    if match["status"] not in [StatusMatch.AGENDADO, StatusMatch.EM_ANDAMENTO]:
        raise HTTPException(
            status_code=400,
            detail=f"Match com status '{match['status']}' não pode ser iniciado"
        )
    await db.poomsae_matches.update_one(
        {"_id": ObjectId(match_id)},
        {"$set": {"status": StatusMatch.EM_ANDAMENTO, "timestamp_inicio": datetime.utcnow()}}
    )
    return await obter_match(db, match_id)


# ─────────────────────────────────────────────
#  Score de juízes
# ─────────────────────────────────────────────

async def submeter_score(db: AsyncIOMotorDatabase, dados: ScoreJuiz) -> dict:
    """
    Juiz submete seu score para um match.
    Após submissão, calcula automaticamente o resultado
    se todos os juízes já submeteram.
    """
    match = await obter_match(db, dados.match_id)

    if match["status"] not in [StatusMatch.EM_ANDAMENTO, StatusMatch.AGUARDANDO_SCORES]:
        raise HTTPException(
            status_code=400,
            detail=f"Match com status '{match['status']}' não aceita scores"
        )

    # Verificar se juiz já submeteu
    ja_submeteu = await db.poomsae_scores.find_one({
        "match_id": dados.match_id,
        "juiz_id": dados.juiz_id,
    })
    if ja_submeteu and not ja_submeteu.get("editavel", True):
        raise HTTPException(status_code=409, detail="Score já submetido e não editável")

    # Validar tipo de score compatível com o match
    tipo_match = match.get("tipo_poomsae")
    if tipo_match == TipoPoomsaeMatch.RECOGNIZED and dados.score_freestyle:
        raise HTTPException(
            status_code=400,
            detail="Match Recognized requer score_recognized, não score_freestyle"
        )
    if tipo_match == TipoPoomsaeMatch.FREESTYLE and dados.score_recognized:
        raise HTTPException(
            status_code=400,
            detail="Match Freestyle requer score_freestyle, não score_recognized"
        )

    doc = dados.model_dump()
    doc["timestamp_submissao"] = datetime.utcnow()
    doc["editavel"] = False

    # Upsert do score do juiz
    if ja_submeteu:
        await db.poomsae_scores.update_one(
            {"match_id": dados.match_id, "juiz_id": dados.juiz_id},
            {"$set": doc}
        )
        score_id = str(ja_submeteu["_id"])
    else:
        resultado = await db.poomsae_scores.insert_one(doc)
        score_id = str(resultado.inserted_id)

    # Adicionar score à lista do match
    await db.poomsae_matches.update_one(
        {"_id": ObjectId(dados.match_id)},
        {"$addToSet": {"scores_juizes": score_id},
         "$set": {"status": StatusMatch.AGUARDANDO_SCORES}}
    )

    # Verificar se todos os juízes submeteram → calcular automaticamente
    total_juizes = match.get("numero_juizes") or (len(match.get("juiz_ids", [])) + 1)
    scores_recebidos = await db.poomsae_scores.count_documents({"match_id": dados.match_id})
    if scores_recebidos >= total_juizes:
        await calcular_pontuacao_final(db, dados.match_id)

    score = await db.poomsae_scores.find_one({"match_id": dados.match_id, "juiz_id": dados.juiz_id})
    return _serialize(score)


async def listar_scores_match(db: AsyncIOMotorDatabase, match_id: str) -> list:
    """Lista todos os scores de um match com status por juiz"""
    match = await obter_match(db, match_id)

    scores = await db.poomsae_scores.find({"match_id": match_id}).to_list(length=20)
    juizes_submeteram = {s["juiz_id"] for s in scores}

    todos_juizes = match.get("juiz_ids", [])
    if match.get("referee_id"):
        todos_juizes = [match["referee_id"]] + todos_juizes

    resultado = {
        "match_id": match_id,
        "total_juizes": len(todos_juizes),
        "scores_recebidos": len(scores),
        "pendentes": [j for j in todos_juizes if j not in juizes_submeteram],
        "scores": [_serialize(s) for s in scores],
    }
    return resultado


# ─────────────────────────────────────────────
#  Cálculo de Pontuação (CORAÇÃO DO SISTEMA)
# ─────────────────────────────────────────────

async def calcular_pontuacao_final(db: AsyncIOMotorDatabase, match_id: str) -> dict:
    """
    ALGORITMO OFICIAL WT (Artigo 13):

    Para cada componente:
      1. Coletar todos os scores do componente
      2. Remover o MÁXIMO e o MÍNIMO
      3. Calcular a MÉDIA dos restantes
    Total = soma das médias
    Total Final = Total - Deduções

    Recognized: acuracia_media + apresentacao_media - deducoes
    Freestyle:  habilidade_tecnica_media + apresentacao_media - deducoes
    """
    match = await obter_match(db, match_id)
    scores_raw = await db.poomsae_scores.find({"match_id": match_id}).to_list(length=20)

    min_scores = match.get("numero_juizes") or 1
    if len(scores_raw) < min_scores:
        raise HTTPException(
            status_code=400,
            detail=f"Aguardando {min_scores - len(scores_raw)} score(s) pendente(s). Recebidos: {len(scores_raw)}/{min_scores}"
        )

    tipo = match.get("tipo_poomsae")
    deducoes_doc = match.get("deducoes", {})
    deducoes = Deducoes(**deducoes_doc)

    # DQ imediata
    if deducoes.desqualificado or deducoes.num_kyeong_go >= 2:
        resultado_doc = {
            "match_id": match_id,
            "pontuacao_base": 0.0,
            "total_deducoes": 0.0,
            "pontuacao_final": 0.0,
            "soma_total_scores": 0.0,
            "desqualificado": True,
            "num_juizes_computados": len(scores_raw),
            "timestamp_calculo": datetime.utcnow(),
        }
        await db.poomsae_matches.update_one(
            {"_id": ObjectId(match_id)},
            {"$set": {"resultado": resultado_doc, "status": StatusMatch.CALCULADO}}
        )
        return resultado_doc

    resultado_doc = {
        "match_id": match_id,
        "desqualificado": False,
        "num_juizes_computados": len(scores_raw),
        "timestamp_calculo": datetime.utcnow(),
    }

    if tipo == TipoPoomsaeMatch.RECOGNIZED:
        acuracias = [s["score_recognized"]["acuracia"] for s in scores_raw if s.get("score_recognized")]
        apresentacoes = [s["score_recognized"]["apresentacao"] for s in scores_raw if s.get("score_recognized")]

        detalhe_ac = _calcular_componente(acuracias)
        detalhe_ap = _calcular_componente(apresentacoes)

        pontuacao_base = round(detalhe_ac.media + detalhe_ap.media, 2)
        soma_total = round(sum(acuracias) + sum(apresentacoes), 2)

        resultado_doc.update({
            "detalhe_acuracia": detalhe_ac.model_dump(),
            "detalhe_apresentacao": detalhe_ap.model_dump(),
            "pontuacao_base": pontuacao_base,
            "soma_total_scores": soma_total,
        })

    elif tipo == TipoPoomsaeMatch.FREESTYLE:
        hab_tecs = [s["score_freestyle"]["habilidade_tecnica"] for s in scores_raw if s.get("score_freestyle")]
        apresentacoes = [s["score_freestyle"]["apresentacao"] for s in scores_raw if s.get("score_freestyle")]

        detalhe_ht = _calcular_componente(hab_tecs)
        detalhe_ap = _calcular_componente(apresentacoes)

        pontuacao_base = round(detalhe_ht.media + detalhe_ap.media, 2)
        soma_total = round(sum(hab_tecs) + sum(apresentacoes), 2)

        resultado_doc.update({
            "detalhe_habilidade_tecnica": detalhe_ht.model_dump(),
            "detalhe_apresentacao": detalhe_ap.model_dump(),
            "pontuacao_base": pontuacao_base,
            "soma_total_scores": soma_total,
        })

    total_deducoes = deducoes.total_deducao
    pontuacao_final = max(0.0, round(resultado_doc["pontuacao_base"] - total_deducoes, 2))

    resultado_doc["total_deducoes"] = total_deducoes
    resultado_doc["pontuacao_final"] = pontuacao_final

    await db.poomsae_matches.update_one(
        {"_id": ObjectId(match_id)},
        {"$set": {
            "resultado": resultado_doc,
            "status": StatusMatch.CALCULADO,
            "timestamp_fim": datetime.utcnow(),
        }}
    )
    return resultado_doc


# ─────────────────────────────────────────────
#  Deduções (Árbitro principal aplica)
# ─────────────────────────────────────────────

async def aplicar_deducoes(
    db: AsyncIOMotorDatabase,
    match_id: str,
    deducoes: Deducoes
) -> dict:
    """
    Aplica deduções ao match (Artigo 11):
    - saiu_zona: -0.3
    - fora_do_tempo: -0.3
    - 2 kyeong-go: DQ
    """
    match = await obter_match(db, match_id)

    if match["status"] not in [StatusMatch.EM_ANDAMENTO, StatusMatch.AGUARDANDO_SCORES, StatusMatch.CALCULADO]:
        raise HTTPException(status_code=400, detail="Não é possível aplicar deduções neste momento")

    # Verificar DQ por 2 kyeong-go
    if deducoes.num_kyeong_go >= 2:
        deducoes.desqualificado = True
        deducoes.motivo_dq = MotivoDQ.DOIS_KYEONG_GO

    await db.poomsae_matches.update_one(
        {"_id": ObjectId(match_id)},
        {"$set": {"deducoes": deducoes.model_dump()}}
    )

    # Recalcular pontuação se já calculada
    if match["status"] == StatusMatch.CALCULADO:
        return await calcular_pontuacao_final(db, match_id)

    return await obter_match(db, match_id)


# ─────────────────────────────────────────────
#  Desempate (Artigo 13.4)
# ─────────────────────────────────────────────

async def resolver_desempate(
    db: AsyncIOMotorDatabase,
    match_id_1: str,
    match_id_2: str,
    tipo_competicao: str = "Recognized",
) -> ResultadoDesempate:
    """
    Critérios de desempate WT (Artigo 13.4), nesta ordem:
    1. Recognized → maior apresentação
    2. Freestyle  → maior habilidade técnica
    3. Mixed      → maior score freestyle
    4. Se ainda empatado → maior soma total (incl. max/min)
    5. Se AINDA empatado → REMATCH
    """
    m1 = await obter_match(db, match_id_1)
    m2 = await obter_match(db, match_id_2)

    res1 = m1.get("resultado", {})
    res2 = m2.get("resultado", {})

    if not res1 or not res2:
        raise HTTPException(status_code=400, detail="Ambos os matches precisam estar calculados")

    pf1 = res1.get("pontuacao_final", 0.0)
    pf2 = res2.get("pontuacao_final", 0.0)

    if pf1 != pf2:
        vencedor = match_id_1 if pf1 > pf2 else match_id_2
        return ResultadoDesempate(
            match_id_1=match_id_1,
            match_id_2=match_id_2,
            criterio_aplicado=CriterioDesempate.SOMA_TOTAL,
            vencedor_match_id=vencedor,
            precisa_rematch=False,
            detalhes=f"Sem empate: {pf1} vs {pf2}",
        )

    # Critério 1: Recognized → maior apresentação
    if tipo_competicao == "Recognized":
        ap1 = res1.get("detalhe_apresentacao", {}).get("media", 0.0)
        ap2 = res2.get("detalhe_apresentacao", {}).get("media", 0.0)
        if ap1 != ap2:
            return ResultadoDesempate(
                match_id_1=match_id_1,
                match_id_2=match_id_2,
                criterio_aplicado=CriterioDesempate.APRESENTACAO,
                vencedor_match_id=match_id_1 if ap1 > ap2 else match_id_2,
                precisa_rematch=False,
                detalhes=f"Apresentação: {ap1} vs {ap2}",
            )

    # Critério 2: Freestyle → maior habilidade técnica
    elif tipo_competicao == "Freestyle":
        ht1 = res1.get("detalhe_habilidade_tecnica", {}).get("media", 0.0)
        ht2 = res2.get("detalhe_habilidade_tecnica", {}).get("media", 0.0)
        if ht1 != ht2:
            return ResultadoDesempate(
                match_id_1=match_id_1,
                match_id_2=match_id_2,
                criterio_aplicado=CriterioDesempate.HABILIDADE_TECNICA,
                vencedor_match_id=match_id_1 if ht1 > ht2 else match_id_2,
                precisa_rematch=False,
                detalhes=f"Habilidade Técnica: {ht1} vs {ht2}",
            )

    # Critério 3: Mixed → maior score Freestyle
    elif tipo_competicao == "Mixed":
        # Buscar score freestyle de cada atleta no mix
        fs1 = res1.get("detalhe_habilidade_tecnica", {}).get("media", 0.0)
        fs2 = res2.get("detalhe_habilidade_tecnica", {}).get("media", 0.0)
        if fs1 != fs2:
            return ResultadoDesempate(
                match_id_1=match_id_1,
                match_id_2=match_id_2,
                criterio_aplicado=CriterioDesempate.FREESTYLE_EM_MIXED,
                vencedor_match_id=match_id_1 if fs1 > fs2 else match_id_2,
                precisa_rematch=False,
                detalhes=f"Freestyle em Mixed: {fs1} vs {fs2}",
            )

    # Critério 4: Soma total (incluindo max/min removidos)
    soma1 = res1.get("soma_total_scores", 0.0)
    soma2 = res2.get("soma_total_scores", 0.0)
    if soma1 != soma2:
        return ResultadoDesempate(
            match_id_1=match_id_1,
            match_id_2=match_id_2,
            criterio_aplicado=CriterioDesempate.SOMA_TOTAL,
            vencedor_match_id=match_id_1 if soma1 > soma2 else match_id_2,
            precisa_rematch=False,
            detalhes=f"Soma total (incl. max/min): {soma1} vs {soma2}",
        )

    # Critério 5: REMATCH
    return ResultadoDesempate(
        match_id_1=match_id_1,
        match_id_2=match_id_2,
        criterio_aplicado=CriterioDesempate.REMATCH,
        vencedor_match_id=None,
        precisa_rematch=True,
        detalhes="Todos os critérios de desempate esgotados. Rematch necessário com forma designada pelo TD.",
    )


async def criar_rematch(db: AsyncIOMotorDatabase, match_id_1: str, match_id_2: str) -> dict:
    """
    Cria novos matches de rematch após desempate total.
    A forma do rematch é designada pelo Technical Delegate.
    """
    m1 = await obter_match(db, match_id_1)
    m2 = await obter_match(db, match_id_2)

    rematch_1 = {
        **{k: v for k, v in m1.items() if k not in ["_id", "resultado", "scores_juizes", "status"]},
        "status": StatusMatch.REMATCH,
        "rodada": m1.get("rodada", 1),
        "forma_designada": "A ser designada pelo Technical Delegate",
        "timestamp_criacao": datetime.utcnow(),
    }
    rematch_2 = {
        **{k: v for k, v in m2.items() if k not in ["_id", "resultado", "scores_juizes", "status"]},
        "status": StatusMatch.REMATCH,
        "rodada": m2.get("rodada", 1),
        "forma_designada": "A ser designada pelo Technical Delegate",
        "timestamp_criacao": datetime.utcnow(),
    }

    r1 = await db.poomsae_matches.insert_one(rematch_1)
    r2 = await db.poomsae_matches.insert_one(rematch_2)

    return {
        "rematch_match_id_1": str(r1.inserted_id),
        "rematch_match_id_2": str(r2.inserted_id),
        "instrucao": "TD deve designar a forma antes do início",
    }
