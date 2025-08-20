# Author: Matthias Maderer
# E-Mail: matthias.maderer@web.de
# URL: https://github.com/edvler/check_mk_proxmox-qemu-backup
# License: GPLv2

from cmk.rulesets.v1 import (
    Title,
)
from cmk.rulesets.v1.form_specs import (
    BooleanChoice,
    DefaultValue,
    DictElement,
    Dictionary,
    InputHint,
    LevelDirection,
    migrate_to_upper_float_levels,
    SimpleLevels,
    TimeMagnitude,
    TimeSpan,
    CascadingSingleChoice,
    CascadingSingleChoiceElement,
    FixedValue,
    )
from cmk.rulesets.v1.rule_specs import (
    CheckParameters,
    HostAndItemCondition,
    Topic,
)

def _migrate_int_to_float(model):
    if isinstance(model, int):
        return float(model)
    return model

def _parameter_proxmox_qemu_backup():
    return Dictionary(
        ignored_elements=("backup_minsize","check_backup"),
        #migrate=lambda model: {  # force defaults for with model.get(...,DEFAULT)
        #    'check_backup': model.get('check_backup', True),
        #    'backup_age': migrate_to_upper_float_levels(model.get('backup_age', ('fixed', (1.5 * 86400.0, 2 * 86400.0)))),
        #    'running_time': model.get('running_time', (TimeSpan(30, TimeMagnitude.MINUTES), None)),
        #},
        elements={
            'backup_age': DictElement(
                required=True,
                parameter_form=SimpleLevels(
                    title = Title('Age of Backup before changing to warn or critical'),
                    migrate = lambda model: migrate_to_upper_float_levels(model),
                    level_direction = LevelDirection.UPPER,
                    form_spec_template = TimeSpan(
                        displayed_magnitudes=[TimeMagnitude.DAY, TimeMagnitude.HOUR],
                    ),
                    prefill_fixed_levels = InputHint(
                        value=(1.5 * 86400.0, 2 * 86400.0),
                    )
                )
            ),
            'running_time': DictElement(
                required=False,
                parameter_form=TimeSpan(
                    migrate = lambda model: _migrate_int_to_float(model),
                    title=Title("Runtime of the backup process"),
                    displayed_magnitudes=[TimeMagnitude.DAY, TimeMagnitude.HOUR, TimeMagnitude.MINUTE],              
                    prefill=DefaultValue(180)
                )
            ),
        }
    )

# def register_check_parameters_proxmox_qemu_backup():
#     return Dictionary(
#         elements = [
#             ("check_backup",
#              DropdownChoice(
#                  title = _("Enable (default) or disable check of VM guest backup"),
#                  help=_("If disabled is choosen, the check will always return OK. To enable checks of the backup, select enable. This is usefull if you have clients in UrBackup, for which no regular backups are done and you dont want them to be checked."),
#                  choices = [
#                      ("ignore", _("disable")),
#                      ("check", _("enable")),
#                  ]
#              )
#             ),
#             ('backup_age',
#              Tuple(title = "Age of Backup before changing to warn (default 26h) or error (default 30h). This parameters are only used, if modi Backup Age is choosen!",
#                  elements = [
#                      Age(title=_("Warning at or above backupage"),
#                          default_value = 93600, 
#                          help=_("If the backup is older than the specified time, the check changes to warning. (24h=1440m; 26h=1560m)")
#                      ),
#                      Age(title=_("Critical at or above backupage"),
#                          default_value = 108000,
#                          help=_("If the backup is older than the specified time, the check changes to critical. (24h=1440m; 26h=1560m)")
#                      ),
#                  ]
#              )
#             ),
#             ("backup_minsize",
#                 Tuple(
#                     title = _("Minimal size of vzdump archive"),
#                     elements = [
#                       Filesize(title = _("Warning if below")),
#                       Filesize(title = _("Critical if below")),
#                     ]
#                 )
#             ),
#             ('running_time',
#                 Age(title=_("Runtime (default 30min) of the backup process"),
#                     default_value = 1800,
#                     help=_("Define here how long the backup process is running. If the Backup is running, the check dont change to warning or error for the specified time. If the backup runs longer as specified here, the check changes to warning.")
#                 ),
#             )
#         ]
#     )

rule_spec_urbackup = CheckParameters(
    name="proxmox",
    topic=Topic.STORAGE,
    parameter_form=_parameter_proxmox_qemu_backup,
    title=Title("Proxmox VM guest backup"),
    condition=HostAndItemCondition(item_title=Title("Proxmox Guest Service item")),
)


# rulespec_registry.register(
#     CheckParameterRulespecWithItem(
#         check_group_name="proxmox",
#         group=RulespecGroupCheckParametersStorage,
#         item_spec=lambda: TextAscii(title=_('Proxmox VM guest backup'), ),
#         match_type='dict',
#         parameter_valuespec=register_check_parameters_proxmox_qemu_backup,
#         title=lambda: _("Proxmox VM guest backup"),
#     ))


#if cmk_version.is_enterprise_version() or cmk_version.is_managed_version():
#    from cmk.gui.cee.plugins.wato.agent_bakery.rulespecs.utils import (
#        RulespecGroupMonitoringAgentsAgentPlugins,
#    )


#   def _valuespec_proxmox_qemu_backup():
#        return DropdownChoice(
#            title = _("Proxmox VE guest backup"),
#            help = _(
#                "This will deploy the agent plugin <tt>proxmox_qemu_backup</tt>"
#            ),
#            choices = [
#                (True, _("Deploy plugin for Proxmox VE guest backups")),
#                (False, _("Do not deploy plugin for Proxmox VE guest backups")),
#            ]
#        )

#    rulespec_registry.register(
#        HostRulespec(
#            group=RulespecGroupMonitoringAgentsAgentPlugins,
#            name="agent_config:proxmox_qemu_backup",
#            valuespec=_valuespec_proxmox_qemu_backup,
#        )
#    )

