# [Check MK](https://checkmk.com) Plugin to check [Proxmox](https://www.proxmox.com) VM guest (QEMU) backups

# Installation

## On the Monitoring Server where Check_mk is installed:
For a detailed description how to work with mkp's goto [https://docs.checkmk.com/latest/de/mkps.html](https://docs.checkmk.com/latest/de/mkps.html).

### Short tasks
1. copy the XXXXXX.mkp (see [dist](dist) folder) to your Check_mk server into the /tmp folder.
2. su - <SITE_NAME> (mkp has to be installed on every site you are running!)
3. mkp install /tmp/XXXXXX.mkp (replace XXXXXX with the filename downloaded)
4. Check if installation worked
```
SITEUSER@monitoring01:/opt/omd# find . -name '*proxmox_qemu_*'
./sites/XXXX/local/share/check_mk/checks/proxmox_qemu_backup
./sites/XXXX/local/share/check_mk/checkman/proxmox_qemu_backup
./sites/XXXX/local/share/check_mk/web/plugins/wato/check_parameters_proxmox_qemu_backup.py
./sites/XXXX/local/share/check_mk/agents/plugins/proxmox_qemu_backup
```
5. Goto your Check_mk webinterface. Open "Service Rules" and search for proxmox.

## On the Proxmox Server (NOT THE CHECK_MK SERVER!):
1. Copy the plugin script [check_mk/agents/plugins/proxmox_qemu_backup](check_mk/agents/plugins/proxmox_qemu_backup) into /usr/lib/check_mk_agent/plugins/
2. chmod 755 /usr/lib/check_mk_agent/plugins/proxmox_qemu_backup
3. Execute the script: /usr/lib/check_mk_agent/plugins/proxmox_qemu_backup. If everythings works the output should look like this
```
root@pve:/usr/lib/check_mk_agent/plugins# ./proxmox_qemu_backup
<<<proxmox_qemu_backup>>>
QEMU-MACHINE;;;;;/etc/pve/qemu-server/103.conf;;;;;machine1
QEMU-MACHINE;;;;;/etc/pve/qemu-server/102.conf;;;;;machine2
QEMU-MACHINE;;;;;/etc/pve/qemu-server/101.conf;;;;;machine3
QEMU-MACHINE;;;;;/etc/pve/qemu-server/105.conf;;;;;machine4
QEMU-MACHINE;;;;;/etc/pve/qemu-server/104.conf;;;;;machine5
/var/log/vzdump/qemu-100.log Jul 12 12:00:01 INFO: Starting Backup of VM 100 (qemu)
/var/log/vzdump/qemu-100.log Jul 12 12:00:01 INFO: status = running
/var/log/vzdump/qemu-100.log Jul 12 12:00:02 INFO: update VM 100: -lock backup
/var/log/vzdump/qemu-100.log Jul 12 12:00:02 INFO: VM Name: machine1
/var/log/vzdump/qemu-100.log Jul 12 12:00:02 INFO: backup mode: snapshot
/var/log/vzdump/qemu-100.log Jul 12 12:00:02 INFO: ionice priority: 7
/var/log/vzdump/qemu-100.log Jul 12 12:00:02 INFO: creating archive '/vmfs/bkp-fs-stor-001/dump/vzdump-qemu-100-2017_07_12-12_00_01.vma.gz'
/var/log/vzdump/qemu-100.log Jul 12 12:00:02 INFO: started backup task '0a8d0864-ffd8-497c-83ae-5422162ca8cd'
/var/log/vzdump/qemu-100.log Jul 12 12:30:31 INFO: transferred 16106 MB in 1829 seconds (8 MB/s)
/var/log/vzdump/qemu-100.log Jul 12 12:30:31 INFO: archive file size: 594MB
/var/log/vzdump/qemu-100.log Jul 12 12:30:31 INFO: delete old backup '/vmfs/bkp-fs-stor-001/dump/vzdump-qemu-100-2017_07_07-12_00_01.vma.gz'
/var/log/vzdump/qemu-100.log Jul 12 12:30:31 INFO: Finished Backup of VM 100 (00:30:30)
/var/log/vzdump/qemu-101.log 2018-02-23 07:40:02 INFO: Starting Backup of VM 101 (qemu)
/var/log/vzdump/qemu-101.log 2018-02-23 07:40:02 INFO: status = running
/var/log/vzdump/qemu-101.log 2018-02-23 07:40:02 INFO: update VM 101: -lock backup
...
...
...
```

## Functions of the plugin
![](https://github.com/edvler/check_mk_proxmox-qemu-backup/blob/master/docs/proxmox_qemu_backup_man-page.png)

## Services screenshot
![](https://github.com/edvler/check_mk_proxmox-qemu-backup/blob/master/docs/example-services-screenshot.png)


