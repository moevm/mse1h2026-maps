#!/usr/bin/env python
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

project_root = Path(__file__).resolve().parent

django_project_dir = project_root / "src" / "django" / "maps"
sys.path.insert(0, str(project_root))

sys.path.insert(0, str(django_project_dir))

os.chdir(django_project_dir)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "maps.settings")

from celery.bin import celery

if __name__ == "__main__":
    sys.argv = [
        "celery",
        "-A",
        "maps",
        "worker",
        "--pool=solo",
        "--loglevel=info",
    ]
    celery.main()
