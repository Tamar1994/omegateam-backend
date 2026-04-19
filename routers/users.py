"""
Rotas de Usuários (Perfil, Senha, Preferências)
"""
from fastapi import APIRouter, HTTPException, Depends
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
