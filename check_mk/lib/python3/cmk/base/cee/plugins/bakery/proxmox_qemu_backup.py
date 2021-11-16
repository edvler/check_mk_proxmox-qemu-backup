#!/usr/bin/env python3
# -*- encoding: utf-8; py-indent-offset: 4 -*-

from pathlib import Path
from typing import Any, Dict

from .bakery_api.v1 import FileGenerator, OS, Plugin, register

def get_proxmox_qemu_backup_files(conf: Dict[str, Any]) -> FileGenerator:
    yield Plugin(base_os=OS.LINUX, source=Path("proxmox_qemu_backup"))

register.bakery_plugin(
    name="proxmox_qemu_backup",
    files_function=get_proxmox_qemu_backup_files,
)

