from enum import Enum

class CommandStatus:
    PENDING = "PENDING"
    DISPATCHED = "DISPATCHED"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"
    ACKED = "ACKED"
    VERIFIED = "VERIFIED"
    
    # Estados terminais
    TERMINAL_STATES = [FAILED, VERIFIED]

class SecurityQuestion(Enum):
    PET = "Qual o nome do seu primeiro animal de estimação?"
    MOTHER = "Qual o nome de solteira da sua mãe?"
    SCHOOL = "Qual o nome da primeira escola que você frequentou?"
    BIRTH = "Em qual cidade você nasceu?"
    BOOK = "Qual seu livro favorito?"
