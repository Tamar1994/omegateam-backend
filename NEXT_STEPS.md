# 🚀 Próximos Passos - Backend Refatoração

## 📋 Checklist para Completar a Migração

### Fase 1: Validar Nova Estrutura ✅ (Feita)
- [x] Criar estrutura de pastas
- [x] Separar modelos por domínio
- [x] Criar services de auth e email
- [x] Criar routers iniciais (auth, users, campeonatos, uploads)
- [x] Criar main.py limpo
- [x] Documentação

### Fase 2: Testar Localmente ⏳ (Próxima)
```bash
# No terminal PowerShell do VS Code:

# 1. Ativar venv
.\venv\Scripts\Activate.ps1

# 2. Renomear (backup)
mv main.py main_old.py

# 3. Renomear o novo
mv main_novo.py main.py

# 4. Testar se compila
python -m uvicorn main:app --reload

# 5. Testar endpoint
# GET http://localhost:8000/api/health
```

### Fase 3: Completar Routers Faltantes ⏳ (Depois)

**Arquivo:** `routers/inscricoes.py`
```python
# Copiar essas rotas do main_old.py:
- POST /api/inscricoes
- GET /api/campeonatos/{camp_id}/inscricoes
- PUT /api/inscricoes/{inscricao_id}/status
```

**Arquivo:** `routers/lutas.py`
```python
# Copiar:
- POST /api/campeonatos/{camp_id}/gerar-chaves
- POST /api/campeonatos/{camp_id}/gerar-cronograma
- GET /api/campeonatos/{camp_id}/lutas
- GET /api/campeonatos/{camp_id}/quadras/{num_quadra}/proxima-luta
- PUT /api/lutas/{luta_id}/finalizar
- PUT /api/campeonatos/{camp_id}/quadras/{num_quadra}/ready
- POST /api/campeonatos/{camp_id}/sortear-poomsaes
```

**Arquivo:** `routers/arbitros.py`
```python
# Copiar:
- GET /api/arbitro/{email}/campeonatos
- GET /api/campeonatos/{camp_id}/minha-quadra/{email}
```

**Arquivo:** `routers/quadras.py`
```python
# Copiar:
- GET /api/campeonatos/{camp_id}/quadras
- POST /api/campeonatos/{camp_id}/quadras
```

### Fase 4: Mover Lógica Complexa para Services ⏳ (Depois)

**Arquivo:** `services/chaves_service.py`
```python
async def gerar_chaves_kyorugui(inscricoes: list, categoria_id: str, nivel: str) -> list:
    """Gera chaves matemáticas para Kyorugui"""
    # Mover a lógica de calculo de BYEs, potências de 2, etc

async def gerar_apresentacoes_poomsae(inscricoes: list, categoria_id: str) -> list:
    """Gera ordem de apresentação para Poomsae"""
```

**Arquivo:** `services/cronograma_service.py`
```python
async def distribuir_lutas_nas_quadras(lutas: list, config: ConfigCronograma) -> list:
    """Distribui lutas nas quadras com horários automáticos"""
    # Mover a lógica de scheduling e horários
```

### Fase 5: Testes e Validação ⏳ (Depois)
```bash
# Testar cada rota
curl http://localhost:8000/api/health
curl http://localhost:8000/api/campeonatos
curl http://localhost:8000/api/usuarios
# ... etc
```

### Fase 6: Deploy ⏳ (Depois)
```bash
# Quando tudo estiver ok:
# 1. Commit no git (sem main_old.py)
# 2. Push para repositório
# 3. Redeploy no Render
```

---

## 📊 Estrutura Final

```
backend/
├── config/
│   ├── __init__.py
│   └── settings.py              ✅
├── database/
│   ├── __init__.py
│   └── connection.py            ✅
├── models/
│   ├── __init__.py
│   ├── user.py                  ✅
│   ├── campeonato.py            ✅
│   ├── inscricao.py             ✅
│   └── luta.py                  ✅
├── services/
│   ├── __init__.py
│   ├── auth_service.py          ✅
│   ├── email_service.py         ✅
│   ├── chaves_service.py        ⏳
│   └── cronograma_service.py    ⏳
├── routers/
│   ├── __init__.py
│   ├── auth.py                  ✅
│   ├── users.py                 ✅
│   ├── campeonatos.py           ✅
│   ├── uploads.py               ✅
│   ├── inscricoes.py            ⏳
│   ├── lutas.py                 ⏳
│   ├── arbitros.py              ⏳
│   └── quadras.py               ⏳
├── utils/
│   ├── __init__.py
│   └── helpers.py               ✅
├── uploads/                      (pasta)
├── main.py                      (original - backup temporário)
├── main_novo.py                 (novo - será main.py)
├── REFACTORING_GUIDE.md         ✅
├── NEXT_STEPS.md                ✅ (este arquivo)
└── requirements.txt
```

---

## 🎯 Estimativa de Tempo

| Etapa | Tempo |
|-------|-------|
| Fase 2 (Testar) | 30 min |
| Fase 3 (Routers) | 2-3 horas |
| Fase 4 (Services) | 2-3 horas |
| Fase 5 (Testes) | 1-2 horas |
| Fase 6 (Deploy) | 30 min |
| **Total** | **6-9 horas** |

---

## 💡 Dicas Importantes

1. **Não apague `main_old.py` ainda** - Mantenha como referência enquanto migra
2. **Copie rota por rota** - Não tente migrar tudo de uma vez
3. **Teste cada router** - Após criar cada um, teste o endpoint
4. **Use imports relativos** - `from database.connection import get_db`
5. **Manter o banco em sync** - Não altere o schema do MongoDB

---

## 📞 Suporte

Se tiver dúvidas:
1. Consulte `REFACTORING_GUIDE.md`
2. Verifique a estrutura de pastas
3. Compare com um router que já foi feito (auth.py)

**Pronto para começar!** 🚀
