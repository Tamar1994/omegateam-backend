"""
Endpoint de teste para WebSocket - sem lógica complexa
Apenas conectar e manter vivo
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import json

router = APIRouter(prefix="/api/debug", tags=["Debug"])

@router.websocket("/ws/test")
async def websocket_test(websocket: WebSocket):
    """
    WebSocket de teste simples
    Apenas para verificar se a conexão WebSocket funciona
    """
    print("\n" + "="*60)
    print("🧪 WEBSOCKET TEST - TENTATIVA DE CONEXÃO")
    print("="*60)
    print(f"Headers: {dict(websocket.headers)}")
    print(f"Client: {websocket.client}")
    
    try:
        print("[ACEITANDO]...")
        await websocket.accept()
        print("✅ ACEITO!")
        
        # Enviar mensagem de boas-vindas
        await websocket.send_json({
            "status": "conectado",
            "mensagem": "WebSocket test ativo!",
            "timestamp": __import__('datetime').datetime.now().isoformat()
        })
        
        # Aguardar mensagens indefinidamente
        while True:
            data = await websocket.receive_json()
            print(f"📥 Recebido: {data}")
            
            # Echo back
            await websocket.send_json({
                "status": "echo",
                "dados": data,
                "timestamp": __import__('datetime').datetime.now().isoformat()
            })
    
    except WebSocketDisconnect:
        print("❌ DESCONECTADO")
    except Exception as e:
        print(f"❌ ERRO: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
