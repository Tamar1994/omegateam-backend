"""
Rotas de Joystick com WebSocket para Árbitros Laterais (Tempo Real)
"""
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from database.connection import get_db
from services.joystick_service import joystick_manager
import asyncio

router = APIRouter(prefix="/api", tags=["Joystick"])

# Gerenciador de conexões WebSocket
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict = {}  # {campeonato_id: {lateral_email: websocket}}
        self.mesario_connections: dict = {}  # {luta_id: websocket}
    
    async def connect(self, campeonato_id: str, lateral_email: str, websocket: WebSocket):
        """Conecta um árbitro lateral ao WebSocket"""
        try:
            print(f"  [ACEITANDO] WebSocket...")
            await websocket.accept()
            print(f"  [ACEITO] WebSocket aceito com sucesso!")
            
            if campeonato_id not in self.active_connections:
                self.active_connections[campeonato_id] = {}
            
            self.active_connections[campeonato_id][lateral_email] = websocket
            print(f"✅ LATERAL CONECTADO: {lateral_email} → campeonato {campeonato_id}")
            print(f"   Conexões ativas neste campeonato: {list(self.active_connections[campeonato_id].keys())}")
        except Exception as e:
            print(f"❌ ERRO AO ACEITAR WEBSOCKET: {type(e).__name__}: {e}")
            raise
    
    async def connect_mesario(self, luta_id: str, numero_quadra: int, websocket: WebSocket):
        """Conecta o Mesário ao WebSocket"""
        await websocket.accept()
        self.mesario_connections[f"{luta_id}:{numero_quadra}"] = websocket
        print(f"✅ Mesário da quadra {numero_quadra} conectado à luta {luta_id}")
    
    def disconnect(self, campeonato_id: str, lateral_email: str):
        """Desconecta um árbitro lateral"""
        if campeonato_id in self.active_connections:
            if lateral_email in self.active_connections[campeonato_id]:
                del self.active_connections[campeonato_id][lateral_email]
            
            if not self.active_connections[campeonato_id]:
                del self.active_connections[campeonato_id]
        
        print(f"❌ Lateral {lateral_email} desconectado do campeonato {campeonato_id}")
    
    def disconnect_mesario(self, luta_id: str, numero_quadra: int):
        """Desconecta o Mesário"""
        key = f"{luta_id}:{numero_quadra}"
        if key in self.mesario_connections:
            del self.mesario_connections[key]
        
        print(f"❌ Mesário da quadra {numero_quadra} desconectado da luta {luta_id}")
    
    async def broadcast_to_luta(self, campeonato_id: str, message: dict):
        """Envia mensagem para todos os árbitros de um campeonato"""
        if campeonato_id not in self.active_connections:
            return
        
        for lateral_email, websocket in list(self.active_connections[campeonato_id].items()):
            try:
                await websocket.send_json(message)
            except Exception as e:
                print(f"❌ Erro ao enviar para {lateral_email}: {e}")
                self.disconnect(campeonato_id, lateral_email)
    
    async def broadcast_to_all_mesarios(self, message: dict):
        """Envia mensagem para TODOS os Mesários conectados"""
        for key, websocket in list(self.mesario_connections.items()):
            try:
                await websocket.send_json(message)
            except Exception as e:
                print(f"❌ Erro ao enviar para Mesário {key}: {e}")
                luta_id, numero_quadra = key.split(":")
                self.disconnect_mesario(luta_id, int(numero_quadra))
    
    async def notificar_status_laterais(self, campeonato_id: str):
        """Notifica o Mesário que o status dos laterais mudou (alguém conectou/desconectou)"""
        # Pega lista de laterais conectados
        laterais_conectados = list(self.active_connections.get(campeonato_id, {}).keys()) if campeonato_id in self.active_connections else []
        
        mensagem = {
            "status": "laterais_atualizacao",
            "campeonato_id": campeonato_id,
            "laterais_conectados": laterais_conectados,
            "total_laterais": len(laterais_conectados),
            "timestamp": __import__('datetime').datetime.now().isoformat()
        }
        
        # Enviar para TODOS os Mesários desta luta
        for key, websocket in list(self.mesario_connections.items()):
            # Nota: Mesário armazena como "luta_id:numero_quadra", vamos enviar para todos por enquanto
            try:
                await websocket.send_json(mensagem)
            except Exception as e:
                print(f"❌ Erro ao notificar Mesário {key}: {e}")

    async def notificar_luta_iniciada(self, campeonato_id: str, luta_data: dict):
        """
        🎬 Notifica TODOS os laterais sobre luta iniciada
        
        Envia:
        {
            "status": "luta_iniciada",
            "luta_id": luta_id,
            "modalidade": "Kyorugui" ou "Poomsae",
            "atleta_vermelho": "Nome",
            "atleta_azul": "Nome",
            "timestamp": ISO
        }
        """
        print(f"\n{'='*60}")
        print(f"🎬 NOTIFICANDO LATERAIS - LUTA INICIADA")
        print(f"{'='*60}")
        print(f"  Campeonato ID: {campeonato_id}")
        print(f"  Luta Data: {luta_data}")
        
        # Verificar conexões ativas
        laterais_conectados = list(self.active_connections.get(campeonato_id, {}).keys()) if campeonato_id in self.active_connections else []
        print(f"  Laterais conectados neste campeonato: {laterais_conectados}")
        print(f"  Total: {len(laterais_conectados)}")
        
        mensagem = {
            "status": "luta_iniciada",
            "luta_id": luta_data.get("luta_id"),
            "modalidade": luta_data.get("modalidade", "Kyorugui"),
            "atleta_vermelho": luta_data.get("atleta_vermelho", "Atleta 1"),
            "atleta_azul": luta_data.get("atleta_azul", "Atleta 2"),
            "timestamp": __import__('datetime').datetime.now().isoformat()
        }

        # Enviar para TODOS os laterais deste campeonato
        if campeonato_id in self.active_connections:
            for lateral_email, websocket in list(self.active_connections[campeonato_id].items()):
                try:
                    print(f"  📤 Enviando luta_iniciada para {lateral_email}...")
                    await websocket.send_json(mensagem)
                    print(f"  ✅ Enviado com sucesso para {lateral_email}")
                except Exception as e:
                    print(f"  ❌ Erro ao notificar lateral {lateral_email}: {e}")
        else:
            print(f"  ⚠️ Nenhuma conexão ativa para campeonato {campeonato_id}")
        
        print(f"{'='*60}\n")


# Instância global de gerenciador de conexões
manager = ConnectionManager()


@router.websocket("/ws/lateral/{campeonato_id}/{lateral_email}")
async def websocket_lateral(websocket: WebSocket, campeonato_id: str, lateral_email: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """
    WebSocket para árbitro lateral enviar pontos e receber confirmações.
    
    Fluxo:
    1. Lateral conecta ao WebSocket (identificado por campeonato_id, não luta_id)
    2. Lateral carrega em botão ("+1", "+2", "+3")
    3. Servidor registra clique e aguarda coincidência
    4. Se houver coincidência (2+ árbitros), ponto é validado
    5. Confirmação é enviada de volta para todos os laterais
    """
    print(f"\n{'='*60}")
    print(f"🔌 WEBSOCKET LATERAL - TENTATIVA DE CONEXÃO")
    print(f"{'='*60}")
    print(f"  Hora: {__import__('datetime').datetime.now().isoformat()}")
    print(f"  Campeonato ID: {campeonato_id}")
    print(f"  Email: {lateral_email}")
    print(f"  Headers: {dict(websocket.headers)}")
    print(f"{'='*60}\n")
    
    try:
        await manager.connect(campeonato_id, lateral_email, websocket)
        print(f"✅ CONEXÃO ACEITA: lateral={lateral_email}, campeonato={campeonato_id}")
        
        # 🔔 NOTIFICAR O MESÁRIO QUE UM LATERAL CONECTOU
        await manager.notificar_status_laterais(campeonato_id)
    except Exception as e:
        print(f"❌ ERRO AO CONECTAR: {e}")
        raise
    
    try:
        while True:
            # Receber mensagem do lateral
            data = await websocket.receive_json()
            
            # ✅ IMPORTANTE: Extrair luta_id da mensagem (enviado pelo frontend)
            luta_id = data.get("luta_id")
            if not luta_id and data.get("tipo") != "lateral_pronto":
                # Para pontos, luta_id é obrigatório
                await websocket.send_json({
                    "status": "erro",
                    "mensagem": "luta_id não encontrado na mensagem"
                })
                continue
            
            # ✋ HANDLER: Lateral marca como pronto
            if data.get("tipo") == "lateral_pronto":
                print(f"\n{'='*60}")
                print(f"✋ LATERAL MARCANDO COMO PRONTO")
                print(f"{'='*60}")
                print(f"  Email: {lateral_email}")
                print(f"  Campeonato: {campeonato_id}")
                print(f"  Timestamp: {data.get('timestamp')}")
                
                # 🔍 Procurar qual quadra tem este lateral
                quadra = await db.quadras.find_one({
                    "campeonato_id": campeonato_id,
                    "$or": [
                        {"lateral1_email": lateral_email},
                        {"lateral2_email": lateral_email},
                        {"lateral3_email": lateral_email},
                        {"lateral4_email": lateral_email},
                        {"lateral5_email": lateral_email}
                    ]
                })
                
                if quadra:
                    # 🎯 Encontrar qual slot (1-5) este lateral ocupa
                    numero_quadra = quadra.get("numero_quadra")
                    lateral_slot = None
                    for i in range(1, 6):
                        if quadra.get(f"lateral{i}_email") == lateral_email:
                            lateral_slot = i
                            break
                    
                    if lateral_slot:
                        # ✅ Atualizar no banco: lateral{N}_ready = true
                        await db.quadras.update_one(
                            {"campeonato_id": campeonato_id, "numero_quadra": numero_quadra},
                            {"$set": {f"lateral{lateral_slot}_ready": True}}
                        )
                        print(f"  ✅ Marcado como pronto: lateral{lateral_slot} na quadra {numero_quadra}")
                        print(f"{'='*60}\n")
                        
                        # 📡 Notificar Mesário que status mudou
                        asyncio.create_task(manager.notificar_status_laterais(campeonato_id))
                        
                        # ✅ Confirmar para o lateral
                        await websocket.send_json({
                            "status": "pronto_confirmado",
                            "mensagem": "Você está pronto para a luta!",
                            "timestamp": data.get("timestamp")
                        })
                    else:
                        print(f"  ❌ Não encontrou qual slot o lateral ocupa")
                        print(f"{'='*60}\n")
                else:
                    print(f"  ❌ Nenhuma quadra encontrada com este lateral")
                    print(f"{'='*60}\n")
                
                continue
            
            # Validar dados para pontos
            if "tipo_ponto" not in data or "cor" not in data:
                await websocket.send_json({
                    "status": "erro",
                    "mensagem": "Faltam campos: tipo_ponto e cor"
                })
                continue
            
            tipo_ponto = data["tipo_ponto"]  # "+1", "+2", "+3"
            cor = data["cor"]  # "vermelho" ou "azul"
            
            # 📊 Contar quantos laterais conectados para validação por maioria
            total_laterais_conectados = len(manager.active_connections.get(campeonato_id, {}))
            
            # Registrar clique e verificar validação (MAIORIA ABSOLUTA)
            ponto_validado = joystick_manager.registrar_clique_lateral(
                luta_id=luta_id,
                lateral_email=lateral_email,
                tipo_ponto=tipo_ponto,
                cor=cor,
                total_laterais=total_laterais_conectados  # ✅ Passa o total de laterais
            )
            
            # Enviar confirmação de recebimento ao lateral
            await websocket.send_json({
                "status": "clique_recebido",
                "tipo_ponto": tipo_ponto,
                "cor": cor,
                "timestamp": data.get("timestamp")
            })
            
            # Se ponto foi validado, enviar para todos
            if ponto_validado:
                mensagem_validacao = {
                    "status": "ponto_validado",
                    "luta_id": luta_id,
                    "cor": ponto_validado["cor"],
                    "pontos": ponto_validado["pontos"],
                    "arbitros_confirmados": ponto_validado["arbitros_confirmados"],
                    "validado_em": ponto_validado["validado_em"]
                }
                
                # Broadcast para todos os laterais deste campeonato
                await manager.broadcast_to_luta(campeonato_id, mensagem_validacao)
                
                # Broadcast para todos os Mesários
                await manager.broadcast_to_all_mesarios(mensagem_validacao)
    
    except WebSocketDisconnect:
        print(f"\n{'='*60}")
        print(f"❌ WEBSOCKET LATERAL DESCONECTADO")
        print(f"{'='*60}")
        print(f"  Hora: {__import__('datetime').datetime.now().isoformat()}")
        print(f"  Lateral: {lateral_email}")
        print(f"  Campeonato: {campeonato_id}")
        print(f"{'='*60}\n")
        manager.disconnect(campeonato_id, lateral_email)
        
        # � RESETAR O READY DO LATERAL QUE DESCONECTOU
        quadra = await db.quadras.find_one({
            "campeonato_id": campeonato_id,
            "$or": [
                {"lateral1_email": lateral_email},
                {"lateral2_email": lateral_email},
                {"lateral3_email": lateral_email},
                {"lateral4_email": lateral_email},
                {"lateral5_email": lateral_email}
            ]
        })
        
        if quadra:
            numero_quadra = quadra.get("numero_quadra")
            for i in range(1, 6):
                if quadra.get(f"lateral{i}_email") == lateral_email:
                    # ❌ Resetar ready para false
                    await db.quadras.update_one(
                        {"campeonato_id": campeonato_id, "numero_quadra": numero_quadra},
                        {"$set": {f"lateral{i}_ready": False}}
                    )
                    print(f"  🔴 Resetado: lateral{i}_ready = False (lateral desconectou)")
                    break
        
        # �🔔 NOTIFICAR O MESÁRIO QUE UM LATERAL DESCONECTOU
        asyncio.create_task(manager.notificar_status_laterais(campeonato_id))
    except Exception as e:
        print(f"\n{'='*60}")
        print(f"❌ ERRO INESPERADO NO WEBSOCKET LATERAL")
        print(f"{'='*60}")
        print(f"  Tipo de erro: {type(e).__name__}")
        print(f"  Mensagem: {e}")
        print(f"  Lateral: {lateral_email}")
        print(f"  Campeonato: {campeonato_id}")
        print(f"{'='*60}\n")
        manager.disconnect(campeonato_id, lateral_email)
        
        # � RESETAR O READY DO LATERAL (POR ERRO)
        quadra = await db.quadras.find_one({
            "campeonato_id": campeonato_id,
            "$or": [
                {"lateral1_email": lateral_email},
                {"lateral2_email": lateral_email},
                {"lateral3_email": lateral_email},
                {"lateral4_email": lateral_email},
                {"lateral5_email": lateral_email}
            ]
        })
        
        if quadra:
            numero_quadra = quadra.get("numero_quadra")
            for i in range(1, 6):
                if quadra.get(f"lateral{i}_email") == lateral_email:
                    # ❌ Resetar ready para false
                    await db.quadras.update_one(
                        {"campeonato_id": campeonato_id, "numero_quadra": numero_quadra},
                        {"$set": {f"lateral{i}_ready": False}}
                    )
                    print(f"  🔴 Resetado: lateral{i}_ready = False (erro na conexão)")
                    break
        
        # �🔔 NOTIFICAR O MESÁRIO QUE UM LATERAL FOI DESCONECTADO (POR ERRO)
        asyncio.create_task(manager.notificar_status_laterais(campeonato_id))
        raise


@router.websocket("/ws/poomsae/{luta_id}/{juiz_email}")
async def websocket_poomsae(websocket: WebSocket, luta_id: str, juiz_email: str):
    """
    WebSocket para juiz lateral enviar nota de Poomsae.
    
    Fluxo:
    1. Juiz conecta
    2. Juiz seleciona nota (0-10)
    3. Servidor registra e aguarda outros juízes
    4. Quando todas as notas chegam, calcula média
    5. Resultado é enviado para Mesário
    """
    await websocket.accept()
    
    try:
        # Enviar confirmação de conexão
        await websocket.send_json({
            "status": "conectado",
            "mensagem": "Aguardando sua nota de Poomsae"
        })
        
        # Receber nota do juiz
        data = await websocket.receive_json()
        
        if "nota" not in data:
            await websocket.send_json({
                "status": "erro",
                "mensagem": "Campo 'nota' é obrigatório"
            })
            await websocket.close()
            return
        
        try:
            nota = float(data["nota"])
            
            # Registrar nota
            resultado = joystick_manager.registrar_nota_poomsae(
                luta_id=luta_id,
                juiz_email=juiz_email,
                nota=nota
            )
            
            # Enviar confirmação ao juiz
            await websocket.send_json({
                "status": "nota_registrada",
                "nota": nota,
                "notas_recebidas": resultado["notas_recebidas"],
                "notas_esperadas": resultado["notas_esperadas"]
            })
            
            # Se todas as notas foram recebidas, enviar resultado
            if resultado["status"] == "completo":
                relatorio = resultado.get("relatorio", {})
                await websocket.send_json({
                    "status": "resultado_final",
                    "nota_final": relatorio.get("nota_final"),
                    "relatorio": relatorio
                })
        
        except ValueError as e:
            await websocket.send_json({
                "status": "erro",
                "mensagem": str(e)
            })
    
    except WebSocketDisconnect:
        print(f"Juiz {juiz_email} desconectado da sessão Poomsae {luta_id}")


@router.post("/lutas/{luta_id}/notificar-fim-luta")
async def notificar_fim_luta(luta_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """
    Notifica TODOS os laterais que a luta foi FINALIZADA.
    Chamado pelo Mesário ao encerrar a luta.
    
    Envia:
    {
        "status": "luta_finalizada",
        "luta_id": luta_id,
        "timestamp": ISO
    }
    """
    print(f"\n{'='*60}")
    print(f"🎬 NOTIFICANDO LATERAIS - LUTA FINALIZADA")
    print(f"{'='*60}")
    print(f"  Luta ID: {luta_id}")
    
    # Procurar a luta para pegar campeonato_id
    try:
        luta = await db.lutas.find_one({"_id": ObjectId(luta_id)})
    except:
        luta = await db.lutas.find_one({"_id": luta_id})
    
    if not luta:
        print(f"  ❌ Luta não encontrada")
        print(f"{'='*60}\n")
        return {"status": "erro", "mensagem": "Luta não encontrada"}
    
    campeonato_id = luta.get("campeonato_id")
    
    mensagem = {
        "status": "luta_finalizada",
        "luta_id": luta_id,
        "timestamp": __import__('datetime').datetime.now().isoformat()
    }
    
    # Enviar para TODOS os laterais deste campeonato
    laterais_notificados = 0
    if campeonato_id in manager.active_connections:
        for lateral_email, websocket in list(manager.active_connections[campeonato_id].items()):
            try:
                await websocket.send_json(mensagem)
                print(f"  📤 Enviando para {lateral_email}... ✅")
                laterais_notificados += 1
            except Exception as e:
                print(f"  ❌ Erro ao notificar lateral {lateral_email}: {e}")
    
    print(f"  ✅ Notificação enviada para {laterais_notificados} laterais")
    print(f"{'='*60}\n")
    
    return {
        "status": "ok",
        "mensagem": "Luta finalizada notificada",
        "laterais_notificados": laterais_notificados
    }


@router.websocket("/ws/mesario/{luta_id}/{numero_quadra}")
async def websocket_mesario(websocket: WebSocket, luta_id: str, numero_quadra: int):
    """
    WebSocket para Mesário receber pontos validados em tempo real.
    
    Fluxo:
    1. Mesário conecta ao WebSocket
    2. Aguarda mensagens de pontos validados dos laterais
    3. Quando um ponto é validado pela Coincidence Window, recebe notificação
    4. Atualiza automaticamente o placar
    """
    print(f"\n{'='*60}")
    print(f"🔌 WEBSOCKET MESARIO - TENTATIVA DE CONEXÃO")
    print(f"{'='*60}")
    print(f"  Hora: {__import__('datetime').datetime.now().isoformat()}")
    print(f"  Luta ID: {luta_id}")
    print(f"  Número Quadra: {numero_quadra}")
    print(f"  Headers: {dict(websocket.headers)}")
    print(f"{'='*60}\n")
    
    try:
        await manager.connect_mesario(luta_id, numero_quadra, websocket)
    except Exception as e:
        print(f"❌ ERRO AO CONECTAR MESARIO: {e}")
        raise
    
    try:
        while True:
            # Manter conexão aberta e aguardar mensagens
            data = await websocket.receive_json()
            
            # Se receber "ping", responder com "pong"
            if data.get("tipo") == "ping":
                await websocket.send_json({"tipo": "pong"})
    
    except WebSocketDisconnect:
        print(f"\n{'='*60}")
        print(f"❌ WEBSOCKET MESARIO DESCONECTADO")
        print(f"{'='*60}")
        print(f"  Hora: {__import__('datetime').datetime.now().isoformat()}")
        print(f"  Luta: {luta_id}")
        print(f"  Quadra: {numero_quadra}")
        print(f"{'='*60}\n")
        manager.disconnect_mesario(luta_id, numero_quadra)
        manager.disconnect_mesario(luta_id, numero_quadra)


# ===== ENDPOINTS HTTP (complementares) =====

@router.post("/lutas/{luta_id}/joystick/iniciar-kyorugui")
async def iniciar_kyorugui(luta_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Inicia uma nova janela de coincidência para Kyorugui"""
    joystick_manager.criar_janela_coincidencia(luta_id)
    
    return {
        "status": "iniciado",
        "luta_id": luta_id,
        "tipo": "kyorugui",
        "janela_duracao_ms": 1500
    }


@router.post("/lutas/{luta_id}/joystick/iniciar-poomsae")
async def iniciar_poomsae(
    luta_id: str, 
    numero_juizes: int = 3,
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Inicia uma nova sessão de Poomsae"""
    sessao = joystick_manager.criar_sessao_poomsae(luta_id, numero_juizes)
    
    return {
        "status": "iniciado",
        "luta_id": luta_id,
        "tipo": "poomsae",
        "numero_juizes": numero_juizes,
        "timeout_segundos": sessao.timeout_segundos
    }


@router.get("/lutas/{luta_id}/joystick/status-poomsae")
async def status_poomsae(luta_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Obtém status atual da sessão de Poomsae"""
    status = joystick_manager.obter_status_poomsae(luta_id)
    return status


@router.get("/lutas/{luta_id}/joystick/conexoes-ativas")
async def conexoes_ativas(luta_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Lista árbitros laterais conectados a uma luta"""
    if luta_id not in manager.active_connections:
        return {"luta_id": luta_id, "laterais_conectado": []}
    
    laterais = list(manager.active_connections[luta_id].keys())
    
    return {
        "luta_id": luta_id,
        "laterais_conectados": laterais,
        "total": len(laterais)
    }


@router.get("/joystick/health")
async def joystick_health():
    """Health check para o sistema de WebSocket do Joystick"""
    import fastapi
    import starlette
    
    return {
        "status": "ok",
        "mensagem": "Sistema de Joystick está pronto para WebSocket",
        "diagnostico": {
            "fastapi_version": fastapi.__version__,
            "starlette_version": starlette.__version__,
            "websocket_suportado": True,
            "tempo_servidor": __import__('datetime').datetime.now().isoformat()
        },
        "websocket_endpoints": [
            "/api/ws/lateral/{luta_id}/{lateral_email}",
            "/api/ws/mesario/{luta_id}/{numero_quadra}",
            "/api/ws/poomsae/{luta_id}/{juiz_email}"
        ],
        "conexoes_ativas": {
            "laterais": sum(len(emails) for emails in manager.active_connections.values()),
            "mesarios": len(manager.mesario_connections),
            "lutas_ativas": len(manager.active_connections),
            "detalhe_laterais": {
                luta_id: list(emails.keys()) 
                for luta_id, emails in manager.active_connections.items()
            }
        },
        "dicas_para_debug": [
            "Se receber erro 1006: verifique se o servidor está rodando",
            "WebSocket requer upgrade HTTP 101, verificar proxy/firewall",
            "URL deve usar wss:// em produção (Render com https)"
        ]
    }


@router.post("/lutas/{luta_id}/notificar-laterais")
async def notificar_laterais_luta_iniciada(luta_id: str, dados: dict, db: AsyncIOMotorDatabase = Depends(get_db)):
    """
    🎬 Notifica todos os laterais que a luta iniciou
    
    Chamado pelo Mesário quando puxa a próxima luta.
    Envia modalidade (Kyorugui/Poomsae) e dados do atletas para lateral renderizar joystick correto.
    """
    from bson import ObjectId
    
    print(f"\n{'='*60}")
    print(f"🎬 NOTIFICANDO LATERAIS SOBRE LUTA INICIADA")
    print(f"{'='*60}")
    print(f"  Luta ID: {luta_id}")
    print(f"  Dados: {dados}")
    
    try:
        # ⚠️ IMPORTANTE: Buscar a luta no banco para descobrir seu campeonato_id
        # Os laterals conectam via campeonato_id, não via luta_id!
        luta = await db.lutas.find_one({"_id": ObjectId(luta_id)})
        
        if not luta:
            raise HTTPException(status_code=404, detail="Luta não encontrada")
        
        campeonato_id = luta.get("campeonato_id")
        print(f"  Campeonato ID: {campeonato_id}")
        
        # Prepara dados da luta para enviar
        luta_data = {
            "luta_id": luta_id,  # ✅ Enviar luta_id também para frontend
            "modalidade": dados.get("modalidade", "Kyorugui"),
            "atleta_vermelho": dados.get("atleta_vermelho", "Atleta 1"),
            "atleta_azul": dados.get("atleta_azul", "Atleta 2")
        }
        
        # ✅ Notifica laterals usando campeonato_id (assim encontra as conexões)
        await manager.notificar_luta_iniciada(campeonato_id, luta_data)
        
        print(f"✅ Notificação enviada para laterais")
        print(f"{'='*60}\n")
        
        return {
            "status": "sucesso",
            "mensagem": "Laterais notificados sobre luta iniciada",
            "luta_id": luta_id,
            "campeonato_id": campeonato_id,
            "luta_data": luta_data
        }
    except Exception as e:
        print(f"❌ ERRO ao notificar laterais: {e}")
        print(f"{'='*60}\n")
        raise HTTPException(status_code=500, detail=f"Erro ao notificar laterais: {str(e)}")
