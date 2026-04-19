"""
Endpoint alternativo usando Server-Sent Events (SSE)
Para testar se o problema é específico do WebSocket ou geral
"""
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import asyncio
from datetime import datetime

router = APIRouter(prefix="/api/debug", tags=["Debug"])

@router.get("/streaming/test")
async def streaming_test():
    """
    Teste de streaming HTTP (SSE - Server-Sent Events)
    Alternativa ao WebSocket para testar comunicação bidirecional
    """
    async def event_generator():
        try:
            print(f"\n[{datetime.now().isoformat()}] 🔄 Cliente conectado a SSE")
            
            for i in range(10):
                data = {
                    "id": i,
                    "mensagem": f"Streaming test evento #{i+1}",
                    "timestamp": datetime.now().isoformat()
                }
                yield f"data: {__import__('json').dumps(data)}\n\n"
                await asyncio.sleep(1)
            
            print(f"[{datetime.now().isoformat()}] ✅ SSE completou")
        except asyncio.CancelledError:
            print(f"[{datetime.now().isoformat()}] 👋 Cliente desconectou do SSE")
        except Exception as e:
            print(f"[{datetime.now().isoformat()}] ❌ Erro no SSE: {e}")
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/http-polling/test")
async def http_polling_test():
    """
    Endpoint para teste de HTTP Polling
    Cliente faz GET a cada 2 segundos
    """
    import random
    return {
        "status": "ok",
        "mensagem": "Use GET repetitivo para simular polling",
        "evento_id": random.randint(1000, 9999),
        "timestamp": datetime.now().isoformat()
    }
