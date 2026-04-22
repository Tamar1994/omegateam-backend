from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from dotenv import load_dotenv
import os
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from motor.motor_asyncio import AsyncIOMotorClient
import bcrypt
from fastapi import UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
import aiofiles
from datetime import datetime
from datetime import timedelta
import uuid
import random
import math
from bson.objectid import ObjectId  
from routers.joystick import router as joystick_router
from routers.arbitros import router as arbitros_router
from routers.noticias import router as noticias_router
from routers.poomsae_campeonatos import router as poomsae_campeonatos_router
from routers.poomsae_atletas import router as poomsae_atletas_router
from routers.poomsae_inscricoes import router as poomsae_inscricoes_router
from routers.poomsae_juizes import router as poomsae_juizes_router
from routers.poomsae_scoring import router as poomsae_scoring_router

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

app = FastAPI()

# Configuração de CORS para permitir requisições do frontend React (Vite)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== REGISTRAR ROUTERS =====
app.include_router(joystick_router)
app.include_router(arbitros_router)
app.include_router(noticias_router)
app.include_router(poomsae_campeonatos_router)
app.include_router(poomsae_atletas_router)
app.include_router(poomsae_inscricoes_router)
app.include_router(poomsae_juizes_router)
app.include_router(poomsae_scoring_router)

# Conexão com MongoDB
MONGO_URI = os.getenv("MONGO_URI")
client = AsyncIOMotorClient(MONGO_URI)
db = client.omegateam 

# --- CONFIGURAÇÃO DE UPLOADS (Render Persistent Disk) ---
PASTA_UPLOADS = "uploads/fotos_perfil"
os.makedirs(PASTA_UPLOADS, exist_ok=True) # Cria a pasta automaticamente se não existir

# Serve a pasta estática para o frontend acessar via URL (ex: localhost:8000/uploads/foto.png)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


PASTA_OFICIOS = "uploads/oficios"
os.makedirs(PASTA_OFICIOS, exist_ok=True)
app.mount("/oficios", StaticFiles(directory="uploads/oficios"), name="oficios")

POOMSAES_WT = {
    "Cadete": ["Taegeuk 4 Jang", "Taegeuk 5 Jang", "Taegeuk 6 Jang", "Taegeuk 7 Jang", "Taegeuk 8 Jang", "Koryo", "Keumgang"],
    "Juvenil": ["Taegeuk 4 Jang", "Taegeuk 5 Jang", "Taegeuk 6 Jang", "Taegeuk 7 Jang", "Taegeuk 8 Jang", "Koryo", "Keumgang", "Taeback"],
    "Sub 30": ["Taegeuk 6 Jang", "Taegeuk 7 Jang", "Taegeuk 8 Jang", "Koryo", "Keumgang", "Taeback", "Pyongwon", "Shipjin"],
    "Sub 40": ["Taegeuk 6 Jang", "Taegeuk 7 Jang", "Taegeuk 8 Jang", "Koryo", "Keumgang", "Taeback", "Pyongwon", "Shipjin", "Jitae"],
    "Sub 50": ["Taegeuk 8 Jang", "Koryo", "Keumgang", "Taeback", "Pyongwon", "Shipjin", "Jitae", "Chonkwon"],
    "Master": ["Koryo", "Keumgang", "Taeback", "Pyongwon", "Shipjin", "Jitae", "Chonkwon", "Hansu"]
}

# --- CONFIGURAÇÃO DE CRIPTOGRAFIA (BCRYPT PURO) ---
def get_password_hash(password: str) -> str:
    # Transforma a string em bytes, gera o salt e cria o hash
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password=pwd_bytes, salt=salt)
    # Retorna como string para salvar no banco de dados
    return hashed_password.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    # Compara a senha digitada no login com o hash do banco
    password_byte_enc = plain_password.encode('utf-8')
    hashed_password_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password_byte_enc, hashed_password_bytes)

# --- MODELOS DE DADOS ---
class DadosCadastro(BaseModel):
    nome: str
    sobrenome: str
    email: EmailStr
    cpf_passaporte: str
    senha: str
    sexo: str
    nascimento: str
    peso: float
    altura: float
    graduacao: str
    registro_federacao: str = ""
    registro_cbtkd: str = ""
    registro_kukkiwon: str = ""

class ValidacaoToken(BaseModel):
    email: EmailStr
    token: str

class LoginData(BaseModel):
    email: EmailStr
    senha: str

class AtualizarPerfilData(BaseModel):
    email: str
    nome: str
    sobrenome: str
    sexo: str
    nascimento: str
    peso: float
    altura: float
    graduacao: str
    registro_federacao: str = ""
    registro_cbtkd: str = ""
    registro_kukkiwon: str = ""
    equipe: str = ""
    estado: str = ""
    pais: str = ""

class AlterarSenhaData(BaseModel):
    email: str
    senha_atual: str
    nova_senha: str

class ExcluirContaData(BaseModel):
    email: str
    senha_confirmacao: str

class AtualizarPreferenciasData(BaseModel):
    email: str
    receber_notificacoes: bool

class CategoriaData(BaseModel):
    id: str
    modalidade: str # "Kyorugui", "Poomsae", "Parataekwondo"
    idade_genero: str # Ex: "Sub 11 Masc"
    graduacao: str # Ex: "8º a 5º Gub"
    peso_ou_tipo: str # Ex: "Até 30 kg" ou "Individual"
    pesagem: bool

class CampeonatoData(BaseModel):
    nome: str
    data_evento: str
    local: str
    modalidades: str 
    inclui_parataekwondo: bool = False
    status: str = "Inscrições Abertas"
    oficio_url: str = ""
    categorias: list[CategoriaData] = []
    nivel: str = "Estadual"

class AtualizarCategoriasData(BaseModel):
    categorias: list[CategoriaData]

class InscricaoData(BaseModel):
    campeonato_id: str
    atleta_email: str
    categoria_id: str
    modalidade: str # Kyorugui ou Poomsae

class AtualizarStatusInscricao(BaseModel):
    status_pagamento: str # "Confirmado", "Pendente" ou "Cancelado"

class GerarChavesData(BaseModel):
    modalidade: str # 'Kyorugui' ou 'Poomsae'

class ConfigCronograma(BaseModel):
    num_quadras: int = 1
    isolar_poomsae: bool = True
    horario_inicio: str = "08:30"

class EquipeQuadraData(BaseModel):
    numero_quadra: int
    mesario_email: str = ""
    central_email: str = ""
    lateral1_email: str = ""
    lateral2_email: str = ""
    lateral3_email: str = ""
    lateral4_email: str = ""
    lateral5_email: str = ""

class UpdateRoleData(BaseModel):
    role: str # "user", "arbitro" ou "admin"

class LateralReadyData(BaseModel):
    lateral_slot: str # Ex: "lateral1", "lateral2", etc.
    is_ready: bool

class FinalizarLutaData(BaseModel):
    vencedor: str # 'red' ou 'blue'
    placar_red: int
    placar_blue: int
    faltas_red: int
    faltas_blue: int

# --- FUNÇÕES AUXILIARES ---
def enviar_email_token(destinatario: str, token: str):
    remetente = os.getenv("EMAIL_REMETENTE")
    senha = os.getenv("SENHA_EMAIL")
    
    msg = MIMEMultipart()
    msg['From'] = f"Omega Team <{remetente}>"
    msg['To'] = destinatario
    msg['Subject'] = "Seu Código de Verificação - Omega Team"
    
    corpo = f"""
    Olá!
    
    Você iniciou seu cadastro na plataforma Omega Team.
    Seu código de verificação é: {token}
    
    Este código é válido por 15 minutos.
    Se você não solicitou este cadastro, ignore este e-mail.
    """
    msg.attach(MIMEText(corpo, 'plain', 'utf-8'))
    
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(remetente, senha)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Erro ao enviar email: {e}")
        return False

# --- ROTAS DA API ---
@app.get("/api/verificar-email/{email}")
async def verificar_email_existente(email: str):
    # Procura se o e-mail já existe na coleção definitiva de usuários
    usuario = await db.users.find_one({"email": email})
    
    if usuario:
        return {"disponivel": False, "mensagem": "E-mail já cadastrado."}
    
    return {"disponivel": True}


@app.post("/api/enviar-token")
async def processar_cadastro(dados: DadosCadastro):
    # 1. Verifica se usuário já existe na coleção definitiva 'users'
    usuario_existente = await db.users.find_one({
        "$or": [{"email": dados.email}, {"cpf_passaporte": dados.cpf_passaporte}]
    })
    
    if usuario_existente:
        raise HTTPException(status_code=400, detail="E-mail ou Documento já cadastrados e validados.")

    # 2. Gera Token de 6 dígitos
    token = str(random.randint(100000, 999999))
    
    # 3. Salva os dados na coleção temporária
    dados_dict = dados.dict()
    dados_dict["token"] = token
    dados_dict["senha"] = get_password_hash(dados.senha)
    dados_dict["role"] = "atleta"
    
    await db.cadastros_pendentes.update_one(
        {"email": dados.email},
        {"$set": dados_dict},
        upsert=True
    )
    
    # 4. Dispara o E-mail
    sucesso_email = enviar_email_token(dados.email, token)
    if not sucesso_email:
        raise HTTPException(status_code=500, detail="Falha ao enviar o e-mail. Verifique o endereço.")
        
    return {"mensagem": "Token enviado com sucesso", "email": dados.email}


@app.post("/api/validar-token")
async def validar_cadastro(dados: ValidacaoToken):
    # 1. Busca na coleção temporária
    cadastro_pendente = await db.cadastros_pendentes.find_one({
        "email": dados.email,
        "token": dados.token
    })
    
    if not cadastro_pendente:
        raise HTTPException(status_code=400, detail="Código inválido ou expirado.")
    
    # 2. Remove os dados temporários e de controle antes de salvar na coleção oficial
    del cadastro_pendente["_id"]
    del cadastro_pendente["token"]
    
    # 3. Salva na coleção oficial 'users'
    await db.users.insert_one(cadastro_pendente)
    
    # 4. Limpa a coleção temporária
    await db.cadastros_pendentes.delete_one({"email": dados.email})
    
    return {"mensagem": "Conta ativada com sucesso!", "usuario": cadastro_pendente["email"]}


@app.post("/api/login")
async def login(dados: LoginData):
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


@app.post("/api/upload-foto")
async def upload_foto_perfil(email: str = Form(...), foto: UploadFile = File(...)):
    try:
        # Pega a extensão original do arquivo (ex: .png, .jpg)
        extensao = os.path.splitext(foto.filename)[1]
        
        # Cria um nome único usando o e-mail (substituindo o @ para evitar problemas de URL)
        nome_arquivo = f"{email.replace('@', '_')}{extensao}"
        caminho_completo = os.path.join(PASTA_UPLOADS, nome_arquivo)
        
        # Salva o arquivo fisicamente na pasta
        async with aiofiles.open(caminho_completo, 'wb') as out_file:
            conteudo = await foto.read()
            await out_file.write(conteudo)
            
        # Atualiza a URL da foto no banco de dados do atleta
        url_foto = f"http://localhost:8000/uploads/fotos_perfil/{nome_arquivo}"
        await db.users.update_one(
            {"email": email}, 
            {"$set": {"foto": url_foto}}
        )
        
        return {"mensagem": "Foto atualizada com sucesso", "url_foto": url_foto}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao salvar foto: {str(e)}")
    
@app.put("/api/atualizar-perfil")
async def atualizar_perfil(dados: AtualizarPerfilData):
    # Excluímos o e-mail da atualização para evitar que o usuário mude a chave principal
    update_data = dados.dict(exclude={"email"})
    
    resultado = await db.users.update_one(
        {"email": dados.email},
        {"$set": update_data}
    )
    
    if resultado.matched_count == 0:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
        
    return {"mensagem": "Perfil atualizado com sucesso!"}

@app.put("/api/alterar-senha")
async def alterar_senha(dados: AlterarSenhaData):
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

@app.delete("/api/excluir-conta")
async def excluir_conta(dados: ExcluirContaData):
    usuario = await db.users.find_one({"email": dados.email})
    
    if not usuario or not verify_password(dados.senha_confirmacao, usuario["senha"]):
        raise HTTPException(status_code=400, detail="Senha incorreta. Não foi possível excluir a conta.")
    
    # 1. Fazemos uma cópia do documento do usuário
    usuario_arquivado = usuario.copy()
    
    # 2. Adicionamos a data e hora exata da exclusão
    usuario_arquivado["data_exclusao"] = datetime.utcnow().isoformat()
    
    # 3. Inserimos o usuário na nova coleção de backup
    await db.usuarios_excluidos.insert_one(usuario_arquivado)
    
    # 4. Só então, removemos da coleção principal 'users'
    await db.users.delete_one({"email": dados.email})
    
    return {"mensagem": "Conta arquivada e removida do sistema principal."}
  
  # --- ROTA PARA ATUALIZAR PREFERÊNCIAS ---
@app.put("/api/atualizar-preferencias")
async def atualizar_preferencias(dados: AtualizarPreferenciasData):
    resultado = await db.users.update_one(
        {"email": dados.email},
        {"$set": {"receber_notificacoes": dados.receber_notificacoes}}
    )
    
    if resultado.matched_count == 0:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
        
    return {"mensagem": "Preferências atualizadas com sucesso!"}

# --- ROTAS DE CAMPEONATOS ---
@app.post("/api/campeonatos")
async def criar_campeonato(dados: CampeonatoData):
    novo_campeonato = dados.dict()
    novo_campeonato["data_criacao"] = datetime.utcnow().isoformat()
    
    # Se a lista de categorias vier vazia do front, o backend pode injetar 
    # o array gigante padrão da FETESP aqui no futuro.
    
    resultado = await db.campeonatos.insert_one(novo_campeonato)
    novo_campeonato["_id"] = str(resultado.inserted_id)
    
    return {"mensagem": "Campeonato criado com sucesso!", "campeonato": novo_campeonato}

@app.put("/api/campeonatos/{camp_id}/categorias")
async def atualizar_categorias(camp_id: str, dados: AtualizarCategoriasData):
    from bson.objectid import ObjectId
    
    resultado = await db.campeonatos.update_one(
        {"_id": ObjectId(camp_id)},
        {"$set": {"categorias": [c.dict() for c in dados.categorias]}}
    )
    
    if resultado.matched_count == 0:
        raise HTTPException(status_code=404, detail="Campeonato não encontrado.")
        
    return {"mensagem": "Categorias atualizadas com sucesso!"}

@app.get("/api/campeonatos")
async def listar_campeonatos():
    campeonatos_cursor = db.campeonatos.find().sort("data_criacao", -1)
    campeonatos = await campeonatos_cursor.to_list(length=100)
    for camp in campeonatos:
        camp["_id"] = str(camp["_id"])
    return campeonatos

@app.post("/api/upload-oficio")
async def upload_oficio(arquivo: UploadFile = File(...)):
    try:
        extensao = os.path.splitext(arquivo.filename)[1]
        nome_arquivo = f"oficio_{uuid.uuid4().hex}{extensao}"
        caminho_completo = os.path.join(PASTA_OFICIOS, nome_arquivo)
        
        async with aiofiles.open(caminho_completo, 'wb') as out_file:
            conteudo = await arquivo.read()
            await out_file.write(conteudo)
            
        url_oficio = f"http://localhost:8000/oficios/{nome_arquivo}"
        return {"url": url_oficio}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Erro ao salvar o ofício.")
    
@app.post("/api/inscricoes")
async def realizar_inscricao(dados: InscricaoData):
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

# --- ROTAS DE GESTÃO DO EVENTO ---
@app.get("/api/campeonatos/{camp_id}/inscricoes")
async def listar_inscricoes_campeonato(camp_id: str):
    # 1. Busca todas as inscrições daquele evento
    inscricoes_cursor = db.inscricoes.find({"campeonato_id": camp_id})
    inscricoes = await inscricoes_cursor.to_list(length=1000)
    
    # 2. Busca os dados dos usuários para pegar o Nome e Sobrenome
    emails = [i["atleta_email"] for i in inscricoes]
    usuarios_cursor = db.users.find({"email": {"$in": emails}})
    usuarios = await usuarios_cursor.to_list(length=1000)
    
    # Cria um dicionário para cruzar os dados rápido
    mapa_usuarios = {u["email"]: f"{u.get('nome', '')} {u.get('sobrenome', '')}" for u in usuarios}
    
    # 3. Monta a lista final com o nome do atleta incluído
    for insc in inscricoes:
        insc["_id"] = str(insc["_id"])
        insc["atleta_nome"] = mapa_usuarios.get(insc["atleta_email"], "Atleta Desconhecido")
        
    return inscricoes

@app.put("/api/inscricoes/{inscricao_id}/status")
async def atualizar_status_inscricao(inscricao_id: str, dados: AtualizarStatusInscricao):
    from bson.objectid import ObjectId
    resultado = await db.inscricoes.update_one(
        {"_id": ObjectId(inscricao_id)},
        {"$set": {"status_pagamento": dados.status_pagamento}}
    )
    
    if resultado.matched_count == 0:
        raise HTTPException(status_code=404, detail="Inscrição não encontrada.")
        
    return {"mensagem": "Status atualizado com sucesso!"}

# --- ROTA PARA GERAR FILA E CHAVES ---
@app.post("/api/campeonatos/{camp_id}/gerar-chaves")
async def gerar_chaves(camp_id: str, dados: GerarChavesData):
    # 1. Limpa chaves anteriores
    await db.lutas.delete_many({"campeonato_id": camp_id, "modalidade": dados.modalidade})

    campeonato = await db.campeonatos.find_one({"_id": ObjectId(camp_id)})
    nivel_camp = campeonato.get("nivel", "Estadual") if campeonato else "Estadual"

    # 2. Busca inscrições pagas ORDENADAS por data (os primeiros a se inscreverem vêm primeiro)
    inscricoes_cursor = db.inscricoes.find({
        "campeonato_id": camp_id,
        "modalidade": dados.modalidade,
        "status_pagamento": "Confirmado"
    }).sort("data_inscricao", 1) # 1 = Ascendente (Do mais antigo para o mais novo)
    
    inscricoes = await inscricoes_cursor.to_list(length=2000)

    if not inscricoes:
        raise HTTPException(status_code=400, detail=f"Nenhum atleta confirmado em {dados.modalidade}.")

    emails = [i["atleta_email"] for i in inscricoes]
    usuarios_cursor = db.users.find({"email": {"$in": emails}})
    
    mapa_usuarios = {}
    for u in await usuarios_cursor.to_list(length=2000):
        nome_base = f"{u.get('nome', '')} {u.get('sobrenome', '')}"
        complemento = ""
        
        # Decide qual sufixo usar baseado no nível do campeonato
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
        # Garante a ordem por data de inscrição dentro da categoria
        atletas.sort(key=lambda x: x["data"])

        if dados.modalidade == "Kyorugui":
            N = len(atletas)
            
            # Caso raro: Apenas 1 atleta na chave (Ouro direto)
            if N == 1:
                luta = {
                    "campeonato_id": camp_id, "categoria_id": cat_id, "modalidade": "Kyorugui",
                    "ordem_luta": ordem_geral, "atleta_vermelho": atletas[0]["nome"],
                    "atleta_azul": "Sem Oponente (Ouro)", "status": "Encerrado"
                }
                lutas_geradas.append(luta)
                ordem_geral += 1
                continue
            
            # Matemática da Chave: Encontra a próxima potência de 2 (2, 4, 8, 16...)
            next_power_of_2 = 2 ** math.ceil(math.log2(N))
            num_byes = next_power_of_2 - N
            
            # Os N primeiros inscritos viram "Cabeças de Chave" e ganham BYE
            cabecas_de_chave = atletas[:num_byes]
            restantes = atletas[num_byes:]

            pares = []
            
            # 1. Lutas fantasma dos cabeças de chave (Avançam direto na primeira rodada)
            for atleta in cabecas_de_chave:
                pares.append((atleta["nome"], "BYE (Avança Direto)"))
            
            # 2. Lutas reais dos que sobraram (Os últimos a se inscreverem)
            for i in range(0, len(restantes), 2):
                if i + 1 < len(restantes):
                    pares.append((restantes[i]["nome"], restantes[i+1]["nome"]))
                else:
                    pares.append((restantes[i]["nome"], "BYE (Avança Direto)")) 

            # 3. Salva os pares no banco
            for vermelho, azul in pares:
                luta = {
                    "campeonato_id": camp_id, "categoria_id": cat_id, "modalidade": "Kyorugui",
                    "ordem_luta": ordem_geral, "atleta_vermelho": vermelho, "atleta_azul": azul,
                    "status": "Aguardando Chamada"
                }
                lutas_geradas.append(luta)
                ordem_geral += 1
                
        else:  # ✅ POOMSAE - Criar chaves 1v1 (Chong vs Hong)
            # Mantém a ordem de inscrição para criar os pares
            N = len(atletas)
            for i in range(0, N, 2):
                if i + 1 < N:
                    # Par completo: Chong e Hong
                    apresentacao = {
                        "campeonato_id": camp_id, "categoria_id": cat_id, "modalidade": "Poomsae",
                        "ordem_luta": ordem_geral,
                        "atleta_vermelho": atletas[i]["nome"],      # Chong (Vermelho)
                        "atleta_azul": atletas[i+1]["nome"],        # Hong (Azul)
                        "status": "Aguardando Chamada"
                    }
                else:
                    # Atleta impar (só apresenta, sem oponente)
                    apresentacao = {
                        "campeonato_id": camp_id, "categoria_id": cat_id, "modalidade": "Poomsae",
                        "ordem_luta": ordem_geral,
                        "atleta_vermelho": atletas[i]["nome"],
                        "atleta_azul": "BYE (Avança Direto)",
                        "status": "Aguardando Chamada"
                    }
                lutas_geradas.append(apresentacao)
                ordem_geral += 1

    if lutas_geradas:
        await db.lutas.insert_many(lutas_geradas)

    for l in lutas_geradas:
        if "_id" in l: l["_id"] = str(l["_id"])

    return {"mensagem": f"Chaves e Fila de {dados.modalidade} geradas com sucesso!", "lutas": lutas_geradas}

# --- ROTAS PARA A TELA AO VIVO (LIVE) ---
@app.get("/api/campeonatos/{camp_id}")
async def obter_campeonato(camp_id: str):
    from bson.objectid import ObjectId
    camp = await db.campeonatos.find_one({"_id": ObjectId(camp_id)})
    if not camp:
        raise HTTPException(status_code=404, detail="Campeonato não encontrado")
    camp["_id"] = str(camp["_id"])
    return camp

@app.get("/api/campeonatos/{camp_id}/lutas")
async def listar_lutas(camp_id: str):
    # Busca todas as lutas e ordena pela ordem oficial
    cursor = db.lutas.find({"campeonato_id": camp_id}).sort("ordem_luta", 1)
    lutas = await cursor.to_list(length=2000)
    
    for l in lutas:
        l["_id"] = str(l["_id"])
        
    return lutas

@app.post("/api/campeonatos/{camp_id}/gerar-cronograma")
async def gerar_cronograma(camp_id: str, config: ConfigCronograma):
    await db.lutas.delete_many({"campeonato_id": camp_id}) # Limpa tudo para regerar

    inscricoes_cursor = db.inscricoes.find({"campeonato_id": camp_id, "status_pagamento": "Confirmado"}).sort("data_inscricao", 1)
    inscricoes = await inscricoes_cursor.to_list(length=3000)

    if not inscricoes:
        raise HTTPException(status_code=400, detail="Nenhum atleta confirmado.")

    # Puxa o nível do campeonato para a sigla (Equipe/Estado/País)
    from bson.objectid import ObjectId
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

    # 1. GERA AS LUTAS E APRESENTAÇÕES (com as regras matemáticas)
    for cat_id, info in categorias_dict.items():
        atletas = info["atletas"]
        modalidade = info["modalidade"]
        atletas.sort(key=lambda x: x["data"]) # Ordem de inscrição

        # Busca detalhes da categoria para saber o tempo
        cat_detalhes = next((c for c in campeonato["categorias"] if c["id"] == cat_id), None)
        is_preta = "Preta" in cat_detalhes["graduacao"] if cat_detalhes else False
        is_adulto = "Adulto" in cat_detalhes["idade_genero"] or "Sub 21" in cat_detalhes["idade_genero"] if cat_detalhes else False

        if modalidade == "Kyorugui":
            # Calcula a duração da luta + 5 min de transição
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
        else: # ✅ POOMSAE - Criar chaves 1v1 (Chong vs Hong)
            duracao = 8 if is_preta else 7
            N = len(atletas)
            for i in range(0, N, 2):
                if i + 1 < N:
                    # Par completo: Chong e Hong
                    todas_as_lutas_geradas.append({
                        "campeonato_id": camp_id, "categoria_id": cat_id, "modalidade": "Poomsae",
                        "atleta_vermelho": atletas[i]["nome"],      # Chong (Vermelho)
                        "atleta_azul": atletas[i+1]["nome"],        # Hong (Azul)
                        "status": "Aguardando Chamada", "duracao_min": duracao
                    })
                else:
                    # Atleta impar (só apresenta, sem oponente)
                    todas_as_lutas_geradas.append({
                        "campeonato_id": camp_id, "categoria_id": cat_id, "modalidade": "Poomsae",
                        "atleta_vermelho": atletas[i]["nome"],
                        "atleta_azul": "BYE (Avança Direto)",
                        "status": "Aguardando Chamada", "duracao_min": duracao
                    })

    # 2. DISTRIBUI NAS QUADRAS (CRONOGRAMA)
    # Inicializa os relógios das quadras
    hora_inicio_dt = datetime.strptime(config.horario_inicio, "%H:%M")
    quadras = [{"id": i+1, "tempo_atual": hora_inicio_dt, "tipo": "Mista"} for i in range(config.num_quadras)]
    
    if config.isolar_poomsae and config.num_quadras > 1:
        quadras[0]["tipo"] = "Poomsae"
        for i in range(1, config.num_quadras):
            quadras[i]["tipo"] = "Kyorugui"

    ordem_geral = 1
    # Para organizar melhor, agendamos Poomsae primeiro, depois Kyorugui
    todas_as_lutas_geradas.sort(key=lambda x: (x["modalidade"] == "Kyorugui", x["categoria_id"]))

    for luta in todas_as_lutas_geradas:
        luta["ordem_luta"] = ordem_geral
        ordem_geral += 1
        
        # Encontra a quadra certa
        quadras_compativeis = [q for q in quadras if q["tipo"] == "Mista" or q["tipo"] == luta["modalidade"]]
        if not quadras_compativeis:
            quadras_compativeis = quadras # Fallback se não tiver quadra compatível
        
        # Pega a quadra que libera mais cedo
        quadra_escolhida = min(quadras_compativeis, key=lambda q: q["tempo_atual"])
        
        luta["quadra"] = quadra_escolhida["id"]
        luta["horario_previsto"] = quadra_escolhida["tempo_atual"].strftime("%H:%M")
        
        # Avança o relógio da quadra
        quadra_escolhida["tempo_atual"] += timedelta(minutes=luta["duracao_min"])

    if todas_as_lutas_geradas:
        await db.lutas.insert_many(todas_as_lutas_geradas)

    for l in todas_as_lutas_geradas:
        if "_id" in l: l["_id"] = str(l["_id"])

    return {"mensagem": "Cronograma Oficial Gerado com Sucesso!", "lutas": todas_as_lutas_geradas}

@app.get("/api/usuarios/arbitros")
async def listar_arbitros_disponiveis():
    # FILTRO APLICADO AQUI: {"role": "arbitro"}
    cursor = db.users.find({"role": "arbitro"}).sort("nome", 1)
    usuarios = await cursor.to_list(length=1000)
    
    lista = []
    for u in usuarios:
        nome_completo = f"{u.get('nome', '')} {u.get('sobrenome', '')}".strip()
        lista.append({"email": u["email"], "nome": nome_completo})
        
    return lista

@app.get("/api/campeonatos/{camp_id}/quadras")
async def listar_equipes_quadras(camp_id: str):
    cursor = db.quadras.find({"campeonato_id": camp_id})
    quadras = await cursor.to_list(length=20)
    for q in quadras:
        q["_id"] = str(q["_id"])
    return quadras

@app.post("/api/campeonatos/{camp_id}/quadras")
async def salvar_equipe_quadra(camp_id: str, dados: EquipeQuadraData):
    # Atualiza a quadra se ela existir, ou cria uma nova (upsert=True)
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

@app.get("/api/usuarios")
async def listar_todos_usuarios():
    cursor = db.users.find({}).sort("nome", 1)
    usuarios = await cursor.to_list(length=2000)
    for u in usuarios:
        u["_id"] = str(u["_id"])
        u.pop("senha", None) # Remove a password por segurança antes de enviar para o Front!
    return usuarios

# 3. Rota NOVA: Atualiza a permissão (role) de um utilizador
@app.put("/api/usuarios/{usuario_id}/role")
async def atualizar_role_usuario(usuario_id: str, dados: UpdateRoleData):
    from bson.objectid import ObjectId
    resultado = await db.users.update_one(
        {"_id": ObjectId(usuario_id)},
        {"$set": {"role": dados.role}}
    )
    if resultado.matched_count == 0:
        raise HTTPException(status_code=404, detail="Utilizador não encontrado.")
    return {"mensagem": "Nível de acesso atualizado com sucesso!"}

# --- ROTAS PARA O LOBBY DA QUADRA ---
@app.get("/api/campeonatos/{camp_id}/minha-quadra/{email}")
async def obter_minha_quadra(camp_id: str, email: str):
    # Procura a quadra onde o email logado é o Mesário
    quadra = await db.quadras.find_one({"campeonato_id": camp_id, "mesario_email": email})
    
    if not quadra:
        raise HTTPException(status_code=404, detail="Você não está escalado como Mesário em nenhuma quadra neste evento.")
    
    quadra["_id"] = str(quadra["_id"])
    
    # Garante que os status de "ready" existam no documento (caso a quadra seja antiga)
    for i in range(1, 6):
        campo_ready = f"lateral{i}_ready"
        if campo_ready not in quadra:
            quadra[campo_ready] = False

    return quadra

@app.put("/api/campeonatos/{camp_id}/quadras/{num_quadra}/ready")
async def atualizar_ready_lateral(camp_id: str, num_quadra: int, dados: LateralReadyData):
    # Rota que o Joystick do lateral vai chamar para ficar verde no painel do mesário
    await db.quadras.update_one(
        {"campeonato_id": camp_id, "numero_quadra": num_quadra},
        {"$set": {f"{dados.lateral_slot}_ready": dados.is_ready}}
    )
    return {"mensagem": "Status de prontidão atualizado!"}

@app.get("/api/campeonatos/{camp_id}/quadras/{num_quadra}/proxima-luta")
async def buscar_proxima_luta(camp_id: str, num_quadra: int):
    # Busca a primeira luta da fila desta quadra que ainda não foi encerrada
    luta = await db.lutas.find_one(
        {"campeonato_id": camp_id, "quadra": num_quadra, "status": "Aguardando Chamada"},
        sort=[("ordem_luta", 1)]
    )
    
    if not luta:
        raise HTTPException(status_code=404, detail="Não há mais lutas na fila para esta quadra.")
        
    luta["_id"] = str(luta["_id"])
    
    # Cruza com os dados do campeonato para pegar o nome da categoria formatado
    from bson.objectid import ObjectId
    camp = await db.campeonatos.find_one({"_id": ObjectId(camp_id)})
    nome_cat = "Categoria Desconhecida"
    if camp and "categorias" in camp:
        for c in camp["categorias"]:
            if c["id"] == luta["categoria_id"]:
                nome_cat = f"{c.get('idade_genero', '')} | {c.get('graduacao', '').replace('_', ' ')} | {c.get('peso_ou_tipo', '')}"
                break
    luta["nome_categoria"] = nome_cat
    
    # Muda o status para "Em Andamento" logo ao puxar para a tela
    await db.lutas.update_one({"_id": ObjectId(luta["_id"])}, {"$set": {"status": "Em Andamento"}})
    
    return luta

@app.put("/api/lutas/{luta_id}/finalizar")
async def finalizar_luta_banco(luta_id: str, dados: FinalizarLutaData):
    from bson.objectid import ObjectId
    await db.lutas.update_one(
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
    return {"mensagem": "Luta encerrada salva no banco!"}

@app.post("/api/campeonatos/{camp_id}/sortear-poomsaes")
async def sortear_poomsaes_campeonato(camp_id: str):
    # Procura todas as lutas de Poomsae Faixa Preta neste campeonato
    lutas_poomsae = await db.lutas.find({"campeonato_id": camp_id, "modalidade": "Poomsae"}).to_list(length=1000)
    
    atualizados = 0
    for luta in lutas_poomsae:
        # Se for Freestyle, não sorteia os convencionais
        if "freestyle" in luta.get("nome_categoria", "").lower():
            await db.lutas.update_one({"_id": luta["_id"]}, {"$set": {"poomsae_1": "Poomsae Free Style", "poomsae_2": None}})
            continue
            
        # Verifica se é faixa colorida (Colorida faz o da faixa, não sorteia)
        if "colorida" in luta.get("nome_categoria", "").lower() or "gub" in luta.get("nome_categoria", "").lower():
            await db.lutas.update_one({"_id": luta["_id"]}, {"$set": {"poomsae_1": "Poomsae da Faixa Atual", "poomsae_2": None}})
            continue

        # Sorteio para Faixas Pretas
        cat_nome = luta.get("nome_categoria", "")
        grupo = "Adulto" # Default
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

# --- ROTA PARA O JOYSTICK DO LATERAL ---
@app.get("/api/campeonatos/{camp_id}/quadras/{num_quadra}/luta-atual")
async def obter_luta_atual(camp_id: str, num_quadra: int):
    # Procura a luta que o Mesário colocou como "Em Andamento"
    luta = await db.lutas.find_one({
        "campeonato_id": camp_id, 
        "quadra": num_quadra, 
        "status": "Em Andamento"
    })
    
    if not luta:
        raise HTTPException(status_code=404, detail="Nenhuma luta em andamento.")
        
    luta["_id"] = str(luta["_id"])
    return luta
