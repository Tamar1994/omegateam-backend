# 🏗️ Refatoração do Backend - Arquitetura Modular

## 📊 Status da Refatoração

✅ **Estrutura criada:**
- ✅ `config/settings.py` - Configurações centralizadas
- ✅ `database/connection.py` - Conexão com MongoDB
- ✅ `models/` - Modelos Pydantic organizados
- ✅ `services/` - Lógica de negócio isolada
- ✅ `routers/auth.py` - Rotas de autenticação
- ✅ `routers/users.py` - Rotas de usuários
- ✅ `routers/campeonatos.py` - Rotas de campeonatos
- ✅ `routers/uploads.py` - Rotas de upload
- ✅ `main_novo.py` - Novo main.py limpo

## 🎯 Arquitetura Atual vs. Nova

### Antes (main.py monolítico)
```
main.py (2000+ linhas)
├── Imports
├── Configurações
├── Modelos
├── Funções auxiliares
├── Rotas de autenticação
├── Rotas de usuários
├── Rotas de campeonatos
├── Rotas de inscrições
├── Rotas de lutas
├── Rotas de árbitros
└── Rotas de uploads
```

### Depois (Modular)
```
backend/
├── config/
│   └── settings.py          # Configurações
├── database/
│   └── connection.py        # Conexão DB
├── models/                  # Modelos Pydantic
│   ├── user.py
│   ├── campeonato.py
│   ├── inscricao.py
│   └── luta.py
├── services/                # Lógica de negócio
│   ├── auth_service.py
│   ├── email_service.py
│   └── [mais a criar]
├── routers/                 # Rotas organizadas
│   ├── auth.py
│   ├── users.py
│   ├── campeonatos.py
│   ├── uploads.py
│   └── [mais a criar]
└── main_novo.py            # App principal (limpo)
```

## 🚀 Como Migrar (Passo a Passo)

### Opção 1: Migração Gradual (RECOMENDADO)

1. **Manter o `main.py` original** como backup
2. **Testar o `main_novo.py`** localmente:
   ```bash
   # Ativar o venv
   .\venv\Scripts\Activate.ps1
   
   # Renomear
   mv main.py main_old.py
   mv main_novo.py main.py
   
   # Testar
   python -m uvicorn main:app --reload
   ```

3. **Ir completando os routers** faltantes:
   - `routers/inscricoes.py`
   - `routers/lutas.py`
   - `routers/arbitros.py`
   - `routers/quadras.py`

4. **Mover a lógica complexa** para services:
   - `services/chaves_service.py` - Geração de chaves
   - `services/cronograma_service.py` - Cronograma

### Opção 2: Migração Completa Agora

Copiar TODO o resto do código do `main.py` para os routers e services correspondentes.

## 📝 Próximas Etapas

### Criar os Routers Faltantes

#### `routers/inscricoes.py`
```python
@router.post("/inscricoes")
async def realizar_inscricao(dados: InscricaoData):
    ...

@router.get("/campeonatos/{camp_id}/inscricoes")
async def listar_inscricoes_campeonato(camp_id: str):
    ...

@router.put("/inscricoes/{inscricao_id}/status")
async def atualizar_status_inscricao(inscricao_id: str, dados: AtualizarStatusInscricao):
    ...
```

#### `routers/lutas.py`
```python
@router.post("/campeonatos/{camp_id}/gerar-chaves")
async def gerar_chaves(camp_id: str, dados: GerarChavesData):
    ...

@router.post("/campeonatos/{camp_id}/gerar-cronograma")
async def gerar_cronograma(camp_id: str, config: ConfigCronograma):
    ...

@router.get("/campeonatos/{camp_id}/lutas")
async def listar_lutas(camp_id: str):
    ...
```

#### `routers/arbitros.py`
```python
@router.get("/arbitro/{email}/campeonatos")
async def listar_campeonatos_arbitro(email: str):
    ...

@router.get("/campeonatos/{camp_id}/minha-quadra/{email}")
async def obter_minha_quadra(camp_id: str, email: str):
    ...
```

### Mover Lógica para Services

#### `services/chaves_service.py`
```python
async def gerar_chaves_kyorugui(inscricoes: list, categoria_id: str) -> list:
    """Gera as chaves matemáticas para Kyorugui"""
    ...

async def gerar_apresentacoes_poomsae(inscricoes: list, categoria_id: str) -> list:
    """Gera a ordem de apresentação para Poomsae"""
    ...
```

#### `services/cronograma_service.py`
```python
async def distribuir_lutas_quadras(lutas: list, num_quadras: int) -> list:
    """Distribui as lutas nas quadras com horários"""
    ...
```

## ✨ Benefícios da Nova Arquitetura

| Benefício | Antes | Depois |
|-----------|-------|--------|
| **Tamanho do main.py** | 2000+ linhas | ~100 linhas |
| **Manutenção** | Difícil | Fácil |
| **Testes** | Monolítico | Isolado por módulo |
| **Reutilização** | Baixa | Alta |
| **Escalabilidade** | Limitada | Excelente |
| **Onboarding** | Complexo | Simples |
| **Deploy** | Arriscado | Seguro |

## 📋 Checklist de Migração

- [ ] Testar `main_novo.py` localmente
- [ ] Criar `routers/inscricoes.py`
- [ ] Criar `routers/lutas.py`
- [ ] Criar `routers/arbitros.py`
- [ ] Criar `routers/quadras.py`
- [ ] Criar `services/chaves_service.py`
- [ ] Criar `services/cronograma_service.py`
- [ ] Testar todas as rotas
- [ ] Deploy em produção
- [ ] Remover `main_old.py`

## 🔗 Estrutura de Dependências

```
main.py (orquestra)
  ├─ config/settings.py (define constantes)
  ├─ database/connection.py (gerencia DB)
  └─ routers/ (cada router é independente)
      ├─ auth.py
      │   ├─ models/user.py
      │   ├─ services/auth_service.py
      │   └─ services/email_service.py
      ├─ users.py
      │   ├─ models/user.py
      │   └─ services/auth_service.py
      ├─ campeonatos.py
      │   ├─ models/campeonato.py
      │   └─ services/chaves_service.py (futura)
      └─ uploads.py
          └─ config/settings.py
```

## 📚 Recursos para Consulta

- **FastAPI Best Practices**: https://fastapi.tiangolo.com/best-practices/
- **Project Structure**: https://fullstackpython.com/application-programming-interfaces.html
- **Motor (Async MongoDB)**: https://motor.readthedocs.io/

---

**Próximo passo:** Criar os routers faltantes! Quer que eu continue?
