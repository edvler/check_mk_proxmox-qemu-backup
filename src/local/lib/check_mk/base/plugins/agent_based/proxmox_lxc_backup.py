#!/usr/bin/python


# Author: Matthias Maderer
# E-Mail: edvler@edvler-blog.de
# URL: https://github.com/edvler/check_mk_proxmox-lxc-backup
# License: GPLv2

from .agent_based_api.v1 import *
import time
import datetime
import re

# the inventory function (dummy)
def inventory_lxc_backup(section):
    # loop over all output lines of the agent
    for line in section:
        if line[0].startswith('LXC-MACHINE;;;;;'):
            arr_lxc_vars = line[0].split(';;;;;')
            arr_lxc_id = arr_lxc_vars[1].split('/')
            lxc_id = arr_lxc_id[-1].replace('.conf','')
            yield Service(item=arr_lxc_vars[2] + " Id: " + lxc_id + "")

# the check function (dummy)
def check_lxc_backup(item, params, section):
    #return 0 if check of backups should not be done
    if params['check_backup'] == 'ignore':
       # return 0, 'check disabled by rule'
#        yield 0, 'check disabled by rule'
        yield Result(state=State.OK, summary='check disabled by rule')
        return



    #get name of the logfile (the output of each logfile is
    #prefixed with its filename from the plugin)
    lxc_id=item.split(' ')[-1]
    logfile = '/var/log/vzdump/lxc-' + lxc_id + '.log'

#    ft=time.strftime("-%Y-%m-%d_%H%M%S")
#    f=open(os.getenv("OMD_ROOT") + '/tmp/' + lxc_id + ft  + ".info_agent"  , 'w')
#    for item in info:
#        f.write("%s\n" % item)
#    f.close()

    #counter
    line_count=0
    warn_count=0
    warn_msg=""
    error_count=0
    error_msg=""

    archive="nothing"
    finished="nothing"
    started="nothing"
    file_created="nothing"
    incremental=False

    vzdump_is_running = 0

    offset=0

    #check all lines
    for line in section:
        #Check for running tasks
        #task UPID:pve01:00000E8D:009D1950:5E344CAA:vzdump:101:root@pam:
        if line[0] == 'PSOUTPUT':
            #taskinfos = line[1].split(":")
            #if taskinfos[6] == lxc_id:
            #    vzdump_is_running = 1
            for x in line:
                if x == lxc_id:
                    vzdump_is_running = 1

        #is this line of the given item (lxc_id)
        if line[0] == logfile:
            line_count += 1 #count lines of log for this id

            #old or new dateformat in logfile?
            #old /var/log/vzdump/lxc-104.log Feb 07 12:10:54 INFO: creating archive '/vmfs/bkp-fs-stor-001/dump/vzdump-lxc-104-2018_02_07-12_10_54.vma.gz'
            #new /var/log/vzdump/lxc-105.log 2018-02-06 16:00:03 INFO: creating archive '/vmfs/bkp-urbackup01-001/dump/vzdump-lxc-105-2018_02_06-16_00_02.vma.gz'
            d = ""
            try:
                d = time.strptime(line[1]  + ' ' + line[2],"%Y-%m-%d %H:%M:%S")
                offset=0
            except ValueError:
                try:
                    d = time.strptime(time.strftime("%Y",time.localtime()) + ' ' + line[1]  + ' ' + line[2] + ' ' + line[3],"%Y %b %d %H:%M:%S")
                    offset=1
                except ValueError:
                    pass

            try:
                #extract several infos
                #proxmox 6.2-9 introduced a new log-format
                if line[offset+5] == 'vzdump':
                    if line[offset+3] + ' ' + line[offset+4] + ' ' + line[offset+5] + ' ' + line[offset+6] == 'INFO: creating vzdump archive':
                        file_created = line
                        startdate = getDateFromFileCreated(file_created[offset+7].split("/")[-1])
                #Proxmox Backup Server
                if line[offset+5] + ' ' + line[offset+6] + ' ' + line[offset+7] == 'Proxmox Backup Server':
                    if line[offset+3] + ' ' + line[offset+4] + ' ' + line[offset+5] + ' ' + line[offset+6] + ' ' + line[offset+7] + ' ' + line[offset+8] == 'INFO: creating Proxmox Backup Server archive':
                        file_created = line
                        startdate = getDateFromFileCreated(file_created[offset+9].split("/")[-1])
                else:
                    if line[offset+3] + ' ' + line[offset+4] + ' ' + line[offset+5] == 'INFO: creating archive':
                        file_created = line
                        startdate = getDateFromFileCreated(file_created[offset+6].split("/")[-1])

                if line[offset+3] + ' ' + line[offset+4] + ' ' + line[offset+5] + ' ' + line[offset+6] == 'INFO: archive file size:':
                    archive = line
                #we have no archive here, only reused and transfered
                #root.pxar:', u'had', u'to', u'upload', u'585.86', u'MiB', u'of', u'5.95', u'GiB', u'in', u'60.17s,', u'average', u'speed', u'9.74', u'MiB/s).']
                if line[offset+3] + ' ' + line[offset+4] + ' ' + line[offset+5] + ' ' + line[offset+6] + ' ' + line[offset+7] == 'INFO: root.pxar: had to upload':
                    archive = line
                if line[offset+3] + ' ' + line[offset+4] + ' ' + line[offset+5] + ' ' + line[offset+6] + ' ' + line[offset+7] == 'INFO: root.pxar: had to backup':
                    archive = line
                if 'incrementally,' in line:
                    incremental = True
                    size, size_unit = '0', 'B'
                if line[offset+3] + ' ' + line[offset+4] + ' ' + line[offset+5] + ' ' + line[offset+6] + ' ' + line[offset+7] == 'INFO: Starting Backup of VM':
                    started = line
                    started_datetime = d

                if line[offset+3] + ' ' + line[offset+4] + ' ' + line[offset+5] + ' ' + line[offset+6] + ' ' + line[offset+7] == 'INFO: Finished Backup of VM':
                    finished = line

            except IndexError:
                pass

            #search for keywords
            for content in line:
                if 'warn' in content.lower():
                    warn_count += 1
                    warn_msg += " ".join(line[offset+3:]) + "; "
                elif 'error' in content.lower() or 'fail' in content.lower():
                    error_count += 1
                    error_msg += " ".join(line[offset+3:]) + "; "

    #if line_count is 0, no backup file exists --> error!
    if line_count == 0:
        yield Result(state=State.CRIT, summary="no backup exists for this VM guest")
        return

    #check counter
    if error_count > 0:
        yield Result(state=State.CRIT, summary=error_msg)
        return
    if warn_count > 0:
        yield Result(state=State.CRIT, summary=warn_msg)
        return
    #no warnings and erros!! check if lines indicating a successfull backup exists
    if (archive != "nothing" or incremental) and finished != "nothing" and started != "nothing" and file_created != "nothing":

        warn, error = params['backup_age']

        # Age of Backup
        old = time.time() - time.mktime(startdate)
        duration_formatted = pretty_time_delta(old)
        infotext = 'last backup: ' + time.strftime("%Y-%m-%d %H:%M", startdate) + ' (Age: ' + duration_formatted + ' warn/crit at ' + pretty_time_delta(warn) + '/' + pretty_time_delta(error) + ')'

        # Example sizes
        #lxc-100.log:Aug 21 05:01:31 INFO: archive file size: 594MB
        #lxc-101.log:Jun 12 05:08:59 INFO: archive file size: 3.94GB
        #lxc-102.log:Jun 12 05:09:00 INFO: archive file size: 0KB
        #lxc-104.log:Jun 12 05:09:00 INFO: archive file size: 0KB
        #lxc-105.log:Jun 12 05:10:58 INFO: archive file size: 832MB
        #lxc-106.log:Jun 12 05:19:39 INFO: archive file size: 3.84GB
        warn_size = 0
        error_size = 0
        if 'backup_minsize' in params:
            warn_size, error_size = params['backup_minsize']
        if archive[offset+4] == "archive":
            size = archive[offset+7]
            size_unit = size[-2:]
        if archive[offset+3] + ' ' + archive[offset+4] + ' ' + archive[offset+5] + ' ' + archive[offset+6] + ' ' + archive[offset+7] == 'INFO: root.pxar: had to upload':
            size = archive[offset+8]
            size_unit = archive[offset+9]
        if archive[offset+3] + ' ' + archive[offset+4] + ' ' + archive[offset+5] + ' ' + archive[offset+6] + ' ' + archive[offset+7] == 'INFO: root.pxar: had to backup':
            size = archive[offset+8]
            size_unit = archive[offset+9]
        size_numbers = float(size[:len(size)-2])
        size_cal = -1

        # Norm to Byte
        # .../share/check_mk/web/plugins/metrics/check_mk.py
        if size_unit == "TB":
            size_cal = size_numbers*1024*1024*1024*1024
        if size_unit == "GB":
            size_cal = size_numbers*1024*1024*1024
        if size_unit == "MB":
            size_cal = size_numbers*1024*1024
        if size_unit == "KB":
            size_cal = size_numbers*1024
        if size_unit == "TiB":
            size_cal = size_numbers*1000*1000*1000*1000
        if size_unit == "GiB":
            size_cal = size_numbers*1000*1000*1000
        if size_unit == "MiB":
            size_cal = size_numbers*1000*1000
        if size_unit == "KiB":
            size_cal = size_numbers*1000
        # metrics from .../share/check_mk/web/plugins/metrics/check_mk.py
        perfdata = [
            ( "backup_age", int(old), warn, error ),
            ( "file_size", int(size_cal), warn_size, error_size ),
        ]

        if old < warn:
            yield Result(state=State.OK, summary=infotext)
            #yield 0, infotext, perfdata
        if old >= warn and old < error:
            yield Result(state=State.WARN, summary=infotext)
            #yield 1, infotext, perfdata
        if old >= error:
            yield Result(state=State.CRIT, summary=infotext)
            #yield 2, infotext, perfdata

        if archive[offset+4] == "archive":
            size_infotext = "Archive size: " + str(size_numbers) + ' ' + size_unit
        elif archive[offset+3] + ' ' + archive[offset+4] + ' ' + archive[offset+5] + ' ' + archive[offset+6] + ' ' + archive[offset+7] == 'INFO: root.pxar: had to upload':
            size_infotext = "upload size: " + str(size_numbers) + ' ' + size_unit
        elif archive[offset+3] + ' ' + archive[offset+4] + ' ' + archive[offset+5] + ' ' + archive[offset+6] + ' ' + archive[offset+7] == 'INFO: root.pxar: had to backup':
            size_infotext = "upload size: " + str(size_numbers) + ' ' + size_unit
        else:
            size_infotext = "empty incremental backup"

        if size_cal >= warn_size or incremental:
            yield Result(state=State.OK, summary=size_infotext)
            #yield 0, size_infotext, perfdata
        elif size_cal < warn_size and size_cal >= error_size:
            yield Result(state=State.WARN, summary=size_infotext)
            #yield 1, size_infotext, perfdata
        elif size_cal < error_size:
            yield Result(state=State.CRIT, summary=size_infotext)
            #yield 2, size_infotext, perfdata

        return
    elif started != "nothing":
        vzdump_is_running = 1

    #is backup currently running?
    if vzdump_is_running == 1:
        old = time.time() - time.mktime(started_datetime)
        if old < params['running_time']:
            yield Result(state=State.OK, summary='backup is running since: ' + time.strftime("%Y-%m-%d %H:%M", started_datetime))
            #yield 0, 'backup is running since: ' + time.strftime("%Y-%m-%d %H:%M", started_datetime)
            return
        else:
            yield Result(state=State.WARN, summary='backup is running since: ' + time.strftime("%Y-%m-%d %H:%M", started_datetime))
            #yield 1, 'backup is running since: ' + time.strftime("%Y-%m-%d %H:%M", started_datetime)
            return

    #yield 3, "error occured in check plugin. Please post a issue on https://github.com/edvler/check_mk_proxmox-lxc-backup/issues inlcuding the output of the agent plugin /usr/lib/check_mk_agent/plugins/proxmox-lxc-backup"
    yield Result(state=State.UNKOWN, summary="error occured in check plugin. Please post a issue on https://github.com/edvler/check_mk_proxmox-lxc-backup/issues inlcuding the output of the agent plugin /usr/lib/check_mk_agent/plugins/proxmox-lxc-backup")
    return

register.check_plugin(
    name = "proxmox_lxc_backup",
    service_name = "Proxmox LXC VM backup %s",
    discovery_function = inventory_lxc_backup,
    check_function = check_lxc_backup,
    check_default_parameters = {'check_backup': 'check', 'backup_age': (93600, 108000), 'running_time': 1800},
    check_ruleset_name = "proxmox"
)




def getDateFromFileCreated(vma_name):
    if "T" in vma_name:
        p = re.compile("([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2})")
        m = p.search(vma_name)
        d = time.strptime(m.group(1),"%Y-%m-%dT%H:%M:%S")
    else:
        if "differential" in vma_name:
            p = re.compile("differential-(20[0-9][0-9]_[0-9][0-9]_[0-9][0-9]-[0-9][0-9]_[0-9][0-9]_[0-9][0-9])")
        else:
            p = re.compile("(20[0-9][0-9]_[0-9][0-9]_[0-9][0-9]-[0-9][0-9]_[0-9][0-9]_[0-9][0-9])")
        m = p.search(vma_name)
        d = time.strptime(m.group(1),"%Y_%m_%d-%H_%M_%S")
    return d
#    p = re.compile("(20[0-9][0-9]_[0-9][0-9]_[0-9][0-9]-[0-9][0-9]_[0-9][0-9]_[0-9][0-9])")
#    m = p.search(vma_name)
#    d = time.strptime(m.group(1),"%Y_%m_%d-%H_%M_%S")
#    return d

#thanks to https://gist.github.com/thatalextaylor/7408395
def pretty_time_delta(seconds):
    sign_string = '-' if seconds < 0 else ''
    seconds = abs(int(seconds))
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    if days > 0:
        return '%s%dd %dh %dm' % (sign_string, days, hours, minutes)
    elif hours > 0:
        return '%s%dh %dm' % (sign_string, hours, minutes)
    elif minutes > 0:
        return '%s%dm' % (sign_string, minutes)
    else:
        return '0m'

#Example output of agent
#
#root@pve01:/usr/lib/check_mk_agent/plugins# ./proxmox_lxc_backup
#<<<proxmox_lxc_backup>>>
#LXC-MACHINE;;;;;/etc/pve/lxc-server/103.conf;;;;;server01-hlds
#LXC-MACHINE;;;;;/etc/pve/lxc-server/102.conf;;;;;firewall01
#lXC-MACHINE;;;;;/etc/pve/lxc-server/108.conf;;;;;monitoring01
#lXC-MACHINE;;;;;/etc/pve/lxc-server/101.conf;;;;;guacamole01
#lXC-MACHINE;;;;;/etc/pve/lxc-server/100.conf;;;;;pfsense01
#lXC-MACHINE;;;;;/etc/pve/lxc-server/106.conf;;;;;server02
#lXC-MACHINE;;;;;/etc/pve/lxc-server/105.conf;;;;;urbackup01
#lXC-MACHINE;;;;;/etc/pve/lxc-server/104.conf;;;;;zbox
#task UPID:pve01:000031A4:009F1CF0:5E3451D2:vzdump:108:root@pam:
#/var/log/vzdump/lxc-100.log 2017-09-05 11:45:02 INFO: Starting Backup of VM 100 (lxc)
#/var/log/vzdump/lxc-100.log 2017-09-05 11:45:02 INFO: status = stopped
#/var/log/vzdump/lxc-100.log 2017-09-05 11:45:02 INFO: update VM 100: -lock backup
#/var/log/vzdump/lxc-100.log 2017-09-05 11:45:02 INFO: backup mode: stop
#/var/log/vzdump/lxc-100.log 2017-09-05 11:45:02 INFO: ionice priority: 7
#/var/log/vzdump/lxc-100.log 2017-09-05 11:45:02 INFO: VM Name: pfsense01
#/var/log/vzdump/lxc-100.log 2017-09-05 11:45:02 INFO: include disk 'virtio0' 'WDC15EADS-tpool-001:vm-100-disk-1' 32G
#/var/log/vzdump/lxc-100.log 2017-09-05 11:45:04 INFO: creating archive '/vmfs/bkp-vol-001/dump/vzdump-lxc-100-2017_09_05-11_45_02.vma.gz'
#/var/log/vzdump/lxc-100.log 2017-09-05 11:45:04 INFO: starting kvm to execute backup task
#/var/log/vzdump/lxc-100.log 2017-09-05 11:45:06 INFO: started backup task 'bb24a1d8-e70a-4cda-a10e-86adb9dab94d'
#/var/log/vzdump/lxc-100.log 2017-09-05 11:46:35 INFO: transferred 34359 MB in 89 seconds (386 MB/s)
#/var/log/vzdump/lxc-100.log 2017-09-05 11:46:35 INFO: stopping kvm after backup task
#/var/log/vzdump/lxc-100.log 2017-09-05 11:46:36 INFO: archive file size: 686MB
#/var/log/vzdump/lxc-100.log 2017-09-05 11:46:36 INFO: Finished Backup of VM 100 (00:01:34)
#/var/log/vzdump/lxc-101.log Apr 06 11:46:34 INFO: Starting Backup of VM 101 (lxc)
#/var/log/vzdump/lxc-101.log Apr 06 11:46:34 INFO: status = stopped
#/var/log/vzdump/lxc-101.log Apr 06 11:46:34 INFO: update VM 101: -lock backup
#/var/log/vzdump/lxc-101.log Apr 06 11:46:35 INFO: backup mode: stop
#/var/log/vzdump/lxc-101.log Apr 06 11:46:35 INFO: ionice priority: 7
#/var/log/vzdump/lxc-101.log Apr 06 11:46:35 INFO: VM Name: guacamole01
#/var/log/vzdump/lxc-101.log Apr 06 11:46:35 INFO: include disk 'sata0' 'WDC15EADS-tpool-001:vm-101-disk-1'
#/var/log/vzdump/lxc-101.log Apr 06 11:46:35 INFO: creating archive '/vmfs/usbbac001-fs-backup-001/dump/vzdump-lxc-101-2017_04_06-11_46_34.vma.gz'
#/var/log/vzdump/lxc-101.log Apr 06 11:46:35 INFO: starting kvm to execute backup task
#/var/log/vzdump/lxc-101.log Apr 06 11:46:38 INFO: started backup task '78127b22-7948-4555-8c48-10b8f3d01ce5'
#/var/log/vzdump/lxc-101.log Apr 06 11:59:11 INFO: transferred 54760 MB in 753 seconds (72 MB/s)
#/var/log/vzdump/lxc-101.log Apr 06 11:59:11 INFO: stopping kvm after backup task
#/var/log/vzdump/lxc-101.log Apr 06 11:59:12 INFO: archive file size: 1.41GB
#/var/log/vzdump/lxc-101.log Apr 06 11:59:12 INFO: delete old backup '/vmfs/usbbac001-fs-backup-001/dump/vzdump-lxc-101-2017_03_14-11_46_37.vma.gz'
#/var/log/vzdump/lxc-101.log Apr 06 11:59:13 INFO: Finished Backup of VM 101 (00:12:39)
#/var/log/vzdump/lxc-102.log 2017-09-05 11:46:36 INFO: Starting Backup of VM 102 (lxc)
#/var/log/vzdump/lxc-102.log 2017-09-05 11:46:36 INFO: status = stopped
#/var/log/vzdump/lxc-102.log 2017-09-05 11:46:36 INFO: update VM 102: -lock backup
#/var/log/vzdump/lxc-102.log 2017-09-05 11:46:36 INFO: backup mode: stop
#/var/log/vzdump/lxc-102.log 2017-09-05 11:46:36 INFO: ionice priority: 7
#/var/log/vzdump/lxc-102.log 2017-09-05 11:46:36 INFO: VM Name: firewall01
#/var/log/vzdump/lxc-102.log 2017-09-05 11:46:36 INFO: include disk 'sata0' 'ssd-850evo-tpool-001:vm-102-disk-2' 9G
#/var/log/vzdump/lxc-102.log 2017-09-05 11:46:36 INFO: creating archive '/vmfs/bkp-vol-001/dump/vzdump-lxc-102-2017_09_05-11_46_36.vma.gz'
#/var/log/vzdump/lxc-102.log 2017-09-05 11:46:36 INFO: starting kvm to execute backup task
#/var/log/vzdump/lxc-102.log 2017-09-05 11:46:38 INFO: started backup task '0ca8bbd7-65cb-4443-8743-0f2074fa736d'
#/var/log/vzdump/lxc-102.log 2017-09-05 11:50:29 INFO: transferred 9663 MB in 231 seconds (41 MB/s)
#/var/log/vzdump/lxc-102.log 2017-09-05 11:50:29 INFO: stopping kvm after backup task
#/var/log/vzdump/lxc-102.log 2017-09-05 11:50:30 INFO: archive file size: 1.95GB
#/var/log/vzdump/lxc-102.log 2017-09-05 11:50:30 INFO: Finished Backup of VM 102 (00:03:54)
#/var/log/vzdump/lxc-103.log 2017-09-05 11:50:30 INFO: Starting Backup of VM 103 (lxc)
#/var/log/vzdump/lxc-103.log 2017-09-05 11:50:30 INFO: status = stopped
#/var/log/vzdump/lxc-103.log 2017-09-05 11:50:31 INFO: update VM 103: -lock backup
#/var/log/vzdump/lxc-103.log 2017-09-05 11:50:31 INFO: backup mode: stop
#/var/log/vzdump/lxc-103.log 2017-09-05 11:50:31 INFO: ionice priority: 7
#/var/log/vzdump/lxc-103.log 2017-09-05 11:50:31 INFO: VM Name: server01-hlds
#/var/log/vzdump/lxc-103.log 2017-09-05 11:50:31 INFO: include disk 'sata0' 'WDC15EADS-tpool-001:vm-103-disk-2' 101G
#/var/log/vzdump/lxc-103.log 2017-09-05 11:50:33 INFO: creating archive '/vmfs/bkp-vol-001/dump/vzdump-lxc-103-2017_09_05-11_50_30.vma.gz'
#/var/log/vzdump/lxc-103.log 2017-09-05 11:50:33 INFO: starting kvm to execute backup task
#/var/log/vzdump/lxc-103.log 2017-09-05 11:50:36 INFO: started backup task 'fe948ba6-3b3a-4737-b9c2-1419864e6fe4'
#/var/log/vzdump/lxc-103.log 2017-09-05 13:02:25 INFO: transferred 108447 MB in 4309 seconds (25 MB/s)
#/var/log/vzdump/lxc-103.log 2017-09-05 13:02:25 INFO: stopping kvm after backup task
#/var/log/vzdump/lxc-103.log 2017-09-05 13:02:28 INFO: archive file size: 33.09GB
#/var/log/vzdump/lxc-103.log 2017-09-05 13:02:28 INFO: Finished Backup of VM 103 (01:11:58)
#/var/log/vzdump/lxc-104.log 2018-02-22 14:11:02 INFO: Starting Backup of VM 104 (lxc)
#/var/log/vzdump/lxc-104.log 2018-02-22 14:11:02 INFO: status = running
#/var/log/vzdump/lxc-104.log 2018-02-22 14:11:03 INFO: update VM 104: -lock backup
#/var/log/vzdump/lxc-104.log 2018-02-22 14:11:03 INFO: VM Name: zbox
#/var/log/vzdump/lxc-104.log 2018-02-22 14:11:03 INFO: exclude disk 'virtio0' 'ssd-850evo-tpool-001:vm-104-disk-1' (backup=no)
#/var/log/vzdump/lxc-104.log 2018-02-22 14:11:03 INFO: exclude disk 'virtio1' 'ST2000DM-tpool-001:vm-104-disk-4' (backup=no)
#/var/log/vzdump/lxc-104.log 2018-02-22 14:11:03 INFO: exclude disk 'virtio2' 'ST2000DM-tpool-001:vm-104-disk-1' (backup=no)
#/var/log/vzdump/lxc-104.log 2018-02-22 14:11:03 INFO: exclude disk 'virtio3' 'ST2000DM-tpool-001:vm-104-disk-2' (backup=no)
#/var/log/vzdump/lxc-104.log 2018-02-22 14:11:03 INFO: exclude disk 'virtio15' 'bkp-zbox-wss-001:104/vm-104-disk-1.raw' (backup=no)
#/var/log/vzdump/lxc-104.log 2018-02-22 14:11:03 INFO: backup mode: snapshot
#/var/log/vzdump/lxc-104.log 2018-02-22 14:11:03 INFO: ionice priority: 7
#/var/log/vzdump/lxc-104.log 2018-02-22 14:11:03 INFO: pending configuration changes found (not included into backup)
#/var/log/vzdump/lxc-104.log 2018-02-22 14:11:03 INFO: creating archive '/vmfs/bkp-vol-001/dump/vzdump-lxc-104-2018_02_22-14_11_02.vma.gz'
#/var/log/vzdump/lxc-104.log 2018-02-22 14:11:03 INFO: backup contains no disks
#/var/log/vzdump/lxc-104.log 2018-02-22 14:11:03 INFO: starting template backup
#/var/log/vzdump/lxc-104.log 2018-02-22 14:11:03 INFO: /usr/bin/vma create -v -c /vmfs/bkp-vol-001/dump/vzdump-lxc-104-2018_02_22-14_11_02.tmp/lxc-server.conf exec:gzip > /vmfs/bkp-vol-001/dump/vzdump-lxc-104-2018_02_22-14_11_02.vma.dat
#/var/log/vzdump/lxc-104.log 2018-02-22 14:11:04 INFO: archive file size: 0KB
#/var/log/vzdump/lxc-104.log 2018-02-22 14:11:04 INFO: delete old backup '/vmfs/bkp-vol-001/dump/vzdump-lxc-104-2018_02_13-14_11_02.vma.gz'
#/var/log/vzdump/lxc-104.log 2018-02-22 14:11:04 INFO: Finished Backup of VM 104 (00:00:02)
#/var/log/vzdump/lxc-105.log 2018-02-22 16:00:02 INFO: Starting Backup of VM 105 (lxc)
#/var/log/vzdump/lxc-105.log 2018-02-22 16:00:02 INFO: status = running
#/var/log/vzdump/lxc-105.log 2018-02-22 16:00:02 INFO: update VM 105: -lock backup
#/var/log/vzdump/lxc-105.log 2018-02-22 16:00:02 INFO: VM Name: urbackup01
#/var/log/vzdump/lxc-105.log 2018-02-22 16:00:02 INFO: include disk 'virtio0' 'WDC15EADS-tpool-001:vm-105-disk-1' 32G
#/var/log/vzdump/lxc-105.log 2018-02-22 16:00:02 INFO: exclude disk 'virtio1' 'bkp-urbackup01-001:105/vm-105-disk-1.qcow2' (backup=no)
#/var/log/vzdump/lxc-105.log 2018-02-22 16:00:03 INFO: backup mode: snapshot
#/var/log/vzdump/lxc-105.log 2018-02-22 16:00:03 INFO: ionice priority: 7
#/var/log/vzdump/lxc-105.log 2018-02-22 16:00:03 INFO: creating archive '/vmfs/bkp-urbackup01-001/dump/vzdump-lxc-105-2018_02_22-16_00_02.vma.gz'
#/var/log/vzdump/lxc-105.log 2018-02-22 16:00:03 INFO: started backup task '459b5abe-aa47-47f0-9bc1-144ab9cabe54'
#/var/log/vzdump/lxc-105.log 2018-02-22 16:18:47 INFO: transferred 34359 MB in 1124 seconds (30 MB/s)
#/var/log/vzdump/lxc-105.log 2018-02-22 16:18:47 INFO: archive file size: 7.03GB
#/var/log/vzdump/lxc-105.log 2018-02-22 16:18:47 INFO: delete old backup '/vmfs/bkp-urbackup01-001/dump/vzdump-lxc-105-2018_02_15-16_00_02.vma.gz'
#/var/log/vzdump/lxc-105.log 2018-02-22 16:18:47 INFO: Finished Backup of VM 105 (00:18:45)
#/var/log/vzdump/lxc-106.log 2018-02-22 14:11:04 INFO: Starting Backup of VM 106 (lxc)
#/var/log/vzdump/lxc-106.log 2018-02-22 14:11:04 INFO: status = running
#/var/log/vzdump/lxc-106.log 2018-02-22 14:11:05 INFO: update VM 106: -lock backup
#/var/log/vzdump/lxc-106.log 2018-02-22 14:11:05 INFO: VM Name: server02
#/var/log/vzdump/lxc-106.log 2018-02-22 14:11:05 INFO: include disk 'virtio0' 'ST2000DM-tpool-001:vm-106-disk-1' 32G
#/var/log/vzdump/lxc-106.log 2018-02-22 14:11:05 INFO: backup mode: snapshot
#/var/log/vzdump/lxc-106.log 2018-02-22 14:11:05 INFO: ionice priority: 7
#/var/log/vzdump/lxc-106.log 2018-02-22 14:11:05 INFO: creating archive '/vmfs/bkp-vol-001/dump/vzdump-lxc-106-2018_02_22-14_11_04.vma.gz'
#/var/log/vzdump/lxc-106.log 2018-02-22 14:11:05 INFO: started backup task '45a19f0d-dfcb-43d8-bcb2-9ce11cdecfb4'
#/var/log/vzdump/lxc-106.log 2018-02-22 14:30:31 INFO: transferred 34359 MB in 1166 seconds (29 MB/s)
#/var/log/vzdump/lxc-106.log 2018-02-22 14:30:31 INFO: archive file size: 7.53GB
#/var/log/vzdump/lxc-106.log 2018-02-22 14:30:31 INFO: delete old backup '/vmfs/bkp-vol-001/dump/vzdump-lxc-106-2018_02_13-14_11_04.vma.gz'
#/var/log/vzdump/lxc-106.log 2018-02-22 14:30:32 INFO: Finished Backup of VM 106 (00:19:28)

