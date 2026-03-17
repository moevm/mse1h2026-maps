import os
import sys
import subprocess
import platform


def get_venv_python():
    base_dir = os.path.dirname(os.path.abspath(__file__))

    if platform.system() == "Windows":
        python_path = os.path.join(base_dir, "venv", "Scripts", "python.exe")
    else:
        # ВНИМАНИЕ: я не уверен что это правильный путь, поэтому его возможно надо поменять
        python_path = os.path.join(base_dir, "venv", "bin", "python")

    return python_path


def main():
    python_exec = get_venv_python()

    manage_py = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "src", "django", "maps", "manage.py"
    )

    cmd = [python_exec, manage_py, "runserver"]

    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()