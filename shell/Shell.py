import os
import logging

import dbus
import dbus.glib
import gtk
import gobject
import wnck

from home.HomeWindow import HomeWindow
from home.HomeModel import HomeModel
from sugar import env
from Owner import ShellOwner
from sugar.presence import PresenceService
from ActivityHost import ActivityHost
from ChatController import ChatController
from sugar.activity import ActivityFactory
from sugar.activity import Activity
from FirstTimeDialog import FirstTimeDialog
from panel.PanelManager import PanelManager
from globalkeys import KeyGrabber
import sugar
from sugar import conf
import sugar.logger

class ShellDbusService(dbus.service.Object):
	def __init__(self, shell, bus_name):
		dbus.service.Object.__init__(self, bus_name, '/com/redhat/Sugar/Shell')
		self._shell = shell

	def __show_console_idle(self):
		self._shell.show_console()

	@dbus.service.method('com.redhat.Sugar.Shell')
	def show_console(self):
		gobject.idle_add(self.__show_console_idle)

class Shell(gobject.GObject):
	__gsignals__ = {
		'activity-opened':  (gobject.SIGNAL_RUN_FIRST,
							 gobject.TYPE_NONE, ([gobject.TYPE_PYOBJECT])),
		'activity-changed': (gobject.SIGNAL_RUN_FIRST,
							 gobject.TYPE_NONE, ([gobject.TYPE_PYOBJECT])),
		'activity-closed':  (gobject.SIGNAL_RUN_FIRST,
							 gobject.TYPE_NONE, ([gobject.TYPE_PYOBJECT]))
	}

	def __init__(self):
		gobject.GObject.__init__(self)

		self._screen = wnck.screen_get_default()
		self._hosts = {}
		self._current_window = None

		self._key_grabber = KeyGrabber()
		self._key_grabber.connect('key-pressed', self.__global_key_pressed_cb)
		self._key_grabber.grab('F1')
		self._key_grabber.grab('F2')
		self._key_grabber.grab('F3')
		self._key_grabber.grab('F4')
		self._key_grabber.grab('F5')

		self._home_window = HomeWindow(self)
		self._home_window.show()

		self._screen.connect('window-opened', self.__window_opened_cb)
		self._screen.connect('window-closed', self.__window_closed_cb)
		self._screen.connect('active-window-changed',
							 self.__active_window_changed_cb)
		self._screen.connect("showing_desktop_changed",
							 self.__showing_desktop_changed_cb)

		profile = conf.get_profile()
		if profile.get_nick_name() == None:
			dialog = FirstTimeDialog()
			dialog.connect('destroy', self.__first_time_dialog_destroy_cb)
			dialog.set_transient_for(self._home_window)
			dialog.show()
		else:
			self.start()

	def __global_key_pressed_cb(self, grabber, key):
		if key == 'F1':
			self.set_zoom_level(sugar.ZOOM_ACTIVITY)
		elif key == 'F2':
			self.set_zoom_level(sugar.ZOOM_HOME)
		elif key == 'F3':
			self.set_zoom_level(sugar.ZOOM_FRIENDS)
		elif key == 'F4':
			self.set_zoom_level(sugar.ZOOM_MESH)
		elif key == 'F5':
			self._panel_manager.toggle_visibility()

	def __first_time_dialog_destroy_cb(self, dialog):
		conf.get_profile().save()
		self.start()

	def start(self):
		session_bus = dbus.SessionBus()
		bus_name = dbus.service.BusName('com.redhat.Sugar.Shell', bus=session_bus)
		ShellDbusService(self, bus_name)

		PresenceService.start()

		self._owner = ShellOwner()
		self._owner.announce()

		self._chat_controller = ChatController(self)
		self._chat_controller.listen()

		home_model = HomeModel()
		self._home_window.set_model(home_model)
		self.set_zoom_level(sugar.ZOOM_HOME)

		self._panel_manager = PanelManager(self)
		self._panel_manager.show()

	def get_panel_manager(self):
		return self._panel_manager

	def set_console(self, console):
		self._console = console

	def __showing_desktop_changed_cb(self, screen):
		if not screen.get_showing_desktop():
			self._zoom_level = sugar.ZOOM_ACTIVITY

	def __window_opened_cb(self, screen, window):
		if window.get_window_type() == wnck.WINDOW_NORMAL:
			host = ActivityHost(self, window)
			self._hosts[window.get_xid()] = host
			self.emit('activity-opened', host)

	def __active_window_changed_cb(self, screen):
		window = screen.get_active_window()
		if window and window.get_window_type() == wnck.WINDOW_NORMAL:
			if self._current_window != window:
				self._current_window = window
				self.emit('activity-changed', self.get_current_activity())

	def __window_closed_cb(self, screen, window):
		if window.get_window_type() == wnck.WINDOW_NORMAL:
			xid = window.get_xid()
			if self._hosts.has_key(xid):
				host = self._hosts[xid]
				self.emit('activity-closed', host)

				del self._hosts[xid]

	def get_activity(self, activity_id):
		for host in self._hosts.values():
			if host.get_id() == activity_id:
				return host
		return None

	def get_current_activity(self):
		if self._current_window != None:
			xid = self._current_window.get_xid()
			return self._hosts[xid]
		else:
			return None

	def show_console(self):
		self._console.show()

		activity = self.get_current_activity()
		if activity:
			registry = conf.get_activity_registry()
			module = registry.get_activity(activity.get_default_type())
			self._console.set_page(module.get_id())

	def join_activity(self, service):
		registry = conf.get_activity_registry()
		info = registry.get_activity(service.get_type())
		
		activity_id = service.get_activity_id()

		activity = self.get_activity(activity_id)
		if activity:
			activity.present()
		else:
			pservice = PresenceService.get_instance()
			activity_ps = pservice.get_activity(activity_id)

			if activity_ps:
				activity = ActivityFactory.create(info.get_id())
				activity.set_default_type(service.get_type())
				activity.join(activity_ps.object_path())
			else:
				logging.error('Cannot start activity.')

	def start_activity(self, activity_name):
		activity = ActivityFactory.create(activity_name)
		registry = conf.get_activity_registry()
		info = registry.get_activity_from_id(activity_name)
		if info:
			default_type = info.get_default_type()
			if default_type != None:
				activity.set_default_type(default_type)
				activity.execute('test', [])
			return activity
		else:
			logging.error('No such activity in the directory')
			return None

	def get_chat_controller(self):
		return self._chat_controller

	def set_zoom_level(self, level):
		self._zoom_level = level

		if level == sugar.ZOOM_ACTIVITY:
			self._screen.toggle_showing_desktop(False)
		else:
			self._screen.toggle_showing_desktop(True)

		if level == sugar.ZOOM_HOME:
			self._home_window.set_view(HomeWindow.HOME_VIEW)
		elif level == sugar.ZOOM_FRIENDS:
			self._home_window.set_view(HomeWindow.FRIENDS_VIEW)
		elif level == sugar.ZOOM_MESH:
			self._home_window.set_view(HomeWindow.MESH_VIEW)
