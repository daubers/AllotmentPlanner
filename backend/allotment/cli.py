"""Maintenance commands: ``flask <command>``."""

import click
from flask import Flask


def register(app: Flask) -> None:
    @app.cli.command("copy-media-to-s3")
    @click.option("--dry-run", is_flag=True, help="Only say what would be copied.")
    def copy_media_to_s3(dry_run: bool) -> None:
        """Copy the photos and map tiles in MEDIA_ROOT into the S3 bucket (see S3_* settings).

        Run this once when switching STORAGE_BACKEND from file to s3. It leaves the files where
        they are and can be repeated safely.
        """
        import boto3

        from .storage import FileStorage, S3Storage, copy_tree

        cfg = app.config
        missing = [
            k for k in ("S3_ENDPOINT_URL", "S3_ACCESS_KEY", "S3_SECRET_KEY") if not cfg.get(k)
        ]
        if missing:
            raise click.UsageError(f"Set {', '.join(missing)} first.")
        client = boto3.client(
            "s3",
            endpoint_url=cfg["S3_ENDPOINT_URL"],
            aws_access_key_id=cfg["S3_ACCESS_KEY"],
            aws_secret_access_key=cfg["S3_SECRET_KEY"],
            region_name="us-east-1",
        )
        dest = S3Storage(client, cfg["S3_BUCKET"])
        copied, skipped = copy_tree(FileStorage(cfg["MEDIA_ROOT"]), dest, dry_run=dry_run)
        verb = "Would copy" if dry_run else "Copied"
        click.echo(f"{verb} {copied} file(s); {skipped} already in the bucket.")

    @app.cli.command("make-admin")
    @click.argument("email")
    @click.option("--revoke", is_flag=True, help="Take admin access away instead.")
    def make_admin(email: str, revoke: bool) -> None:
        """Let a user open the admin page (worker state, jobs and logs)."""
        from .extensions import db
        from .models import User

        user = User.query.filter(db.func.lower(User.email) == email.strip().lower()).one_or_none()
        if user is None:
            raise click.UsageError(f"No user with the email {email}.")
        user.is_admin = not revoke
        db.session.commit()
        click.echo(f"{user.email} is {'no longer' if revoke else 'now'} an admin.")
