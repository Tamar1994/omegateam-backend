"""
Rotas de Upload (Fotos de perfil e Ofícios)
"""
import os
import uuid
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
import aiofiles
from config.settings import PASTA_UPLOADS, PASTA_OFICIOS, BACKEND_BASE_URL
from database.connection import get_db

router = APIRouter(prefix="/api", tags=["Uploads"])


@router.post("/upload-foto")
async def upload_foto_perfil(email: str = Form(...), foto: UploadFile = File(...), db: AsyncIOMotorDatabase = Depends(get_db)):
    """Upload da foto de perfil do usuário"""
    try:
        # Pega a extensão original do arquivo
        extensao = os.path.splitext(foto.filename)[1]
        
        # Cria um nome único usando o e-mail
        nome_arquivo = f"{email.replace('@', '_')}{extensao}"
        caminho_completo = os.path.join(PASTA_UPLOADS, nome_arquivo)
        
        # Salva o arquivo fisicamente na pasta
        async with aiofiles.open(caminho_completo, 'wb') as out_file:
            conteudo = await foto.read()
            await out_file.write(conteudo)
            
        # Atualiza a URL da foto no banco de dados
        url_foto = f"{BACKEND_BASE_URL}/uploads/fotos_perfil/{nome_arquivo}"
        await db.users.update_one(
            {"email": email}, 
            {"$set": {"foto": url_foto}}
        )
        
        return {"mensagem": "Foto atualizada com sucesso", "url_foto": url_foto}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao salvar foto: {str(e)}")


@router.post("/upload-oficio")
async def upload_oficio(arquivo: UploadFile = File(...), db: AsyncIOMotorDatabase = Depends(get_db)):
    """Upload do ofício do campeonato"""
    try:
        extensao = os.path.splitext(arquivo.filename)[1]
        nome_arquivo = f"oficio_{uuid.uuid4().hex}{extensao}"
        caminho_completo = os.path.join(PASTA_OFICIOS, nome_arquivo)
        
        async with aiofiles.open(caminho_completo, 'wb') as out_file:
            conteudo = await arquivo.read()
            await out_file.write(conteudo)
            
        url_oficio = f"{BACKEND_BASE_URL}/oficios/{nome_arquivo}"
        return {"url": url_oficio}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail="Erro ao salvar o ofício.")
