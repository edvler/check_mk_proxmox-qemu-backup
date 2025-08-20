#!/usr/bin/python


# Author: Matthias Maderer
# E-Mail: edvler@edvler-blog.de
# URL: https://github.com/edvler/check_mk_proxmox-qemu-backup
# License: GPLv2

from cmk.agent_based.v2 import (
    AgentSection,
    CheckPlugin,
    CheckResult,
    DiscoveryResult,
    Result,
    Service,
    State,
    Metric,
    render,
    check_levels,
)
import time
import datetime
import re


def params_parser(params):
    params_new = {}

    for p in params:
        if params[p] is not None and isinstance(params[p], tuple):
            if params[p][0] in ("fixed", "no_levels", "predictive"): #e.g ('fixed', (1, 1)) - New Check_MK 2.4 format
                params_new[p] = params[p]            
            elif isinstance(params[p][0], (int, float)) and isinstance(params[p][1], (int, float)):
                params_new[p] = ('fixed', (params[p][0], params[p][1]))
            else:
                params_new[p] = params[p]
        else: 
            params_new[p] = params[p]

    
    return params_new


def inventory_qemu_backup(section):
    yield from _inventory(section,'QEMU')

def inventory_lxc_backup(section):
    yield from _inventory(section,'LXC')

# the inventory function (dummy)
def _inventory(section, vm_type):
    # loop over all output lines of the agent
    for line in section:
        if line[0].startswith(vm_type + '-MACHINE;;;;;'):
            arr_vars = line[0].split(';;;;;')
            arr_id = arr_vars[1].split('/')
            id = arr_id[-1].replace('.conf','')
            yield Service(item=arr_vars[2] + " Id: " + id + "")

def check_qemu_backup(item, params, section):
    yield from _check_backup(item, params, section, 'qemu')

def check_lxc_backup(item, params, section):
    yield from _check_backup(item, params, section, 'lxc')

def _check_backup(item, params, section, vm_type):
    params_cmk_24 = params_parser(params)

    #get name of the logfile (the output of each logfile is
    #prefixed with its filename from the plugin)
    id=item.split(' ')[-1]
    logfile = '/var/log/vzdump/' + vm_type + '-' + id + '.log'

    #counter
    line_count=0

    warn_count=0
    warn_msg=""
    error_count=0
    error_msg=""


    finished=None
    started=None

    offset=0

    #check all lines
    for line in section:
        #is this line of the given item (id)
        if line[0] == logfile:
            #Only proceed with usable lines (min. 4 array entries)
            if len(line) <= 3:
                continue

            line_count += 1 #count lines of log for this id

            #old or new dateformat in logfile?
            #old /var/log/vzdump/qemu-104.log Feb 07 12:10:54 INFO: creating archive '/vmfs/bkp-fs-stor-001/dump/vzdump-qemu-104-2018_02_07-12_10_54.vma.gz'
            #new /var/log/vzdump/qemu-105.log 2018-02-06 16:00:03 INFO: creating archive '/vmfs/bkp-urbackup01-001/dump/vzdump-qemu-105-2018_02_06-16_00_02.vma.gz'
            date_logentry = None
            try:
                date_logentry = time.strptime(line[1]  + ' ' + line[2],"%Y-%m-%d %H:%M:%S")
                offset=0
            except ValueError:
                pass

            try:
                date_logentry = time.strptime(time.strftime("%Y",time.localtime()) + ' ' + line[1]  + ' ' + line[2] + ' ' + line[3],"%Y %b %d %H:%M:%S")
                offset=1
            except ValueError:
                pass

            #parse logtext
            try:
                # found in all backup types (lxc, qemu, Proxmox Backup Server)
                #if line[offset+3] + ' ' + line[offset+4] == 'INFO: creating':
                #    file_created = line

                if line[offset+3] + ' ' + line[offset+4] + ' ' + line[offset+5] + ' ' + line[offset+6] + ' ' + line[offset+7] == 'INFO: Starting Backup of VM':
                    started = line
                    started_datetime = date_logentry

                if line[offset+3] + ' ' + line[offset+4] + ' ' + line[offset+5] + ' ' + line[offset+6] + ' ' + line[offset+7] == 'INFO: Finished Backup of VM':
                    finished = line
            except IndexError:
                pass

            #search for warn and error keywords
            for content in line:
                if 'warn' in content.lower():
                    warn_count += 1
                    warn_msg += " ".join(line[offset+3:]) + "; "
                elif ('error' in content.lower() or 'fail' in content.lower()):
                    error_count += 1
                    error_msg += " ".join(line[offset+3:]) + "; "
    #For each line END

    #if line_count is 0, no backup file exists --> error!
    if line_count == 0:
        yield Result(state=State.CRIT, summary="Backup logfile is missing. No backup? Problems?")
        return

    #check counter
    if error_count > 0:
        yield Result(state=State.CRIT, summary=error_msg)
        return
    if warn_count > 0:
        yield Result(state=State.CRIT, summary=warn_msg)
        return

    #no warnings and erros!! check if lines indicating a successfull backup exists
    if finished != None and started != None:
        levels = params_cmk_24['backup_age'] if 'backup_age' in params_cmk_24 else None

        if levels == None or levels ==("no_levels", None):
            yield (Result(state=State.OK, summary="No check levels defined!"))
            return
        
        if 'backup_age' not in params_cmk_24:
            yield (Result(state=State.UNKNOWN, summary="No backup_age defined, but - Use levels defined in this check - are choosen in rules!"))
            return

        warn, crit = params_cmk_24['backup_age'][1]

        # Age of Backup
        old = time.time() - time.mktime(started_datetime)
        infotext = 'last backup: ' + time.strftime("%Y-%m-%d %H:%M", started_datetime) + ' (Age: ' + render.timespan(old) + ' warn/crit at ' + render.timespan(warn) + '/' + render.timespan(crit) + ')'

        yield Metric('backup_age', int(old), levels=(warn,crit), boundaries=(0, None))

        if old < warn:
            yield Result(state=State.OK, summary=infotext)
        elif old >= warn and old < crit:
            yield Result(state=State.WARN, summary=infotext)
        else: #old >= crit:
            yield Result(state=State.CRIT, summary=infotext)

    elif started != None:
        old = time.time() - time.mktime(started_datetime)
        if old < params['running_time']:
            yield Result(state=State.OK, summary='backup is running since: ' + render.timespan(old))
        else:
            yield Result(state=State.WARN, summary='backup is running since: ' + render.timespan(old))

    else:
        yield Result(state=State.UNKNOWN, summary='no startime found in logfile. Check logfile for errors!')


check_plugin_proxmox_qemu_backup = CheckPlugin(
    name = "proxmox_qemu_backup",
    service_name = "Proxmox QEMU VM backup %s",
    discovery_function = inventory_qemu_backup,
    check_function = check_qemu_backup,
    check_default_parameters = {
                                'backup_age': (1.5 * 86400.0, 2 * 86400.0)
                                },
    check_ruleset_name = "proxmox"
)

check_plugin_proxmox_lxc_backup = CheckPlugin(
    name = "proxmox_lxc_backup",
    service_name = "Proxmox LXC VM backup %s",
    discovery_function = inventory_lxc_backup,
    check_function = check_lxc_backup,
    check_default_parameters = {
                                'backup_age': (1.5 * 86400.0, 2 * 86400.0)
                                },
    check_ruleset_name = "proxmox"
)

#Example output of agent
#
#root@pve01:/usr/lib/check_mk_agent/plugins# ./proxmox_qemu_backup
#<<<proxmox_qemu_backup>>>
#QEMU-MACHINE;;;;;/etc/pve/qemu-server/103.conf;;;;;server01-hlds
#QEMU-MACHINE;;;;;/etc/pve/qemu-server/102.conf;;;;;firewall01
#QEMU-MACHINE;;;;;/etc/pve/qemu-server/108.conf;;;;;monitoring01
#QEMU-MACHINE;;;;;/etc/pve/qemu-server/101.conf;;;;;guacamole01
#QEMU-MACHINE;;;;;/etc/pve/qemu-server/100.conf;;;;;pfsense01
#QEMU-MACHINE;;;;;/etc/pve/qemu-server/106.conf;;;;;server02
#QEMU-MACHINE;;;;;/etc/pve/qemu-server/105.conf;;;;;urbackup01
#QEMU-MACHINE;;;;;/etc/pve/qemu-server/104.conf;;;;;zbox
#task UPID:pve01:000031A4:009F1CF0:5E3451D2:vzdump:108:root@pam:
#/var/log/vzdump/qemu-100.log 2017-09-05 11:45:02 INFO: Starting Backup of VM 100 (qemu)
#/var/log/vzdump/qemu-100.log 2017-09-05 11:45:02 INFO: status = stopped
#/var/log/vzdump/qemu-100.log 2017-09-05 11:45:02 INFO: update VM 100: -lock backup
#/var/log/vzdump/qemu-100.log 2017-09-05 11:45:02 INFO: backup mode: stop
#/var/log/vzdump/qemu-100.log 2017-09-05 11:45:02 INFO: ionice priority: 7
#/var/log/vzdump/qemu-100.log 2017-09-05 11:45:02 INFO: VM Name: pfsense01
#/var/log/vzdump/qemu-100.log 2017-09-05 11:45:02 INFO: include disk 'virtio0' 'WDC15EADS-tpool-001:vm-100-disk-1' 32G
#/var/log/vzdump/qemu-100.log 2017-09-05 11:45:04 INFO: creating archive '/vmfs/bkp-vol-001/dump/vzdump-qemu-100-2017_09_05-11_45_02.vma.gz'
#/var/log/vzdump/qemu-100.log 2017-09-05 11:45:04 INFO: starting kvm to execute backup task
#/var/log/vzdump/qemu-100.log 2017-09-05 11:45:06 INFO: started backup task 'bb24a1d8-e70a-4cda-a10e-86adb9dab94d'
#/var/log/vzdump/qemu-100.log 2017-09-05 11:46:35 INFO: transferred 34359 MB in 89 seconds (386 MB/s)
#/var/log/vzdump/qemu-100.log 2017-09-05 11:46:35 INFO: stopping kvm after backup task
#/var/log/vzdump/qemu-100.log 2017-09-05 11:46:36 INFO: archive file size: 686MB
#/var/log/vzdump/qemu-100.log 2017-09-05 11:46:36 INFO: Finished Backup of VM 100 (00:01:34)
#/var/log/vzdump/qemu-101.log Apr 06 11:46:34 INFO: Starting Backup of VM 101 (qemu)
#/var/log/vzdump/qemu-101.log Apr 06 11:46:34 INFO: status = stopped
#/var/log/vzdump/qemu-101.log Apr 06 11:46:34 INFO: update VM 101: -lock backup
#/var/log/vzdump/qemu-101.log Apr 06 11:46:35 INFO: backup mode: stop
#/var/log/vzdump/qemu-101.log Apr 06 11:46:35 INFO: ionice priority: 7
#/var/log/vzdump/qemu-101.log Apr 06 11:46:35 INFO: VM Name: guacamole01
#/var/log/vzdump/qemu-101.log Apr 06 11:46:35 INFO: include disk 'sata0' 'WDC15EADS-tpool-001:vm-101-disk-1'
#/var/log/vzdump/qemu-101.log Apr 06 11:46:35 INFO: creating archive '/vmfs/usbbac001-fs-backup-001/dump/vzdump-qemu-101-2017_04_06-11_46_34.vma.gz'
#/var/log/vzdump/qemu-101.log Apr 06 11:46:35 INFO: starting kvm to execute backup task
#/var/log/vzdump/qemu-101.log Apr 06 11:46:38 INFO: started backup task '78127b22-7948-4555-8c48-10b8f3d01ce5'
#/var/log/vzdump/qemu-101.log Apr 06 11:59:11 INFO: transferred 54760 MB in 753 seconds (72 MB/s)
#/var/log/vzdump/qemu-101.log Apr 06 11:59:11 INFO: stopping kvm after backup task
#/var/log/vzdump/qemu-101.log Apr 06 11:59:12 INFO: archive file size: 1.41GB
#/var/log/vzdump/qemu-101.log Apr 06 11:59:12 INFO: delete old backup '/vmfs/usbbac001-fs-backup-001/dump/vzdump-qemu-101-2017_03_14-11_46_37.vma.gz'
#/var/log/vzdump/qemu-101.log Apr 06 11:59:13 INFO: Finished Backup of VM 101 (00:12:39)
#/var/log/vzdump/qemu-102.log 2017-09-05 11:46:36 INFO: Starting Backup of VM 102 (qemu)
#/var/log/vzdump/qemu-102.log 2017-09-05 11:46:36 INFO: status = stopped
#/var/log/vzdump/qemu-102.log 2017-09-05 11:46:36 INFO: update VM 102: -lock backup
#/var/log/vzdump/qemu-102.log 2017-09-05 11:46:36 INFO: backup mode: stop
#/var/log/vzdump/qemu-102.log 2017-09-05 11:46:36 INFO: ionice priority: 7
#/var/log/vzdump/qemu-102.log 2017-09-05 11:46:36 INFO: VM Name: firewall01
#/var/log/vzdump/qemu-102.log 2017-09-05 11:46:36 INFO: include disk 'sata0' 'ssd-850evo-tpool-001:vm-102-disk-2' 9G
#/var/log/vzdump/qemu-102.log 2017-09-05 11:46:36 INFO: creating archive '/vmfs/bkp-vol-001/dump/vzdump-qemu-102-2017_09_05-11_46_36.vma.gz'
#/var/log/vzdump/qemu-102.log 2017-09-05 11:46:36 INFO: starting kvm to execute backup task
#/var/log/vzdump/qemu-102.log 2017-09-05 11:46:38 INFO: started backup task '0ca8bbd7-65cb-4443-8743-0f2074fa736d'
#/var/log/vzdump/qemu-102.log 2017-09-05 11:50:29 INFO: transferred 9663 MB in 231 seconds (41 MB/s)
#/var/log/vzdump/qemu-102.log 2017-09-05 11:50:29 INFO: stopping kvm after backup task
#/var/log/vzdump/qemu-102.log 2017-09-05 11:50:30 INFO: archive file size: 1.95GB
#/var/log/vzdump/qemu-102.log 2017-09-05 11:50:30 INFO: Finished Backup of VM 102 (00:03:54)
#/var/log/vzdump/qemu-103.log 2017-09-05 11:50:30 INFO: Starting Backup of VM 103 (qemu)
#/var/log/vzdump/qemu-103.log 2017-09-05 11:50:30 INFO: status = stopped
#/var/log/vzdump/qemu-103.log 2017-09-05 11:50:31 INFO: update VM 103: -lock backup
#/var/log/vzdump/qemu-103.log 2017-09-05 11:50:31 INFO: backup mode: stop
#/var/log/vzdump/qemu-103.log 2017-09-05 11:50:31 INFO: ionice priority: 7
#/var/log/vzdump/qemu-103.log 2017-09-05 11:50:31 INFO: VM Name: server01-hlds
#/var/log/vzdump/qemu-103.log 2017-09-05 11:50:31 INFO: include disk 'sata0' 'WDC15EADS-tpool-001:vm-103-disk-2' 101G
#/var/log/vzdump/qemu-103.log 2017-09-05 11:50:33 INFO: creating archive '/vmfs/bkp-vol-001/dump/vzdump-qemu-103-2017_09_05-11_50_30.vma.gz'
#/var/log/vzdump/qemu-103.log 2017-09-05 11:50:33 INFO: starting kvm to execute backup task
#/var/log/vzdump/qemu-103.log 2017-09-05 11:50:36 INFO: started backup task 'fe948ba6-3b3a-4737-b9c2-1419864e6fe4'
#/var/log/vzdump/qemu-103.log 2017-09-05 13:02:25 INFO: transferred 108447 MB in 4309 seconds (25 MB/s)
#/var/log/vzdump/qemu-103.log 2017-09-05 13:02:25 INFO: stopping kvm after backup task
#/var/log/vzdump/qemu-103.log 2017-09-05 13:02:28 INFO: archive file size: 33.09GB
#/var/log/vzdump/qemu-103.log 2017-09-05 13:02:28 INFO: Finished Backup of VM 103 (01:11:58)





# QEMU-MACHINE;;;;;/etc/pve/qemu-server/107.conf;;;;;server02.mm.lan
# /var/log/vzdump/qemu-107.log 2025-08-20 02:47:34 INFO: Starting Backup of VM 107 (qemu)
# /var/log/vzdump/qemu-107.log 2025-08-20 02:47:34 INFO: status = running
# /var/log/vzdump/qemu-107.log 2025-08-20 02:47:34 INFO: VM Name: server02.mm.lan
# /var/log/vzdump/qemu-107.log 2025-08-20 02:47:34 INFO: include disk 'scsi0' 'local-lvm:vm-107-disk-0' 170G
# /var/log/vzdump/qemu-107.log 2025-08-20 02:47:34 INFO: include disk 'scsi1' 'backup02-offsite:vm-107-disk-0' 50G
# /var/log/vzdump/qemu-107.log 2025-08-20 02:47:34 INFO: include disk 'scsi2' 'tpool-nvme:vm-107-disk-0' 100G
# /var/log/vzdump/qemu-107.log 2025-08-20 02:47:34 INFO: backup mode: snapshot
# /var/log/vzdump/qemu-107.log 2025-08-20 02:47:34 INFO: ionice priority: 7
# /var/log/vzdump/qemu-107.log 2025-08-20 02:47:34 INFO: ----- vzdump scirpt HOOK: backup-start snapshot 107
# /var/log/vzdump/qemu-107.log 2025-08-20 02:47:34 INFO: HOOK-ENV: vmid=107;vmtype=qemu;dumpdir=;storeid=pbs01-fs01;hostname=server02.mm.lan;tarfile=;logfile=
# /var/log/vzdump/qemu-107.log 2025-08-20 02:47:34 INFO: ----- vzdump scirpt HOOK: pre-stop snapshot 107
# /var/log/vzdump/qemu-107.log 2025-08-20 02:47:34 INFO: HOOK-ENV: vmid=107;vmtype=qemu;dumpdir=;storeid=pbs01-fs01;hostname=server02.mm.lan;tarfile=;logfile=
# /var/log/vzdump/qemu-107.log 2025-08-20 02:47:34 INFO: ----- vzdump scirpt HOOK: pre-restart snapshot 107
# /var/log/vzdump/qemu-107.log 2025-08-20 02:47:34 INFO: HOOK-ENV: vmid=107;vmtype=qemu;dumpdir=;storeid=pbs01-fs01;hostname=server02.mm.lan;tarfile=;logfile=
# /var/log/vzdump/qemu-107.log 2025-08-20 02:47:34 INFO: ----- vzdump scirpt HOOK: post-restart snapshot 107
# /var/log/vzdump/qemu-107.log 2025-08-20 02:47:34 INFO: HOOK-ENV: vmid=107;vmtype=qemu;dumpdir=;storeid=pbs01-fs01;hostname=server02.mm.lan;tarfile=;logfile=
# /var/log/vzdump/qemu-107.log 2025-08-20 02:47:34 INFO: pending configuration changes found (not included into backup)
# /var/log/vzdump/qemu-107.log 2025-08-20 02:47:34 INFO: creating Proxmox Backup Server archive 'vm/107/2025-08-20T00:47:34Z'
# /var/log/vzdump/qemu-107.log 2025-08-20 02:47:34 INFO: issuing guest-agent 'fs-freeze' command
# /var/log/vzdump/qemu-107.log 2025-08-20 02:47:35 INFO: issuing guest-agent 'fs-thaw' command
# /var/log/vzdump/qemu-107.log 2025-08-20 02:47:36 INFO: started backup task 'c815016d-2db0-4ecb-8185-8653179ff2c9'
# /var/log/vzdump/qemu-107.log 2025-08-20 02:47:36 INFO: resuming VM again
# /var/log/vzdump/qemu-107.log 2025-08-20 02:47:36 INFO: scsi0: dirty-bitmap status: OK (9.7 GiB of 170.0 GiB dirty)
# /var/log/vzdump/qemu-107.log 2025-08-20 02:47:36 INFO: scsi1: dirty-bitmap status: OK (2.8 GiB of 50.0 GiB dirty)
# /var/log/vzdump/qemu-107.log 2025-08-20 02:47:36 INFO: scsi2: dirty-bitmap status: OK (7.4 GiB of 100.0 GiB dirty)
# /var/log/vzdump/qemu-107.log 2025-08-20 02:47:36 INFO: using fast incremental mode (dirty-bitmap), 19.8 GiB dirty of 320.0 GiB total
# /var/log/vzdump/qemu-107.log 2025-08-20 02:47:39 INFO:   4% (972.0 MiB of 19.8 GiB) in 3s, read: 324.0 MiB/s, write: 324.0 MiB/s
# /var/log/vzdump/qemu-107.log 2025-08-20 02:47:42 INFO:   8% (1.7 GiB of 19.8 GiB) in 6s, read: 270.7 MiB/s, write: 270.7 MiB/s
# /var/log/vzdump/qemu-107.log 2025-08-20 02:47:45 INFO:  13% (2.6 GiB of 19.8 GiB) in 9s, read: 290.7 MiB/s, write: 280.0 MiB/s
# /var/log/vzdump/qemu-107.log 2025-08-20 02:47:48 INFO:  16% (3.3 GiB of 19.8 GiB) in 12s, read: 241.3 MiB/s, write: 241.3 MiB/s
# /var/log/vzdump/qemu-107.log 2025-08-20 02:47:51 INFO:  20% (4.0 GiB of 19.8 GiB) in 15s, read: 240.0 MiB/s, write: 240.0 MiB/s
# /var/log/vzdump/qemu-107.log 2025-08-20 02:47:54 INFO:  23% (4.7 GiB of 19.8 GiB) in 18s, read: 244.0 MiB/s, write: 244.0 MiB/s
# /var/log/vzdump/qemu-107.log 2025-08-20 02:47:57 INFO:  27% (5.4 GiB of 19.8 GiB) in 21s, read: 248.0 MiB/s, write: 248.0 MiB/s
# /var/log/vzdump/qemu-107.log 2025-08-20 02:48:00 INFO:  31% (6.2 GiB of 19.8 GiB) in 24s, read: 252.0 MiB/s, write: 252.0 MiB/s
# /var/log/vzdump/qemu-107.log 2025-08-20 02:48:03 INFO:  34% (6.9 GiB of 19.8 GiB) in 27s, read: 230.7 MiB/s, write: 230.7 MiB/s
# /var/log/vzdump/qemu-107.log 2025-08-20 02:48:06 INFO:  38% (7.6 GiB of 19.8 GiB) in 30s, read: 260.0 MiB/s, write: 253.3 MiB/s
# /var/log/vzdump/qemu-107.log 2025-08-20 02:48:10 INFO:  40% (8.0 GiB of 19.8 GiB) in 34s, read: 96.0 MiB/s, write: 96.0 MiB/s
# /var/log/vzdump/qemu-107.log 2025-08-20 02:48:13 INFO:  42% (8.3 GiB of 19.8 GiB) in 37s, read: 113.3 MiB/s, write: 113.3 MiB/s
# /var/log/vzdump/qemu-107.log 2025-08-20 02:48:16 INFO:  43% (8.5 GiB of 19.8 GiB) in 40s, read: 72.0 MiB/s, write: 72.0 MiB/s
# /var/log/vzdump/qemu-107.log 2025-08-20 02:48:28 INFO:  44% (8.7 GiB of 19.8 GiB) in 52s, read: 15.7 MiB/s, write: 15.7 MiB/s
# /var/log/vzdump/qemu-107.log 2025-08-20 02:48:36 INFO:  45% (8.9 GiB of 19.8 GiB) in 1m, read: 24.0 MiB/s, write: 24.0 MiB/s
# /var/log/vzdump/qemu-107.log 2025-08-20 02:48:44 INFO:  46% (9.1 GiB of 19.8 GiB) in 1m 8s, read: 26.0 MiB/s, write: 26.0 MiB/s
# /var/log/vzdump/qemu-107.log 2025-08-20 02:48:55 INFO:  47% (9.3 GiB of 19.8 GiB) in 1m 19s, read: 17.5 MiB/s, write: 17.5 MiB/s
# /var/log/vzdump/qemu-107.log 2025-08-20 02:49:05 INFO:  48% (9.5 GiB of 19.8 GiB) in 1m 29s, read: 21.6 MiB/s, write: 21.6 MiB/s
# /var/log/vzdump/qemu-107.log 2025-08-20 02:49:10 INFO:  49% (9.7 GiB of 19.8 GiB) in 1m 34s, read: 44.0 MiB/s, write: 44.0 MiB/s
# /var/log/vzdump/qemu-107.log 2025-08-20 02:49:13 INFO:  50% (9.9 GiB of 19.8 GiB) in 1m 37s, read: 74.7 MiB/s, write: 74.7 MiB/s
# /var/log/vzdump/qemu-107.log 2025-08-20 02:49:16 INFO:  51% (10.1 GiB of 19.8 GiB) in 1m 40s, read: 56.0 MiB/s, write: 56.0 MiB/s
# /var/log/vzdump/qemu-107.log 2025-08-20 02:49:19 INFO:  52% (10.3 GiB of 19.8 GiB) in 1m 43s, read: 61.3 MiB/s, write: 61.3 MiB/s
# /var/log/vzdump/qemu-107.log 2025-08-20 02:49:22 INFO:  53% (10.7 GiB of 19.8 GiB) in 1m 46s, read: 132.0 MiB/s, write: 130.7 MiB/s
# /var/log/vzdump/qemu-107.log 2025-08-20 02:49:25 INFO:  54% (10.8 GiB of 19.8 GiB) in 1m 49s, read: 30.7 MiB/s, write: 30.7 MiB/s
# /var/log/vzdump/qemu-107.log 2025-08-20 02:49:33 INFO:  55% (10.9 GiB of 19.8 GiB) in 1m 57s, read: 17.5 MiB/s, write: 17.5 MiB/s
# /var/log/vzdump/qemu-107.log 2025-08-20 02:49:39 INFO:  56% (11.1 GiB of 19.8 GiB) in 2m 3s, read: 36.0 MiB/s, write: 36.0 MiB/s
# /var/log/vzdump/qemu-107.log 2025-08-20 02:49:42 INFO:  59% (11.7 GiB of 19.8 GiB) in 2m 6s, read: 192.0 MiB/s, write: 192.0 MiB/s
# /var/log/vzdump/qemu-107.log 2025-08-20 02:49:45 INFO:  62% (12.3 GiB of 19.8 GiB) in 2m 9s, read: 218.7 MiB/s, write: 217.3 MiB/s
# /var/log/vzdump/qemu-107.log 2025-08-20 02:49:48 INFO:  64% (12.9 GiB of 19.8 GiB) in 2m 12s, read: 182.7 MiB/s, write: 182.7 MiB/s
# /var/log/vzdump/qemu-107.log 2025-08-20 02:49:51 INFO:  67% (13.4 GiB of 19.8 GiB) in 2m 15s, read: 186.7 MiB/s, write: 186.7 MiB/s
# /var/log/vzdump/qemu-107.log 2025-08-20 02:49:54 INFO:  69% (13.8 GiB of 19.8 GiB) in 2m 18s, read: 132.0 MiB/s, write: 129.3 MiB/s
# /var/log/vzdump/qemu-107.log 2025-08-20 02:49:57 INFO:  72% (14.3 GiB of 19.8 GiB) in 2m 21s, read: 174.7 MiB/s, write: 174.7 MiB/s
# /var/log/vzdump/qemu-107.log 2025-08-20 02:50:01 INFO:  73% (14.5 GiB of 19.8 GiB) in 2m 25s, read: 59.0 MiB/s, write: 59.0 MiB/s
# /var/log/vzdump/qemu-107.log 2025-08-20 02:50:04 INFO:  75% (15.0 GiB of 19.8 GiB) in 2m 28s, read: 173.3 MiB/s, write: 172.0 MiB/s
# /var/log/vzdump/qemu-107.log 2025-08-20 02:50:07 INFO:  76% (15.1 GiB of 19.8 GiB) in 2m 31s, read: 38.7 MiB/s, write: 38.7 MiB/s
# /var/log/vzdump/qemu-107.log 2025-08-20 02:50:10 INFO:  77% (15.2 GiB of 19.8 GiB) in 2m 34s, read: 34.7 MiB/s, write: 33.3 MiB/s
# /var/log/vzdump/qemu-107.log 2025-08-20 02:50:14 INFO:  78% (15.4 GiB of 19.8 GiB) in 2m 38s, read: 47.0 MiB/s, write: 47.0 MiB/s
# /var/log/vzdump/qemu-107.log 2025-08-20 02:50:18 INFO:  79% (15.7 GiB of 19.8 GiB) in 2m 42s, read: 63.0 MiB/s, write: 62.0 MiB/s
# /var/log/vzdump/qemu-107.log 2025-08-20 02:50:21 INFO:  80% (15.9 GiB of 19.8 GiB) in 2m 45s, read: 62.7 MiB/s, write: 62.7 MiB/s
# /var/log/vzdump/qemu-107.log 2025-08-20 02:50:25 INFO:  81% (16.1 GiB of 19.8 GiB) in 2m 49s, read: 52.0 MiB/s, write: 49.0 MiB/s
# /var/log/vzdump/qemu-107.log 2025-08-20 02:50:29 INFO:  82% (16.3 GiB of 19.8 GiB) in 2m 53s, read: 60.0 MiB/s, write: 58.0 MiB/s
# /var/log/vzdump/qemu-107.log 2025-08-20 02:50:32 INFO:  83% (16.5 GiB of 19.8 GiB) in 2m 56s, read: 69.3 MiB/s, write: 69.3 MiB/s
# /var/log/vzdump/qemu-107.log 2025-08-20 02:50:35 INFO:  84% (16.7 GiB of 19.8 GiB) in 2m 59s, read: 65.3 MiB/s, write: 64.0 MiB/s
# /var/log/vzdump/qemu-107.log 2025-08-20 02:50:38 INFO:  85% (16.9 GiB of 19.8 GiB) in 3m 2s, read: 57.3 MiB/s, write: 57.3 MiB/s
# /var/log/vzdump/qemu-107.log 2025-08-20 02:50:41 INFO:  86% (17.1 GiB of 19.8 GiB) in 3m 5s, read: 74.7 MiB/s, write: 72.0 MiB/s
# /var/log/vzdump/qemu-107.log 2025-08-20 02:50:44 INFO:  87% (17.3 GiB of 19.8 GiB) in 3m 8s, read: 82.7 MiB/s, write: 81.3 MiB/s
# /var/log/vzdump/qemu-107.log 2025-08-20 02:50:47 INFO:  88% (17.6 GiB of 19.8 GiB) in 3m 11s, read: 78.7 MiB/s, write: 76.0 MiB/s
# /var/log/vzdump/qemu-107.log 2025-08-20 02:50:50 INFO:  89% (17.8 GiB of 19.8 GiB) in 3m 14s, read: 85.3 MiB/s, write: 84.0 MiB/s
# /var/log/vzdump/qemu-107.log 2025-08-20 02:50:53 INFO:  90% (18.0 GiB of 19.8 GiB) in 3m 17s, read: 52.0 MiB/s, write: 45.3 MiB/s
# /var/log/vzdump/qemu-107.log 2025-08-20 02:50:56 INFO:  92% (18.2 GiB of 19.8 GiB) in 3m 20s, read: 93.3 MiB/s, write: 86.7 MiB/s
# /var/log/vzdump/qemu-107.log 2025-08-20 02:50:59 INFO:  93% (18.5 GiB of 19.8 GiB) in 3m 23s, read: 88.0 MiB/s, write: 76.0 MiB/s
# /var/log/vzdump/qemu-107.log 2025-08-20 02:51:02 INFO:  94% (18.7 GiB of 19.8 GiB) in 3m 26s, read: 78.7 MiB/s, write: 70.7 MiB/s
# /var/log/vzdump/qemu-107.log 2025-08-20 02:51:07 INFO:  95% (18.8 GiB of 19.8 GiB) in 3m 31s, read: 17.6 MiB/s, write: 16.0 MiB/s
# /var/log/vzdump/qemu-107.log 2025-08-20 02:51:13 INFO:  96% (19.0 GiB of 19.8 GiB) in 3m 37s, read: 38.0 MiB/s, write: 36.0 MiB/s
# /var/log/vzdump/qemu-107.log 2025-08-20 02:51:16 INFO:  97% (19.2 GiB of 19.8 GiB) in 3m 40s, read: 69.3 MiB/s, write: 66.7 MiB/s
# /var/log/vzdump/qemu-107.log 2025-08-20 02:51:19 INFO:  98% (19.4 GiB of 19.8 GiB) in 3m 43s, read: 68.0 MiB/s, write: 64.0 MiB/s
# /var/log/vzdump/qemu-107.log 2025-08-20 02:51:22 INFO:  99% (19.7 GiB of 19.8 GiB) in 3m 46s, read: 101.3 MiB/s, write: 100.0 MiB/s
# /var/log/vzdump/qemu-107.log 2025-08-20 02:51:25 INFO: 100% (19.8 GiB of 19.8 GiB) in 3m 49s, read: 20.0 MiB/s, write: 17.3 MiB/s
# /var/log/vzdump/qemu-107.log 2025-08-20 02:52:23 INFO: backup is sparse: 48.00 MiB (0%) total zero data
# /var/log/vzdump/qemu-107.log 2025-08-20 02:52:23 INFO: backup was done incrementally, reused 300.49 GiB (93%)
# /var/log/vzdump/qemu-107.log 2025-08-20 02:52:23 INFO: transferred 19.79 GiB in 287 seconds (70.6 MiB/s)
# /var/log/vzdump/qemu-107.log 2025-08-20 02:52:23 INFO: adding notes to backup
# /var/log/vzdump/qemu-107.log 2025-08-20 02:52:23 INFO: ----- vzdump scirpt HOOK: backup-end snapshot 107
# /var/log/vzdump/qemu-107.log 2025-08-20 02:52:23 INFO: HOOK-ENV: vmid=107;vmtype=qemu;dumpdir=;storeid=pbs01-fs01;hostname=server02.mm.lan;tarfile=;logfile=
# /var/log/vzdump/qemu-107.log 2025-08-20 02:52:23 INFO: Finished Backup of VM 107 (00:04:49)




# LXC-MACHINE;;;;;/etc/pve/lxc/102.conf;;;;;monitoring01.mm.lan
# /var/log/vzdump/lxc-102.log 2025-08-20 02:01:32 INFO: Starting Backup of VM 102 (lxc)
# /var/log/vzdump/lxc-102.log 2025-08-20 02:01:32 INFO: status = running
# /var/log/vzdump/lxc-102.log 2025-08-20 02:01:32 INFO: CT Name: monitoring01.mm.lan
# /var/log/vzdump/lxc-102.log 2025-08-20 02:01:32 INFO: including mount point rootfs ('/') in backup
# /var/log/vzdump/lxc-102.log 2025-08-20 02:01:32 INFO: backup mode: snapshot
# /var/log/vzdump/lxc-102.log 2025-08-20 02:01:32 INFO: ionice priority: 7
# /var/log/vzdump/lxc-102.log 2025-08-20 02:01:32 INFO: ----- vzdump scirpt HOOK: backup-start snapshot 102
# /var/log/vzdump/lxc-102.log 2025-08-20 02:01:32 INFO: HOOK-ENV: vmid=102;vmtype=lxc;dumpdir=;storeid=pbs01-fs01;hostname=monitoring01.mm.lan;tarfile=;logfile=
# /var/log/vzdump/lxc-102.log 2025-08-20 02:01:32 INFO: ----- vzdump scirpt HOOK: pre-stop snapshot 102
# /var/log/vzdump/lxc-102.log 2025-08-20 02:01:32 INFO: HOOK-ENV: vmid=102;vmtype=lxc;dumpdir=;storeid=pbs01-fs01;hostname=monitoring01.mm.lan;tarfile=;logfile=
# /var/log/vzdump/lxc-102.log 2025-08-20 02:01:32 INFO: create storage snapshot 'vzdump'
# /var/log/vzdump/lxc-102.log 2025-08-20 02:01:33 INFO: ----- vzdump scirpt HOOK: pre-restart snapshot 102
# /var/log/vzdump/lxc-102.log 2025-08-20 02:01:33 INFO: HOOK-ENV: vmid=102;vmtype=lxc;dumpdir=;storeid=pbs01-fs01;hostname=monitoring01.mm.lan;tarfile=;logfile=
# /var/log/vzdump/lxc-102.log 2025-08-20 02:01:33 INFO: ----- vzdump scirpt HOOK: post-restart snapshot 102
# /var/log/vzdump/lxc-102.log 2025-08-20 02:01:33 INFO: HOOK-ENV: vmid=102;vmtype=lxc;dumpdir=;storeid=pbs01-fs01;hostname=monitoring01.mm.lan;tarfile=;logfile=
# /var/log/vzdump/lxc-102.log 2025-08-20 02:01:33 INFO: creating Proxmox Backup Server archive 'ct/102/2025-08-20T00:01:32Z'
# /var/log/vzdump/lxc-102.log 2025-08-20 02:01:33 INFO: set max number of entries in memory for file-based backups to 1048576
# /var/log/vzdump/lxc-102.log 2025-08-20 02:01:33 INFO: run: lxc-usernsexec -m u:0:100000:65536 -m g:0:100000:65536 -- /usr/bin/proxmox-backup-client backup --cryp208542_102/etc/vzdump/pct.conf root.pxar:/mnt/vzsnap0 --include-dev /mnt/vzsnap0/./ --skip-lost-and-found --exclude=/tmp/?* --exclude=/var/tmp/?* --exclude=/var/102 --backup-time 1755648092 --entries-max 1048576 --repository user_mmlan@pbs@172.31.0.248:fs01 --ns mmlan
# /var/log/vzdump/lxc-102.log 2025-08-20 02:01:33 INFO: Starting backup: [mmlan]:ct/102/2025-08-20T00:01:32Z
# /var/log/vzdump/lxc-102.log 2025-08-20 02:01:33 INFO: Client name: pve01
# /var/log/vzdump/lxc-102.log 2025-08-20 02:01:33 INFO: Starting backup protocol: Wed Aug 20 02:01:33 2025
# /var/log/vzdump/lxc-102.log 2025-08-20 02:01:33 INFO: Downloading previous manifest (Tue Aug 19 02:02:10 2025)
# /var/log/vzdump/lxc-102.log 2025-08-20 02:01:33 INFO: Upload config file '/var/tmp/vzdumptmp1208542_102/etc/vzdump/pct.conf' to 'user_mmlan@pbs@172.31.0.248:8007
# /var/log/vzdump/lxc-102.log 2025-08-20 02:01:33 INFO: Upload directory '/mnt/vzsnap0' to 'user_mmlan@pbs@172.31.0.248:8007:fs01' as root.pxar.didx
# /var/log/vzdump/lxc-102.log 2025-08-20 02:02:33 INFO: processed 7.805 GiB in 1m, uploaded 1.393 GiB
# /var/log/vzdump/lxc-102.log 2025-08-20 02:03:33 INFO: processed 12.65 GiB in 2m, uploaded 1.446 GiB
# /var/log/vzdump/lxc-102.log 2025-08-20 02:03:46 INFO: root.pxar: had to backup 1.58 GiB of 16.308 GiB (compressed 286.611 MiB) in 133.26 s (average 12.141 MiB/s)
# /var/log/vzdump/lxc-102.log 2025-08-20 02:03:46 INFO: root.pxar: backup was done incrementally, reused 14.728 GiB (90.3%)
# /var/log/vzdump/lxc-102.log 2025-08-20 02:03:46 INFO: Uploaded backup catalog (9.827 MiB)
# /var/log/vzdump/lxc-102.log 2025-08-20 02:03:49 INFO: Duration: 135.90s
# /var/log/vzdump/lxc-102.log 2025-08-20 02:03:49 INFO: End Time: Wed Aug 20 02:03:49 2025
# /var/log/vzdump/lxc-102.log 2025-08-20 02:03:49 INFO: adding notes to backup
# /var/log/vzdump/lxc-102.log 2025-08-20 02:03:49 INFO: ----- vzdump scirpt HOOK: backup-end snapshot 102
# /var/log/vzdump/lxc-102.log 2025-08-20 02:03:49 INFO: HOOK-ENV: vmid=102;vmtype=lxc;dumpdir=;storeid=pbs01-fs01;hostname=monitoring01.mm.lan;tarfile=;logfile=
# /var/log/vzdump/lxc-102.log 2025-08-20 02:03:51 INFO: cleanup temporary 'vzdump' snapshot
# /var/log/vzdump/lxc-102.log 2025-08-20 02:03:52 INFO: Finished Backup of VM 102 (00:02:20)
