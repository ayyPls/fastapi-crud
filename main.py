from typing import Union, Annotated, List, Optional
from fastapi import FastAPI, Depends, Query, status, HTTPException
from sqlmodel import Session, SQLModel, create_engine, select, Field, SQLModel, Relationship
from decimal import Decimal

class User(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    role: int = Field(default=0)
    firstname: str | None = Field(default=None)
    lastname: str | None = Field(default=None)
    playlists: List["Playlist"] = Relationship(back_populates="owner")
    albums: List["Album"] = Relationship(back_populates="owner")

class UserCreate(SQLModel):
    email: str = Field(index=True, unique=True)
    role: int = Field(default=0)
    firstname: str | None = Field(default=None)
    lastname: str | None = Field(default=None)

class UserUpdate(SQLModel):
    role: int = Field(default=0)
    firstname: str | None = Field(default=None)
    lastname: str | None = Field(default=None)

class PlaylistSong(SQLModel, table=True):
    playlist_id: Optional[int] = Field(default=None, foreign_key="playlist.id", primary_key=True)
    song_id: Optional[int] = Field(default=None, foreign_key="song.id", primary_key=True)

class Album(SQLModel, table=True):
    id:int = Field(default=None, primary_key=True)
    name:str = Field(default=None)
    owner_id: Optional[int] = Field(default=None, foreign_key="user.id")
    owner: Optional[User] = Relationship(back_populates="albums")
    songs: List["Song"] = Relationship(back_populates="album")

class AlbumCreate(SQLModel):
    name: str = Field(default=None)

class AlbumUpdate(SQLModel):
    name: str = Field(default=None)

class Song(SQLModel, table=True):
    id:int = Field(default=None, primary_key=True)
    duration_in_sec: Decimal = Field(default=0, max_digits=10, decimal_places=2)
    name: str = Field(default=None)
    album_id: Optional[int] = Field(default=None, foreign_key="album.id")
    album: Optional[Album] = Relationship(back_populates="songs")
    playlists: List["Playlist"] = Relationship(back_populates="songs", link_model=PlaylistSong)

class SongCreate(SQLModel):
    name: str = Field(default=None)
    duration_in_sec: Decimal = Field(default=0, max_digits=10, decimal_places=2)

class SongUpdate(SQLModel):
    name: str = Field(default=None)
    duration_in_sec: Decimal = Field(default=0, max_digits=10, decimal_places=2)

class Playlist(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    name: str = Field(default=None)
    owner_id: Optional[int] = Field(default=None, foreign_key="user.id")
    owner: Optional[User] = Relationship(back_populates="playlists")
    songs: List["Song"] = Relationship(back_populates="playlists", link_model=PlaylistSong)

class PlaylistCreate(SQLModel):
    name: str = Field(default=None)

class PlaylistUpdate(SQLModel):
    name: str = Field(default=None)

app = FastAPI()

def get_session():
    with Session(engine) as session:
        yield session

sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"
connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, connect_args=connect_args)
SessionDep = Annotated[Session, Depends(get_session)]

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


@app.on_event("startup")
def init_db():
    create_db_and_tables()

# User logic

@app.get("/user/{user_id}")
def get_user(session: SessionDep, user_id: int):
    response_user = session.get(User, user_id)
    if response_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return {"user": response_user, "user_playlists": response_user.playlists, "owned_albums": response_user.albums}


@app.get("/users")
def get_users(session: SessionDep, limit: Annotated[int, Query(le=100)] = 100, offset: int = 0):
    users = session.exec(select(User)).all()
    return {"users": users[offset:offset+limit], "total": len(users)}


@app.post("/user", response_model=User, status_code=status.HTTP_201_CREATED)
def create_user(session: SessionDep, user: UserCreate):
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


# Playlist logic
@app.get("/user/{user_id}/playlists")
def get_user_playlists(session: SessionDep, user_id:int):
    user = session.get(User, user_id)
    return user.playlists

@app.get("/user/{user_id}/playlist/{playlist_id}")
def get_user_playlist(session: SessionDep, user_id:int, playlist_id: int):
    playlist = session.exec(select(Playlist).where(Playlist.owner_id == user_id).where(Playlist.id == playlist_id)).first()
    playlist_songs = playlist.songs
    print(playlist_songs)
    if playlist is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return {"playlist": playlist, "songs": playlist.songs}

@app.post("/user/{user_id}/playlist/{playlist_id}/song/{song_id}", status_code=status.HTTP_200_OK)
def add_song_in_playlist(session: SessionDep, user_id: int, playlist_id: int, song_id: int):
    playlist = session.exec(select(Playlist).where(Playlist.owner_id == user_id).where(Playlist.id == playlist_id)).first()
    if playlist is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playlist doesn't exist")
    song = session.get(Song, song_id)
    if song is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Song doesn't exist")
    song_is_in_playlist = session.exec(select(PlaylistSong).where(PlaylistSong.song_id == song_id).where(PlaylistSong.playlist_id == playlist_id)).first()
    if song_is_in_playlist is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Song is already in playlist")
    playlist.songs.append(song)
    session.add(playlist)
    session.commit()
    return {"status": status.HTTP_200_OK}
    
@app.delete("/user/{user_id}/playlist/{playlist_id}/song/{song_id}", status_code=status.HTTP_200_OK)
def remove_song_from_playlist(session: SessionDep, user_id: int, playlist_id: int, song_id: int):
    playlist = session.exec(select(Playlist).where(Playlist.owner_id == user_id).where(Playlist.id == playlist_id)).first()
    if playlist is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playlist doesn't exist")
    song = session.get(Song, song_id)
    if song is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Song doesn't exist")
    song_is_in_playlist = session.exec(select(PlaylistSong).where(PlaylistSong.song_id == song_id).where(PlaylistSong.playlist_id == playlist_id)).first()
    if song_is_in_playlist is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Song is not in a playlist")
    playlist.songs.remove(song)
    session.add(playlist)
    session.commit()
    return {"status": status.HTTP_200_OK}
    
@app.post("/user/{user_id}/playlist", status_code=status.HTTP_201_CREATED)
def create_playlist(session: SessionDep, playlist: PlaylistCreate, user_id):
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User doesn't exist")
    playlist_db = Playlist(
        name=playlist.name,
        owner=user
    )
    session.add(playlist_db)
    session.commit()
    session.refresh(playlist_db)
    return playlist_db

@app.patch("/user/{user_id}/playlist/{playlist_id}", response_model=Playlist, status_code=status.HTTP_200_OK)
def update_user_playlist(session: SessionDep, user_id:int, playlist_id: int, playlist: PlaylistUpdate):
    playlist_to_update = session.exec(select(Playlist).where(Playlist.owner_id == user_id).where(Playlist.id == playlist_id)).first()
    if playlist_to_update is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    playlist_data = playlist.model_dump(exclude_unset=True)
    playlist_to_update.sqlmodel_update(playlist_data)
    session.add(playlist_to_update)
    session.commit()
    session.refresh(playlist_to_update)
    return playlist_to_update

@app.delete("/user/{user_id}/playlist/{playlist_id}")
def delete_user_playlist(session: SessionDep, user_id:int, playlist_id: int):
    playlist = session.exec(select(Playlist).where(Playlist.owner_id == user_id).where(Playlist.id == playlist_id)).first()
    if playlist is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    session.delete(playlist)
    session.commit()
    return {"status": status.HTTP_200_OK}

# Album logic
@app.get("/album/{album_id}")
def get_album(session: SessionDep, album_id: int):
    album = session.get(Album, album_id)
    if album is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Album doesn't exist")
    return {"album": album, "songs": album.songs}

@app.get("/user/{user_id}/albums")
def get_user_albums(session: SessionDep, user_id: int):
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Album doesn't exist")
    return user.albums

@app.patch("/album/{album_id}")
def update_album(session: SessionDep, album: AlbumUpdate, album_id: int):
    album_to_update = session.get(Album, album_id)
    if album_to_update is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Album not found")
    album_data = album.model_dump(exclude_unset=True)
    album_to_update.sqlmodel_update(album_data)
    session.add(album_to_update)
    session.commit()
    session.refresh(album_to_update)
    return album_to_update


@app.post("/user/{user_id}/album")
def create_album(session: SessionDep, album: AlbumCreate, user_id: int):
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User doesn't exist")
    album_db = Album(
        name=album.name,
        owner=user
    )
    session.add(album_db)
    session.commit()
    session.refresh(album_db)
    return album_db

@app.delete("/album/{album_id}")
def create_album(session: SessionDep, album_id: int):
    album = session.get(Album, album_id)
    if album is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Album doesn't exist")
    session.delete(album)
    session.commit()
    return {"status": status.HTTP_200_OK}



# Song logic

@app.get("/album/{album_id}/songs")
def get_album_songs(session: SessionDep, album_id: int):
    album = session.get(Album, album_id)
    if album is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Album not found")
    return album.songs

@app.get("/song/{song_id}")
def get_song(session: SessionDep, song_id: int):
    song = session.get(Song, song_id)
    if song is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Song not found")
    return song

@app.post("/album/{album_id}/song")
def add_song_in_album(session: SessionDep, album_id: int, song: SongCreate):
    album = session.get(Album, album_id)
    if album is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Album not found")
    song_db = Song(
        name=song.name,
        duration_in_sec=song.duration_in_sec,
        album=album
    )
    session.add(song_db)
    session.commit()
    session.refresh(song_db)
    return song_db

@app.patch("/song/{song_id}")
def update_song(session: SessionDep, song_id: int, song: SongUpdate):
    song_to_update = session.get(Song, song_id)
    if song_to_update is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Song not found")
    song_data = song.model_dump(exclude_unset=True)
    song_to_update.sqlmodel_update(song_data)
    session.add(song_to_update)
    session.commit()
    session.refresh(song_to_update)
    return song_to_update

@app.delete("/song/{song_id}")
def update_song(session: SessionDep, song_id: int):
    song = session.get(Song, song_id)
    if song is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Song doesn't exist")
    session.delete(song)
    session.commit()
    return {"status": status.HTTP_200_OK}