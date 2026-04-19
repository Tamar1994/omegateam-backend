"""
Rotas de Joystick com WebSocket para Árbitros Laterais (Tempo Real)
"""
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from database.connection import get_db
from services.joystick_service import joystick_manager
import asyncio

router = APIRouter(prefix="/api", tags=["Joystick"])

# Gerenciador de conexões WebSocket
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict = {}  # {luta_id: {lateral_email: websocket}}
        self.mesario_connections: dict = {}  # {luta_id: websocket}
    
    async def connect(self, luta_id: str, lateral_email: str, websocket: WebSocket):
        """Conecta um árbitro lateral ao WebSocket"""
        try:
            print(f"  [ACEITANDO] WebSocket...")
            await websocket.accept()
            print(f"  [ACEITO] WebSocket aceito com sucesso!")
            
            if luta_id not in self.active_connections:
                self.active_connections[luta_id] = {}
            
            self.active_connections[luta_id][lateral_email] = websocket
            print(f"✅ LATERAL CONECTADO: {lateral_email} → luta {luta_id}")
            print(f"   Conexões ativas nesta luta: {list(self.active_connections[luta_id].keys())}")
        except Exception as e:
            print(f"❌ ERRO AO ACEITAR WEBSOCKET: {type(e).__name__}: {e}")
            raise
    
    async def connect_mesario(self, luta_id: str, numero_quadra: int, websocket: WebSocket):
        """Conecta o Mesário ao WebSocket"""
        await websocket.accept()
        self.mesario_connections[f"{luta_id}:{numero_quadra}"] = websocket
        print(f"✅ Mesário da quadra {numero_quadra} conectado à luta {luta_id}")
    
    def disconnect(self, luta_id: str, lateral_email: str):
        """Desconecta um árbitro lateral"""
        if luta_id in self.active_connections:
            if lateral_email in self.active_connections[luta_id]:
                del self.active_connections[luta_id][lateral_email]
            
            if not self.active_connections[luta_id]:
                del self.active_connections[luta_id]
        
        print(f"❌ Lateral {lateral_email} desconectado da luta {luta_id}")
    
    def disconnect_mesario(self, luta_id: str, numero_quadra: int):
        """Desconecta o Mesário"""
        key = f"{luta_id}:{numero_quadra}"
        if key in self.mesario_connections:
            del self.mesario_connections[key]
        
        print(f"❌ Mesário da quadra {numero_quadra} desconectado da luta {luta_id}")
    
    async def broadcast_to_luta(self, luta_id: str, message: dict):
        """Envia mensagem para todos os árbitros de uma luta"""
        if luta_id not in self.active_connections:
            return
        
        for lateral_email, websocket in list(self.active_connections[luta_id].items()):
            try:
                await websocket.send_json(message)
            except Exception as e:
                print(f"❌ Erro ao enviar para {lateral_email}: {e}")
                self.disconnect(luta_id, lateral_email)
    
    async def broadcast_to_all_mesarios(self, message: dict):
        """Envia mensagem para TODOS os Mesários conectados"""
        for key, websocket in list(self.mesario_connections.items()):
            try:
                await websocket.send_json(message)
            except Exception as e:
                print(f"❌ Erro ao enviar para Mesário {key}: {e}")
                luta_id, numero_quadra = key.split(":")
                self.disconnect_mesario(luta_id, int(numero_quadra))


# Instância global de gerenciador de conexões
manager = ConnectionManager()


@router.websocket("/ws/lateral/{luta_id}/{lateral_email}")
async def websocket_lateral(websocket: WebSocket, luta_id: str, lateral_email: str):
    """
    WebSocket para árbitro lateral enviar pontos e receber confirmações.
    
    Fluxo:
    1. Lateral conecta ao WebSocket
    2. Lateral carrega em botão ("+1", "+2", "+3")
    3. Servidor registra clique e aguarda coincidência
    4. Se houver coincidência (2+ árbitros), ponto é validado
    5. Confirmação é enviada de volta para todos os laterais
    """
    print(f"\n{'='*60}")
    print(f"🔌 WEBSOCKET LATERAL - TENTATIVA DE CONEXÃO")
    print(f"{'='*60}")
    print(f"  Hora: {__import__('datetime').datetime.now().isoformat()}")
    print(f"  Luta ID: {luta_id}")
    print(f"  Email: {lateral_email}")
    print(f"  Headers: {dict(websocket.headers)}")
    print(f"{'='*60}\n")
    
    try:
        await manager.connect(luta_id, lateral_email, websocket)
        print(f"✅ CONEXÃO ACEITA: lateral={lateral_email}, luta={luta_id}")
    except Exception as e:
        print(f"❌ ERRO AO CONECTAR: {e}")
        raise
    
    try:
        while True:
            # Receber clique do lateral
            data = await websocket.receive_json()
            
            # Validar dados
            if "tipo_ponto" not in data or "cor" not in data:
                await websocket.send_json({
                    "status": "erro",
                    "mensagem": "Faltam campos: tipo_ponto e cor"
                })
                continue
            
            tipo_ponto = data["tipo_ponto"]  # "+1", "+2", "+3"
            cor = data["cor"]  # "vermelho" ou "azul"
            
            # Registrar clique e verificar validação
            ponto_validado = joystick_manager.registrar_clique_lateral(
                luta_id=luta_id,
                lateral_email=lateral_email,
                tipo_ponto=tipo_ponto,
                cor=cor
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
                
                # Broadcast para todos os laterais
                await manager.broadcast_to_luta(luta_id, mensagem_validacao)
                
                # Broadcast para todos os Mesários
                await manager.broadcast_to_all_mesarios(mensagem_validacao)
    
    except WebSocketDisconnect:
        print(f"\n{'='*60}")
        print(f"❌ WEBSOCKET LATERAL DESCONECTADO")
        print(f"{'='*60}")
        print(f"  Hora: {__import__('datetime').datetime.now().isoformat()}")
        print(f"  Lateral: {lateral_email}")
        print(f"  Luta: {luta_id}")
        print(f"{'='*60}\n")
        manager.disconnect(luta_id, lateral_email)
    except Exception as e:
        print(f"\n{'='*60}")
        print(f"❌ ERRO INESPERADO NO WEBSOCKET LATERAL")
        print(f"{'='*60}")
        print(f"  Tipo de erro: {type(e).__name__}")
        print(f"  Mensagem: {e}")
        print(f"  Lateral: {lateral_email}")
        print(f"  Luta: {luta_id}")
        print(f"{'='*60}\n")
        manager.disconnect(luta_id, lateral_email)
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
    return {
        "status": "ok",
        "mensagem": "Sistema de Joystick está pronto para WebSocket",
        "websocket_endpoints": [
            "/api/ws/lateral/{luta_id}/{lateral_email}",
            "/api/ws/mesario/{luta_id}/{numero_quadra}",
            "/api/ws/poomsae/{luta_id}/{juiz_email}"
        ],
        "conexoes_ativas": {
            "laterais": sum(len(emails) for emails in manager.active_connections.values()),
            "mesarios": len(manager.mesario_connections)
        }
    }
