#!/bin/sh
#
# Simple script to kick off an install from a live CD
#

if [ -z "$LIVE_MOUNT_PATH" ]; then
    LIVE_MOUNT_PATH="/mnt/livecd"
fi

if [ ! -f /.livecd-configured ]; then
  zenity --error --title="Not a Live image" --text "Can't do live image installation unless running from a live image"
fi

# load modules that would get loaded by the loader... (#230945)
for i in md raid0 raid1 raid5 raid6 raid456 raid10 fat msdos lock_nolock gfs2 reiserfs jfs xfs dm-mod dm-zero dm-mirror dm-snapshot dm-multipath dm-round-robin dm-emc vfat ; do /sbin/modprobe $i ; done

export ANACONDA_PRODUCTNAME="Fedora"
export ANACONDA_PRODUCTVERSION=$(rpm -q fedora-release --qf "%{VERSION}")
export ANACONDA_BUGURL="https://bugzilla.redhat.com/bugzilla/"

export PATH=/sbin:/usr/sbin:$PATH

if [ -z "$LANG" ]; then 
  LANG="en_US.UTF-8"
fi

# eventually, we might want to allow a more "normal" install path
ANACONDA="/usr/sbin/anaconda --method=livecd://$LIVE_MOUNT_PATH --lang $LANG"

if [ -x /usr/bin/hal-lock ]; then
    /usr/bin/hal-lock --interface org.freedesktop.Hal.Device.Storage --exclusive --run "$ANACONDA"
else
    $ANACONDA
fi