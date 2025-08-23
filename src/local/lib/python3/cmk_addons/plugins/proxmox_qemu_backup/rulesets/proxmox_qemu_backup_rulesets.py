# Author: Matthias Maderer
# E-Mail: matthias.maderer@web.de
# URL: https://github.com/edvler/check_mk_proxmox-qemu-backup
# License: GPLv2

from cmk.rulesets.v1 import (
    Title,
)
from cmk.rulesets.v1.form_specs import (
    DefaultValue,
    DictElement,
    Dictionary,
    InputHint,
    LevelDirection,
    migrate_to_upper_float_levels,
    SimpleLevels,
    TimeMagnitude,
    TimeSpan,
    )
from cmk.rulesets.v1.rule_specs import (
    CheckParameters,
    HostAndItemCondition,
    Topic,
)

def _migrate_running_time(model):
    if isinstance(model, (float,int)):
        return ('fixed',(float(model),float(model + 60*60))) #add 60min to create a critical level
    return model

def _parameter_proxmox_qemu_backup():
    return Dictionary(
        ignored_elements=("backup_minsize","check_backup"),
        elements={
            'backup_age': DictElement(
                required=True,
                parameter_form=SimpleLevels(
                    title = Title('Age of Backup before changing to warn/critical'),
                    migrate = lambda model: migrate_to_upper_float_levels(model),
                    level_direction = LevelDirection.UPPER,
                    form_spec_template = TimeSpan(
                        displayed_magnitudes=[TimeMagnitude.DAY, TimeMagnitude.HOUR, TimeMagnitude.MINUTE],
                    ),
                    prefill_fixed_levels = InputHint(
                        value=(1.5 * 86400.0, 2 * 86400.0),
                    )
                )
            ),
            'running_time': DictElement(
                required=True,
                parameter_form=SimpleLevels(
                    title = Title('After a runtime of the backup process change to warn/critical (situations in which the backup not completes or hangs)'),
                    migrate = lambda model: _migrate_running_time(model),
                    level_direction = LevelDirection.UPPER,
                    form_spec_template = TimeSpan(
                        displayed_magnitudes=[TimeMagnitude.DAY, TimeMagnitude.HOUR, TimeMagnitude.MINUTE],
                    ),
                    prefill_fixed_levels = DefaultValue(
                        value=(0.5 * 86400.0, 1 * 86400.0),
                    )
                )
            ),
        }
    )

rule_spec_urbackup = CheckParameters(
    name="proxmox",
    topic=Topic.STORAGE,
    parameter_form=_parameter_proxmox_qemu_backup,
    title=Title("Proxmox Backup Logfile Check"),
    condition=HostAndItemCondition(item_title=Title("Proxmox Guest Service item")),
)