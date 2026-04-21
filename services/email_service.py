"""
Serviço de Email
"""
import smtplib
import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config.settings import EMAIL_REMETENTE, SENHA_EMAIL, SMTP_SERVER, SMTP_PORT


def enviar_email_token(destinatario: str, token: str) -> bool:
    """
    Envia email com código de verificação
    
    Args:
        destinatario: Email do destinatário
        token: Código de 6 dígitos
        
    Returns:
        True se enviado com sucesso, False caso contrário
    """
    msg = MIMEMultipart()
    msg['From'] = f"Omega Team <{EMAIL_REMETENTE}>"
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
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_REMETENTE, SENHA_EMAIL)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"❌ Erro ao enviar email: {e}")
        return False


# ✅ PHASE 2: ASYNC EMAIL NOTIFICATIONS FOR ATHLETES

async def enviar_notificacao_pagamento_confirmado(atleta_email: str, atleta_nome: str, campeonato_nome: str):
    """Notifica atleta que pagamento foi confirmado e inscrição ativa"""
    def _send():
        msg = MIMEMultipart()
        msg['From'] = f"Omega Team <{EMAIL_REMETENTE}>"
        msg['To'] = atleta_email
        msg['Subject'] = "✅ Inscrição Confirmada - Omega Team"
        
        corpo = f"""
        Olá {atleta_nome}!
        
        🎉 Sua inscrição foi confirmada no campeonato!
        
        Campeonato: {campeonato_nome}
        Email: {atleta_email}
        Status: ✅ CONFIRMADO
        
        Em breve, você receberá um email com o cronograma de lutas.
        Verifique sua caixa de entrada regularmente.
        
        Boa sorte na competição! 🥋
        
        ---
        Omega Team
        Plataforma de Competições de Taekwondo
        """
        msg.attach(MIMEText(corpo, 'plain', 'utf-8'))
        
        try:
            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
            server.starttls()
            server.login(EMAIL_REMETENTE, SENHA_EMAIL)
            server.send_message(msg)
            server.quit()
            return True
        except Exception as e:
            print(f"❌ Erro ao enviar notificação de pagamento: {e}")
            return False
    
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _send)


async def enviar_notificacao_cronograma_pronto(atleta_email: str, atleta_nome: str, campeonato_nome: str, num_lutas: int):
    """Notifica atleta que cronograma foi gerado"""
    def _send():
        msg = MIMEMultipart()
        msg['From'] = f"Omega Team <{EMAIL_REMETENTE}>"
        msg['To'] = atleta_email
        msg['Subject'] = "📅 Cronograma de Lutas Pronto - Omega Team"
        
        corpo = f"""
        Olá {atleta_nome}!
        
        📅 O cronograma de lutas está pronto!
        
        Campeonato: {campeonato_nome}
        Suas lutas: {num_lutas}
        
        Acesse a plataforma para ver:
        ✅ Hora e local de suas lutas
        ✅ Seus adversários
        ✅ Resultado em tempo real
        
        Link: https://omega-team.com/minhas-lutas
        
        ⚠️ IMPORTANTE: Chegue com 15 minutos de antecedência!
        
        ---
        Omega Team
        """
        msg.attach(MIMEText(corpo, 'plain', 'utf-8'))
        
        try:
            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
            server.starttls()
            server.login(EMAIL_REMETENTE, SENHA_EMAIL)
            server.send_message(msg)
            server.quit()
            return True
        except Exception as e:
            print(f"❌ Erro ao enviar notificação de cronograma: {e}")
            return False
    
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _send)


async def enviar_notificacao_proxima_luta(atleta_email: str, atleta_nome: str, adversario_nome: str, 
                                          quadra: str, horario_previsto: str, categoria: str):
    """Notifica atleta que sua luta está próxima (30 min antes)"""
    def _send():
        msg = MIMEMultipart()
        msg['From'] = f"Omega Team <{EMAIL_REMETENTE}>"
        msg['To'] = atleta_email
        msg['Subject'] = "🔔 Sua Luta Começa em Breve! - Omega Team"
        
        corpo = f"""
        Olá {atleta_nome}!
        
        🔔 AVISO: Sua luta começará em breve!
        
        Adversário: {adversario_nome}
        Categoria: {categoria}
        Quadra: {quadra}
        Horário: {horario_previsto}
        
        ⚠️ APRESENTE-SE COM 15 MINUTOS DE ANTECEDÊNCIA NA QUADRA!
        
        📍 Localize sua quadra na plataforma: https://omega-team.com/minhas-lutas
        
        Boa sorte! 🥋
        
        ---
        Omega Team
        """
        msg.attach(MIMEText(corpo, 'plain', 'utf-8'))
        
        try:
            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
            server.starttls()
            server.login(EMAIL_REMETENTE, SENHA_EMAIL)
            server.send_message(msg)
            server.quit()
            return True
        except Exception as e:
            print(f"❌ Erro ao enviar notificação de próxima luta: {e}")
            return False
    
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _send)


async def enviar_notificacao_resultado_luta(atleta_email: str, atleta_nome: str, adversario_nome: str,
                                            venceu: bool, categoria: str, placar_atleta: int, placar_adv: int):
    """Notifica atleta sobre resultado de sua luta"""
    def _send():
        msg = MIMEMultipart()
        msg['From'] = f"Omega Team <{EMAIL_REMETENTE}>"
        msg['To'] = atleta_email
        resultado = "✅ VITÓRIA" if venceu else "❌ DERROTA"
        msg['Subject'] = f"{resultado} na Luta - Omega Team"
        
        corpo = f"""
        Olá {atleta_nome}!
        
        {resultado} na sua luta!
        
        Categoria: {categoria}
        Adversário: {adversario_nome}
        
        Seu placar: {placar_atleta}
        Placar do adversário: {placar_adv}
        
        Veja o resultado completo em: https://omega-team.com/minhas-lutas
        
        Verifique se tem próxima luta! 🥋
        
        ---
        Omega Team
        """
        msg.attach(MIMEText(corpo, 'plain', 'utf-8'))
        
        try:
            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
            server.starttls()
            server.login(EMAIL_REMETENTE, SENHA_EMAIL)
            server.send_message(msg)
            server.quit()
            return True
        except Exception as e:
            print(f"❌ Erro ao enviar notificação de resultado: {e}")
            return False
    
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _send)


async def enviar_notificacao_torneio_encerrado(atleta_email: str, atleta_nome: str, campeonato_nome: str, medalha: str):
    """Notifica atleta que torneio encerrou e informa medalha"""
    def _send():
        msg = MIMEMultipart()
        msg['From'] = f"Omega Team <{EMAIL_REMETENTE}>"
        msg['To'] = atleta_email
        
        emoji_medalha = {
            "ouro": "🥇",
            "prata": "🥈",
            "bronze": "🥉",
            "participacao": "🎖️"
        }.get(medalha, "🎖️")
        
        msg['Subject'] = f"{emoji_medalha} Torneio Encerrado - Omega Team"
        
        corpo = f"""
        Olá {atleta_nome}!
        
        🏁 O torneio foi encerrado!
        
        Campeonato: {campeonato_nome}
        Sua Medalha: {emoji_medalha} {medalha.upper()}
        
        Visite sua página de perfil para:
        ✅ Baixar seu certificado
        ✅ Ver estatísticas completas
        ✅ Compartilhar seu resultado
        
        Link: https://omega-team.com/meu-perfil
        
        Muito obrigado por participar! 🙏
        
        ---
        Omega Team
        """
        msg.attach(MIMEText(corpo, 'plain', 'utf-8'))
        
        try:
            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
            server.starttls()
            server.login(EMAIL_REMETENTE, SENHA_EMAIL)
            server.send_message(msg)
            server.quit()
            return True
        except Exception as e:
            print(f"❌ Erro ao enviar notificação de encerramento: {e}")
            return False
    
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _send)
