# Author: Matthias Maderer
# E-Mail: edvler@edvler-blog.de
# URL: https://github.com/edvler/check_mk_proxmox-qemu-backup
# License: GPLv2

from cmk.gui.i18n import _
from cmk.gui.plugins.wato import (
    HostRulespec,
    rulespec_registry,
)
from cmk.gui.valuespec import (
    DropdownChoice,
)
import cmk.utils.version as cmk_version

register_check_parameters(
    RulespecGroupCheckParametersVirtualization,
    "proxmox",
    _("Proxmox VM guest backup"),
    Dictionary(
        elements = [
            ("check_backup",
             DropdownChoice(
                 title = _("Enable (default) or disable check of VM guest backup"),
                 help=_("If disabled is choosen, the check will always return OK. To enable checks of the backup, select enable. This is usefull if you have clients in UrBackup, for which no regular backups are done and you dont want them to be checked."),
                 choices = [
                     ("ignore", _("disable")),
                     ("check", _("enable")),
                 ]
             )
            ),
            ('backup_age',
             Tuple(title = "Age of Backup before changing to warn (default 26h) or error (default 30h). This parameters are only used, if modi Backup Age is choosen!",
                 elements = [
                     Age(title=_("Warning at or above backupage"),
                         default_value = 93600, 
                         help=_("If the backup is older than the specified time, the check changes to warning. (24h=1440m; 26h=1560m)")
                     ),
                     Age(title=_("Critical at or above backupage"),
                         default_value = 108000,
                         help=_("If the backup is older than the specified time, the check changes to critical. (24h=1440m; 26h=1560m)")
                     ),
                 ]
             )
            ),
            ("backup_minsize",
                Tuple(
                    title = _("Minimal size of vzdump archive"),
                    elements = [
                      Filesize(title = _("Warning if below")),
                      Filesize(title = _("Critical if below")),
                    ]
                )
            ),
            ('running_time',
                Age(title=_("Runtime (default 30min) of the backup process"),
                    default_value = 1800,
                    help=_("Define here how long the backup process is running. If the Backup is running, the check dont change to warning or error for the specified time. If the backup runs longer as specified here, the check changes to warning.")
                ),
            )
        ]
    ),
    TextAscii(
        title = _("Description"),
        allow_empty = True
    ),
    match_type = "dict",
)

if cmk_version.is_enterprise_version() or cmk_version.is_managed_version():
    from cmk.gui.cee.plugins.wato.agent_bakery.rulespecs.utils import (
        RulespecGroupMonitoringAgentsAgentPlugins,
    )


    def _valuespec_proxmox_qemu_backup():
        return DropdownChoice(
            title = _("Proxmox VE guest backup"),
            help = _(
                "This will deploy the agent plugin <tt>proxmox_qemu_backup</tt>"
            ),
            choices = [
                (True, _("Deploy plugin for Proxmox VE guest backups")),
                (False, _("Do not deploy plugin for Proxmox VE guest backups")),
            ]
        )

    rulespec_registry.register(
        HostRulespec(
            group=RulespecGroupMonitoringAgentsAgentPlugins,
            name="agent_config:proxmox_qemu_backup",
            valuespec=_valuespec_proxmox_qemu_backup,
        )
    )

