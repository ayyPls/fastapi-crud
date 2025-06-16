from typing import Union, Annotated
from fastapi import FastAPI, Depends, Query, status, HTTPException
from sqlmodel import Field, Session, SQLModel, create_engine, select

app = FastAPI()

def get_session():
    with Session(engine) as session:
        yield session


sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"
connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, connect_args=connect_args)
SessionDep = Annotated[Session, Depends(get_session)]


class User(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    email: str = Field(index=True)
    role: int = Field(default=0)
    firstname: str | None = Field(default=None)
    lastname: str | None = Field(default=None)


class UserCreate(SQLModel):
    email: str = Field(index=True)
    role: int = Field(default=0)
    firstname: str | None = Field(default=None)
    lastname: str | None = Field(default=None)

class UserUpdate(SQLModel):
    role: int = Field(default=0)
    firstname: str | None = Field(default=None)
    lastname: str | None = Field(default=None)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


@app.on_event("startup")
def init_db():
    create_db_and_tables()


@app.get("/user/{user_id}")
def get_user_by_id(session: SessionDep, user_id: int):
    response_user = session.get(User, user_id)
    if response_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return response_user


@app.get("/users")
def get_users(session: SessionDep, limit: Annotated[int, Query(le=100)] = 100, offset: int = 0):
    users = session.exec(select(User)).all()
    return {"users": users[offset:offset+limit], "total": len(users)}


@app.post("/user", response_model=User, status_code=status.HTTP_201_CREATED)
def create_user(session: SessionDep, user: UserCreate):
    user_exist = session.exec(select(User).where(User.email == user.email)).first()
    if user_exist:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User with this email already exists.")
    user_db = User.model_validate(user)
    session.add(user_db)
    session.commit()
    session.refresh(user_db)
    return user_db

@app.patch("/user/{user_id}", response_model=User, status_code=status.HTTP_200_OK)
def update_user(session: SessionDep, user_id: int, user: UserUpdate):
    user_to_update = session.get(User, user_id)
    if user_to_update is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    user_data = user.model_dump(exclude_unset=True)
    user_to_update.sqlmodel_update(user_data)
    session.add(user_to_update)
    session.commit()
    session.refresh(user_to_update)
    return user_to_update

@app.delete("/user/{user_id}")
def delete_user(session: SessionDep, user_id: int):
    user_to_delete = session.get(User, user_id)
    if user_to_delete is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    session.delete(user_to_delete)
    session.commit()
    return {"status": status.HTTP_200_OK}