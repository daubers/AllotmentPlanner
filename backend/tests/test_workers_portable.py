"""Workers can run on other machines, so they reach files only through the storage layer.

A job that opened ``MEDIA_ROOT`` (or ``/data/media``) directly would work on the main server and
quietly break on a worker without that volume. New code that needs a file asks ``get_storage()``;
a scratch directory of its own (``tempfile``, ``MAPPING_WORK_DIR``) is fine.
"""

import re
from pathlib import Path

import allotment

SOURCE = Path(allotment.__file__).parent
# The only places that may know where the plain-file backend keeps things.
ALLOWED = {"config.py", "storage.py", "cli.py"}
FORBIDDEN = re.compile(r"MEDIA_ROOT|/data/media|FileStorage")


def test_only_the_storage_layer_knows_where_files_live():
    offenders = [
        f"{path.relative_to(SOURCE)}:{n}"
        for path in SOURCE.rglob("*.py")
        if path.name not in ALLOWED
        for n, line in enumerate(path.read_text().splitlines(), 1)
        if FORBIDDEN.search(line)
    ]
    assert not offenders, (
        "Reach files through get_storage(), not a local path, so workers can run on other "
        f"machines: {offenders}"
    )


def test_every_routed_queue_can_be_served_by_a_worker_that_names_it():
    """Queues are just names: whatever task_routes sends somewhere is served by ``-Q <name>``."""
    from allotment.celery_app import celery

    routes = celery.conf.task_routes or {}
    queues = {r["queue"] for r in routes.values()}
    assert "mapping" in queues
    assert all(re.fullmatch(r"[a-z][a-z0-9_-]*", q) for q in queues)
