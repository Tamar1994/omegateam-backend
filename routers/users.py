"""
Rotas de Usuários (Perfil, Senha, Preferências)
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import FileResponse, StreamingResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime
from models.user import (
    AtualizarPerfilData,
    AlterarSenhaData,
    ExcluirContaData,
    AtualizarPreferenciasData,
    UpdateRoleData
)
from services.auth_service import verify_password, get_password_hash
from services.certificate_service import CertificateService
from database.connection import get_db
from bson.objectid import ObjectId

router = APIRouter(prefix="/api", tags=["Usuários"])


@router.put("/atualizar-perfil")
async def atualizar_perfil(dados: AtualizarPerfilData, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Atualiza dados do perfil do usuário"""
    # Excluímos o e-mail da atualização para evitar que o usuário mude a chave principal
    update_data = dados.dict(exclude={"email"})
    
    resultado = await db.users.update_one(
        {"email": dados.email},
        {"$set": update_data}
    )
    
    if resultado.matched_count == 0:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
        
    return {"mensagem": "Perfil atualizado com sucesso!"}


@router.put("/alterar-senha")
async def alterar_senha(dados: AlterarSenhaData, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Altera a senha do usuário"""
    usuario = await db.users.find_one({"email": dados.email})
    
    if not usuario or not verify_password(dados.senha_atual, usuario["senha"]):
        raise HTTPException(status_code=400, detail="A senha atual está incorreta.")
    
    # Gera o hash da nova senha
    nova_senha_hash = get_password_hash(dados.nova_senha)
    
    await db.users.update_one(
        {"email": dados.email},
        {"$set": {"senha": nova_senha_hash}}
    )
    
    return {"mensagem": "Senha alterada com sucesso!"}


@router.delete("/excluir-conta")
async def excluir_conta(dados: ExcluirContaData, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Exclui a conta do usuário"""
    usuario = await db.users.find_one({"email": dados.email})
    
    if not usuario or not verify_password(dados.senha_confirmacao, usuario["senha"]):
        raise HTTPException(status_code=400, detail="Senha incorreta. Não foi possível excluir a conta.")
    
    # Faz uma cópia do documento do usuário
    usuario_arquivado = usuario.copy()
    usuario_arquivado["data_exclusao"] = datetime.utcnow().isoformat()
    
    # Insere o usuário na coleção de backup
    await db.usuarios_excluidos.insert_one(usuario_arquivado)
    
    # Remove da coleção principal 'users'
    await db.users.delete_one({"email": dados.email})
    
    return {"mensagem": "Conta arquivada e removida do sistema principal."}


@router.put("/atualizar-preferencias")
async def atualizar_preferencias(dados: AtualizarPreferenciasData, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Atualiza as preferências do usuário"""
    resultado = await db.users.update_one(
        {"email": dados.email},
        {"$set": {"receber_notificacoes": dados.receber_notificacoes}}
    )
    
    if resultado.matched_count == 0:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
        
    return {"mensagem": "Preferências atualizadas com sucesso!"}


@router.get("/usuarios")
async def listar_todos_usuarios(db: AsyncIOMotorDatabase = Depends(get_db)):
    """Lista todos os usuários"""
    cursor = db.users.find({}).sort("nome", 1)
    usuarios = await cursor.to_list(length=2000)
    for u in usuarios:
        u["_id"] = str(u["_id"])
        u.pop("senha", None)  # Remove a password por segurança
    return usuarios


@router.put("/usuarios/{usuario_id}/role")
async def atualizar_role_usuario(usuario_id: str, dados: UpdateRoleData, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Atualiza a permissão (role) de um usuário"""
    resultado = await db.users.update_one(
        {"_id": ObjectId(usuario_id)},
        {"$set": {"role": dados.role}}
    )
    if resultado.matched_count == 0:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    return {"mensagem": "Nível de acesso atualizado com sucesso!"}


@router.get("/usuarios/arbitros")
async def listar_arbitros_disponiveis(db: AsyncIOMotorDatabase = Depends(get_db)):
    """Lista todos os árbitros disponíveis"""
    cursor = db.users.find({"role": "arbitro"}).sort("nome", 1)
    usuarios = await cursor.to_list(length=1000)
    
    lista = []
    for u in usuarios:
        nome_completo = f"{u.get('nome', '')} {u.get('sobrenome', '')}".strip()
        lista.append({"email": u["email"], "nome": nome_completo})
        
    return lista


# ========== PHASE 3: ATHLETE CAREER & CERTIFICATES ==========

@router.get("/meu-perfil/carreira")
async def obter_carreira_atleta(email: str = Query(...), db: AsyncIOMotorDatabase = Depends(get_db)):
    """
    Retorna histórico de carreira do atleta
    Query params: email=athlete@example.com
    """
    # Find all results for this athlete
    resultados = await db.resultados.find(
        {"atleta_email": email}
    ).sort("data_luta", -1).to_list(1000)
    
    if not resultados:
        return {
            "email": email,
            "total_competicoes": 0,
            "total_lutas": 0,
            "vitoria": 0,
            "derrotas": 0,
            "medalhas": {"ouro": 0, "prata": 0, "bronze": 0, "participacao": 0},
            "historico": []
        }
    
    # Group by tournament
    competicoes = {}
    vitoria = 0
    derrotas = 0
    medalhas_count = {"ouro": 0, "prata": 0, "bronze": 0, "participacao": 0}
    
    for resultado in resultados:
        camp_id = str(resultado.get("campeonato_id"))
        
        # Count wins/losses
        if resultado.get("venceu", False):
            vitoria += 1
        else:
            derrotas += 1
        
        # Count medals
        medalha = resultado.get("medalha", "participacao")
        medalhas_count[medalha] = medalhas_count.get(medalha, 0) + 1
        
        # Group by competition
        if camp_id not in competicoes:
            competicoes[camp_id] = {
                "campeonato_id": camp_id,
                "campeonato_nome": resultado.get("categoria_id", "Campeonato"),
                "lutas": []
            }
        
        competicoes[camp_id]["lutas"].append({
            "luta_id": resultado.get("luta_id"),
            "adversario": resultado.get("adversario_nome"),
            "categoria": resultado.get("categoria_id"),
            "modalidade": resultado.get("modalidade"),
            "resultado": "Vitória" if resultado.get("venceu", False) else "Derrota",
            "placar": {
                "seu_placar": resultado.get("placar_final"),
                "placar_adversario": resultado.get("placar_adversario")
            },
            "medalha": medalha,
            "data": resultado.get("data_luta").isoformat() if resultado.get("data_luta") else None
        })
    
    return {
        "email": email,
        "total_competicoes": len(competicoes),
        "total_lutas": len(resultados),
        "vitorias": vitoria,
        "derrotas": derrotas,
        "taxa_vitoria": f"{(vitoria / len(resultados) * 100):.1f}%" if len(resultados) > 0 else "0%",
        "medalhas": medalhas_count,
        "historico": list(competicoes.values())
    }


@router.get("/meu-perfil/certificado/{campeonato_id}")
async def baixar_certificado(
    campeonato_id: str,
    email: str = Query(...),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """
    Gera e retorna certificado PDF de participação
    Query params: email=athlete@example.com
    """
    try:
        # Find athlete's best result in this tournament
        resultado = await db.resultados.find_one({
            "atleta_email": email,
            "campeonato_id": campeonato_id
        })
        
        if not resultado:
            raise HTTPException(status_code=404, detail="Nenhuma participação encontrada neste campeonato")
        
        # Get tournament info
        campeonato = await db.campeonatos.find_one({"_id": ObjectId(campeonato_id)})
        if not campeonato:
            raise HTTPException(status_code=404, detail="Campeonato não encontrado")
        
        # Get athlete info
        usuario = await db.users.find_one({"email": email})
        if not usuario:
            raise HTTPException(status_code=404, detail="Usuário não encontrado")
        
        # Generate certificate
        atleta_nome = f"{usuario.get('nome', '')} {usuario.get('sobrenome', '')}".strip()
        
        pdf_buffer = CertificateService.gerar_certificado_participacao(
            atleta_nome=atleta_nome,
            atleta_email=email,
            campeonato_nome=campeonato.get("nome", "Campeonato"),
            data_evento=campeonato.get("data_inicio", datetime.now()),
            categoria=resultado.get("categoria_id", "Geral"),
            modalidade=resultado.get("modalidade", "Taekwondo"),
            medalha=resultado.get("medalha", "participacao")
        )
        
        # Return as downloadable file
        return StreamingResponse(
            iter([pdf_buffer.getvalue()]),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=certificado_{email.split('@')[0]}.pdf"}
        )
    
    except Exception as e:
        print(f"Erro ao gerar certificado: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao gerar certificado: {str(e)}")
