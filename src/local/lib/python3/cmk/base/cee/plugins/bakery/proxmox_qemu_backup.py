#!/usr/bin/env python3

#Author: Matthias Maderer
#E-Mail: matthias.maderer@web.de
#URL: https://github.com/edvler/check_mk_proxmox-qemu-backup
#License: GPLv2

#only CEE!
try:
    from pathlib import Path
    from typing import TypedDict    
    from .bakery_api.v1 import Plugin, register, OS, FileGenerator

    class ProxmoxQemuBackupBakeryConfig(TypedDict, total=False):
        deployment: bool

    def get_proxmox_qemu_backup_files(conf: ProxmoxQemuBackupBakeryConfig) -> FileGenerator:
        deployment = conf["deployment"]

        if deployment == False:
            return

        yield Plugin(
            base_os=OS.LINUX,
            source=Path("proxmox_qemu_backup"),
            interval=None,
            asynchronous=False,
        )

    register.bakery_plugin(
        name="proxmox_qemu_backup_bakery",
        files_function=get_proxmox_qemu_backup_files,
    )
except ModuleNotFoundError:
    pass