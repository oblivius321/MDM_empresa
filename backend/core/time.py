from datetime import datetime

def utcnow():
    """
    Retorna o timestamp UTC atual como um objeto datetime 'naive' 
    (sem informação de timezone), garantindo compatibilidade total 
    com o PostgreSQL (TIMESTAMP WITHOUT TIME ZONE).
    """
    # datetime.utcnow() já retorna naive, mas replace garante 100% de segurança
    return datetime.utcnow().replace(tzinfo=None)
