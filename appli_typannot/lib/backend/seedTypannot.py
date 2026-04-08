# seed_typannot.py
from sqlmodel import Session, select
from db import engine
from models.TypannotCharacter import TypannotCharacter

TYPANNOT_CHARS = [
    {"hex_code": "E002", "decimal_code": 57346, "name": "Sélection gauche"},
    {"hex_code": "E003", "decimal_code": 57347, "name": "Sélection droite"},
    {"hex_code": "E5E2", "decimal_code": 58850, "name": "Epaule"},
    {"hex_code": "E5E5", "decimal_code": 58853, "name": "Bras"},
    {"hex_code": "E5E6", "decimal_code": 58854, "name": "Avant-Bras"},
    {"hex_code": "E018", "decimal_code": 57368, "name": "Paume"},
    {"hex_code": "E5E7", "decimal_code": 58855, "name": "Flexion/Extension"},
    {"hex_code": "E5FD", "decimal_code": 58877, "name": "Flexion"},
    {"hex_code": "E5FE", "decimal_code": 58878, "name": "Extension"},
    {"hex_code": "E5E8", "decimal_code": 58856, "name": "Abduction/Adduction"},
    {"hex_code": "E5FB", "decimal_code": 58875, "name": "Abduction"},
    {"hex_code": "E5FC", "decimal_code": 58876, "name": "Adduction"},
    {"hex_code": "E5EA", "decimal_code": 58858, "name": "Rotation interne/externe"},
    {"hex_code": "E600", "decimal_code": 58880, "name": "Rotation interne"},
    {"hex_code": "E5FF", "decimal_code": 58879, "name": "Rotation externe"},
    {"hex_code": "E5EF", "decimal_code": 58863, "name": "0/4"},
    {"hex_code": "E5EB", "decimal_code": 58859, "name": "1/4"},
    {"hex_code": "E5EC", "decimal_code": 58860, "name": "2/4"},
    {"hex_code": "E5ED", "decimal_code": 58861, "name": "3/4"},
    {"hex_code": "E5EE", "decimal_code": 58862, "name": "4/4"},
    {"hex_code": "E008", "decimal_code": 57352, "name": "Pouce"},
    {"hex_code": "F1A0", "decimal_code": 61856, "name": "Phalange 2-3"},
    {"hex_code": "F19F", "decimal_code": 61855, "name": "Phalange 1"},
    {"hex_code": "E004", "decimal_code": 57348, "name": "Index"},
    {"hex_code": "E005", "decimal_code": 57349, "name": "Majeur"},
    {"hex_code": "E006", "decimal_code": 57350, "name": "Annulaire"},
    {"hex_code": "E007", "decimal_code": 57351, "name": "Auriculaire"},
    {"hex_code": "EBE3", "decimal_code": 60387, "name": "Sélection haut"},
    {"hex_code": "EBE4", "decimal_code": 60388, "name": "Sélection bas"},
    {"hex_code": "EBB8", "decimal_code": 60344, "name": "Mâchoire"},
    {"hex_code": "EBB9", "decimal_code": 60345, "name": "Lèvres"},
    {"hex_code": "EBBA", "decimal_code": 60346, "name": "Coins de la bouche"},
    {"hex_code": "EBE6", "decimal_code": 60390, "name": "Vermillon des lèvres"},
    {"hex_code": "EBBB", "decimal_code": 60347, "name": "Langue"},
    {"hex_code": "EBC4", "decimal_code": 60356, "name": "Position à gauche"},
    {"hex_code": "EBC5", "decimal_code": 60357, "name": "Position à droite"},
    {"hex_code": "EBC3", "decimal_code": 60355, "name": "Position à haut"},
    {"hex_code": "EBC6", "decimal_code": 60358, "name": "Position à bas"},
    {"hex_code": "EBC7", "decimal_code": 60359, "name": "Position en avant"},
    {"hex_code": "EBC8", "decimal_code": 60360, "name": "Position en arrière"},























    

    # ... tes 50 caractères
]

def seed():
    with Session(engine) as session:
        for char in TYPANNOT_CHARS:
            existing = session.exec(
                select(TypannotCharacter).where(TypannotCharacter.hex_code == char["hex_code"])
            ).first()
            if not existing:
                session.add(TypannotCharacter(**char))
        session.commit()
        print("Seed terminé.")

if __name__ == "__main__":
    seed()