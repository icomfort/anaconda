#
# Select which disks to clear and which ones to just mount.
#
# Copyright (C) 2009  Red Hat, Inc.
# All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import gtk, gobject
import gui
from DeviceSelector import *
from constants import *
import isys
from iw_gui import *
from storage.udev import *

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

class ClearDisksWindow (InstallWindow):
    windowTitle = N_("Clear Disks Selector")

    def getNext (self):
        # All the rows that are visible in the right hand side should be cleared.
        cleardisks = []
        for row in self.store:
            if row[self.rightVisible]:
                cleardisks.append(row[OBJECT_COL].name)

        if len(cleardisks) == 0:
            self.anaconda.intf.messageWindow(_("Error"),
                                             _("You must select at least one "
                                               "drive to be used for installation."),
                                             custom_icon="error")
            raise gui.StayOnScreen

        # The selected row is the disk to boot from.
        selected = self.rightDS.getSelected()

        if len(selected) == 0:
            self.anaconda.intf.messageWindow(_("Error"),
                                             _("You must select one drive to "
                                               "boot from."),
                                             custom_icon="error")
            raise gui.StayOnScreen

        bootDisk = selected[0][OBJECT_COL].name

        cleardisks.sort(isys.compareDrives)

        self.anaconda.id.storage.clearPartDisks.extend(cleardisks + [bootDisk])
        self.anaconda.id.bootloader.drivelist = [bootDisk] + cleardisks

    def getScreen (self, anaconda):
        (xml, self.vbox) = gui.getGladeWidget("cleardisks.glade", "vbox")
        self.leftScroll = xml.get_widget("leftScroll")
        self.rightScroll = xml.get_widget("rightScroll")
        self.addButton = xml.get_widget("addButton")
        self.removeButton = xml.get_widget("removeButton")
        self.installTargetImage = xml.get_widget("installTargetImage")
        self.installTargetTip = xml.get_widget("installTargetTip")

        self.anaconda = anaconda

        self.leftVisible = 1
        self.leftActive = 2
        self.rightVisible = 3
        self.rightActive = 4

        # One store for both views.  First the obejct, then a visible/active for
        # the left hand side, then a visible/active for the right hand side, then
        # all the other stuff.
        self.store = gtk.TreeStore(gobject.TYPE_PYOBJECT,
                                   gobject.TYPE_BOOLEAN, gobject.TYPE_BOOLEAN,
                                   gobject.TYPE_BOOLEAN, gobject.TYPE_BOOLEAN,
                                   gobject.TYPE_STRING, gobject.TYPE_STRING,
                                   gobject.TYPE_STRING, gobject.TYPE_STRING,
                                   gobject.TYPE_STRING)
        self.store.set_sort_column_id(5, gtk.SORT_ASCENDING)

        # The left view shows all the drives that will just be mounted, but
        # can still be moved to the right hand side.
        self.leftSortedModel = gtk.TreeModelSort(self.store)
        self.leftFilteredModel = self.store.filter_new()
        self.leftTreeView = gtk.TreeView(self.leftFilteredModel)

        self.leftFilteredModel.set_visible_func(lambda model, iter, view: model.get_value(iter, self.leftVisible), self.leftTreeView)

        self.leftScroll.add(self.leftTreeView)

        self.leftDS = DeviceSelector(self.store, self.leftFilteredModel,
                                     self.leftTreeView, visible=self.leftVisible,
                                     active=self.leftActive)
        self.leftDS.createMenu()
        self.leftDS.addColumn(_("Model"), 5)
        self.leftDS.addColumn(_("Capacity"), 6)
        self.leftDS.addColumn(_("Vendor"), 7)
        self.leftDS.addColumn(_("Interconnect"), 8, displayed=False)
        self.leftDS.addColumn(_("Serial Number"), 9, displayed=False)

        # The right view show all the drives that will be wiped during install.
        self.rightSortedModel = gtk.TreeModelSort(self.store)
        self.rightFilteredModel = self.store.filter_new()
        self.rightTreeView = gtk.TreeView(self.rightFilteredModel)

        self.rightFilteredModel.set_visible_func(lambda model, iter, view: model.get_value(iter, self.rightVisible), self.rightTreeView)

        self.rightScroll.add(self.rightTreeView)

        self.rightDS = DeviceSelector(self.store, self.rightFilteredModel,
                                      self.rightTreeView, visible=self.rightVisible,
                                      active=self.rightActive)
        self.rightDS.createSelectionCol(title=_("Boot"), radioButton=True)
        self.rightDS.addColumn(_("Model"), 5)
        self.rightDS.addColumn(_("Capacity"), 6)

        # The device filtering UI set up exclusiveDisks as a list of the names
        # of all the disks we should use later on.  Now we need to go get those,
        # look up some more information in the devicetree, and set up the
        # selector.
        for d in self.anaconda.id.storage.exclusiveDisks:
            device = self.anaconda.id.storage.devicetree.getDeviceByName(d)
            if not device:
                continue

            self.store.append(None, (device, True, True, False, False,
                                     device.partedDevice.model,
                                     str(int(device.size)) + " MB",
                                     device.vendor, "", device.serial))

        self.addButton.connect("clicked", self._add_clicked)
        self.removeButton.connect("clicked", self._remove_clicked)

        if self.anaconda.id.storage.clearPartType == CLEARPART_TYPE_LINUX:
            self.installTargetTip.set_markup(_("<b>Tip:</b> All Linux filesystems on install target devices will be reformatted and wiped of any data.  Make sure you have backups."))
        elif self.anaconda.id.storage.clearPartType == CLEARPART_TYPE_ALL:
            self.installTargetTip.set_markup(_("<b>Tip:</b> Install target devices will be reformatted and wiped of any data.  Make sure you have backups."))
        else:
            self.installTargetTip.set_markup(_("<b>Tip:</b> Your filesystems on install target devices will not be wiped unless you choose to do so during customization."))

        return self.vbox

    def _add_clicked(self, button):
        (filteredModel, filteredIter) = self.leftTreeView.get_selection().get_selected()

        if not filteredIter:
            return

        # If this is the first row going into the rightDS, it should be checked
        # by default.
        if self.rightDS.getNVisible() == 0:
            active = True
        else:
            active = False

        sortedIter = self.leftFilteredModel.convert_iter_to_child_iter(filteredIter)

        self.store.set_value(sortedIter, self.leftVisible, False)
        self.store.set_value(sortedIter, self.rightVisible, True)
        self.store.set_value(sortedIter, self.rightActive, active)

        self.leftFilteredModel.refilter()
        self.rightFilteredModel.refilter()

    def _remove_clicked(self, button):
        (filteredModel, filteredIter) = self.rightTreeView.get_selection().get_selected()

        if not filteredIter:
            return

        sortedIter = self.rightFilteredModel.convert_iter_to_child_iter(filteredIter)

        # If we're removing a row that was checked and there are other rows
        # available, check the first visible one.
        if self.store.get_value(sortedIter, self.rightActive) and self.rightDS.getNVisible() > 1:
            i = 0

            # Make sure to skip the current row, of course.
            while not self.store[i][self.rightVisible] or self.store[i][0] == self.store[sortedIter][0]:
                i += 1

            self.store[i][self.rightActive] = True

        self.store.set_value(sortedIter, self.leftVisible, True)
        self.store.set_value(sortedIter, self.rightVisible, False)
        self.store.set_value(sortedIter, self.rightActive, False)

        self.leftFilteredModel.refilter()
        self.rightFilteredModel.refilter()