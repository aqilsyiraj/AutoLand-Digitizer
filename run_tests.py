"""
Menjalankan seluruh pengujian AutoLand Digitizer.

Setiap modul pengujian dijalankan dalam proses Python terpisah agar Qt/OpenCV
tidak saling mengganggu saat interpreter ditutup pada Windows. Pada beberapa
mesin, PySide6 bisa menyebabkan crash saat shutdown setelah unittest mencetak
"OK"; kondisi tersebut tetap dianggap lulus selama tidak ada kegagalan test.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
TEST_MODULES = [
    "tests.test_pdf",
    "tests.test_services",
    "tests.test_ui",
]
OK_PATTERN = re.compile(r"(?m)^OK(?: \(.*\))?$")


def _tests_passed(returncode: int, output: str) -> bool:
    if returncode == 0:
        return True
    has_ok = bool(OK_PATTERN.search(output))
    has_failure = "FAILED" in output or "ERROR:" in output
    return has_ok and not has_failure


def main() -> int:
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"

    failed = []
    for module in TEST_MODULES:
        print(f"\n=== {module} ===", flush=True)
        result = subprocess.run(
            [sys.executable, "-m", "unittest", module, "-v"],
            cwd=str(ROOT_DIR),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        print(result.stdout, end="")
        if _tests_passed(result.returncode, result.stdout):
            if result.returncode != 0:
                print(
                    f"[CATATAN] Proses {module} keluar dengan kode {result.returncode} "
                    "setelah semua test dinyatakan OK (kemungkinan crash shutdown PySide6)."
                )
        else:
            failed.append(module)

    if failed:
        print("\nPENGUJIAN GAGAL: " + ", ".join(failed))
        return 1

    print("\nSEMUA PENGUJIAN LULUS.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
