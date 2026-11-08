"""Comandos administrativos de aprovisionamiento inicial.

Uso:
    python -m app.cli create-organization --name "Acme" --slug acme
    python -m app.cli create-admin --organization-slug acme --email admin@acme.com --name "Admin"

La contraseña se solicita de forma interactiva o se toma de la variable de entorno
indicada por --password-env (por defecto ADMIN_PASSWORD). Nunca se pasa por argumento.
"""

import argparse
import asyncio
import getpass
import os
import re
import sys

from app.core.config import get_settings
from app.core.security import hash_password
from app.database.session import session_scope
from app.models.enums import UserRole
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.user_repository import UserRepository

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _read_password(env_name: str, minimum_length: int) -> str:
    password = os.environ.get(env_name)
    if password:
        if len(password) < minimum_length:
            raise ValueError(f"La contraseña debe tener al menos {minimum_length} caracteres.")
        return password

    password = getpass.getpass("Contraseña: ")
    confirmation = getpass.getpass("Confirmar contraseña: ")
    if password != confirmation:
        raise ValueError("Las contraseñas no coinciden.")
    if len(password) < minimum_length:
        raise ValueError(f"La contraseña debe tener al menos {minimum_length} caracteres.")
    return password


async def _create_organization(name: str, slug: str) -> int:
    if not SLUG_PATTERN.match(slug):
        print("Error: el slug solo admite minúsculas, números y guiones.", file=sys.stderr)
        return 1

    async with session_scope() as session:
        repository = OrganizationRepository(session)
        if await repository.get_by_slug(slug) is not None:
            print(f"Error: ya existe una organización con slug '{slug}'.", file=sys.stderr)
            return 1
        if await repository.get_by_name(name) is not None:
            print(f"Error: ya existe una organización con nombre '{name}'.", file=sys.stderr)
            return 1

        organization = await repository.create(name=name, slug=slug)
        print(f"Organización creada: {organization.id} ({organization.slug})")
        return 0


async def _create_admin(*, organization_slug: str, email: str, name: str, password_env: str) -> int:
    settings = get_settings()

    async with session_scope() as session:
        organizations = OrganizationRepository(session)
        organization = await organizations.get_by_slug(organization_slug)
        if organization is None:
            print(
                f"Error: no existe la organización '{organization_slug}'.",
                file=sys.stderr,
            )
            return 1

        users = UserRepository(session)
        if await users.get_by_org_and_email(organization.id, email) is not None:
            print(
                f"Error: ya existe un usuario con email '{email}' en la organización.",
                file=sys.stderr,
            )
            return 1

        try:
            password = _read_password(password_env, settings.password_min_length)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

        user = await users.create(
            organization_id=organization.id,
            name=name,
            email=email,
            password_hash=hash_password(password),
            role=UserRole.ADMIN,
        )
        print(f"Administrador creado: {user.id} ({user.email})")
        return 0


async def _dispatch(args: argparse.Namespace) -> int:
    if args.command == "create-organization":
        return await _create_organization(args.name, args.slug)
    if args.command == "create-admin":
        return await _create_admin(
            organization_slug=args.organization_slug,
            email=args.email,
            name=args.name,
            password_env=args.password_env,
        )
    print("Comando desconocido.", file=sys.stderr)
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="smartdocs", description="CLI de SmartDocs AI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    organization = subparsers.add_parser("create-organization", help="Crea la organización inicial")
    organization.add_argument("--name", required=True)
    organization.add_argument("--slug", required=True)

    admin = subparsers.add_parser("create-admin", help="Crea un administrador")
    admin.add_argument("--organization-slug", required=True)
    admin.add_argument("--email", required=True)
    admin.add_argument("--name", required=True)
    admin.add_argument("--password-env", default="ADMIN_PASSWORD")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return asyncio.run(_dispatch(args))
    except KeyboardInterrupt:
        print("Operación cancelada.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
