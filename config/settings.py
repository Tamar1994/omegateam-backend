"""
Configurações centralizadas da aplicação FastAPI
"""
import os
from dotenv import load_dotenv

# Carrega as variáveis de ambiente
load_dotenv()

# ==========================================
# CONFIGURAÇÕES DO BANCO DE DADOS
# ==========================================
MONGO_URI = os.getenv("MONGO_URI")
DATABASE_NAME = "omegateam"

# ==========================================
# CONFIGURAÇÕES DE EMAIL
# ==========================================
EMAIL_REMETENTE = os.getenv("EMAIL_REMETENTE")
SENHA_EMAIL = os.getenv("SENHA_EMAIL")
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# ==========================================
# CONFIGURAÇÕES DE CORS
# ==========================================
CORS_ORIGINS = [
    "http://localhost:5173",      # Frontend local
    "http://localhost:3000",      # Alternativa
    "https://omegateam-frontend.onrender.com"
    # Adicionar aqui quando fizer deploy
    # "https://seu-frontend.onrender.com",
]

# ==========================================
# CONFIGURAÇÕES DE UPLOADS
# ==========================================
PASTA_UPLOADS = "uploads/fotos_perfil"
PASTA_OFICIOS = "uploads/oficios"

# Cria as pastas automaticamente se não existirem
os.makedirs(PASTA_UPLOADS, exist_ok=True)
os.makedirs(PASTA_OFICIOS, exist_ok=True)

# ==========================================
# CONFIGURAÇÕES DE BACKEND URL (Para URLs nas respostas)
# ==========================================
BACKEND_BASE_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

# ==========================================
# POOMSAES OFICIAIS (WT - World Taekwondo)
# ==========================================
POOMSAES_WT = {
    "Cadete": ["Taegeuk 4 Jang", "Taegeuk 5 Jang", "Taegeuk 6 Jang", "Taegeuk 7 Jang", "Taegeuk 8 Jang", "Koryo", "Keumgang"],
    "Juvenil": ["Taegeuk 4 Jang", "Taegeuk 5 Jang", "Taegeuk 6 Jang", "Taegeuk 7 Jang", "Taegeuk 8 Jang", "Koryo", "Keumgang", "Taeback"],
    "Sub 30": ["Taegeuk 6 Jang", "Taegeuk 7 Jang", "Taegeuk 8 Jang", "Koryo", "Keumgang", "Taeback", "Pyongwon", "Shipjin"],
    "Sub 40": ["Taegeuk 6 Jang", "Taegeuk 7 Jang", "Taegeuk 8 Jang", "Koryo", "Keumgang", "Taeback", "Pyongwon", "Shipjin", "Jitae"],
    "Sub 50": ["Taegeuk 8 Jang", "Koryo", "Keumgang", "Taeback", "Pyongwon", "Shipjin", "Jitae", "Chonkwon"],
    "Master": ["Koryo", "Keumgang", "Taeback", "Pyongwon", "Shipjin", "Jitae", "Chonkwon", "Hansu"]
}
