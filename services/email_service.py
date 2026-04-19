"""
Serviço de Email
"""
import smtplib
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
