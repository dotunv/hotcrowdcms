from __future__ import annotations

import uuid
from datetime import date, datetime, time, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, Time, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "auth_user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    password: Mapped[str] = mapped_column(String(128))
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    username: Mapped[str] = mapped_column(String(150), unique=True)
    first_name: Mapped[str] = mapped_column(String(150), default="")
    last_name: Mapped[str] = mapped_column(String(150), default="")
    email: Mapped[str] = mapped_column(String(254), default="")
    is_staff: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    date_joined: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    store: Mapped[Store | None] = relationship(back_populates="user")


class Store(Base):
    __tablename__ = "core_store"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("auth_user.id"), unique=True)
    business_name: Mapped[str] = mapped_column(String(255), default="")
    branding_color: Mapped[str] = mapped_column(String(7), default="#22c55e")
    description: Mapped[str] = mapped_column(Text, default="")
    phone_number: Mapped[str] = mapped_column(String(20), default="")
    timezone: Mapped[str] = mapped_column(String(50), default="UTC")
    logo: Mapped[str | None] = mapped_column(String(100), nullable=True)
    default_image_duration: Mapped[int] = mapped_column(Integer, default=10)
    transition_effect: Mapped[str] = mapped_column(String(10), default="fade")
    mute_by_default: Mapped[bool] = mapped_column(Boolean, default=False)
    default_volume: Mapped[int] = mapped_column(Integer, default=75)
    fallback_type: Mapped[str] = mapped_column(String(20), default="brand_logo")
    fallback_logo: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    user: Mapped[User] = relationship(back_populates="store")
    screens: Mapped[list[Screen]] = relationship(back_populates="store")
    playlists: Mapped[list[Playlist]] = relationship(back_populates="store")
    media_assets: Mapped[list[MediaAsset]] = relationship(back_populates="store")

    @property
    def initials(self) -> str:
        name = self.business_name or (self.user.username if self.user else "HC")
        parts = name.strip().split()
        if len(parts) >= 2:
            return f"{parts[0][0]}{parts[1][0]}".upper()
        return name[:2].upper() if name else "HC"


class MediaAsset(Base):
    __tablename__ = "core_mediaasset"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    store_id: Mapped[int] = mapped_column(ForeignKey("core_store.id"))
    name: Mapped[str] = mapped_column(String(255), default="")
    file: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_url: Mapped[str] = mapped_column(String(1024), default="")
    media_type: Mapped[str] = mapped_column(String(10))
    source: Mapped[str] = mapped_column(String(10), default="UPLOAD")
    duration: Mapped[int] = mapped_column(Integer, default=10)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    store: Mapped[Store] = relationship(back_populates="media_assets")

    def playback_path(self) -> str | None:
        if self.file:
            return self.file
        return self.external_url or None


class Playlist(Base):
    __tablename__ = "core_playlist"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    store_id: Mapped[int] = mapped_column(ForeignKey("core_store.id"))
    status: Mapped[str] = mapped_column(String(10), default="DRAFT")
    schedule_type: Mapped[str] = mapped_column(String(10), default="ALWAYS")
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    transition_effect: Mapped[str] = mapped_column(String(10), default="FADE")
    is_loop: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    store: Mapped[Store] = relationship(back_populates="playlists")
    items: Mapped[list[PlaylistItem]] = relationship(
        back_populates="playlist",
        order_by="PlaylistItem.position",
        cascade="all, delete-orphan",
    )
    assigned_screens: Mapped[list[Screen]] = relationship(
        back_populates="assigned_playlist",
        foreign_keys="Screen.assigned_playlist_id",
    )


class PlaylistItem(Base):
    __tablename__ = "core_playlistitem"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    playlist_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("core_playlist.id"))
    media_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("core_mediaasset.id"))
    position: Mapped[int] = mapped_column(Integer, default=0)
    custom_duration: Mapped[int | None] = mapped_column(Integer, nullable=True)

    playlist: Mapped[Playlist] = relationship(back_populates="items")
    media: Mapped[MediaAsset] = relationship()

    def play_duration(self) -> int:
        if self.custom_duration:
            return self.custom_duration
        return self.media.duration


class Screen(Base):
    __tablename__ = "core_screen"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    store_id: Mapped[int] = mapped_column(ForeignKey("core_store.id"))
    pairing_code: Mapped[str | None] = mapped_column(String(8), unique=True, nullable=True)
    location: Mapped[str] = mapped_column(String(255), default="")
    last_heartbeat: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    api_token_hash: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    assigned_playlist_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("core_playlist.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    store: Mapped[Store] = relationship(back_populates="screens")
    assigned_playlist: Mapped[Playlist | None] = relationship(
        back_populates="assigned_screens",
        foreign_keys=[assigned_playlist_id],
    )

    @property
    def is_online(self) -> bool:
        if not self.last_heartbeat:
            return False
        hb = self.last_heartbeat
        if hb.tzinfo is None:
            hb = hb.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - hb).total_seconds() < 60


class PairingCode(Base):
    __tablename__ = "core_pairingcode"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(8), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    token_delivered: Mapped[bool] = mapped_column(Boolean, default=False)
