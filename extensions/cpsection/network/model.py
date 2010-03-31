# Copyright (C) 2008 One Laptop Per Child
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
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#

import logging
import dbus
from gettext import gettext as _
from jarabe.model import network
import gconf
import os

_logger = logging.getLogger('ControlPanel - Network')

_NM_SERVICE = 'org.freedesktop.NetworkManager'
_NM_PATH = '/org/freedesktop/NetworkManager'
_NM_IFACE = 'org.freedesktop.NetworkManager'

KEYWORDS = ['network', 'jabber', 'radio', 'server']

class ReadError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

def get_jabber():
    client = gconf.client_get_default()
    return client.get_string('/desktop/sugar/collaboration/jabber_server')

def print_jabber():
    print get_jabber()

def set_jabber(server):
    """Set the jabber server
    server : e.g. 'olpc.collabora.co.uk'
    """
    client = gconf.client_get_default()
    client.set_string('/desktop/sugar/collaboration/jabber_server', server)

    _restart_jabber()
    return 0

def _restart_jabber():
    """Call Sugar Presence Service to restart Telepathy CMs.

    This allows restarting the jabber server connection when we change it.
    """
    _PS_SERVICE = "org.laptop.Sugar.Presence"
    _PS_INTERFACE = "org.laptop.Sugar.Presence"
    _PS_PATH = "/org/laptop/Sugar/Presence"
    bus = dbus.SessionBus()
    try:
        ps = dbus.Interface(bus.get_object(_PS_SERVICE, _PS_PATH), 
                            _PS_INTERFACE)
    except dbus.DBusException:
        raise ReadError('%s service not available' % _PS_SERVICE)
    ps.RestartServerConnection()

def print_radio():
    print ('off', 'on')[get_radio()]
    
def get_radio_nm():
    bus = dbus.SystemBus()
    try:
        obj = bus.get_object(_NM_SERVICE, _NM_PATH)
        nm_props = dbus.Interface(obj, dbus.PROPERTIES_IFACE)
    except dbus.DBusException:
        raise ReadError('%s service not available' % _NM_SERVICE)

    state = nm_props.Get(_NM_IFACE, 'WirelessEnabled')
    if state in (0, 1):
        return state
    else:
        raise ReadError(_('State is unknown.'))


# set_radio_nm/get_radio_nm aren't currently used, but it's
# rumored that in NM 0.8, NM will be able to adjust the
# rfkill state itself.  if it does, and restores it at boot
# time, we can go back to using NM.  leaving this code for now.
def set_radio_nm(state):
    """Turn Radio 'on' or 'off'
    state : 'on/off'
    """    
    if state == 'on' or state == 1:
        bus = dbus.SystemBus()
        try:
            obj = bus.get_object(_NM_SERVICE, _NM_PATH)
            nm_props = dbus.Interface(obj, dbus.PROPERTIES_IFACE)
        except dbus.DBusException:
            raise ReadError('%s service not available' % _NM_SERVICE)
        nm_props.Set(_NM_IFACE, 'WirelessEnabled', True)
    elif state == 'off' or state == 0:
        bus = dbus.SystemBus()
        try:
            obj = bus.get_object(_NM_SERVICE, _NM_PATH)
            nm_props = dbus.Interface(obj, dbus.PROPERTIES_IFACE)
        except dbus.DBusException:
            raise ReadError('%s service not available' % _NM_SERVICE)
        nm_props.Set(_NM_IFACE, 'WirelessEnabled', False)
    else:
        raise ValueError(_("Error in specified radio argument use on/off."))

    return 0

def get_radio_rfkill():
    pipe_stdout = os.popen('/sbin/rfkill list wifi', 'r')
    try:
        output = pipe_stdout.read()
        _logger.debug('rfkill said: %s' % output)
        blocked = " blocked: yes" in output
        # if not soft- or hard-blocked, radio is on
        return not blocked

    finally:
        pipe_stdout.close()

RFKILL_STATE_FILE = '/home/olpc/.rfkill_block_wifi'

def set_radio_rfkill(state):
    """Turn Radio 'on' or 'off'
    state : 'on/off'
    """    
    if state == 'on' or state == 1:
        os.spawnl(os.P_WAIT, "/sbin/rfkill", "rfkill", "unblock", "wifi")
        # remove the flag file (checked at boot)
        try:
            os.unlink(RFKILL_STATE_FILE)
        except:
            _logger.debug('File %s was not unlinked' % RFKILL_STATE_FILE)
    elif state == 'off' or state == 0:
        os.spawnl(os.P_WAIT, "/sbin/rfkill", "rfkill", "block", "wifi")
        # touch the flag file
        try:
            fd = open(RFKILL_STATE_FILE, 'w')
        except IOError:
            _logger.debug('File %s is not writeable' % RFKILL_STATE_FILE)
        else:
            fd.close()
    else:
        raise ValueError(_("Error in specified radio argument use on/off."))

    return 0

# get current status from rfkill
def get_radio():
    return get_radio_rfkill()

# set new status to both the dot-file and rfkill
def set_radio(state):
    set_radio_rfkill(state)

def clear_registration():
    """Clear the registration with the schoolserver
    """
    client = gconf.client_get_default()
    client.set_string('/desktop/sugar/backup_url', '')
    return 1

def clear_networks():
    """Clear saved passwords and network configurations.
    """
    network.clear_connections()

def count_networks():
    return network.count_connections()

def get_publish_information():
    client = gconf.client_get_default()
    publish = client.get_bool('/desktop/sugar/collaboration/publish_gadget')
    return publish

def print_publish_information():
    print get_publish_information()

def set_publish_information(value):
    """ If set to true, Sugar will make you searchable for 
    the other users of the Jabber server.
    value: 0/1
    """
    try:
        value = (False, True)[int(value)]
    except:
        raise ValueError(_("Error in specified argument use 0/1."))

    client = gconf.client_get_default()
    client.set_bool('/desktop/sugar/collaboration/publish_gadget', value)
    return 0
