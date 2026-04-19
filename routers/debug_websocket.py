"""
Endpoint de teste para WebSocket - ULTRA DEBUG
Objetivo: Descobrir exatamente onde está falhando
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import json
import sys
import traceback
from datetime import datetime

router = APIRouter(prefix="/api/debug", tags=["Debug"])

# Função auxiliar para logging estruturado
def log_event(stage, message, details=None):
    """Registra eventos do WebSocket com timestamp e detalhes"""
    ts = datetime.now().isoformat()
    print(f"\n[{ts}] {stage}: {message}")
    if details:
        for key, value in details.items():
            print(f"       {key}: {value}")
    sys.stdout.flush()  # Força flush para Render capturar logs imediatamente

@router.websocket("/ws/test")
async def websocket_test(websocket: WebSocket):
    """
    WebSocket de teste ULTRA DETALHADO
    - Registra CADA etapa
    - Se falhar, vai mostrar exatamente onde
    """
    connection_id = f"{websocket.client[0]}:{websocket.client[1]}" if websocket.client else "unknown"
    
    log_event("🔌 STAGE_1", "Requisição WebSocket recebida", {
        "connection_id": connection_id,
        "scope_type": websocket.scope.get("type"),
        "path": websocket.scope.get("path"),
        "query_string": websocket.scope.get("query_string"),
    })
    
    log_event("🔌 STAGE_2", "Analisando headers", {
        "host": websocket.headers.get("host"),
        "upgrade": websocket.headers.get("upgrade"),
        "connection": websocket.headers.get("connection"),
        "sec_websocket_key": websocket.headers.get("sec-websocket-key"),
        "sec_websocket_version": websocket.headers.get("sec-websocket-version"),
    })
    
    try:
        log_event("🔌 STAGE_3", "Tentando aceitar WebSocket (await websocket.accept())...")
        await websocket.accept()
        log_event("✅ STAGE_4", "WebSocket ACEITO com sucesso!")
        
        # Enviar mensagem de confirmação
        log_event("📤 STAGE_5", "Enviando mensagem de boas-vindas...")
        await websocket.send_json({
            "status": "conectado",
            "mensagem": "WebSocket test FUNCIONANDO!",
            "connection_id": connection_id,
            "timestamp": datetime.now().isoformat()
        })
        log_event("✅ STAGE_6", "Mensagem enviada com sucesso!")
        
        # Loop para receber mensagens
        log_event("📥 STAGE_7", "Aguardando mensagens do cliente...")
        while True:
            data = await websocket.receive_json()
            log_event("📥 STAGE_8", "Mensagem recebida", {"data": str(data)})
            
            # Echo back
            await websocket.send_json({
                "status": "echo",
                "dados_recebidos": data,
                "timestamp": datetime.now().isoformat()
            })
            log_event("📤 STAGE_9", "Echo enviado de volta")
    
    except WebSocketDisconnect:
        log_event("👋 DESCONEXÃO", "Cliente desconectou normalmente")
    except Exception as e:
        log_event("❌ ERRO CRÍTICO", f"{type(e).__name__}: {str(e)}", {
            "traceback": traceback.format_exc(),
            "connection_id": connection_id
        })
        traceback.print_exc()


@router.get("/health")
async def debug_health():
    """Health check simples para debug"""
    return {
        "status": "ok",
        "endpoint": "/api/debug/ws/test",
        "instrucoes": "Tente conectar WebSocket a wss://omegateam-backend.onrender.com/api/debug/ws/test",
        "logs": "Verifique os logs do Render para ver as STAGES de conexão"
    }
