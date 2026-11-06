from __future__ import annotations

import os
import re
from datetime import date, datetime
from pathlib import Path
from typing import Literal, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from app.database import get_db, init_db
from app.exporter import export_flight_report
from app.models import Aeronave, Mision, PilotoCertificacion, PilotoHabilitacionAeronave, PilotoTripulante, RegistroVuelo, Usuario

app = FastAPI(title="Sistema de Horas de Vuelo - Escuadrón", version="1.0.0")
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.add_middleware(SessionMiddleware, secret_key=os.getenv("APP_SECRET_KEY", "jesc-flight-hours-secret-key-change-me"))

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
DEFAULT_ADMIN_USERNAME = os.getenv("APP_ADMIN_USERNAME", "admin")
DEFAULT_ADMIN_PASSWORD = os.getenv("APP_ADMIN_PASSWORD", "admin123")
AIRCRAFT_TYPES = ("C-172", "EMB-312/T-27", "T-41", "Mxt-7-180")
PILOT_RANKS = (
    "Alférez",
    "Subteniente",
    "Teniente",
    "Capitán",
    "Mayor",
    "Teniente Coronel",
    "Coronel",
    "General de Brigada",
    "General de División",
)


class PilotoCreate(BaseModel):
    grado: Literal[
        "Alférez",
        "Subteniente",
        "Teniente",
        "Capitán",
        "Mayor",
        "Teniente Coronel",
        "Coronel",
        "General de Brigada",
        "General de División",
    ]
    nombres: str
    apellidos: str
    identificacion: str
    funcion_habitual: str = "Tripulante"
    estado: str = "Activo"
    cualificaciones: list[str] = []
    habilitaciones_aeronave: list[str] = []


class AeronaveCreate(BaseModel):
    matricula: str
    modelo: Literal["C-172", "EMB-312/T-27", "T-41", "Mxt-7-180"]
    horas_vuelo_iniciales: float = 0.0
    estado: str = "Servicial"


class MisionCreate(BaseModel):
    codigo: str
    tipo_mision: str
    fecha_salida: str
    observaciones: Optional[str] = None


class PilotoCertificacionCreate(BaseModel):
    id_piloto: int
    id_aeronave: Optional[int] = None
    modelo_aeronave: Optional[str] = None
    tipo_cualificacion: str
    nivel: str = "Tipo"
    estado: str = "Activo"
    observaciones: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class UsuarioCreate(BaseModel):
    username: str
    password: str
    rol: str = "user"
    estado: str = "Activo"


class UsuarioUpdate(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    rol: Optional[str] = None
    estado: Optional[str] = None


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> Usuario:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="No autenticado.")

    user = db.query(Usuario).filter(Usuario.id == user_id, Usuario.estado == "Activo").first()
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no válido o inactivo.")
    return user


def require_admin(current_user: Usuario = Depends(get_current_user)) -> Usuario:
    if current_user.rol != "admin":
        raise HTTPException(status_code=403, detail="No tienes permisos de administrador.")
    return current_user


def serialize_user(user: Usuario) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "rol": user.rol,
        "estado": user.estado,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def ensure_default_admin_user(db: Session) -> None:
    user = db.query(Usuario).filter(Usuario.username == DEFAULT_ADMIN_USERNAME).first()
    if user is None:
        db.add(
            Usuario(
                username=DEFAULT_ADMIN_USERNAME,
                password_hash=hash_password(DEFAULT_ADMIN_PASSWORD),
                rol="admin",
                estado="Activo",
            )
        )
        db.commit()
        return

    if user.rol != "admin":
        user.rol = "admin"
        if user.estado != "Activo":
            user.estado = "Activo"
        db.commit()


def parse_hhmm_to_minutes(value: str) -> int:
    if value is None:
        raise ValueError("La duración del vuelo es obligatoria.")

    text = str(value).strip()
    if not re.fullmatch(r"\d{1,2}:\d{2}", text):
        raise ValueError("La duración del vuelo debe estar en formato HH:MM.")

    hours, minutes = text.split(":")
    hours_int = int(hours)
    minutes_int = int(minutes)
    if minutes_int >= 60:
        raise ValueError("Los minutos de la duración del vuelo no pueden exceder 59.")

    return hours_int * 60 + minutes_int


def normalize_flight_breakdown(
    total_minutes: int,
    horas_diurnas: Optional[float],
    horas_nocturnas: Optional[float],
    horas_nvg: Optional[float],
    horas_instrumentos: Optional[float],
) -> dict:
    if total_minutes <= 0:
        raise HTTPException(status_code=400, detail="La duración del vuelo debe ser mayor que cero.")

    other_minutes = sum(
        float(value or 0) * 60
        for value in [horas_nocturnas, horas_nvg, horas_instrumentos]
    )

    if all((value is None or float(value) == 0) for value in [horas_diurnas, horas_nocturnas, horas_nvg, horas_instrumentos]):
        return {
            "horas_diurnas": total_minutes / 60.0,
            "horas_nocturnas": 0.0,
            "horas_nvg": 0.0,
            "horas_instrumentos": 0.0,
        }

    diurnas_minutes = float(horas_diurnas) * 60 if horas_diurnas is not None else max(total_minutes - other_minutes, 0)
    nocturnas_minutes = float(horas_nocturnas or 0) * 60
    nvg_minutes = float(horas_nvg or 0) * 60
    instrumentos_minutes = float(horas_instrumentos or 0) * 60

    if diurnas_minutes + nocturnas_minutes + nvg_minutes + instrumentos_minutes > total_minutes + 1e-9:
        raise HTTPException(
            status_code=400,
            detail="La suma de las fracciones de vuelo no puede exceder la duración total registrada.",
        )

    return {
        "horas_diurnas": diurnas_minutes / 60.0,
        "horas_nocturnas": nocturnas_minutes / 60.0,
        "horas_nvg": nvg_minutes / 60.0,
        "horas_instrumentos": instrumentos_minutes / 60.0,
    }


class RegistroVueloCreate(BaseModel):
    id_mision: int
    id_aeronave: int
    id_piloto: int
    id_copiloto: Optional[int] = None
    grado_piloto: Optional[str] = None
    origen: str
    destino: str
    fecha_vuelo: date
    horas_vuelo: str
    horas_diurnas: Optional[float] = None
    horas_nocturnas: Optional[float] = None
    horas_nvg: Optional[float] = None
    horas_instrumentos: Optional[float] = None


@app.on_event("startup")
def startup_event() -> None:
    init_db()
    db = next(get_db())
    try:
        ensure_default_admin_user(db)
    finally:
        db.close()


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "message": "Sistema de control de horas de vuelo en línea."}


@app.post("/login")
async def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    username = payload.username.strip()
    user = db.query(Usuario).filter(Usuario.username == username).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Credenciales inválidas.")
    if user.estado != "Activo":
        raise HTTPException(status_code=403, detail="Usuario inactivo.")

    request.session["user_id"] = user.id
    return {"mensaje": "Inicio de sesión correcto.", "user": serialize_user(user)}


@app.post("/logout")
async def logout(request: Request):
    request.session.clear()
    return {"mensaje": "Sesión cerrada."}


@app.get("/me")
def get_me(current_user: Usuario = Depends(get_current_user)) -> dict:
    return {"user": serialize_user(current_user)}


@app.get("/api/usuarios")
def list_usuarios(current_user: Usuario = Depends(require_admin), db: Session = Depends(get_db)):
    items = db.query(Usuario).order_by(Usuario.id).all()
    return [serialize_user(item) for item in items]


@app.post("/usuarios")
@app.post("/api/usuarios")
def create_usuario(payload: UsuarioCreate, current_user: Usuario = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    username = payload.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="El nombre de usuario es obligatorio.")
    if len(payload.password) < 4:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 4 caracteres.")
    existing = db.query(Usuario).filter(Usuario.username == username).first()
    if existing:
        raise HTTPException(status_code=409, detail="El usuario ya existe.")

    rol = payload.rol.lower() if payload.rol else "user"
    if rol not in {"admin", "user"}:
        raise HTTPException(status_code=400, detail="El rol debe ser 'admin' o 'user'.")

    user = Usuario(
        username=username,
        password_hash=hash_password(payload.password),
        rol=rol,
        estado=payload.estado or "Activo",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"mensaje": "Usuario creado correctamente.", "user": serialize_user(user)}


@app.put("/usuarios/{usuario_id}")
@app.put("/api/usuarios/{usuario_id}")
def update_usuario(usuario_id: int, payload: UsuarioUpdate, current_user: Usuario = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    user = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    if payload.username is not None:
        username = payload.username.strip()
        if not username:
            raise HTTPException(status_code=400, detail="El nombre de usuario es obligatorio.")
        existing = db.query(Usuario).filter(Usuario.username == username, Usuario.id != usuario_id).first()
        if existing:
            raise HTTPException(status_code=409, detail="El nombre de usuario ya existe.")
        user.username = username

    if payload.password is not None:
        if len(payload.password) < 4:
            raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 4 caracteres.")
        user.password_hash = hash_password(payload.password)

    if payload.rol is not None:
        rol = payload.rol.lower()
        if rol not in {"admin", "user"}:
            raise HTTPException(status_code=400, detail="El rol debe ser 'admin' o 'user'.")
        user.rol = rol

    if payload.estado is not None:
        user.estado = payload.estado

    db.commit()
    db.refresh(user)
    return {"mensaje": "Usuario actualizado correctamente.", "user": serialize_user(user)}


@app.delete("/usuarios/{usuario_id}")
@app.delete("/api/usuarios/{usuario_id}")
def delete_usuario(usuario_id: int, current_user: Usuario = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    if usuario_id == current_user.id:
        raise HTTPException(status_code=400, detail="No puedes borrar tu propio usuario.")

    user = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    db.delete(user)
    db.commit()
    return {"mensaje": "Usuario eliminado correctamente."}


@app.get("/api/pilotos")
def list_pilotos(current_user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    items = db.query(PilotoTripulante).order_by(PilotoTripulante.apellidos).all()
    result = []
    for item in items:
        qualifications = db.query(PilotoCertificacion).filter(
            PilotoCertificacion.id_piloto == item.id,
            PilotoCertificacion.id_aeronave.is_(None),
            PilotoCertificacion.tipo_cualificacion.in_(OPERATIONAL_QUALIFICATIONS),
        ).all()
        result.append(
            {
                "id": item.id,
                "grado": item.grado,
                "nombres": item.nombres,
                "apellidos": item.apellidos,
                "identificacion": item.identificacion,
                "funcion_habitual": item.funcion_habitual,
                "estado": item.estado,
                "nombre_completo": f"{item.grado} {item.nombres} {item.apellidos}",
                "cualificaciones": [qualification.tipo_cualificacion for qualification in qualifications],
                "habilitaciones_aeronave": [qualification.tipo_aeronave for qualification in item.habilitaciones_aeronave],
            }
        )
    return result


@app.get("/api/aeronaves")
def list_aeronaves(current_user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    items = db.query(Aeronave).order_by(Aeronave.matricula).all()
    result = []
    for aircraft in items:
        flight_minutes = sum(
            registro.tiempo_total_minutos or 0
            for registro in db.query(RegistroVuelo).filter(RegistroVuelo.id_aeronave == aircraft.id).all()
        )
        horas_actuales = float(aircraft.horas_vuelo_iniciales or 0) + flight_minutes / 60.0
        result.append(
            {
                "id": aircraft.id,
                "matricula": aircraft.matricula,
                "modelo": aircraft.modelo,
                "estado": aircraft.estado,
                "horas_vuelo_iniciales": aircraft.horas_vuelo_iniciales,
                "horas_actuales": round(horas_actuales, 2),
            }
        )
    return result


@app.get("/api/misiones")
def list_misiones(current_user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    items = db.query(Mision).order_by(Mision.fecha_salida.desc()).all()
    return [
        {
            "id": record.id,
            "codigo": record.codigo,
            "tipo_mision": record.tipo_mision,
            "fecha_salida": record.fecha_salida.isoformat(),
            "observaciones": record.observaciones,
        }
        for record in items
    ]


@app.get("/api/vuelos")
def list_vuelos(current_user: Usuario = Depends(require_admin), db: Session = Depends(get_db)):
    items = db.query(RegistroVuelo).order_by(RegistroVuelo.fecha_vuelo.desc(), RegistroVuelo.id.desc()).all()
    result = []
    for item in items:
        piloto = db.query(PilotoTripulante).filter(PilotoTripulante.id == item.id_piloto).first()
        copiloto = db.query(PilotoTripulante).filter(PilotoTripulante.id == item.id_copiloto).first() if item.id_copiloto else None
        aeronave = db.query(Aeronave).filter(Aeronave.id == item.id_aeronave).first()
        mision = db.query(Mision).filter(Mision.id == item.id_mision).first()
        result.append(
            {
                "id": item.id,
                "id_mision": item.id_mision,
                "mision": mision.codigo if mision else "",
                "id_aeronave": item.id_aeronave,
                "aeronave": aeronave.matricula if aeronave else "",
                "id_piloto": item.id_piloto,
                "grado_piloto": item.grado_piloto,
                "piloto": f"{piloto.grado} {piloto.nombres} {piloto.apellidos}" if piloto else "",
                "id_copiloto": item.id_copiloto,
                "copiloto": f"{copiloto.grado} {copiloto.nombres} {copiloto.apellidos}" if copiloto else "",
                "origen": item.origen,
                "destino": item.destino,
                "fecha_vuelo": item.fecha_vuelo.isoformat(),
                "horas_vuelo": item.horas_vuelo,
                "horas_diurnas": item.horas_diurnas,
                "horas_nocturnas": item.horas_nocturnas,
                "horas_nvg": item.horas_nvg,
                "horas_instrumentos": item.horas_instrumentos,
            }
        )
    return result


@app.get("/api/certificaciones")
def list_certificaciones(current_user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    items = db.query(PilotoCertificacion).order_by(PilotoCertificacion.id.desc()).all()
    result = []
    for item in items:
        piloto = db.query(PilotoTripulante).filter(PilotoTripulante.id == item.id_piloto).first()
        aeronave = db.query(Aeronave).filter(Aeronave.id == item.id_aeronave).first() if item.id_aeronave else None
        result.append(
            {
                "id": item.id,
                "id_piloto": item.id_piloto,
                "piloto": f"{piloto.grado} {piloto.nombres} {piloto.apellidos}" if piloto else "",
                "id_aeronave": item.id_aeronave,
                "aeronave": aeronave.matricula if aeronave else item.modelo_aeronave,
                "tipo_cualificacion": item.tipo_cualificacion,
                "nivel": item.nivel,
                "estado": item.estado,
                "observaciones": item.observaciones,
            }
        )
    return result


@app.post("/certificaciones")
@app.post("/api/certificaciones")
def create_certificacion(payload: PilotoCertificacionCreate, current_user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    piloto = db.query(PilotoTripulante).filter(PilotoTripulante.id == payload.id_piloto).first()
    if not piloto:
        raise HTTPException(status_code=404, detail="Piloto no encontrado.")

    if payload.id_aeronave is not None:
        aeronave = db.query(Aeronave).filter(Aeronave.id == payload.id_aeronave).first()
        if not aeronave:
            raise HTTPException(status_code=404, detail="Aeronave no encontrada.")
        modelo = aeronave.modelo
    else:
        modelo = payload.modelo_aeronave

    item = PilotoCertificacion(
        id_piloto=payload.id_piloto,
        id_aeronave=payload.id_aeronave,
        modelo_aeronave=modelo,
        tipo_cualificacion=payload.tipo_cualificacion,
        nivel=payload.nivel,
        estado=payload.estado,
        observaciones=payload.observaciones,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"id": item.id, "mensaje": "Cualificación registrada correctamente."}


@app.put("/certificaciones/{certificacion_id}")
@app.put("/api/certificaciones/{certificacion_id}")
def update_certificacion(certificacion_id: int, payload: PilotoCertificacionCreate, current_user: Usuario = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    item = db.query(PilotoCertificacion).filter(PilotoCertificacion.id == certificacion_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Cualificación no encontrada.")

    item.id_piloto = payload.id_piloto
    item.id_aeronave = payload.id_aeronave
    item.modelo_aeronave = payload.modelo_aeronave
    item.tipo_cualificacion = payload.tipo_cualificacion
    item.nivel = payload.nivel
    item.estado = payload.estado
    item.observaciones = payload.observaciones
    db.commit()
    return {"id": item.id, "mensaje": "Cualificación actualizada correctamente."}


@app.delete("/certificaciones/{certificacion_id}")
@app.delete("/api/certificaciones/{certificacion_id}")
def delete_certificacion(certificacion_id: int, current_user: Usuario = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    item = db.query(PilotoCertificacion).filter(PilotoCertificacion.id == certificacion_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Cualificación no encontrada.")
    db.delete(item)
    db.commit()
    return {"mensaje": "Cualificación eliminada correctamente."}


OPERATIONAL_QUALIFICATIONS = {
    "Instructor",
    "Capitán de nave",
    "Piloto regular",
    "IFR",
    "NVG",
    "Inglés ICAO 4",
    "Táctico",
}


def sync_pilot_qualifications(piloto_id: int, qualifications: list[str], db: Session) -> None:
    selected = {
        qualification.strip()
        for qualification in qualifications
        if qualification and qualification.strip() in OPERATIONAL_QUALIFICATIONS
    }
    existing = db.query(PilotoCertificacion).filter(
        PilotoCertificacion.id_piloto == piloto_id,
        PilotoCertificacion.id_aeronave.is_(None),
        PilotoCertificacion.tipo_cualificacion.in_(OPERATIONAL_QUALIFICATIONS),
    ).all()
    existing_by_type = {item.tipo_cualificacion: item for item in existing}

    for item in existing:
        if item.tipo_cualificacion not in selected:
            db.delete(item)

    for qualification in selected:
        if qualification not in existing_by_type:
            db.add(PilotoCertificacion(id_piloto=piloto_id, tipo_cualificacion=qualification))


def sync_aircraft_qualifications(piloto_id: int, qualifications: list[str], db: Session) -> None:
    selected = {qualification.strip() for qualification in qualifications if qualification in AIRCRAFT_TYPES}
    existing = db.query(PilotoHabilitacionAeronave).filter(PilotoHabilitacionAeronave.id_piloto == piloto_id).all()
    existing_by_type = {item.tipo_aeronave: item for item in existing}

    for item in existing:
        if item.tipo_aeronave not in selected:
            db.delete(item)

    for qualification in selected:
        if qualification not in existing_by_type:
            db.add(PilotoHabilitacionAeronave(id_piloto=piloto_id, tipo_aeronave=qualification))


@app.post("/pilotos")
def create_piloto(payload: PilotoCreate, current_user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    piloto_data = payload.model_dump(exclude={"cualificaciones", "habilitaciones_aeronave"})
    piloto = PilotoTripulante(**piloto_data)
    db.add(piloto)
    db.flush()
    sync_pilot_qualifications(piloto.id, payload.cualificaciones, db)
    sync_aircraft_qualifications(piloto.id, payload.habilitaciones_aeronave, db)
    db.commit()
    db.refresh(piloto)
    return {"id": piloto.id, "mensaje": "Piloto registrado correctamente."}


@app.put("/pilotos/{piloto_id}")
def update_piloto(piloto_id: int, payload: PilotoCreate, current_user: Usuario = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    piloto = db.query(PilotoTripulante).filter(PilotoTripulante.id == piloto_id).first()
    if not piloto:
        raise HTTPException(status_code=404, detail="Piloto no encontrado.")

    for key, value in payload.model_dump(exclude={"cualificaciones", "habilitaciones_aeronave"}).items():
        setattr(piloto, key, value)
    sync_pilot_qualifications(piloto.id, payload.cualificaciones, db)
    sync_aircraft_qualifications(piloto.id, payload.habilitaciones_aeronave, db)
    db.commit()
    return {"id": piloto.id, "mensaje": "Piloto actualizado correctamente."}


@app.delete("/pilotos/{piloto_id}")
def delete_piloto(piloto_id: int, current_user: Usuario = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    piloto = db.query(PilotoTripulante).filter(PilotoTripulante.id == piloto_id).first()
    if not piloto:
        raise HTTPException(status_code=404, detail="Piloto no encontrado.")
    db.query(PilotoCertificacion).filter(PilotoCertificacion.id_piloto == piloto_id).delete(synchronize_session=False)
    db.delete(piloto)
    db.commit()
    return {"mensaje": "Piloto eliminado correctamente."}


@app.post("/aeronaves")
def create_aeronave(payload: AeronaveCreate, current_user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    aeronave = Aeronave(**payload.model_dump())
    db.add(aeronave)
    db.commit()
    db.refresh(aeronave)
    return {"id": aeronave.id, "mensaje": "Aeronave registrada correctamente."}


@app.put("/aeronaves/{aeronave_id}")
def update_aeronave(aeronave_id: int, payload: AeronaveCreate, current_user: Usuario = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    aeronave = db.query(Aeronave).filter(Aeronave.id == aeronave_id).first()
    if not aeronave:
        raise HTTPException(status_code=404, detail="Aeronave no encontrada.")

    for key, value in payload.model_dump().items():
        setattr(aeronave, key, value)
    db.commit()
    return {"id": aeronave.id, "mensaje": "Aeronave actualizada correctamente."}


@app.delete("/aeronaves/{aeronave_id}")
def delete_aeronave(aeronave_id: int, current_user: Usuario = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    aeronave = db.query(Aeronave).filter(Aeronave.id == aeronave_id).first()
    if not aeronave:
        raise HTTPException(status_code=404, detail="Aeronave no encontrada.")
    db.delete(aeronave)
    db.commit()
    return {"mensaje": "Aeronave eliminada correctamente."}


@app.post("/misiones")
def create_mision(payload: MisionCreate, current_user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    mision = Mision(
        codigo=payload.codigo,
        tipo_mision=payload.tipo_mision,
        fecha_salida=datetime.strptime(payload.fecha_salida, "%Y-%m-%d").date(),
        observaciones=payload.observaciones,
    )
    db.add(mision)
    db.commit()
    db.refresh(mision)
    return {"id": mision.id, "mensaje": "Misión registrada correctamente."}


@app.put("/misiones/{mision_id}")
def update_mision(mision_id: int, payload: MisionCreate, current_user: Usuario = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    mision = db.query(Mision).filter(Mision.id == mision_id).first()
    if not mision:
        raise HTTPException(status_code=404, detail="Misión no encontrada.")

    mision.codigo = payload.codigo
    mision.tipo_mision = payload.tipo_mision
    mision.fecha_salida = datetime.strptime(payload.fecha_salida, "%Y-%m-%d").date()
    mision.observaciones = payload.observaciones
    db.commit()
    return {"id": mision.id, "mensaje": "Misión actualizada correctamente."}


@app.delete("/misiones/{mision_id}")
def delete_mision(mision_id: int, current_user: Usuario = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    mision = db.query(Mision).filter(Mision.id == mision_id).first()
    if not mision:
        raise HTTPException(status_code=404, detail="Misión no encontrada.")
    db.delete(mision)
    db.commit()
    return {"mensaje": "Misión eliminada correctamente."}


@app.post("/api/seed-demo")
def seed_demo_data(current_user: Usuario = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    pilotos_count = db.query(PilotoTripulante).count()
    if pilotos_count > 0:
        return {"mensaje": "Los datos de demostración ya existen.", "creados": 0}

    pilotos = [
        PilotoTripulante(grado="Capitán", nombres="José", apellidos="López", identificacion="P-001", funcion_habitual="Piloto al Mando", estado="Activo"),
        PilotoTripulante(grado="Primer Teniente", nombres="Carlos", apellidos="Martínez", identificacion="P-002", funcion_habitual="Copiloto", estado="Activo"),
        PilotoTripulante(grado="Teniente", nombres="Luis", apellidos="García", identificacion="P-003", funcion_habitual="Ingeniero de Vuelo", estado="Activo"),
    ]
    db.add_all(pilotos)
    db.flush()

    aeronaves = [
        Aeronave(matricula="F-101", modelo="EMB-312/T-27", horas_vuelo_iniciales=150.0, estado="Servicial"),
        Aeronave(matricula="F-102", modelo="EMB-312/T-27", horas_vuelo_iniciales=120.0, estado="Servicial"),
    ]
    db.add_all(aeronaves)
    db.flush()

    misiones = [
        Mision(codigo="M-101", tipo_mision="Patrulla", fecha_salida=datetime.strptime("2026-09-10", "%Y-%m-%d").date(), observaciones="Coordinación aérea regional."),
        Mision(codigo="M-102", tipo_mision="Traslado", fecha_salida=datetime.strptime("2026-09-11", "%Y-%m-%d").date(), observaciones="Desplazamiento técnico."),
    ]
    db.add_all(misiones)
    db.flush()

    db.commit()
    return {"mensaje": "Datos de demostración cargados correctamente.", "creados": 3 + 2 + 2}


@app.post("/vuelos/register")
@app.post("/api/vuelos/register")
def register_vuelo(payload: RegistroVueloCreate, current_user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    try:
        total_minutes = parse_hhmm_to_minutes(payload.horas_vuelo)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    fracciones = normalize_flight_breakdown(
        total_minutes=total_minutes,
        horas_diurnas=payload.horas_diurnas,
        horas_nocturnas=payload.horas_nocturnas,
        horas_nvg=payload.horas_nvg,
        horas_instrumentos=payload.horas_instrumentos,
    )
    piloto = db.query(PilotoTripulante).filter(PilotoTripulante.id == payload.id_piloto).first()
    if not piloto:
        raise HTTPException(status_code=404, detail="Piloto no encontrado.")

    vuelo = RegistroVuelo(
        id_mision=payload.id_mision,
        id_aeronave=payload.id_aeronave,
        id_piloto=payload.id_piloto,
        id_copiloto=payload.id_copiloto,
        grado_piloto=payload.grado_piloto or piloto.grado,
        origen=payload.origen,
        destino=payload.destino,
        fecha_vuelo=payload.fecha_vuelo,
        horas_vuelo=payload.horas_vuelo,
        tiempo_total_minutos=float(total_minutes),
        horas_diurnas=fracciones["horas_diurnas"],
        horas_nocturnas=fracciones["horas_nocturnas"],
        horas_nvg=fracciones["horas_nvg"],
        horas_instrumentos=fracciones["horas_instrumentos"],
    )

    db.add(vuelo)
    db.commit()
    db.refresh(vuelo)
    return {"id": vuelo.id, "mensaje": "Vuelo registrado correctamente."}


@app.put("/vuelos/{vuelo_id}")
@app.put("/api/vuelos/{vuelo_id}")
def update_vuelo(vuelo_id: int, payload: RegistroVueloCreate, current_user: Usuario = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    vuelo = db.query(RegistroVuelo).filter(RegistroVuelo.id == vuelo_id).first()
    if not vuelo:
        raise HTTPException(status_code=404, detail="Vuelo no encontrado.")

    try:
        total_minutes = parse_hhmm_to_minutes(payload.horas_vuelo)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    fracciones = normalize_flight_breakdown(
        total_minutes=total_minutes,
        horas_diurnas=payload.horas_diurnas,
        horas_nocturnas=payload.horas_nocturnas,
        horas_nvg=payload.horas_nvg,
        horas_instrumentos=payload.horas_instrumentos,
    )

    vuelo.id_mision = payload.id_mision
    vuelo.id_aeronave = payload.id_aeronave
    vuelo.id_piloto = payload.id_piloto
    vuelo.id_copiloto = payload.id_copiloto
    if payload.grado_piloto is not None:
        vuelo.grado_piloto = payload.grado_piloto
    vuelo.origen = payload.origen
    vuelo.destino = payload.destino
    vuelo.fecha_vuelo = payload.fecha_vuelo
    vuelo.horas_vuelo = payload.horas_vuelo
    vuelo.tiempo_total_minutos = float(total_minutes)
    vuelo.horas_diurnas = fracciones["horas_diurnas"]
    vuelo.horas_nocturnas = fracciones["horas_nocturnas"]
    vuelo.horas_nvg = fracciones["horas_nvg"]
    vuelo.horas_instrumentos = fracciones["horas_instrumentos"]
    db.commit()
    return {"id": vuelo.id, "mensaje": "Vuelo actualizado correctamente."}


@app.delete("/vuelos/{vuelo_id}")
@app.delete("/api/vuelos/{vuelo_id}")
def delete_vuelo(vuelo_id: int, current_user: Usuario = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    vuelo = db.query(RegistroVuelo).filter(RegistroVuelo.id == vuelo_id).first()
    if not vuelo:
        raise HTTPException(status_code=404, detail="Vuelo no encontrado.")
    db.delete(vuelo)
    db.commit()
    return {"mensaje": "Vuelo eliminado correctamente."}


def build_report_rows(db: Session, id_piloto: Optional[int] = None, id_aeronave: Optional[int] = None, fecha_desde: Optional[str] = None, fecha_hasta: Optional[str] = None, tipo_vuelo: Optional[str] = None):
    query = db.query(RegistroVuelo)

    if id_piloto is not None:
        query = query.filter(RegistroVuelo.id_piloto == id_piloto)

    if id_aeronave is not None:
        query = query.filter(RegistroVuelo.id_aeronave == id_aeronave)

    if fecha_desde:
        date_from = datetime.strptime(fecha_desde, "%Y-%m-%d").date()
        query = query.filter(RegistroVuelo.fecha_vuelo >= date_from)

    if fecha_hasta:
        date_to = datetime.strptime(fecha_hasta, "%Y-%m-%d").date()
        query = query.filter(RegistroVuelo.fecha_vuelo <= date_to)

    if tipo_vuelo:
        tipo = tipo_vuelo.lower()
        if tipo == "diurno":
            query = query.filter(RegistroVuelo.horas_diurnas > 0)
        elif tipo == "nocturno":
            query = query.filter(RegistroVuelo.horas_nocturnas > 0)
        elif tipo == "nvg":
            query = query.filter(RegistroVuelo.horas_nvg > 0)
        elif tipo == "instrumentos":
            query = query.filter(RegistroVuelo.horas_instrumentos > 0)

    result = []
    for reg in query.all():
        piloto = db.query(PilotoTripulante).filter(PilotoTripulante.id == reg.id_piloto).first()
        aeronave = db.query(Aeronave).filter(Aeronave.id == reg.id_aeronave).first()
        copiloto = db.query(PilotoTripulante).filter(PilotoTripulante.id == reg.id_copiloto).first()

        result.append(
            {
                "fecha": reg.fecha_vuelo.isoformat(),
                "mision": reg.mision.codigo if reg.mision else "Misión no disponible",
                "matricula": aeronave.matricula if aeronave else "",
                "piloto": f"{piloto.nombres} {piloto.apellidos}" if piloto else "",
                "grado_piloto": reg.grado_piloto,
                "copiloto": f"{copiloto.nombres} {copiloto.apellidos}" if copiloto else "",
                "origen": reg.origen,
                "destino": reg.destino,
                "hora_salida": None,
                "hora_llegada": None,
                "tiempo_total": round(reg.tiempo_total_minutos / 60.0, 2),
                "diurna": reg.horas_diurnas,
                "nocturna": reg.horas_nocturnas,
                "nvg": reg.horas_nvg,
                "instrumentos": reg.horas_instrumentos,
                "duracion_vuelo": reg.horas_vuelo,
            }
        )

    return result


@app.get("/api/report")
def get_report(
    id_piloto: Optional[int] = Query(default=None),
    id_aeronave: Optional[int] = Query(default=None),
    fecha_desde: Optional[str] = Query(default=None),
    fecha_hasta: Optional[str] = Query(default=None),
    tipo_vuelo: Optional[str] = Query(default=None),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return build_report_rows(db, id_piloto, id_aeronave, fecha_desde, fecha_hasta, tipo_vuelo)


@app.get("/export/report")
def export_report(
    id_piloto: Optional[int] = Query(default=None),
    id_aeronave: Optional[int] = Query(default=None),
    fecha_desde: Optional[str] = Query(default=None),
    fecha_hasta: Optional[str] = Query(default=None),
    tipo_vuelo: Optional[str] = Query(default=None),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = build_report_rows(db, id_piloto, id_aeronave, fecha_desde, fecha_hasta, tipo_vuelo)
    export_dir = BASE_DIR.parent / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    filename = export_dir / "reporte_horas.xlsx"
    generated = export_flight_report(rows, filename)
    return FileResponse(generated, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename="reporte_horas.xlsx")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
