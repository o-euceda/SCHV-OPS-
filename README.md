# Sistema de Contabilización y Control de Horas de Vuelo

Sistema cliente-servidor para la Sección de Operaciones de un Escuadrón Aéreo. Está diseñado para operar en una LAN privada con un servidor central y múltiples clientes conectados por IP local.

## Objetivo

Centralizar la información de:
- Pilotos / tripulantes
- Aeronaves
- Misiones
- Bitácoras de vuelo
- Reportes de horas acumuladas
- Exportación a Excel profesional

## Arquitectura

- Servidor central: PostgreSQL + backend FastAPI
- Clientes: estaciones de trabajo en la LAN, cada una con acceso a la API central
- Exportación: reportes en .xlsx con formato profesional

## Estructura del proyecto

```text
Control de Horas JESC/
├── README.md
├── requirements.txt
├── config.ini.example
├── app/
│   ├── __init__.py
│   ├── models.py
│   ├── database.py
│   ├── exporter.py
│   └── main.py
└── data/
    └── .gitkeep
```

## Requisitos

- Python 3.10+
- PostgreSQL 14+
- Pip
- Acceso a LAN privada / red cerrada

## Instalación rápida

1. Crear entorno virtual

```bash
python -m venv .venv
source .venv/bin/activate
```

2. Instalar dependencias

```bash
pip install -r requirements.txt
```

3. Configurar base de datos

- Copiar ejemplo:

```bash
cp config.ini.example config.ini
```

- Ajustar IP, puerto, usuario y contraseña.

4. Crear base de datos y tablas

```bash
python -c "from app.database import init_db; init_db()"
```

5. Ejecutar backend

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Endpoints principales

- GET /health
- POST /pilotos
- POST /aeronaves
- POST /misiones
- POST /vuelos/register
- GET /vuelos/report

## Exportación a Excel

Ejemplo:

```python
from app.exporter import export_flight_report

rows = [
    {
        "fecha": "2026-09-10",
        "matricula": "F-101",
        "piloto": "Capitán Ruiz",
        "tot_horas": 2.5,
        "diurna": 1.5,
        "nocturna": 1.0,
    }
]

export_flight_report(rows, "reporte_horas.xlsx")
```

## Notas de seguridad

- No exponer el servicio públicamente.
- Usar firewall local.
- Mantener la base de datos en un servidor interno no accesible desde Internet.
- Usar credenciales privativas y no hardcodeadas en producción.

## Soporte

Este proyecto ofrece la base arquitectónica para un sistema operativo en una sección de operaciones. Se recomienda expandirlo con:
- autenticación de usuarios
- permisos por rol
- auditoría de cambios
- interfaz cliente PyQt6 o web con Bootstrap
- sincronización de respaldo
