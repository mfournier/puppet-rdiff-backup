class rdiff-backup::server {

  include buildenv::c
  include python::dev

  file {"/opt/rdiff-backup":
    ensure => directory,
  }
  
  file {"/etc/rdiff-backup.d":
    ensure  => directory,
    owner   => root,
    group   => root,
    recurse => true,
    purge   => true,
    force   => true,
  }

  if defined (Package["curl"]) {
    notice "package curl is already defined"
  } else {
    package {"curl":
      ensure => present,
    }
  }

  case $operatingsystem {
    Debian: {
      package {
        "librsync-dev":  ensure => present, alias => "librsync-devel";
      }
      case $lsbdistcodename {
        'squeeze': { $python_version = '2.6' }
        'lenny':   { $python_version = '2.5' }
        default:   { fail "No python version defined for $lsbdistcodename" }
      }
    }
    RedHat: {
      package {
        "librsync-devel": ensure => present, alias => "librsync-devel";
      }
      $python_version = '2.5'
    }
  }

  tidy {"/var/log/rdiff-backup/":
    matches => "*.log",
    recurse => true,
    age     => $rdiff_backup_log_age? {
      "" => '15d',
      default => $rdiff_backup_log_age,
    }
  }

  if ($rdiff_backup_backupdir) {
    $backupdir = $rdiff_backup_backupdir
  } else {
    $backupdir = "/srv/rdiff-backup"
  }

  file {$backupdir:
    ensure => directory,
  }

  file {"/var/log/rdiff-backup":
    ensure => directory,
  }

  file {"/etc/multiprocessing-rdiff-backup.conf":
    ensure => present,
    owner => root,
    group => root,
    content => template("rdiff-backup/mainconfig.erb"),
  }

  file {"/usr/local/sbin/multiprocessing-rdiff-backup.py":
    source => "puppet:///rdiff-backup/usr/local/sbin/multiprocessing-rdiff-backup.py",
    ensure  => present,
    owner   => root,
    group   => root,
    mode    => 755,
    content => template("rdiff-backup/multithreaded-rdiff-backup.py.erb"),
  }
  
  # cron to start multi-thread script
  cron {"start multiprocessing backup script":
    ensure  => present,
    command => "/usr/bin/python /usr/local/sbin/multiprocessing-rdiff-backup.py --all",
    minute  => "0",
    hour    => "1",
    user    => "root",
    require => File["/usr/local/sbin/multiprocessing-rdiff-backup.py"],
  }

}
