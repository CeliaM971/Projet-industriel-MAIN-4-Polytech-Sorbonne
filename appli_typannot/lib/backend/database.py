from sqlmodel import SQLModel, create_engine, Session
from models import Groupe#, Video

##engine =  create_engine("sqlite:///database.db")
##SQLModel.metadata.create_all(engine)

## on construit l'url dynamiquement avec une variable sqlite_file_ame
## utile si on veut changer le nom du fichier ou utiliser une autre base

sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"
engine = create_engine(sqlite_url, echo=True, connect_args={"check_same_thread": False})  ## activer les cles etrangeres
##echo=True pour afficher toutes les requetes SQL dans le terminal

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def add_group( g : Groupe ):
    with Session(engine) as session:
        session.add(g)
        session.commit()
        session.refresh(g)
        print(f"Group added with id: {g.id}")

def add_video( v : Video ):
    with Session(engine) as session:
        session.add(v)
        session.commit()
        session.refresh(v)
        print(f"Video added with id: {v.id}")

def create_group(name: str):
    g = Groupe(name=name)
    add_group(g)
    return g

def create_video(title: str, path :str, group_id :int | None):
    v = Video(title=title, path=path, group_id=group_id)
    add_video(v)
    return v

create_db_and_tables()

