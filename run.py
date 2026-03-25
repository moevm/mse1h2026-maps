import os
import platform
import subprocess
import sys


def set_env(env):
    env["DB_NAME"] = "mapsdb"
    env["DB_USER"] = "admin"
    env["DB_PASSWORD"] = "CHANGETHAT"
    env["DB_HOST"] = "localhost"
    env["DB_PORT"] = "5432"

    env["DJANGO_SECRET"] = (
        "django-insecure-2eyh*ng0f3ugi9@t1sk$n%o!^7f9$wddn8tl7b_guxf@xtp+qu"
    )

    env["NEO_URI"] = "bolt://localhost:7687"
    env["NEO_USER"] = "neo4j"
    env["NEO_PASSWORD"] = "12345678"

    base_dir = os.path.dirname(os.path.abspath(__file__))
    env["PYTHONPATH"] = base_dir


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))

    print(base_dir)
    env = os.environ.copy()
    set_env(env)

    if platform.system() == "Windows":
        python_exec = os.path.join(base_dir, ".venv", "Scripts", "python.exe")
    else:
        python_exec = os.path.join(base_dir, ".venv", "bin", "python")

    manage_py = os.path.join(base_dir, "src", "django", "maps", "manage.py")

    cmd = [python_exec, manage_py, "runserver"]

    try:
        subprocess.run(cmd, env=env, check=True)
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
