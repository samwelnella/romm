from decorators.database import begin_session
from models.rom import Rom, RomNote
from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.orm import Session

from .base_handler import DBBaseHandler


class DBRomsHandler(DBBaseHandler):
    def _filter(self, data, platform_id: int | None, search_term: str):
        if platform_id:
            data = data.filter_by(platform_id=platform_id)

        if search_term:
            data = data.filter(
                or_(
                    Rom.file_name.ilike(f"%{search_term}%"),  # type: ignore[attr-defined]
                    Rom.name.ilike(f"%{search_term}%"),  # type: ignore[attr-defined]
                )
            )

        return data

    def _order(self, data, order_by: str, order_dir: str):
        if order_by == "id":
            _column = Rom.id
        else:
            _column = func.lower(Rom.name)

        if order_dir == "desc":
            return data.order_by(_column.desc())
        else:
            return data.order_by(_column.asc())

    @begin_session
    def add_rom(self, rom: Rom, session: Session = None) -> Rom:
        return session.merge(rom)

    @begin_session
    def get_roms(
        self,
        id: int | None = None,
        platform_id: int | None = None,
        search_term: str = "",
        order_by: str = "name",
        order_dir: str = "asc",
        session: Session = None,
    ) -> Rom | list[Rom] | None:
        return (
            session.get(Rom, id)
            if id
            else self._order(
                self._filter(select(Rom), platform_id, search_term),
                order_by,
                order_dir,
            )
        )

    @begin_session
    def get_rom_by_filename(
        self, platform_id: int, file_name: str, session: Session = None
    ) -> Rom | None:
        return session.scalars(
            select(Rom).filter_by(platform_id=platform_id, file_name=file_name).limit(1)
        ).first()

    @begin_session
    def get_rom_by_filename_no_tags(
        self, file_name_no_tags: str, session: Session = None
    ) -> Rom | None:
        return session.scalars(
            select(Rom).filter_by(file_name_no_tags=file_name_no_tags).limit(1)
        ).first()

    @begin_session
    def get_rom_by_filename_no_ext(
        self, file_name_no_ext: str, session: Session = None
    ) -> Rom | None:
        return session.scalars(
            select(Rom).filter_by(file_name_no_ext=file_name_no_ext).limit(1)
        ).first()

    @begin_session
    def update_rom(self, id: int, data: dict, session: Session = None) -> Rom:
        return session.execute(
            update(Rom)
            .where(Rom.id == id)
            .values(**data)
            .execution_options(synchronize_session="evaluate")
        )

    @begin_session
    def delete_rom(self, id: int, session: Session = None) -> None:
        return session.execute(
            delete(Rom)
            .where(Rom.id == id)
            .execution_options(synchronize_session="evaluate")
        )

    @begin_session
    def purge_roms(
        self, platform_id: int, roms: list[str], session: Session = None
    ) -> None:
        return session.execute(
            delete(Rom)
            .where(and_(Rom.platform_id == platform_id, Rom.file_name.not_in(roms)))  # type: ignore[attr-defined]
            .execution_options(synchronize_session="evaluate")
        )

    @begin_session
    def get_rom_note(
        self, rom_id: int, user_id: int, session: Session = None
    ) -> RomNote | None:
        return session.scalars(
            select(RomNote).filter_by(rom_id=rom_id, user_id=user_id).limit(1)
        ).first()

    @begin_session
    def add_rom_note(
        self, rom_id: int, user_id: int, session: Session = None
    ) -> RomNote:
        return session.merge(RomNote(rom_id=rom_id, user_id=user_id))

    @begin_session
    def update_rom_note(self, id: int, data: dict, session: Session = None) -> RomNote:
        return session.execute(
            update(RomNote)
            .where(RomNote.id == id)
            .values(**data)
            .execution_options(synchronize_session="evaluate")
        )
