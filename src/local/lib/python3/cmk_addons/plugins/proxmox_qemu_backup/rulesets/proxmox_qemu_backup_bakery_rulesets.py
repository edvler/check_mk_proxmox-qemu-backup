#!/usr/bin/env python3
# Author: Matthias Maderer
# E-Mail: matthias.maderer@web.de
# URL: https://github.com/edvler/check_mk_proxmox-qemu-backup
# License: GPLv2

#example: \lib\python3\cmk\gui\plugins\wato\check_parameters\memory.py


from cmk.rulesets.v1 import Title, Help
from cmk.rulesets.v1.form_specs import (
    DefaultValue,
    DictElement,
    Dictionary,
    BooleanChoice
)

from cmk.rulesets.v1.rule_specs import AgentConfig, Topic


def _valuespec_agent_config_proxmox_qemu_backup_bakery():
    return Dictionary(
        title=Title("Agent Plugin Parameters"),
        elements={
            'deployment': DictElement(
                required=True,
                parameter_form=BooleanChoice(    
                    #migrate=lambda model: _migrate_check_backup(model),
                    title=Title('Deploy Proxmox Backup Logfile Check'),
                    prefill=DefaultValue(True),
                )
            ),
        },
    )


rule_spec_agent_config_proxmox_qemu_backup_bakery = AgentConfig(
    title=Title("Proxmox Backup Logfile Check"),
    topic=Topic.OPERATING_SYSTEM,
    name="proxmox_qemu_backup_bakery",
    parameter_form=_valuespec_agent_config_proxmox_qemu_backup_bakery,
)
