import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

app = FastAPI(title="D1 Mini Compiler")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://echomixjstv-hash.github.io"
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def home():
    return {
        "status": "online",
        "service": "D1 Mini Compiler"
    }


@app.post("/compile")
async def compile_code(file: UploadFile = File(...)):

    filename = file.filename or ""

    if not filename.lower().endswith((".cpp", ".ino")):
        raise HTTPException(
            status_code=400,
            detail="Only .cpp or .ino files are allowed."
        )

    workdir = Path(tempfile.mkdtemp(prefix="d1mini_"))

    try:
        src_dir = workdir / "src"
        src_dir.mkdir(parents=True, exist_ok=True)

        source = await file.read()

        if len(source) > 200_000:
            raise HTTPException(
                status_code=413,
                detail="Source file is too large."
            )

        source_text = source.decode("utf-8", errors="replace")

        # Arduino source normally needs Arduino.h
        if "#include <Arduino.h>" not in source_text:
            source_text = "#include <Arduino.h>\n\n" + source_text

        (src_dir / "main.cpp").write_text(
            source_text,
            encoding="utf-8"
        )

        platformio_ini = """
[env:d1_mini]
platform = espressif8266
board = d1_mini
framework = arduino
monitor_speed = 115200
upload_protocol = esptool
"""

        (workdir / "platformio.ini").write_text(
            platformio_ini.strip(),
            encoding="utf-8"
        )

        result = subprocess.run(
            [
                "pio",
                "run",
                "-e",
                "d1_mini"
            ],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=180
        )

        if result.returncode != 0:
            output = result.stdout + "\n" + result.stderr

            raise HTTPException(
                status_code=400,
                detail=output[-12000:]
            )

        firmware = (
            workdir /
            ".pio" /
            "build" /
            "d1_mini" /
            "firmware.bin"
        )

        if not firmware.exists():
            raise HTTPException(
                status_code=500,
                detail="firmware.bin was not generated."
            )

        # Copy to a temporary downloadable location
        output_file = workdir / "firmware.bin"
        shutil.copyfile(firmware, output_file)

        return FileResponse(
            output_file,
            media_type="application/octet-stream",
            filename="firmware.bin"
        )

    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=408,
            detail="Compilation timeout."
        )

    finally:
        # Keep this simple for now.
        # We can improve cleanup after testing.
        pass
