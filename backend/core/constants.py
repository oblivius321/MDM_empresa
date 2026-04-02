from enum import Enum

class SecurityQuestion(str, Enum):
    PET = "Nome do seu primeiro pet?"
    CITY = "Cidade onde você nasceu?"
    MOTHER = "Nome da sua mãe?"
    SCHOOL = "Nome da sua escola primária?"
    FOOD = "Comida favorita na infância?"
