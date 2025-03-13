#!/usr/bin/env python3
import subprocess
import sys
import os

def check_dependencies():
    required_packages = ["rich", "yaml"]
    missing_packages = []

    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)

    if missing_packages:
        print("\n[ERROR] Faltan dependencias necesarias:")
        for pkg in missing_packages:
            print(f"  - {pkg}")
        print("\nPor favor, instala las dependencias con:")
        print("  pip install -r requirements.txt\n")
        sys.exit(1)  # Terminar ejecución si faltan paquetes

# Verificar dependencias antes de continuar
check_dependencies()

# Importar rich y otras librerías
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.table import Table

console = Console()

def print_banner():
    """ Muestra el banner de DockerGen"""
    banner = r"""
  ____             _              ____
 |  _ \  ___   ___| | _____ _ __ / ___| ___ _ __
 | | | |/ _ \ / __| |/ / _ \ '__| |  _ / _ \ '_ \
 | |_| | (_) | (__|   <  __/ |  | |_| |  __/ | | |
 |____/ \___/ \___|_|\_\___|_|   \____|\___|_| |_|

---- By: MARH ------------------------------------
    """
    console.print(Panel(banner, border_style="", expand=False))

def get_non_empty_input(prompt_message: str) -> str:
    """ Solicita al usuario una entrada que no esté vacía. """
    while True:
        value = console.input(f"[bold green]{prompt_message}[/bold green] ").strip()
        if value:
            return value
        console.print("[red]Este campo es obligatorio. Intenta nuevamente.[/red]")

def input_list(prompt_message: str):
    """ Solicita una entrada separada por comas y devuelve una lista de elementos. """
    line = console.input(f"[bold green]{prompt_message}[/bold green] ").strip()
    return [x.strip() for x in line.split(",") if x.strip()] if line else []

def get_validated_port(prompt_message: str) -> str:
    """ Solicita y valida que el puerto ingresado sea numérico. """
    while True:
        port = console.input(f"[bold green]{prompt_message}[/bold green] ").strip()
        if port == "":
            return ""
        if port.isdigit():
            return port
        console.print("[red]Por favor, ingrese un número válido para el puerto.[/red]")

def input_env_vars():
    """ Solicita variables de entorno en formato KEY=VALUE. """
    env_vars = {}
    console.print("[bold green]Ingrese las variables de entorno (formato KEY=VALUE). Deje en blanco para terminar.[/bold green]")
    while True:
        pair = console.input("  > ").strip()
        if not pair:
            break
        if "=" not in pair:
            console.print("[red]Formato inválido. Use KEY=VALUE.[/red]")
            continue
        key, value = pair.split("=", 1)
        env_vars[key.strip()] = value.strip()
    return env_vars

def input_volumes():
    """ Solicita mapeos de volúmenes en formato host:container. """
    volumes = []
    console.print("[bold green]Ingrese mapeos de volúmenes (formato /ruta/host:/ruta/container). Deje en blanco para terminar.[/bold green]")
    while True:
        mapping = console.input("  > ").strip()
        if not mapping:
            break
        if ":" not in mapping:
            console.print("[red]Formato inválido. Use /ruta/host:/ruta/container.[/red]")
            continue
        volumes.append(mapping)
    return volumes

def input_service():
    """
    Recopila de manera interactiva la configuración de un servicio.
    Retorna el nombre del servicio y su configuración como diccionario.
    """
    console.print(Panel("Configuración de un nuevo servicio", style="bold blue", expand=False))
    name = get_non_empty_input("Ingrese el nombre del servicio:")
    service = {}

    # Seleccionar método de creación: imagen o build.
    method = ""
    while method not in ["1", "2"]:
        console.print("[bold yellow]Seleccione el método para el servicio:[/bold yellow]")
        console.print("  1. Usar una imagen Docker")
        console.print("  2. Especificar un build context")
        method = console.input("[bold green]Ingrese 1 o 2:[/bold green] ").strip()

    if method == "1":
        image = get_non_empty_input("Ingrese el nombre de la imagen Docker:")
        service["image"] = image
    else:
        context = get_non_empty_input("Ingrese el directorio de build (contexto):")
        build_dict = {"context": context}
        dockerfile = console.input("[bold green]Ingrese el nombre del Dockerfile (deje en blanco para 'Dockerfile'):[/bold green] ").strip()
        if dockerfile:
            build_dict["dockerfile"] = dockerfile
        service["build"] = build_dict

    # Opciones adicionales
    container_name = console.input("[bold green]Nombre del contenedor (opcional):[/bold green] ").strip()
    if container_name:
        service["container_name"] = container_name

    command = console.input("[bold green]Comando a ejecutar (opcional):[/bold green] ").strip()
    if command:
        service["command"] = command

    restart_policy = console.input("[bold green]Política de reinicio (ej. always, unless-stopped) (opcional):[/bold green] ").strip()
    if restart_policy:
        service["restart"] = restart_policy

    # Mapeo de puertos
    if Confirm.ask("[bold green]¿Desea mapear puertos?[/bold green]"):
        ports = []
        while True:
            host_port = get_validated_port("Puerto en el host (deje en blanco para terminar):")
            if not host_port:
                break
            container_port = get_validated_port("Puerto en el contenedor:")
            if not container_port:
                console.print("[red]El puerto del contenedor es obligatorio si se ingresa el puerto del host.[/red]")
                continue
            ports.append(f"{host_port}:{container_port}")
        if ports:
            service["ports"] = ports

    # Variables de entorno
    if Confirm.ask("[bold green]¿Desea agregar variables de entorno?[/bold green]"):
        env_vars = input_env_vars()
        if env_vars:
            service["environment"] = env_vars

    # Mapeo de volúmenes
    if Confirm.ask("[bold green]¿Desea mapear volúmenes?[/bold green]"):
        vols = input_volumes()
        if vols:
            service["volumes"] = vols

    # Dependencias y redes
    depends_on = input_list("Ingrese servicios de los que depende (separados por coma) o deje en blanco:")
    if depends_on:
        service["depends_on"] = depends_on

    networks = input_list("Ingrese las redes a las que se conectará (separadas por coma) o deje en blanco:")
    if networks:
        service["networks"] = networks

    # Límites de recursos (opcional, para despliegues en Swarm)
    if Confirm.ask("[bold green]¿Desea especificar límites de recursos para el servicio?[/bold green]"):
        deploy = {}
        resources = {}
        limits = {}
        cpus = console.input("[bold green]Número máximo de CPUs (ej. 0.5) (deje en blanco para omitir):[/bold green] ").strip()
        if cpus:
            limits["cpus"] = cpus
        memory = console.input("[bold green]Memoria máxima (ej. 512M o 1G) (deje en blanco para omitir):[/bold green] ").strip()
        if memory:
            limits["memory"] = memory
        if limits:
            resources["limits"] = limits
            deploy["resources"] = resources
        if deploy:
            service["deploy"] = deploy

    return name, service

def preview_configuration(compose_config: dict):
    """ Muestra un resumen de la configuración en forma de tabla. """
    table = Table(title="Resumen de Docker Compose", show_lines=True)
    table.add_column("Sección", style="bold cyan")
    table.add_column("Detalles", style="white")
    
    table.add_row("Version", compose_config.get("version", ""))
    
    services = compose_config.get("services", {})
    for svc_name, svc_conf in services.items():
        details = ""
        for key, value in svc_conf.items():
            details += f"[bold]{key}:[/bold] {value}\n"
        table.add_row(f"Servicio: {svc_name}", details.strip())
    
    networks = compose_config.get("networks", {})
    if networks:
        nets = ", ".join(networks.keys())
        table.add_row("Redes", nets)
    
    console.print(table)

def main():
    print_banner()
    # Panel principal rosa ajustado al tamaño del texto (expand=False)
    console.print(Panel("Generador Interactivo de Docker Compose", style="bold magenta", expand=False))
    compose_version = console.input("[bold green]Ingrese la versión de docker-compose (por defecto 3.8):[/bold green] ").strip() or "3.8"

    services = {}
    while True:
        name, service = input_service()
        services[name] = service
        if not Confirm.ask("[bold green]¿Desea agregar otro servicio?[/bold green]"):
            break

    compose_config = {"version": compose_version, "services": services}
    # Agregar redes a nivel superior si hay alguna definida en servicios
    all_networks = set()
    for svc in services.values():
        nets = svc.get("networks", [])
        all_networks.update(nets)
    if all_networks:
        compose_config["networks"] = {net: {} for net in all_networks}

    # Imprimir título de vista previa sin panel azul
    console.print("[bold magenta]Vista previa de la configuración:[/bold magenta]")
    preview_configuration(compose_config)

    if not Confirm.ask("[bold green]¿Desea continuar y guardar el archivo?[/bold green]"):
        console.print("[red]Operación cancelada por el usuario.[/red]")
        sys.exit(0)

    output_filename = get_non_empty_input("Ingrese el nombre del archivo resultante (ej: docker-compose.yml):")
    output_path = os.path.join(os.getcwd(), output_filename) if not os.path.dirname(output_filename) else output_filename

    if os.path.exists(output_path):
        if not Confirm.ask(f"[yellow]El archivo '{output_path}' ya existe. ¿Desea sobrescribirlo?[/yellow]"):
            console.print("[red]Operación cancelada. No se sobreescribió el archivo existente.[/red]")
            sys.exit(0)

    try:
        yaml_output = yaml.dump(compose_config, sort_keys=False, default_flow_style=False)
    except Exception as e:
        console.print(f"[red]Error al generar YAML: {e}[/red]")
        sys.exit(1)

    try:
        with open(output_path, "w") as f:
            f.write(yaml_output)
        console.print(f"[bold blue]Archivo guardado exitosamente en:[/bold blue] {output_path}")
    except Exception as e:
        console.print(f"[bold red]Error al guardar el archivo:[/bold red] {e}")

if __name__ == "__main__":
    main()
