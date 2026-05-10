import os
import platform
import subprocess
import sys


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))

    print(base_dir)
    env = os.environ.copy()

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
