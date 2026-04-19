"""
Serviço de Autenticação (Hash de senha, verificação)
"""
import bcrypt


def get_password_hash(password: str) -> str:
    """
    Gera o hash bcrypt de uma senha
    
    Args:
        password: Senha em texto plano
        
    Returns:
        Hash da senha como string
    """
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password=pwd_bytes, salt=salt)
    return hashed_password.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica se a senha digitada corresponde ao hash
    
    Args:
        plain_password: Senha em texto plano
        hashed_password: Hash da senha armazenado
        
    Returns:
        True se a senha está correta, False caso contrário
    """
    password_byte_enc = plain_password.encode('utf-8')
    hashed_password_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password_byte_enc, hashed_password_bytes)
