#!/usr/bin/env python

import os
import time
import sys
import glob
import shlex
import subprocess
from optparse import OptionParser
import ConfigParser
from os.path import join
from multiprocessing import Pool
from commands import getstatusoutput

_RBDIR  = "/opt/rdiff-backup"
_CONFIG = "/etc/multiprocessing-rdiff-backup.conf"
_LOCKFILE="/tmp/multiprocessing-rdiff-backup.running"

def backup(host):
  
  logFile = "/var/log/rdiff-backup/%s-%s.log" % (
    host['host'], 
    time.strftime("%d-%m-%Y", time.localtime())
  )
  
  args = []
  args.append("%s/rdiff-backup-%s/bin/rdiff-backup" % (_RBDIR, host['version']))
  args.extend(shlex.split(host['args']))
  args.append(host['source'])
  args.append(join(host['destination'], host['host']))
 
  env = []
  for l in ["lib", "lib64"]:
    env.append("%s/rdiff-backup-%s/%s/python%s.%s/site-packages" % (
      _RBDIR, host['version'], l, sys.version_info[0], sys.version_info[1]))

  proc = subprocess.Popen(
    args,
    env={"PYTHONPATH": ":".join(env)}, 
    stdout=subprocess.PIPE, 
    stderr=subprocess.PIPE, 
    close_fds=True)

  status = os.waitpid(proc.pid,0)[1]
  output = proc.stdout.read()
  if status: output += proc.stderr.read()

  if not status:
    start_time = time.time()
    args = []
    args.append("%s/rdiff-backup-%s/bin/rdiff-backup" % (_RBDIR, host['version']))
    args.extend(["--remove-older-than", host['retention'], "--force", join(host['destination'], host['host'])])

    proc = subprocess.Popen(
      args, 
      env={"PYTHONPATH": ":".join(env)},
      stdout=subprocess.PIPE, 
      stderr=subprocess.PIPE,
      close_fds=True)  
    
    status = os.waitpid(proc.pid,0)[1]
    elapsed_time = time.strftime("%H:%M:%S", time.gmtime(time.time()-start_time))
    output += proc.stdout.read()
    output += "DeletingIncrementsElapsedTime: %s\n\n" % elapsed_time
    if status: output += proc.stderr.read()

  # writes a logfile with rdiff-backup stdin and stderr
  flog = open(logFile, 'w')
  flog.write(output)
  flog.write("RDIFF-BACKUP-EXIT-STATUS=%s\n" % status) 
  flog.close()

def getBackupList(pool_dests, dest="",):
  backups = []
  backupList = glob.glob('/etc/rdiff-backup.d/*.conf')
  for backup in backupList:
    config = ConfigParser.ConfigParser()
    config.read(backup)
    if config.get('hostconfig', 'destination') in pool_dests:
      backups.append(dict(config.items('hostconfig')))
    else:
      print "Bypass host %s cause it doesn't match an existing pool destination_dir!" % config.get('hostconfig', 'host')

  if dest:
    return filter(lambda x:x['enable'].lower() == "true" and x['destination'] == dest, backups)
  else:
    return filter(lambda x:x['enable'].lower() == "true", backups)

def addlock():
  if os.path.exists(_LOCKFILE):
    print "multiprocessing-rdiff-backup --all is already running!\n"
    sys.exit(1)
  else:
    f = open(_LOCKFILE,'w')
    f.write("multiprocessing-rdiff-backup session is running!\n")
    f.close()

def dellock():
  if os.path.exists(_LOCKFILE):
    os.remove(_LOCKFILE)

def readPoolConfig():
  pools = {}
  if not os.path.exists(_CONFIG):
    print "Main configuration %s not found!" % mainConfig
    sys.exit(1)
  config = ConfigParser.ConfigParser()
  config.read(_CONFIG)
  for section in config.sections():
    pools[section] = dict(config.items(section))
  return pools

if __name__=="__main__":

  # only root can run this script
  if os.getuid():
    print "not root!"
    sys.exit(1)

  options = OptionParser(version="1.0")
  options.add_option("--host", dest="host", help="launch backup for <host> only")
  options.add_option("--all", action="store_true", help="launch backup for all hosts")
  (opt, args) = options.parse_args()

  if not (opt.host or opt.all):
    options.print_help()
    sys.exit(1)

  pool_config = readPoolConfig()
  pool_destination_dirs = [ y['destination_dir'] for x,y in pool_config.items() ]

  if opt.host:
    backups = getBackupList(pool_dests=pool_destination_dirs)
    backups = filter(lambda x: x['host'] == opt.host, backups)
    if not backups:
      options.error("Host %s not found!" % opt.host)

    pool = Pool(processes=1)
    pool.map(backup, backups)

  else:
    addlock()
    pools = []
    for key, value in pool_config.items():
      backups = getBackupList(pool_destination_dirs, pool_config[key]['destination_dir'])
      pool = Pool(processes=int(value['max_process']))
      pool.imap_unordered(backup, backups)
      pool.close()
      pools.append(pool)
        
    [p.join() for p in pools]

  if opt.all:
    dellock()
