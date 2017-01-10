"""
Created on May 6, 2012

@author: Daniel Marohn
"""

from gi.repository import Gtk

import terminatorlib.plugin as plugin
from terminatorlib.util import dbg, err
from terminatorlib.config import Config
import uuid
from os import path

EXPORTER_NAME = 'TerminalExporter'

SETTING_DIR = 'directory'
SETTING_EXPORT_FILE = 'exportNameToFile'
SETTING_EXPORT_ENV = 'exportNameToEnv'
SETTING_CONSOLE_ALIAS = 'consoleAlias'
SETTING_CONSOLE_LOGFILE_VARIABLE = 'consoleLogfileVariable'
SETTING_MENU_MAIN = 'mainMenuText'
SETTING_MENU_EXPORT = 'exportMenuText'
SETTING_MENU_STOP_LOG = 'stopLogMenuText'
SETTING_MENU_START_LOG = 'logMenuText'
SETTING_MENU_EXPORT_LOG = 'exportLogMenuText'
SETTING_MENU_CONSOLE = 'showConsole'

DEFAULT_SETTINGS = {SETTING_DIR: '/tmp',
                    SETTING_EXPORT_FILE: '/tmp/.terminatorExports',
                    SETTING_EXPORT_ENV: '',
                    SETTING_MENU_MAIN: EXPORTER_NAME,
                    SETTING_MENU_EXPORT: 'export terminal',
                    SETTING_MENU_STOP_LOG: 'stop log',
                    SETTING_MENU_START_LOG: 'log terminal',
                    SETTING_MENU_EXPORT_LOG: 'export and log terminal',
                    SETTING_MENU_CONSOLE: 'show console',
                    SETTING_CONSOLE_ALIAS: ['tgrep="cat %s | grep"',
                                            'ttail="tail %s"',
                                            'tless="less %s"'],
                    SETTING_CONSOLE_LOGFILE_VARIABLE: 'TERMINAL_LOGFILE',
                    }


AVAILABLE = [EXPORTER_NAME, ]
# older versions of terminator require available instead of AVAILABLE
available = AVAILABLE


def parse_plugin_config(config):
    """merge the default settings with settings from terminator's config"""
    ret = DEFAULT_SETTINGS
    plugin_config = config.plugin_get_config(EXPORTER_NAME)
    if plugin_config:
        for current_key in ret.keys():
            if current_key in plugin_config:
                ret[current_key] = plugin_config[current_key]
        for current_key in plugin_config:
            if current_key not in ret:
                err('invalid config parameter: %s' % current_key)
    return ret


class LogParameter:
    """Container class, holding information about a logged terminal"""

    def __init__(self, watcher, filename, last_logged_line=-1):
        """
        @param watcher: the gtk object, returned by vte.connect
        @param filename: terminal output is logged into this file
        @param last_logged_line: number of last line number that was written to file
        """
        self.watcher = watcher
        self.last_logged_line = last_logged_line
        self.filename = filename


class TerminalExporter(plugin.MenuItem):
    """
    plugin that allows to export full terminal content into file,
    and provides a logging function for a terminal.
    """

    capabilities = ['terminal_menu']

    def __init__(self):
        super(TerminalExporter, self).__init__()
        self.config = Config()
        self.plugin_config = parse_plugin_config(self.config)
        self.logging_terminals = {}
        self.scrollback_lines = self.config['scrollback_lines']
        dbg('using config: %s' % self.plugin_config)

    def callback(self, menuitems, menu, terminal):
        """called by terminator on context menu open"""
        item = Gtk.MenuItem(self.plugin_config[SETTING_MENU_MAIN])
        submenu = Gtk.Menu()
        export_item = Gtk.MenuItem(self.plugin_config[SETTING_MENU_EXPORT])
        export_item.connect('activate', self.do_export, terminal)
        submenu.append(export_item)
        if terminal in self.logging_terminals:
            log_item = Gtk.MenuItem(self.plugin_config[SETTING_MENU_STOP_LOG])
            log_item.connect('activate', self.do_stop_log, terminal)
            submenu.append(log_item)
        else:
            log_item = Gtk.MenuItem(self.plugin_config[SETTING_MENU_START_LOG])
            log_item.connect('activate', self.do_log, terminal)
            submenu.append(log_item)
            log_item = Gtk.MenuItem(self.plugin_config[SETTING_MENU_EXPORT_LOG])
            log_item.connect('activate', self.do_export_log, terminal)
            submenu.append(log_item)
        console_item = Gtk.MenuItem(self.plugin_config[SETTING_MENU_CONSOLE])
        console_item.connect('activate', self.do_console, terminal)
        submenu.append(console_item)
        item.set_submenu(submenu)
        menuitems.append(item)

    def do_export_log(self, widget, terminal):
        filename = self.do_export(widget, terminal)
        self.do_log(widget, terminal, filename)
        return filename

    def do_export(self, _, terminal):
        """
        Export complete terminal content into file.
        """
        vte = terminal.get_vte()
        (start_row, end_row, end_column) = self.get_vte_buffer_range(vte)
        content = vte.get_text_range(start_row, 0, end_row, end_column,
                                     lambda widget, col, row, junk: True)
        filename = self.get_filename()
        with open(filename, "w") as output_file:
            output_file.writelines(str(content))
            output_file.close()
        dbg('terminal content written to [%s]' % filename)
        if self.plugin_config[SETTING_EXPORT_ENV] != '':
            terminal.feed('%s="%s"\n' % (self.plugin_config[SETTING_EXPORT_ENV], filename))
        return filename

    def do_log(self, _, terminal, filename=None):
        if filename is None:
            filename = self.get_filename()
        vte = terminal.get_vte()
        (start_row, end_row, end_column) = self.get_vte_buffer_range(vte)
        watcher = vte.connect('contents-changed', self.log_notify, terminal)
        parameter = LogParameter(watcher, filename, end_row)
        self.logging_terminals[terminal] = parameter

    def do_stop_log(self, _, terminal):
        vte = terminal.get_vte()
        vte.disconnect(self.logging_terminals.pop(terminal).watcher)

    def do_console(self, widget, terminal):
        if terminal in self.logging_terminals:
            filename = self.logging_terminals[terminal].filename
        else:
            filename = self.do_export_log(widget, terminal)
        terminal.get_parent().split_axis(terminal, True)
        new_terminal = terminal.get_parent().get_children()[1]
        new_terminal.titlebar.set_custom_string(EXPORTER_NAME)
        for alias in self.plugin_config[SETTING_CONSOLE_ALIAS]:
            new_terminal.feed('alias %s\n' % alias % filename)
        variable_name = self.plugin_config[SETTING_CONSOLE_LOGFILE_VARIABLE]
        if variable_name:
            new_terminal.feed('export %s=%s\n' % (variable_name, filename))

    def log_notify(self, _, terminal):
        vte = terminal.get_vte()
        (start_row, end_row, end_column) = self.get_vte_buffer_range(vte)
        parameter = self.logging_terminals[terminal]
        if end_row > parameter.last_logged_line:
            content = vte.get_text_range(parameter.last_logged_line, 0, end_row, end_column,
                                         lambda widget, col, row, junk: True)
            with open(parameter.filename, "a") as output_file:
                output_file.writelines(content)
                output_file.close()
            parameter.last_logged_line = end_row

    def get_vte_buffer_range(self, vte):
        """
        Get the range of a vte widget.
        """
        end_column, end_row = vte.get_cursor_position()
        if self.scrollback_lines < 0:
            start_row = 0
        else:
            start_row = max(0, end_row - self.scrollback_lines)
        return start_row, end_row, end_column

    def get_filename(self):
        filename = path.join(self.plugin_config[SETTING_DIR], uuid.uuid1().__str__())
        ret = '%s.terminatorExport' % filename
        if self.plugin_config[SETTING_EXPORT_FILE]:
            with open(self.plugin_config[SETTING_EXPORT_FILE], "a") as targetFile:
                targetFile.writelines(ret + "\n")
                targetFile.close()

        return ret
