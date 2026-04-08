####FastAPI ne lance pas MariaDB 
### sudo systemctl start mariadb
### sudo systemctl status mariadb

### sudo systemctl enable mariadb
### systemctl start mariadb
#####puis à vie :

"""
Dans le terminal :

sudo mariadb -p -e "
CREATE DATABASE IF NOT EXISTS typannot_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

ALTER USER 'typannot'@'localhost' IDENTIFIED BY 'motdepasse'; 
CREATE USER IF NOT EXISTS 'typannot'@'127.0.0.1' IDENTIFIED BY 'motdepasse';
ALTER USER 'typannot'@'127.0.0.1' IDENTIFIED BY 'motdepasse';

GRANT ALL PRIVILEGES ON typannot_db.* TO 'typannot'@'localhost';
GRANT ALL PRIVILEGES ON typannot_db.* TO 'typannot'@'127.0.0.1';

FLUSH PRIVILEGES;
"

mettre le mdp "motdepasse"

sur linux pas besoin de -p --> pas de demande de mdp


"""

### uvicorn backend.main:app --reload



from typing import Annotated
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from sqlmodel import Session, SQLModel, create_engine

import os
from sqlalchemy import text


# si une var d'environnement existe on l'utilise sinon on prends
# la valeur par defaut

# prends DB_USER si ca existe sinon prends "typannot" comme val par defaut
DB_USER = os.getenv("DB_USER", "typannot")
DB_PASSWORD = os.getenv("DB_PASSWORD", "motdepasse")
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "typannot_db")

"""
On peut écrire dans le terminal :

export DB_USER=typannot
export DB_PASSWORD=motdepasse
export DB_HOST=127.0.0.1
export DB_PORT=3306
export DB_NAME=typannot_db

puis :

uvicorn main:app --reload

"""


# se connecter au serveur mariaDB avec PyMySQL / SQLModel (sans la base), on est sur mariadb sans avoir selectionné aucune base
#SERVER_DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}"
SERVER_DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}"

#connexion a la base
DATABASE_URL = f"{SERVER_DATABASE_URL}/{DB_NAME}"

# connexion globale ?
engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)


def create_database_if_not_exists():
    
    # crée la base mariaDB si elle n'existe pas
    server_engine = create_engine(
        SERVER_DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
    )

    # ouvre une connexion sql
    with server_engine.connect() as conn:
        conn.execute(
            text(f"CREATE DATABASE IF NOT EXISTS {DB_NAME} CHARACTER SET utf8mb4")
        )
        conn.commit()

        """
        Equivaut à :

        CREATE DATABASE IF NOT EXISTS typannot_db
        CHARACTER SET utf8mb4;

        dans le terminal

        """


def create_db_and_tables():
    create_database_if_not_exists()  #on s'assure que la base existe
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Démarrage...")
    create_db_and_tables()
    yield
    print("Arrêt...")
