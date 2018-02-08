register_check_parameters(
    subgroup_os,
    "proxmox",
    _("Proxmox VM guest backup"),
    Dictionary(
        elements = [
            ( "check_backup",
              DropdownChoice(
                  title = _("Ignore or check VM (QEMU) guests"),
		  help=_("If this is set to ignore, the check will always be {ok}. To enable backup checks use the check option."),
                  choices = [
                     ( "ignore",   _("ignore missing backups") ),
                     ( "check",   _("check for backups") ),
                  ]
              )
	    ),
            ('backup_age',
             Tuple(title = "Age of Backup before changing to warn or error",
                   elements = [
                       Age(title=_("Warning if backup is older than"), default_value = 93600, display = [ "minutes" ], help=_("If the backup is older as the specified time, the check changes to warning. (24h=1440m; 26h=1560m)")),
                       Age(title=_("Critical if backup is older than"), default_value = 108000, display = [ "minutes" ], help=_("If the backup is older as the specified time, the check changes to warning. (24h=1440m; 26h=1560m)")),
                   ]
		  )
            ),
	    ('running_time',
		Age(
			title=_("Runtime of the backup process"),
			default_value = 1800, display = [ "minutes" ],
			help=_("Define here how long the backup process is running. If the Backup is running, the check dont change to warning for the specified time. If the backup runs longer as specified here, the check changes to warning.")
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

