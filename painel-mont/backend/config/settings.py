"""
Configuração Django.

Django é usado aqui como CAMADA DE DADOS: ORM, migrations, admin e os comandos
de carga. A API analítica que o front consome é FastAPI (ver backend/api/main.py).

Banco: SQLite por padrão, para que `make seed` funcione em qualquer máquina sem
infraestrutura. Definir DATABASE_URL aponta para PostgreSQL sem tocar em código —
o modelo dimensional foi escrito para os dois.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-only-nao-usar-em-producao")
DEBUG = os.getenv("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]
WSGI_APPLICATION = "config.wsgi.application"

_db_url = os.getenv("DATABASE_URL", "")
if _db_url.startswith("postgres"):
    # postgres://user:pass@host:port/dbname
    from urllib.parse import urlparse

    u = urlparse(_db_url)
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": u.path.lstrip("/"),
        "USER": u.username,
        "PASSWORD": u.password,
        "HOST": u.hostname,
        "PORT": u.port or 5432,
    }}
else:
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "painel_mont.sqlite3",
    }}

AUTH_PASSWORD_VALIDATORS = []
LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Sinalização de dados de demonstração.
# O briefing (seção 14) rejeita "dados inexistentes apresentados como se fossem
# reais". Enquanto a base oficial não for disponibilizada, a API devolve esta
# flag em toda resposta e o front exibe um aviso permanente e não dispensável.
# ---------------------------------------------------------------------------
DADOS_DEMONSTRATIVOS = os.getenv("DADOS_DEMONSTRATIVOS", "1") == "1"
