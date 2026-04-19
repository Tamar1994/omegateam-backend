"""
Rotas de Autenticação (Login, Cadastro, Verificação)
"""
import random
from fastapi import APIRouter, HTTPException, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from models.user import DadosCadastro, LoginData, ValidacaoToken
from services.auth_service import get_password_hash, verify_password
from services.email_service import enviar_email_token
from database.connection import get_db

router = APIRouter(prefix="/api", tags=["Autenticação"])


@router.get("/verificar-email/{email}")
async def verificar_email_existente(email: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Verifica se o email já está cadastrado"""
    usuario = await db.users.find_one({"email": email})
    
    if usuario:
        return {"disponivel": False, "mensagem": "E-mail já cadastrado."}
    
    return {"disponivel": True}


@router.post("/enviar-token")
async def processar_cadastro(dados: DadosCadastro, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Processa o cadastro e envia token de verificação"""
    # Verifica se usuário já existe
    usuario_existente = await db.users.find_one({
        "$or": [{"email": dados.email}, {"cpf_passaporte": dados.cpf_passaporte}]
    })
    
    if usuario_existente:
        raise HTTPException(status_code=400, detail="E-mail ou Documento já cadastrados e validados.")

    # Gera Token de 6 dígitos
    token = str(random.randint(100000, 999999))
    
    # Salva os dados na coleção temporária
    dados_dict = dados.dict()
    dados_dict["token"] = token
    dados_dict["senha"] = get_password_hash(dados.senha)
    dados_dict["role"] = "atleta"
    
    await db.cadastros_pendentes.update_one(
        {"email": dados.email},
        {"$set": dados_dict},
        upsert=True
    )
    
    # Dispara o E-mail
    sucesso_email = enviar_email_token(dados.email, token)
    if not sucesso_email:
        raise HTTPException(status_code=500, detail="Falha ao enviar o e-mail. Verifique o endereço.")
        
    return {"mensagem": "Token enviado com sucesso", "email": dados.email}


@router.post("/validar-token")
async def validar_cadastro(dados: ValidacaoToken, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Valida o token e ativa a conta"""
    # Busca na coleção temporária
    cadastro_pendente = await db.cadastros_pendentes.find_one({
        "email": dados.email,
        "token": dados.token
    })
    
    if not cadastro_pendente:
        raise HTTPException(status_code=400, detail="Código inválido ou expirado.")
    
    # Remove os dados temporários e de controle
    del cadastro_pendente["_id"]
    del cadastro_pendente["token"]
    
    # Salva na coleção oficial 'users'
    await db.users.insert_one(cadastro_pendente)
    
    # Limpa a coleção temporária
    await db.cadastros_pendentes.delete_one({"email": dados.email})
    
    return {"mensagem": "Conta ativada com sucesso!", "usuario": cadastro_pendente["email"]}


@router.post("/login")
async def login(dados: LoginData, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Autentica o usuário"""
    usuario = await db.users.find_one({"email": dados.email})
    
    if not usuario or not verify_password(dados.senha, usuario["senha"]):
        raise HTTPException(status_code=401, detail="E-mail ou senha incorretos.")
    
    # Pega a foto do banco, ou gera uma provisória se não existir
    foto_url = usuario.get("foto", f"https://api.dicebear.com/7.x/avataaars/svg?seed={usuario.get('nome', 'Omega')}")
    
    # Retorna TODOS os dados para o Front-end preencher o perfil
    return {
        "mensagem": "Login efetuado com sucesso!",
        "usuario": {
            "nome": usuario.get("nome", ""),
            "sobrenome": usuario.get("sobrenome", ""),
            "email": usuario.get("email", ""),
            "role": usuario.get("role", "atleta"),
            "cpf_passaporte": usuario.get("cpf_passaporte", ""),
            "sexo": usuario.get("sexo", "M"),
            "nascimento": usuario.get("nascimento", ""),
            "peso": usuario.get("peso", 0),
            "altura": usuario.get("altura", 0),
            "graduacao": usuario.get("graduacao", ""),
            "registro_federacao": usuario.get("registro_federacao", ""),
            "registro_cbtkd": usuario.get("registro_cbtkd", ""),
            "registro_kukkiwon": usuario.get("registro_kukkiwon", ""),
            "foto": foto_url,
            "equipe": usuario.get("equipe", ""),
            "estado": usuario.get("estado", "SP"),
            "pais": usuario.get("pais", "BRA")
        }
    }
