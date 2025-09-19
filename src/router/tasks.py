from __future__ import annotations
from celery import shared_task
from src.router.route import route_new_links

@shared_task(name="src.router.tasks.route_once")
def route_once() -> dict:
    return route_new_links()
