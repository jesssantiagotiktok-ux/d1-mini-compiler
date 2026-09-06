import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse


app = FastAPI(
    title="D1 Mini C++ Compiler",
    version="1.0"
)


# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,

    allow_origins=[
        "https://echomixjstv-hash.github.io"
    ],

    allow_credentials=False,

    allow_methods=["*"],

    allow_headers=["*"],
)


# =========================================================
# HOME
# =========================================================

@app.get("/")
def home():

    return {
        "status": "online",
        "service": "D1 Mini Compiler",
        "compiler": "PlatformIO",
        "board": "Wemos D1 Mini ESP8266"
    }

@app.get("/test")
def test():
    return {
        "ok": True,
        "message": "Render received the request!",
        "service": "D1 Mini Compiler"
    }
# =========================================================
# COMPILE
# =========================================================

@app.post("/compile")
async def compile_code(
    file: UploadFile = File(...)
):

    filename = file.filename or ""

    print("")
    print("======================================")
    print("NEW COMPILATION REQUEST")
    print("FILE:", filename)
    print("======================================")

    # -----------------------------------------------------
    # Check extension
    # -----------------------------------------------------

    if not filename.lower().endswith(
        (".cpp", ".ino")
    ):

        raise HTTPException(
            status_code=400,
            detail="Only .cpp or .ino files are allowed."
        )


    # -----------------------------------------------------
    # Read file
    # -----------------------------------------------------

    try:

        source = await file.read()

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail="Could not read uploaded file: " + str(e)
        )


    print(
        "Source size:",
        len(source),
        "bytes"
    )


    # -----------------------------------------------------
    # File size limit
    # -----------------------------------------------------

    if len(source) > 200000:

        raise HTTPException(
            status_code=413,
            detail="Source file is too large."
        )


    # -----------------------------------------------------
    # Create temporary project
    # -----------------------------------------------------

    workdir = Path(
        tempfile.mkdtemp(
            prefix="d1mini_"
        )
    )

    print(
        "Project directory:",
        workdir
    )


    try:

        src_dir = workdir / "src"

        src_dir.mkdir(
            parents=True,
            exist_ok=True
        )


        # -------------------------------------------------
        # Decode source
        # -------------------------------------------------

        try:

            source_text = source.decode(
                "utf-8"
            )

        except UnicodeDecodeError:

            source_text = source.decode(
                "utf-8",
                errors="replace"
            )


        # -------------------------------------------------
        # Add Arduino.h
        # -------------------------------------------------

        if "#include <Arduino.h>" not in source_text:

            source_text = (
                "#include <Arduino.h>\n\n"
                + source_text
            )


        # -------------------------------------------------
        # Write main.cpp
        # -------------------------------------------------

        main_cpp = (
            src_dir /
            "main.cpp"
        )

        main_cpp.write_text(
            source_text,
            encoding="utf-8"
        )


        print(
            "Created:",
            main_cpp
        )


        # -------------------------------------------------
        # PlatformIO configuration
        # -------------------------------------------------

        platformio_ini = """
[env:d1_mini]

platform = espressif8266

board = d1_mini

framework = arduino

monitor_speed = 115200
"""


        (workdir / "platformio.ini").write_text(
            platformio_ini.strip(),
            encoding="utf-8"
        )


        print(
            "Created platformio.ini"
        )


        # -------------------------------------------------
        # Check PlatformIO
        # -------------------------------------------------

        print(
            "Checking PlatformIO..."
        )


        pio_version = subprocess.run(
            [
                "pio",
                "--version"
            ],

            capture_output=True,

            text=True,

            timeout=30
        )


        print(
            "PIO:",
            pio_version.stdout.strip()
        )


        if pio_version.returncode != 0:

            raise HTTPException(
                status_code=500,
                detail=(
                    "PlatformIO is not working.\n\n"
                    + pio_version.stderr
                )
            )


        # -------------------------------------------------
        # Compile
        # -------------------------------------------------

        print(
            "Starting PlatformIO compilation..."
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

            timeout=900

        )


        output = (
            result.stdout +
            "\n" +
            result.stderr
        )


        print("")
        print(
            "========== PLATFORMIO OUTPUT =========="
        )
        print(output)
        print(
            "========================================"
        )


        # -------------------------------------------------
        # Compilation failed
        # -------------------------------------------------

        if result.returncode != 0:

            raise HTTPException(

                status_code=400,

                detail=(
                    "PlatformIO compilation failed.\n\n"
                    + output[-15000:]
                )

            )


        # -------------------------------------------------
        # Find firmware
        # -------------------------------------------------

        firmware = (

            workdir /
            ".pio" /
            "build" /
            "d1_mini" /
            "firmware.bin"

        )


        print(
            "Looking for firmware:"
        )

        print(
            firmware
        )


        if not firmware.exists():

            raise HTTPException(

                status_code=500,

                detail=(
                    "Compilation finished but "
                    "firmware.bin was not found.\n\n"
                    + output[-10000:]
                )

            )


        # -------------------------------------------------
        # Copy firmware
        # -------------------------------------------------

        output_file = (
            workdir /
            "firmware.bin"
        )


        shutil.copyfile(
            firmware,
            output_file
        )


        print(
            "Firmware created successfully."
        )


        print(
            "Firmware size:",
            output_file.stat().st_size,
            "bytes"
        )


        # -------------------------------------------------
        # Return BIN
        # -------------------------------------------------

        return FileResponse(

            path=output_file,

            media_type="application/octet-stream",

            filename="firmware.bin"

        )


    except subprocess.TimeoutExpired:
    print("COMPILATION TIMEOUT")
    raise HTTPException(
        status_code=408,
        detail="Compilation timed out after 15 minutes."
    )


    except HTTPException:

        raise


    except Exception as e:

        print(
            "UNEXPECTED ERROR:",
            repr(e)
        )


        raise HTTPException(

            status_code=500,

            detail=(
                "Unexpected compiler error:\n\n"
                + repr(e)
            )

    )
