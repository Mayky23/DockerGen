#!/usr/bin/env python3
"""
DockerGen - Generador interactivo de archivos docker-compose.yml.

Uso (el script no tiene parámetros, todo se pregunta de forma interactiva):

    python3 DockerGen.py

Al arrancar comprueba que las dependencias (rich y PyYAML) están instaladas
y, si faltan o están desactualizadas, las instala automáticamente.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

__version__ = "2.0"


# ---------------------------------------------------------------------------
# Comprobación e instalación automática de dependencias.
# Solo usa la biblioteca estándar: se ejecuta antes de importar rich y PyYAML.
# ---------------------------------------------------------------------------

MIN_PYTHON = (3, 8)

# (módulo que se importa, paquete de pip, versión mínima).
# Mantener en sincronía con requirements.txt.
REQUIREMENTS = (
    ("rich", "rich", (12, 0)),
    ("yaml", "PyYAML", (5, 4)),
)

SCRIPT_PATH = Path(__file__).resolve()
LOCAL_VENV = SCRIPT_PATH.parent / ".venv"
BOOTSTRAP_FLAG = "DOCKERGEN_BOOTSTRAPPED"


def check_python_version():
    """ Termina con un mensaje claro si la versión de Python es demasiado antigua. """
    if sys.version_info < MIN_PYTHON:
        print(
            f"[ERROR] DockerGen necesita Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} o superior "
            f"(versión actual: {sys.version.split()[0]})."
        )
        sys.exit(1)


def _version_tuple(version: str) -> tuple:
    return tuple(int(part) for part in re.findall(r"\d+", version)[:2])


def _requirement_spec(package: str, min_version: tuple) -> str:
    return f"{package}>={'.'.join(str(n) for n in min_version)}"


def missing_requirements() -> list:
    """ Devuelve las dependencias (formato pip) que faltan o están desactualizadas. """
    import importlib.util
    from importlib import metadata

    missing = []
    for module, package, min_version in REQUIREMENTS:
        spec = _requirement_spec(package, min_version)
        if importlib.util.find_spec(module) is None:
            missing.append(spec)
            continue
        try:
            installed = metadata.version(package)
        except metadata.PackageNotFoundError:
            continue  # Se puede importar aunque no tenga metadatos (p. ej. paquete del sistema).
        if _version_tuple(installed) < min_version:
            missing.append(spec)
    return missing


def _run(command: list):
    """ Ejecuta un comando y devuelve (ok, salida). """
    try:
        result = subprocess.run(
            [str(part) for part in command],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        )
    except OSError as exc:
        return False, str(exc)
    return result.returncode == 0, result.stdout.strip()


def _pip_install(python, specs: list, user: bool = False):
    command = [python, "-m", "pip", "install", "--disable-pip-version-check"]
    if user:
        command.append("--user")
    return _run(command + specs)


def _venv_python(venv: Path) -> Path:
    if os.name == "nt":
        return venv / "Scripts" / "python.exe"
    return venv / "bin" / "python"


def _relaunch(python, after_install: bool = True):
    """
    Vuelve a ejecutar DockerGen con el intérprete indicado. Si 'after_install' es True,
    el nuevo proceso ya no intentará instalar nada (evita bucles si algo falla).
    """
    env = dict(os.environ)
    if after_install:
        env[BOOTSTRAP_FLAG] = "1"
    args = [str(python), str(SCRIPT_PATH)]
    sys.stdout.flush()
    try:
        if os.name != "nt":
            os.execve(args[0], args, env)
        code = subprocess.call(args, env=env)
    except KeyboardInterrupt:
        code = 130
    except OSError:
        return  # Intérprete no utilizable: se sigue con la siguiente opción.
    sys.exit(code)


def _install_failed(specs: list, detail: str):
    print(f"\n[ERROR] No se pudieron instalar automáticamente: {', '.join(specs)}")
    if detail:
        print("Detalle:")
        for line in detail.splitlines()[-8:]:
            print(f"    {line}")
    requirements_file = SCRIPT_PATH.parent / "requirements.txt"
    if requirements_file.exists():
        target = f'-r "{requirements_file}"'
    else:
        target = " ".join(f'"{spec}"' for spec in specs)
    print("\nInstálelas manualmente con:")
    print(f"    python3 -m pip install {target}\n")
    sys.exit(1)


def ensure_requirements():
    """ Comprueba las dependencias y, si hace falta, las instala y reinicia el script. """
    missing = missing_requirements()
    if not missing:
        return
    if os.environ.get(BOOTSTRAP_FLAG):
        _install_failed(missing, "Las dependencias siguen sin estar disponibles después de instalarlas.")

    in_local_venv = Path(sys.prefix).resolve() == LOCAL_VENV.resolve()
    venv_python = _venv_python(LOCAL_VENV)

    # 1) Entorno virtual local creado en una ejecución anterior: se usa directamente
    #    (si allí faltara algo, esa ejecución lo instalará en el propio entorno).
    if venv_python.exists() and not in_local_venv:
        _relaunch(venv_python, after_install=False)

    print(f"[DockerGen] Faltan dependencias: {', '.join(missing)}")
    print("[DockerGen] Instalándolas automáticamente, espere unos segundos...")

    all_specs = [_requirement_spec(package, version) for _, package, version in REQUIREMENTS]

    # 2) Intérprete actual (fuera de un entorno virtual se prueba también con --user).
    ok, detail = _pip_install(sys.executable, missing)
    if not ok and sys.prefix == sys.base_prefix:
        ok, detail = _pip_install(sys.executable, missing, user=True)
    if ok:
        _relaunch(sys.executable)

    # 3) Python gestionado por el sistema (PEP 668) o sin pip: entorno virtual propio.
    if not in_local_venv and not venv_python.exists():
        print(f"[DockerGen] Creando un entorno virtual en {LOCAL_VENV} ...")
        ok, detail = _run([sys.executable, "-m", "venv", LOCAL_VENV])
        if ok:
            ok, detail = _pip_install(venv_python, all_specs)
            if ok:
                _relaunch(venv_python)

    _install_failed(missing, detail)


check_python_version()
try:
    ensure_requirements()
except KeyboardInterrupt:
    print("\n[DockerGen] Instalación cancelada por el usuario.")
    sys.exit(130)

import ipaddress  # noqa: E402
import shutil  # noqa: E402
from collections import namedtuple  # noqa: E402

import yaml  # noqa: E402
from rich.console import Console  # noqa: E402
from rich.panel import Panel  # noqa: E402
from rich.rule import Rule  # noqa: E402
from rich.syntax import Syntax  # noqa: E402
from rich.table import Table  # noqa: E402
from rich.text import Text  # noqa: E402

console = Console()

DEFAULT_OUTPUT = "docker-compose.yml"
YAML_HEADER = f"# Generado con DockerGen {__version__} - https://github.com/Mayky23/DockerGen\n"


# ---------------------------------------------------------------------------
# Validaciones. Son funciones puras: devuelven el valor válido o lanzan
# ValueError con un mensaje en español que se muestra al usuario.
# ---------------------------------------------------------------------------

NAME_RE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.-]*")
CONTAINER_NAME_RE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.-]+")
PROJECT_NAME_RE = re.compile(r"[a-z0-9][a-z0-9_-]*")
ENV_KEY_RE = re.compile(r"[^\s=]+")
CPUS_RE = re.compile(r"[0-9]+(?:\.[0-9]+)?")
MEMORY_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?) ?([kmgtp]?)(?:i?b)?", re.IGNORECASE)
DURATION_RE = re.compile(r"(?:[0-9]+(?:\.[0-9]+)?(?:ns|us|ms|s|m|h))+")
POSITIVE_INT_RE = re.compile(r"[0-9]+")
IMAGE_PATH_RE = re.compile(r"[a-z0-9]+(?:(?:[._]|__|-+)[a-z0-9]+)*")
IMAGE_TAG_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}")
IMAGE_DIGEST_RE = re.compile(r"[A-Za-z][A-Za-z0-9]*(?:[-_+.][A-Za-z][A-Za-z0-9]*)*:[0-9a-fA-F]{32,}")
REGISTRY_RE = re.compile(r"[A-Za-z0-9.-]+(?::[0-9]+)?")
WINDOWS_DRIVE_RE = re.compile(r"[A-Za-z]:[\\/]")
PORT_RE = re.compile(
    r"(?:(?P<ip>\[[0-9a-fA-F:.]+\]|[0-9]{1,3}(?:\.[0-9]{1,3}){3}):(?P<ip_host>[0-9]+(?:-[0-9]+)?)?:"
    r"|(?P<host>[0-9]+(?:-[0-9]+)?):)?"
    r"(?P<container>[0-9]+(?:-[0-9]+)?)"
    r"(?:/(?P<proto>tcp|udp|sctp))?"
)

MEMORY_UNITS = {"": 1, "k": 1024, "m": 1024 ** 2, "g": 1024 ** 3, "t": 1024 ** 4, "p": 1024 ** 5}
MIN_MEMORY = 6 * 1024 ** 2  # Mínimo que admite Docker.
VOLUME_MODES = {"ro", "rw", "z", "Z", "cached", "delegated", "consistent", "nocopy"}

PortMapping = namedtuple("PortMapping", "ip host container proto")
Volume = namedtuple("Volume", "source target mode named")


def validate_service_name(name: str, existing=()) -> str:
    if not NAME_RE.fullmatch(name):
        raise ValueError(
            "Nombre no válido: use solo letras, números, '.', '_' o '-' (sin espacios) "
            "y empiece por una letra o un número."
        )
    if name in existing:
        raise ValueError(f"Ya existe un servicio llamado '{name}'.")
    return name


def validate_project_name(name: str) -> str:
    if not PROJECT_NAME_RE.fullmatch(name):
        raise ValueError(
            "Nombre de proyecto no válido: use minúsculas, números, '_' o '-' "
            "y empiece por una letra o un número."
        )
    return name


def validate_network_name(name: str) -> str:
    if not NAME_RE.fullmatch(name):
        raise ValueError(f"'{name}' no es un nombre de red válido (letras, números, '.', '_' o '-').")
    return name


def validate_container_name(name: str, used=()) -> str:
    if not CONTAINER_NAME_RE.fullmatch(name):
        raise ValueError(
            "Nombre de contenedor no válido: mínimo 2 caracteres, solo letras, números, "
            "'.', '_' o '-', empezando por letra o número."
        )
    if name in used:
        raise ValueError(f"El nombre de contenedor '{name}' ya lo usa otro servicio.")
    return name


def validate_image(image: str) -> str:
    """ Valida una referencia de imagen: [registro/]ruta[:etiqueta][@digest]. """
    if re.search(r"\s", image):
        raise ValueError("El nombre de la imagen no puede contener espacios.")
    if "$" in image:
        return image  # Usa variables de Compose (ej. miapp:${TAG}); se resuelven al ejecutar.
    name, _, digest = image.partition("@")
    if digest and not IMAGE_DIGEST_RE.fullmatch(digest):
        raise ValueError("El digest de la imagen no es válido (ej. @sha256:<hash>).")
    if ":" in name.rsplit("/", 1)[-1]:
        name, tag = name.rsplit(":", 1)
        if not IMAGE_TAG_RE.fullmatch(tag):
            raise ValueError(f"La etiqueta '{tag}' no es válida.")
    parts = name.split("/")
    if len(parts) > 1 and ("." in parts[0] or ":" in parts[0] or parts[0] == "localhost"):
        registry, parts = parts[0], parts[1:]
        if not REGISTRY_RE.fullmatch(registry):
            raise ValueError(f"El registro '{registry}' no es válido.")
    for part in parts:
        if not IMAGE_PATH_RE.fullmatch(part):
            raise ValueError(
                f"'{part}' no es válido en el nombre de la imagen: use minúsculas, números, "
                "'.', '_' o '-' (ej. nginx, bitnami/redis:7.2)."
            )
    return image


def _port_range(text: str, where: str) -> tuple:
    start, _, end = text.partition("-")
    first, last = int(start), int(end) if end else int(start)
    for port in (first, last):
        if not 1 <= port <= 65535:
            raise ValueError(f"El puerto {port} del {where} está fuera de rango (1-65535).")
    if last < first:
        raise ValueError(f"El rango de puertos {text} no es válido.")
    return first, last


def parse_port(value: str) -> PortMapping:
    """ Interpreta un mapeo de puertos con la sintaxis corta de Compose. """
    match = PORT_RE.fullmatch(value)
    if not match:
        raise ValueError(
            "Formato de puerto no válido. Ejemplos: 8080:80, 80, 127.0.0.1:8080:80, "
            "53:53/udp, 8000-8010:8000-8010."
        )
    ip = None
    if match.group("ip"):
        raw_ip = match.group("ip")
        bracketed = raw_ip.startswith("[")
        try:
            address = ipaddress.ip_address(raw_ip.strip("[]"))
        except ValueError:
            raise ValueError(f"La dirección IP {raw_ip} no es válida.") from None
        if address.version == 4 and bracketed:
            raise ValueError("Las direcciones IPv4 se escriben sin corchetes.")
        ip = None if address.is_unspecified else address
    host_text = match.group("host") or match.group("ip_host")
    host = _port_range(host_text, "host") if host_text else None
    container = _port_range(match.group("container"), "contenedor")
    if host and container[0] != container[1] and host[1] - host[0] != container[1] - container[0]:
        raise ValueError("Los rangos de puertos del host y del contenedor deben tener el mismo tamaño.")
    return PortMapping(ip, host, container, match.group("proto") or "tcp")


def ports_conflict(a: PortMapping, b: PortMapping) -> bool:
    """ Indica si dos mapeos publican el mismo puerto del host. """
    if a.host is None or b.host is None or a.proto != b.proto:
        return False
    if a.ip is not None and b.ip is not None and a.ip != b.ip:
        return False
    return a.host[0] <= b.host[1] and b.host[0] <= a.host[1]


def is_host_path(source: str) -> bool:
    return source.startswith((".", "/", "~", "$", "\\")) or bool(WINDOWS_DRIVE_RE.match(source))


def parse_volume(spec: str) -> Volume:
    """ Interpreta un volumen con la sintaxis corta: [origen:]destino[:modo]. """
    drive, rest = "", spec
    if WINDOWS_DRIVE_RE.match(spec):  # C:\ruta tiene ':' propio.
        drive, rest = spec[:2], spec[2:]
    parts = rest.split(":")
    parts[0] = drive + parts[0]
    if len(parts) > 3:
        raise ValueError("Formato no válido. Use origen:destino o origen:destino:modo.")
    source, target, mode = (None, parts[0], None) if len(parts) == 1 else (parts + [None])[:3]
    if source == "":
        raise ValueError("Falta el origen (ruta del host o nombre de volumen) antes de ':'.")
    if not target:
        raise ValueError("Falta la ruta dentro del contenedor.")
    if not target.startswith(("/", "$")):
        raise ValueError(f"La ruta del contenedor debe ser absoluta (empezar por '/'): '{target}'.")
    named = source is not None and not is_host_path(source)
    if named and not NAME_RE.fullmatch(source):
        raise ValueError(
            f"'{source}' no es un nombre de volumen válido. Para rutas del host "
            "empiece por './', '/' o '~/'."
        )
    if mode is not None:
        flags = mode.split(",")
        invalid = [flag for flag in flags if flag not in VOLUME_MODES]
        if invalid:
            raise ValueError(
                f"Modo no válido: '{','.join(invalid)}'. Use ro, rw, z, Z, cached, delegated o nocopy."
            )
        if {"ro", "rw"} <= set(flags) or {"z", "Z"} <= set(flags):
            raise ValueError("Hay modos incompatibles entre sí (ro/rw o z/Z).")
    return Volume(source, target, mode, named)


def parse_env_pair(pair: str) -> tuple:
    if "=" not in pair:
        raise ValueError("Formato no válido. Use CLAVE=VALOR.")
    key, value = pair.split("=", 1)
    key = key.strip()
    if not key:
        raise ValueError("El nombre de la variable no puede estar vacío.")
    if not ENV_KEY_RE.fullmatch(key):
        raise ValueError("El nombre de la variable no puede contener espacios.")
    return key, value.strip()


def validate_cpus(value: str) -> str:
    if not CPUS_RE.fullmatch(value) or float(value) <= 0:
        raise ValueError("Indique un número mayor que 0 (ej. 0.5, 1, 2).")
    return value


def validate_memory(value: str) -> str:
    match = MEMORY_RE.fullmatch(value)
    if not match:
        raise ValueError("Formato no válido. Ejemplos: 512M, 1G, 1.5g, 256MB.")
    if float(match.group(1)) * MEMORY_UNITS[match.group(2).lower()] < MIN_MEMORY:
        raise ValueError("Docker exige un mínimo de 6M de memoria.")
    return value


def validate_duration(value: str) -> str:
    if not DURATION_RE.fullmatch(value):
        raise ValueError("Duración no válida. Ejemplos: 30s, 1m, 1m30s, 500ms.")
    return value


def validate_positive_int(value: str) -> str:
    if not POSITIVE_INT_RE.fullmatch(value) or int(value) < 1:
        raise ValueError("Indique un número entero mayor que 0.")
    return value


def dollar_issue(value: str):
    """ Devuelve un mensaje si el valor tiene un '$' que Compose no sabría interpretar. """
    rest = value.replace("$$", "")
    rest = re.sub(r"\$\{[A-Za-z_][A-Za-z0-9_]*(?:(?::?[-?+])[^}]*)?\}", "", rest)
    rest = re.sub(r"\$[A-Za-z_][A-Za-z0-9_]*", "", rest)
    if "$" in rest:
        return "contiene un '$' que no forma una variable válida ($VAR o ${VAR})"
    return None


def dependency_names(service: dict) -> list:
    deps = service.get("depends_on", [])
    return list(deps) if isinstance(deps, (dict, list)) else []


def creates_cycle(services: dict, name: str, dep: str) -> bool:
    """ Indica si 'dep' depende ya (directa o indirectamente) de 'name'. """
    pending, seen = [dep], set()
    while pending:
        current = pending.pop()
        if current == name:
            return True
        if current in seen:
            continue
        seen.add(current)
        pending.extend(dependency_names(services.get(current, {})))
    return False


def missing_dependencies(services: dict) -> dict:
    """ {servicio que falta: [servicios que dependen de él]} """
    missing = {}
    for name, service in services.items():
        for dep in dependency_names(service):
            if dep not in services:
                missing.setdefault(dep, []).append(name)
    return missing


def remove_dependency(service: dict, dep: str):
    deps = service.get("depends_on")
    if isinstance(deps, dict):
        deps.pop(dep, None)
    elif isinstance(deps, list):
        service["depends_on"] = [d for d in deps if d != dep]
    if not service.get("depends_on"):
        service.pop("depends_on", None)


# ---------------------------------------------------------------------------
# Generación del YAML
# ---------------------------------------------------------------------------

class QuotedStr(str):
    """ Cadena que siempre se escribe entre comillas dobles (p. ej. "8080:80"). """


class FlowList(list):
    """ Lista que se escribe en una sola línea (p. ej. ["CMD-SHELL", "..."]). """


class ComposeDumper(yaml.SafeDumper):
    """ Dumper con listas indentadas y sin anclas/alias de YAML. """

    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow, False)

    def ignore_aliases(self, data):
        return True


ComposeDumper.add_representer(
    QuotedStr, lambda dumper, data: dumper.represent_scalar("tag:yaml.org,2002:str", str(data), style='"')
)
ComposeDumper.add_representer(
    FlowList, lambda dumper, data: dumper.represent_sequence("tag:yaml.org,2002:seq", data, flow_style=True)
)


def build_compose(project_name: str, services: dict) -> dict:
    """ Construye el diccionario completo, declarando redes y volúmenes con nombre. """
    compose = {}
    if project_name:
        compose["name"] = project_name
    compose["services"] = services

    networks = dict.fromkeys(net for svc in services.values() for net in svc.get("networks", []))
    if networks:
        compose["networks"] = {net: {} for net in networks}

    volumes = {}
    for svc in services.values():
        for spec in svc.get("volumes", []):
            volume = parse_volume(spec)
            if volume.named:
                volumes[volume.source] = {}
    if volumes:
        compose["volumes"] = volumes
    return compose


def to_yaml(compose: dict) -> str:
    return YAML_HEADER + yaml.dump(
        compose,
        Dumper=ComposeDumper,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=4096,
    )


# ---------------------------------------------------------------------------
# Entrada interactiva. Todo el texto del usuario se muestra con Text (sin
# interpretar marcado de rich), así que valores como "[/opt]" no rompen nada.
# ---------------------------------------------------------------------------

YES_ANSWERS = ("s", "si", "sí", "y", "yes")
NO_ANSWERS = ("n", "no")


def say(message: str, style: str = ""):
    console.print(Text(message, style=style))


def _prompt(message: str, hint: str = None) -> str:
    text = Text(message, style="bold green")
    if hint:
        text.append(f" {hint}", style="dim")
    text.append(" ")
    return console.input(text).strip()


def ask(message: str, default: str = None, validator=None, required: bool = False) -> str:
    """ Pide un texto. Con 'default', Enter acepta ese valor; 'validator' lanza ValueError. """
    while True:
        value = _prompt(message, f"({default})" if default else None)
        if not value:
            if default:
                value = default
            elif required:
                say("Este campo es obligatorio.", "red")
                continue
            else:
                return ""
        if validator is None:
            return value
        try:
            return validator(value)
        except ValueError as exc:
            say(str(exc), "red")


def ask_list(message: str, item_validator=None) -> list:
    """ Pide una lista separada por comas, sin elementos vacíos ni repetidos. """
    while True:
        raw = ask(message)
        items = list(dict.fromkeys(item.strip() for item in raw.split(",") if item.strip()))
        try:
            if item_validator:
                for item in items:
                    item_validator(item)
            return items
        except ValueError as exc:
            say(str(exc), "red")


def confirm(message: str, default: bool = None) -> bool:
    hint = {True: "[S/n]", False: "[s/N]", None: "[s/n]"}[default]
    while True:
        answer = _prompt(message, hint).lower()
        if not answer and default is not None:
            return default
        if answer in YES_ANSWERS:
            return True
        if answer in NO_ANSWERS:
            return False
        say("Responda 's' (sí) o 'n' (no).", "red")


def choose(message: str, options: list, default=None):
    """ Muestra un menú numerado. 'options' es una lista de (valor, descripción). """
    say(message, "bold yellow")
    for number, (_, label) in enumerate(options, 1):
        line = Text(f"  {number}. ", style="cyan")
        line.append(label)
        console.print(line)
    values = [value for value, _ in options]
    keys = {str(number): value for number, value in enumerate(values, 1)}
    default_key = str(values.index(default) + 1) if default is not None else None
    while True:
        answer = ask("Opción:", default=default_key, required=True)
        if answer in keys:
            return keys[answer]
        say(f"Elija un número del 1 al {len(options)}.", "red")


def resolve_dollars(value: str, field: str) -> str:
    """ Decide si los '$' de un valor son variables de Compose o texto literal ('$$'). """
    if "$" not in value:
        return value
    issue = dollar_issue(value)
    if issue:
        say(f"{field} {issue}: se guardará como texto literal.", "yellow")
        return value.replace("$", "$$")
    say(f"{field} contiene '$'. Docker Compose sustituye $VAR y ${{VAR}} por variables de entorno.", "yellow")
    if confirm("¿Debe Compose sustituir esas variables? (n = guardar el texto tal cual)", default="${" in value):
        return value
    return value.replace("$", "$$")


def input_restart_policy() -> str:
    policy = choose(
        "Política de reinicio:",
        [
            ("", "Ninguna (no indicar)"),
            ("no", "no: no reiniciar nunca"),
            ("always", "always: reiniciar siempre"),
            ("on-failure", "on-failure: solo si termina con error"),
            ("unless-stopped", "unless-stopped: siempre, salvo si se detuvo a mano"),
        ],
        default="",
    )
    if policy == "on-failure":
        retries = ask("Número máximo de reintentos (opcional):", validator=validate_positive_int)
        if retries:
            policy = f"on-failure:{retries}"
    return policy


def input_ports(services: dict) -> list:
    """ Pide mapeos de puertos evitando repetir puertos del host ya publicados. """
    taken = [(owner, parse_port(port)) for owner, svc in services.items() for port in svc.get("ports", [])]
    say("Formatos: 8080:80 | 80 | 127.0.0.1:8080:80 | 53:53/udp | 8000-8010:8000-8010", "dim")
    ports = []
    while True:
        raw = ask("  Puerto (vacío para terminar):")
        if not raw:
            return ports
        try:
            mapping = parse_port(raw)
        except ValueError as exc:
            say(str(exc), "red")
            continue
        owner = next((owner for owner, other in taken if ports_conflict(mapping, other)), False)
        if owner is not False:
            where = f"el servicio '{owner}'" if owner else "este mismo servicio"
            say(f"Ese puerto del host ya lo usa {where}.", "red")
            continue
        ports.append(QuotedStr(raw))
        taken.append((None, mapping))


def input_env_vars() -> dict:
    say("Escriba las variables en formato CLAVE=VALOR (vacío para terminar).", "bold green")
    env = {}
    while True:
        pair = ask("  >")
        if not pair:
            return env
        try:
            key, value = parse_env_pair(pair)
        except ValueError as exc:
            say(str(exc), "red")
            continue
        if key in env:
            say(f"La variable {key} ya existía: se reemplaza su valor.", "yellow")
        env[key] = resolve_dollars(value, f"La variable {key}")


def input_volumes() -> list:
    say("Formatos: ./datos:/datos | datos_db:/var/lib/mysql | /ruta/host:/ruta:ro | /solo/en/contenedor", "dim")
    volumes, targets = [], set()
    while True:
        spec = ask("  Volumen (vacío para terminar):")
        if not spec:
            return volumes
        try:
            volume = parse_volume(spec)
        except ValueError as exc:
            say(str(exc), "red")
            continue
        if volume.target in targets:
            say(f"Ya hay un volumen montado en {volume.target}.", "red")
            continue
        targets.add(volume.target)
        volumes.append(spec)
        if volume.named:
            say(f"'{volume.source}' es un volumen con nombre: se declarará en la sección 'volumes'.", "dim")


def input_dependencies(services: dict, name: str):
    def check(dep):
        if not NAME_RE.fullmatch(dep):
            raise ValueError(f"'{dep}' no es un nombre de servicio válido.")
        if dep == name:
            raise ValueError("Un servicio no puede depender de sí mismo.")
        if creates_cycle(services, name, dep):
            raise ValueError(f"'{dep}' ya depende (directa o indirectamente) de '{name}': se formaría un ciclo.")

    deps = ask_list("Servicios de los que depende (separados por comas, opcional):", check)
    pending = [dep for dep in deps if dep not in services]
    if pending:
        say(
            f"Aún no existe: {', '.join(pending)}. Antes de guardar se le pedirá crearlo o quitar la dependencia.",
            "yellow",
        )
    healthy = [dep for dep in deps if "healthcheck" in services.get(dep, {})]
    if healthy and confirm(
        f"{', '.join(healthy)} tiene healthcheck. ¿Esperar a que esté 'healthy' antes de arrancar?", default=True
    ):
        return {dep: {"condition": "service_healthy" if dep in healthy else "service_started"} for dep in deps}
    return deps


def input_healthcheck() -> dict:
    test = ask("Comando de comprobación (ej. curl -f http://localhost || exit 1):", required=True)
    healthcheck = {"test": FlowList([QuotedStr("CMD-SHELL"), QuotedStr(resolve_dollars(test, "El healthcheck"))])}
    healthcheck["interval"] = ask("Intervalo entre comprobaciones:", default="30s", validator=validate_duration)
    healthcheck["timeout"] = ask("Tiempo máximo por comprobación:", default="10s", validator=validate_duration)
    retries = ask("Fallos seguidos para marcarlo 'unhealthy':", default="3", validator=validate_positive_int)
    healthcheck["retries"] = int(retries)
    start_period = ask("Margen inicial tras arrancar (start_period, opcional, ej. 10s):", validator=validate_duration)
    if start_period:
        healthcheck["start_period"] = start_period
    return healthcheck


def input_service(services: dict, name: str = None) -> tuple:
    """
    Recopila de forma interactiva la configuración de un servicio.
    'services' son los demás servicios ya definidos (para evitar nombres, contenedores
    y puertos repetidos y ciclos de dependencias). Si se pasa 'name' no se pregunta.
    """
    console.print()
    console.print(Panel(Text(f"Servicio '{name}'" if name else "Nuevo servicio"), style="bold blue", expand=False))
    if name is None:
        name = ask("Nombre del servicio:", required=True, validator=lambda v: validate_service_name(v, services))
    service = {}

    source = choose(
        "¿De dónde sale la imagen del servicio?",
        [
            ("image", "Usar una imagen de Docker (ej. nginx:1.27, postgres:16)"),
            ("build", "Construirla a partir de un Dockerfile (build)"),
        ],
    )
    if source == "image":
        service["image"] = ask("Imagen de Docker:", required=True, validator=validate_image)
    else:
        build = {"context": ask("Directorio de build (contexto):", default=".")}
        dockerfile = ask("Nombre del Dockerfile:", default="Dockerfile")
        if dockerfile != "Dockerfile":
            build["dockerfile"] = dockerfile
        service["build"] = build
        tag = ask("Nombre para la imagen construida (opcional, ej. miapp:1.0):", validator=validate_image)
        if tag:
            service["image"] = tag

    used_names = {svc["container_name"] for svc in services.values() if "container_name" in svc}
    container_name = ask(
        "Nombre del contenedor (opcional):", validator=lambda v: validate_container_name(v, used_names)
    )
    if container_name:
        service["container_name"] = container_name

    command = ask("Comando a ejecutar (opcional):")
    if command:
        service["command"] = resolve_dollars(command, "El comando")

    restart = input_restart_policy()
    if restart:
        service["restart"] = restart

    if confirm("¿Desea publicar puertos?", default=False):
        ports = input_ports(services)
        if ports:
            service["ports"] = ports

    if confirm("¿Desea añadir variables de entorno?", default=False):
        env = input_env_vars()
        if env:
            service["environment"] = env
        env_files = ask_list("Archivos .env a cargar (env_file, separados por comas, opcional):")
        if env_files:
            service["env_file"] = env_files

    if confirm("¿Desea montar volúmenes?", default=False):
        volumes = input_volumes()
        if volumes:
            service["volumes"] = volumes

    deps = input_dependencies(services, name)
    if deps:
        service["depends_on"] = deps

    networks = ask_list("Redes a las que se conecta (separadas por comas, opcional):", validate_network_name)
    if networks:
        service["networks"] = networks

    if confirm("¿Desea añadir un healthcheck (comprobación de salud)?", default=False):
        service["healthcheck"] = input_healthcheck()

    # Docker Compose v2 aplica estos límites también fuera de Swarm.
    if confirm("¿Desea limitar CPU y memoria?", default=False):
        limits = {}
        cpus = ask("Máximo de CPUs (ej. 0.5) (opcional):", validator=validate_cpus)
        if cpus:
            limits["cpus"] = cpus
        memory = ask("Memoria máxima (ej. 512M, 1G) (opcional):", validator=validate_memory)
        if memory:
            limits["memory"] = memory
        if limits:
            service["deploy"] = {"resources": {"limits": limits}}

    return name, service


# ---------------------------------------------------------------------------
# Resumen, guardado y validación
# ---------------------------------------------------------------------------

def summarize_service(service: dict) -> list:
    """ Devuelve pares (etiqueta, texto) legibles para el resumen. """
    rows = []
    if "build" in service:
        build = service["build"]
        text = build["context"] + (f" (Dockerfile: {build['dockerfile']})" if "dockerfile" in build else "")
        rows.append(("build", text))
    if "image" in service:
        rows.append(("imagen", service["image"]))
    simple = (("container_name", "contenedor"), ("command", "comando"), ("restart", "reinicio"))
    rows += [(label, service[key]) for key, label in simple if key in service]
    if "ports" in service:
        rows.append(("puertos", ", ".join(service["ports"])))
    if "environment" in service:
        rows.append(("entorno", ", ".join(f"{k}={v}" for k, v in service["environment"].items())))
    if "env_file" in service:
        rows.append(("env_file", ", ".join(service["env_file"])))
    if "volumes" in service:
        rows.append(("volúmenes", ", ".join(service["volumes"])))
    deps = service.get("depends_on")
    if isinstance(deps, dict):
        rows.append(("depende de", ", ".join(
            f"{dep} (healthy)" if cond["condition"] == "service_healthy" else dep for dep, cond in deps.items()
        )))
    elif deps:
        rows.append(("depende de", ", ".join(deps)))
    if "networks" in service:
        rows.append(("redes", ", ".join(service["networks"])))
    if "healthcheck" in service:
        rows.append(("healthcheck", service["healthcheck"]["test"][-1]))
    limits = service.get("deploy", {}).get("resources", {}).get("limits", {})
    if limits:
        rows.append(("límites", ", ".join(f"{k}={v}" for k, v in limits.items())))
    return rows


def show_summary(project_name: str, services: dict):
    table = Table(title="Resumen de Docker Compose", show_lines=True)
    table.add_column("Servicio", style="bold cyan", no_wrap=True)
    table.add_column("Configuración")
    if project_name:
        table.caption = Text(f"Proyecto: {project_name}")
    for name, service in services.items():
        details = Text()
        for index, (label, value) in enumerate(summarize_service(service)):
            if index:
                details.append("\n")
            details.append(f"{label}: ", style="bold")
            details.append(str(value))
        table.add_row(Text(name), details)
    console.print()
    console.print(table)


def pick_service(services: dict, message: str) -> str:
    return choose(message, [(name, name) for name in services])


def resolve_missing_dependencies(services: dict):
    """ Antes de guardar, obliga a crear o quitar las dependencias que no existen. """
    while True:
        missing = missing_dependencies(services)
        if not missing:
            return
        dep, users = next(iter(missing.items()))
        say(f"{', '.join(users)} depende de '{dep}', pero ese servicio no existe.", "yellow")
        action = choose(
            "¿Qué desea hacer?",
            [("create", f"Crear ahora el servicio '{dep}'"), ("drop", f"Quitar '{dep}' de las dependencias")],
            default="create",
        )
        if action == "create":
            name, service = input_service(services, name=dep)
            services[name] = service
        else:
            for user in users:
                remove_dependency(services[user], dep)


def ask_output_path() -> Path:
    while True:
        raw = ask("Nombre del archivo de salida:", default=DEFAULT_OUTPUT)
        path = Path(os.path.expanduser(raw))
        if not path.is_absolute():
            path = Path.cwd() / path
        if path.is_dir():
            path = path / DEFAULT_OUTPUT
            say(f"Es una carpeta: se guardará como {path}", "dim")
        if path.suffix.lower() not in (".yml", ".yaml") and not confirm(
            "El archivo no termina en .yml ni .yaml. ¿Usarlo igualmente?", default=False
        ):
            continue
        if not path.parent.is_dir():
            if path.parent.exists():
                say(f"{path.parent} no es una carpeta.", "red")
                continue
            if not confirm(f"La carpeta {path.parent} no existe. ¿Crearla?", default=True):
                continue
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                say(f"No se pudo crear la carpeta: {exc}", "red")
                continue
        if path.exists() and not confirm(f"El archivo {path} ya existe. ¿Sobrescribirlo?", default=False):
            continue
        return path


def warn_missing_env_files(services: dict, base: Path):
    env_files = dict.fromkeys(f for svc in services.values() for f in svc.get("env_file", []))
    for env_file in env_files:
        path = Path(os.path.expanduser(env_file))
        if not (path if path.is_absolute() else base / path).exists():
            say(f"Recuerde crear el archivo {env_file} (env_file): Docker Compose lo necesita para arrancar.", "yellow")


def validate_with_docker(path: Path):
    """ Si Docker está instalado, valida el archivo con 'docker compose config'. """
    docker = shutil.which("docker")
    if docker is None:
        say("Docker no está instalado: se omite la validación con 'docker compose config'.", "dim")
        return
    try:
        result = subprocess.run(
            [docker, "compose", "-f", str(path), "config", "--quiet"],
            cwd=str(path.parent),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError, KeyboardInterrupt):
        say("No se pudo ejecutar 'docker compose': se omite la validación.", "dim")
        return
    output = (result.stderr or result.stdout).strip()
    if result.returncode == 0:
        say("Validado con 'docker compose config': el archivo es correcto.", "bold green")
        if output:
            say(output, "dim")
    elif "is not a docker command" in output or "unknown command" in output:
        say("Docker Compose v2 no está disponible: se omite la validación.", "dim")
    else:
        say("'docker compose config' ha detectado problemas:", "bold yellow")
        say(output, "yellow")


def show_next_steps(path: Path):
    try:
        shown = str(path.relative_to(Path.cwd()))
    except ValueError:
        shown = str(path)
    if " " in shown:
        shown = f'"{shown}"'
    say("\nPara arrancar los servicios:", "bold")
    say(f"  docker compose -f {shown} up -d")
    say("Para detenerlos y eliminar los contenedores:", "bold")
    say(f"  docker compose -f {shown} down")


def save_compose(project_name: str, services: dict):
    """ Muestra el YAML final y lo guarda. Devuelve el código de salida, o None para volver al menú. """
    resolve_missing_dependencies(services)
    content = to_yaml(build_compose(project_name, services))
    console.print(Rule("Vista previa del archivo"))
    console.print(Syntax(content, "yaml", theme="ansi_dark", background_color="default", word_wrap=True))
    console.print(Rule())
    if not confirm("¿Guardar este contenido?", default=True):
        return None

    while True:
        path = ask_output_path()
        try:
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(content)
            break
        except OSError as exc:
            say(f"Error al guardar el archivo: {exc}", "bold red")
            if not confirm("¿Probar con otra ruta?", default=True):
                return 1

    say(f"Archivo guardado en: {path}", "bold blue")
    warn_missing_env_files(services, path.parent)
    validate_with_docker(path)
    show_next_steps(path)
    return 0


# ---------------------------------------------------------------------------
# Programa principal
# ---------------------------------------------------------------------------

BANNER = r"""
  ____             _              ____
 |  _ \  ___   ___| | _____ _ __ / ___| ___ _ __
 | | | |/ _ \ / __| |/ / _ \ '__| |  _ / _ \ '_ \
 | |_| | (_) | (__|   <  __/ |  | |_| |  __/ | | |
 |____/ \___/ \___|_|\_\___|_|   \____|\___|_| |_|
"""


def print_banner():
    """ Muestra el banner de DockerGen. """
    left, right = "---- By: MARH ", f" v{__version__} ----"
    footer = left + "-" * (50 - len(left) - len(right)) + right
    console.print(Panel(Text(BANNER + "\n" + footer + "\n"), expand=False))


def main() -> int:
    print_banner()
    console.print(Panel(Text("Generador interactivo de Docker Compose"), style="bold magenta", expand=False))
    say("Pulse Enter para aceptar el valor entre paréntesis. Ctrl+C para salir sin guardar.", "dim")
    project_name = ask("Nombre del proyecto (opcional, en minúsculas):", validator=validate_project_name)

    services = {}
    name, service = input_service(services)
    services[name] = service

    while True:
        show_summary(project_name, services)
        action = choose(
            "¿Qué desea hacer ahora?",
            [
                ("add", "Añadir otro servicio"),
                ("edit", "Rehacer un servicio"),
                ("remove", "Eliminar un servicio"),
                ("save", "Ver el YAML y guardarlo"),
                ("quit", "Salir sin guardar"),
            ],
        )
        if action == "add":
            name, service = input_service(services)
            services[name] = service
        elif action == "edit":
            target = pick_service(services, "¿Qué servicio desea rehacer?")
            others = {key: value for key, value in services.items() if key != target}
            services[target] = input_service(others, name=target)[1]
        elif action == "remove":
            target = pick_service(services, "¿Qué servicio desea eliminar?")
            if confirm(f"¿Eliminar el servicio '{target}'?", default=False):
                del services[target]
                dependents = [n for n, svc in services.items() if target in dependency_names(svc)]
                if dependents:
                    say(
                        f"Aviso: {', '.join(dependents)} depende de '{target}'. Antes de guardar se le "
                        "pedirá crearlo de nuevo o quitar la dependencia.",
                        "yellow",
                    )
                if not services:
                    say("No quedan servicios: añada al menos uno.", "yellow")
                    name, service = input_service(services)
                    services[name] = service
        elif action == "save":
            code = save_compose(project_name, services)
            if code is not None:
                return code
        elif confirm("¿Seguro que desea salir? Se perderá la configuración.", default=False):
            say("Operación cancelada. No se ha guardado nada.", "red")
            return 0


def run():
    try:
        code = main()
    except KeyboardInterrupt:
        console.print()
        say("Operación cancelada por el usuario (Ctrl+C).", "red")
        code = 130
    except EOFError:
        console.print()
        say("Se ha cerrado la entrada estándar: operación cancelada.", "red")
        code = 1
    sys.exit(code)


if __name__ == "__main__":
    run()
