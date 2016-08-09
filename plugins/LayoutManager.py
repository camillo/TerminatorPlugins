"""
Created on Feb 25, 2011

@author: Daniel Marohn

licence: public domain

This is a plugin for terminator, that saves and restores layouts.

Find updates here: https://github.com/camillo/TerminatorPlugins
"""

import gtk

import terminatorlib.plugin as plugin
from terminatorlib.util import dbg, err, get_config_dir
from terminatorlib.paned import Paned, HPaned, VPaned
from terminatorlib.window import Window
from terminatorlib.terminal import Terminal
from terminatorlib.notebook import Notebook

from xml.etree.ElementTree import parse
# import xml.etree.ElementTree as ElementTree
from xml.etree import ElementTree

from os.path import splitext, isfile, exists, join
from os import listdir, makedirs, linesep

LAYOUTMANAGER_NAME = "LayoutManager"
LAYOUTMANAGER_DISPLAY_NAME = "Layout Manager"

LAYOUT_EXTENSION = ".layout"
SAVE_COMMAND_CAPTION = "save"
NEWLINE = linesep
INDENT_SPACE = "  "
DEFAULT_PARAMETER_PLACEHOLDER = "{}"
DEFAULT_PARAMETER_SEPARATOR = ","

ROOT_ELEMENT = "root"
CHILD_ELEMENT = "child"
SPLIT_ELEMENT = "split"
TERMINAL_ELEMENT = "terminal"
CAPTION_ATTRIBUTE = "caption"
COMMAND_ATTRIBUTE = "command"
GROUP_ATTRIBUTE = "group"
DIRECTORY_ATTRIBUTE = "directory"
EXECUTION_ORDER_ATTRIBUTE = "executionOrder"
EXPORT_TERMINAL_NUMBER_ATTRIBUTE = "exportTerminalNumber"
TAB_ATTRIBUTE = "tab"
PARAMETER_ATTRIBUTE = "parameter"
PARAMETER_PLACEHOLDER_ATTRIBUTE = "parameterPlaceholder"
PARAMETER_SEPARATOR_ATTRIBUTE = "parameterSeparator"
ORIENTATION_ATTRIBUTE = "orientation"
POSITION_ATTRIBUTE = "position"
ROOT_DEFAULT_COMMAND = ""
HORIZONTAL_VALUE = "0"
VERTICAL_VALUE = "1"

DEFAULT_EXECUTION_ORDER = [DIRECTORY_ATTRIBUTE, EXPORT_TERMINAL_NUMBER_ATTRIBUTE, COMMAND_ATTRIBUTE, GROUP_ATTRIBUTE]

WRONG_EXTENSION_MESSAGE = "wrong extension"
FILE_NOT_FOUND_MESSAGE = "file not found"

SAVE_BOX_TITLE = 'name the config'
SAVE_BOX_MESSAGE = 'Enter a name:'

TERMINAL_NUMBER_VARIABLE = "terminalNumber"
CHANGE_DIRECTORY_COMMAND = 'cd "%s"'
EXPORT_TERMINAL_COMMAND = "export %s=%d"

EVENT_ACTIVATE = "activate"

AVAILABLE = [LAYOUTMANAGER_NAME]
# older versions of terminator require available instead of AVAILABLE
available = AVAILABLE


def get_top_window(widget):
    """
    Return the Window instance a widget belongs to.
    @param widget: The gtk widget, that's top window will returned.
    @return: Gtk Window instance, given widget belongs to.
    """
    parent = widget.get_parent()
    while parent:
        widget = parent
        parent = widget.get_parent()
    return widget


class LayoutManager(plugin.MenuItem):
    """
    Layout manager saves and loads layouts.
    """

    capabilities = ['terminal_menu', ]

    configDir = None
    next_terminal_number = 0
    root_command = None
    root_group = None
    root_directory = None
    export_variable = None
    tab = None
    parameter = None
    parameter_placeholder = DEFAULT_PARAMETER_PLACEHOLDER
    parameter_separator = DEFAULT_PARAMETER_SEPARATOR
    use_parameter = False
    execution_order = DEFAULT_EXECUTION_ORDER

    def __init__(self):
        super(LayoutManager, self).__init__()
        self.set_config_dir()

    def set_config_dir(self):
        """
        Set the directory, where our layouts are saved.
        We use terminator's config dir plus LayoutManager (most likely
        ~/.config/terminator/LayoutManager).
        """
        if self.configDir is None:
            config_dir = join(get_config_dir(), LAYOUTMANAGER_NAME)
            if not exists(config_dir):
                makedirs(config_dir)
            self.configDir = config_dir

    def callback(self, menuitems, menu, terminal):
        """
        Terminator calls this when user right clicked into a terminal.
        We add our context menu item here.
        @param menuitems: List of menu items, that will be displayed.
        @param menu: Full gtk menu instance; not used here.
        @param terminal: The terminal instance, that got the right click.
        """
        main_item = self.create_main_item(terminal)
        menuitems.append(main_item)

    def create_main_item(self, terminal):
        """
        Create the 'Layout Manager' menu item.
        @param terminal: The terminal this context menu item belongs to.
        @return: The gtk menu item to display in user's context menu.
        """
        main_item, submenu = self.create_main_items()

        submenu.append(self.create_save_item(terminal))
        submenu.append(gtk.SeparatorMenuItem())

        possible_layouts = listdir(self.configDir)
        possible_layouts.sort()

        for possible_layout in possible_layouts:
            self.try_add_layout_menu_item(possible_layout, terminal, submenu)

        return main_item

    @staticmethod
    def create_main_items():
        """
        Create the 'Layout Manager' menu item, together with the sub menu
        for saved layouts.
        """
        main_item = gtk.MenuItem(LAYOUTMANAGER_DISPLAY_NAME)
        submenu = gtk.Menu()
        main_item.set_submenu(submenu)
        return main_item, submenu

    def create_save_item(self, terminal):
        """
        Create the 'save' menu item, together with bindings for activation.
        @param terminal: The terminal this context menu item belongs to.
        """
        save_item = gtk.ImageMenuItem(SAVE_COMMAND_CAPTION)
        image = gtk.Image()
        image.set_from_icon_name(gtk.STOCK_FLOPPY, gtk.ICON_SIZE_MENU)
        save_item.set_image(image)
        save_item.connect(EVENT_ACTIVATE, self.save_callback, terminal)
        return save_item

    def try_add_layout_menu_item(self, name, terminal, menu):
        """
        Checks if given file is a layout and add a context menu item if so.
        @param name: The file name of the possible layout.
        @param terminal: The terminal this context menu item belongs to.
        @param menu: Full gtk menu instance; not used here.
        """
        is_layout, short_name = self.try_get_layout_short_name(name)
        if is_layout:
            layout_item = gtk.MenuItem(short_name)
            layout_item.connect(EVENT_ACTIVATE, self.load_callback, terminal)
            menu.append(layout_item)
            return True
        else:
            dbg("ignoring [%s] : %s" % (name, short_name))
            return False

    def try_get_layout_short_name(self, name):
        """
        Check if given file name has extension 'layout'.
        @param name: The possible layout to check.
        @return: (True, short name) if has correct extension;
        (False, err) otherwise.
        """
        if isfile(join(self.configDir, name)):
            short_name, extension = splitext(name)
            if extension == LAYOUT_EXTENSION:
                return True, short_name
            else:
                return False, WRONG_EXTENSION_MESSAGE
        else:
            return False, FILE_NOT_FOUND_MESSAGE

    def save_callback(self, _, terminal):
        """
        Called by gtk, if user clicked the save menu item.
        @param terminal: The terminal this context menu item belongs to.
        @param _: full menu item; not used
        """
        window = get_top_window(terminal)
        root_element = self.create_root_element()
        self.save_recursive(window, root_element, terminal)
        self.indent_xml_element(root_element)
        self.write_xml_to_file(root_element)

    @staticmethod
    def create_root_element(name=ROOT_ELEMENT):
        """
        Create the xml root element, that is used to save the layout.
        @param name: Name of root's element.
        @return: Root xml element.
        """
        root_element = ElementTree.Element(name)
        root_element.attrib[COMMAND_ATTRIBUTE] = ROOT_DEFAULT_COMMAND
        root_element.attrib[EXPORT_TERMINAL_NUMBER_ATTRIBUTE] = TERMINAL_NUMBER_VARIABLE

        return root_element

    def save_recursive(self, target, element, terminal=None):
        if isinstance(target, Terminal):
            self.save_terminal(target, element)
        elif isinstance(target, Paned):
            self.save_paned_recursive(target, element)
        elif isinstance(target, Window):
            self.save_window_recursive(target, element, terminal)
        elif isinstance(target, Notebook):
            self.save_notebook_recursive(target, element, terminal)
        else:
            err("ignoring unknown target type %s" % target.__class__)

    @staticmethod
    def save_terminal(terminal, element):
        terminal_element = ElementTree.SubElement(element, TERMINAL_ELEMENT)
        terminal_element.attrib[DIRECTORY_ATTRIBUTE] = terminal.get_cwd()
        caption = terminal.titlebar.get_custom_string()
        if caption:
            terminal_element.attrib[CAPTION_ATTRIBUTE] = caption

    def save_paned_recursive(self, paned, element):
        split_element = self.create_split_element(element, paned)
        children = paned.get_children()

        self.save_split_child_recursive(split_element, children[0])
        self.save_split_child_recursive(split_element, children[1])

    def create_split_element(self, element, paned):
        split_element = ElementTree.SubElement(element, SPLIT_ELEMENT)
        split_element.attrib[ORIENTATION_ATTRIBUTE] = self.get_orientation(paned)
        return split_element

    @staticmethod
    def get_orientation(paned):
        if isinstance(paned, VPaned):
            orientation = VERTICAL_VALUE
        else:
            if not isinstance(paned, HPaned):
                err("unknown Paned type; will use: %s" % HORIZONTAL_VALUE)
            orientation = HORIZONTAL_VALUE

        return orientation

    def save_split_child_recursive(self, split_element, child):
        child_element = ElementTree.SubElement(split_element, CHILD_ELEMENT)
        self.save_recursive(child, child_element)

    def save_window_recursive(self, window, element, terminal):
        child_element = ElementTree.SubElement(element, CHILD_ELEMENT)
        child = window.get_children()[0]
        self.save_recursive(child, child_element, terminal)

    def save_notebook_recursive(self, notebook, element, terminal):
        child = notebook.find_tab_root(terminal)
        self.save_recursive(child, element)

    def write_xml_to_file(self, element, filename=None):
        if filename is None:
            new_filename = input_box(title=SAVE_BOX_TITLE,
                                     message=SAVE_BOX_MESSAGE, default_text="")
            if not (new_filename is None or new_filename == ""):
                self.write_xml_to_file(element, new_filename)
            else:
                dbg("no filename provided; abort saving")
        else:
            target_filename = join(self.configDir, filename)
            target_filename += LAYOUT_EXTENSION
            ElementTree.ElementTree(element).write(target_filename)

    def load_callback(self, layout_menu_item, terminal):
        tree = self.load_xml_tree(layout_menu_item)
        root_element = tree.getroot()

        self.init_root(root_element)

        self.set_target_tab(terminal)

        self.load_layout(terminal, root_element)

    def load_xml_tree(self, layout_menu_item):
        filename = layout_menu_item.props.label + LAYOUT_EXTENSION
        filename = join(self.configDir, filename)
        dbg("loading Layout config [%s]" % filename)

        return parse(filename)

    def init_root(self, root_element):
        self.root_command = self.try_get_xml_attribute(
            root_element, COMMAND_ATTRIBUTE)
        self.root_directory = self.try_get_xml_attribute(
            root_element, DIRECTORY_ATTRIBUTE)
        self.export_variable = self.try_get_xml_attribute(
            root_element, EXPORT_TERMINAL_NUMBER_ATTRIBUTE)
        self.root_group = self.try_get_xml_attribute(
            root_element, GROUP_ATTRIBUTE)
        self.execution_order = self.parse_execution_order(root_element)
        self.tab = self.try_get_xml_attribute(root_element, TAB_ATTRIBUTE)
        self.set_parameter(root_element)
        self.next_terminal_number = 1

    def parse_execution_order(self, root_element):
        execution_order = self.try_get_xml_attribute(
            root_element, EXECUTION_ORDER_ATTRIBUTE)
        if execution_order:
            execution_order = execution_order.split(DEFAULT_PARAMETER_SEPARATOR)
            execution_order = self.normalize_execution_order(execution_order)
            self.add_missing_execution_steps(execution_order)
        else:
            execution_order = DEFAULT_EXECUTION_ORDER

        return execution_order

    @staticmethod
    def normalize_execution_order(execution_order):
        normalized_execution_order = []
        for step in execution_order:
            normalized_execution_order.append(step.strip())

        return normalized_execution_order

    @staticmethod
    def add_missing_execution_steps(execution_order):
        for step in DEFAULT_EXECUTION_ORDER:
            if step not in execution_order:
                execution_order.append(step)

    def set_parameter(self, root_element):
        self.parameter_placeholder = self.get_parameter_placeholder(root_element)
        self.parameter_separator = self.get_parameter_separator(root_element)
        self.use_parameter, self.parameter = self.try_parse_parameter(root_element)

    def get_parameter_placeholder(self, root_element):
        return self.try_get_xml_attribute(
            root_element, PARAMETER_PLACEHOLDER_ATTRIBUTE,
            DEFAULT_PARAMETER_PLACEHOLDER)

    def get_parameter_separator(self, root_element):
        return self.try_get_xml_attribute(
            root_element, PARAMETER_SEPARATOR_ATTRIBUTE,
            DEFAULT_PARAMETER_SEPARATOR)

    def try_parse_parameter(self, root_element):
        parameter = self.try_get_xml_attribute(root_element, PARAMETER_ATTRIBUTE)

        if parameter:
            parameter = parameter.split(self.parameter_separator)
            parameter.reverse()

        return parameter is not None, parameter

    def set_target_tab(self, terminal):
        if self.tab:
            window = get_top_window(terminal)
            window.tab_new()

    def load_layout(self, terminal, root_element):
        child_element = root_element.find(CHILD_ELEMENT)
        if child_element is not None:
            self.load_child_recursive(terminal, child_element)
        else:
            err("rootElement has no child childElement; abort loading")

    def load_child_recursive(self, terminal, child_element):
        target_element = child_element.find(SPLIT_ELEMENT)
        handled = self.try_load_split_recursive(terminal, target_element)

        if not handled:
            target_element = child_element.find(TERMINAL_ELEMENT)
            handled = self.try_load_terminal(terminal, target_element)

        if not handled:
            err("neither split, nor terminal found.")

    def try_load_split_recursive(self, terminal, split_element):
        if split_element is None:
            return False
        split_children = list(split_element.findall(CHILD_ELEMENT))
        if len(split_children) == 2:
            orientation = self.try_get_xml_attribute(
                split_element, ORIENTATION_ATTRIBUTE)
            self.split_and_load_axis_recursive(terminal, orientation,
                                               split_children[0], split_children[1])
        else:
            err("split element needs exactly two child elements.")

        return True

    def split_and_load_axis_recursive(self, terminal, orientation, child1, child2):
        is_vertical = self.is_vertical_orientation(orientation)
        terminal.parent.split_axis(terminal, is_vertical)

        new_terminal = terminal.parent.get_children()[1]

        self.load_child_recursive(terminal, child1)
        self.load_child_recursive(new_terminal, child2)

    @staticmethod
    def is_vertical_orientation(orientation):
        if orientation is None:
            err("orientation is None; use default")
        elif orientation == HORIZONTAL_VALUE:
            return False
        elif not orientation == VERTICAL_VALUE:
            err("unknown orientation [%s]; use default" % orientation)

        return True

    def try_load_terminal(self, terminal, terminal_element):
        if terminal_element is None:
            return False

        self.set_terminal_caption(terminal, terminal_element)

        for step in self.execution_order:
            self.execute_step(step, terminal, terminal_element)

        return True

    def set_terminal_caption(self, terminal, terminal_element):
        caption = self.try_get_xml_attribute(terminal_element, CAPTION_ATTRIBUTE)
        if caption:
            terminal.titlebar.set_custom_string(caption)

    def execute_step(self, step, terminal, terminal_element):
        if step == DIRECTORY_ATTRIBUTE:
            self.set_directory(terminal, terminal_element)
        elif step == EXPORT_TERMINAL_NUMBER_ATTRIBUTE:
            self.export_terminal_number(terminal, self.export_variable)
        elif step == COMMAND_ATTRIBUTE:
            self.execute_terminal_command(terminal, terminal_element)
        elif step == GROUP_ATTRIBUTE:
            self.set_terminal_group(terminal, terminal_element)
        else:
            err("ignoring unknown step [%s]" % step)

    def set_directory(self, terminal, terminal_element):
        directory = self.try_get_xml_attribute(
            terminal_element, DIRECTORY_ATTRIBUTE, self.root_directory)

        if directory:
            self.write_command(terminal, CHANGE_DIRECTORY_COMMAND % directory)

    def export_terminal_number(self, terminal, variable):
        if variable is not None:
            self.write_command(
                terminal, EXPORT_TERMINAL_COMMAND % (variable, self.next_terminal_number))
            self.next_terminal_number += 1

    def execute_terminal_command(self, terminal, terminal_element):
        command = self.get_terminal_command(terminal_element)
        self.write_command(terminal, command)

    def set_terminal_group(self, terminal, terminal_element):
        group = self.try_get_xml_attribute(
            terminal_element, GROUP_ATTRIBUTE)

        if not group:
            group = self.root_group

        if group:
            if group not in terminal.terminator.groups:
                terminal.terminator.create_group(group)

            terminal.group = group
            terminal.titlebar.set_group_label(group)
            terminal.key_broadcast_off()

    def get_terminal_command(self, terminal_element):
        command = self.try_get_xml_attribute(terminal_element, COMMAND_ATTRIBUTE)
        if command is None:
            command = self.root_command
            if self.use_parameter:
                command = self.insert_command_parameter(command)
        if command == "":
            command = None
        return command

    def insert_command_parameter(self, command):
        if not command:
            return None

        if not self.parameter:
            err("no parameter left for terminal; ignoring command")
            return None

        parameter = self.parameter.pop()

        return command.replace(self.parameter_placeholder, parameter)

    @staticmethod
    def write_command(terminal, command):
        if command:
            terminal.feed(command + NEWLINE)

    @staticmethod
    def try_get_xml_attribute(element, attribute_name, default=None):
        if attribute_name in element.attrib:
            return element.attrib[attribute_name]
        else:
            return default

    def indent_xml_element(self, element, level=0):
        indent_space = NEWLINE + level * INDENT_SPACE
        if len(element):
            if not element.text or not element.text.strip():
                element.text = indent_space + INDENT_SPACE
            if not element.tail or not element.tail.strip():
                element.tail = indent_space
            for element in element:
                self.indent_xml_element(element, level + 1)
            if not element.tail or not element.tail.strip():
                element.tail = indent_space
        else:
            if level and (not element.tail or not element.tail.strip()):
                element.tail = indent_space


class InputBoxDialog(gtk.Dialog):
    def __init__(self, message="", default_text='', modal=True):
        gtk.Dialog.__init__(self)
        self.connect("destroy", self.quit)
        self.connect("delete_event", self.quit)
        if modal:
            self.set_modal(True)
        box = gtk.VBox(spacing=10)
        box.set_border_width(10)
        self.vbox.pack_start(box)
        box.show()

        if message:
            label = gtk.Label(message)
            box.pack_start(label)
            label.show()

        self.entry = gtk.Entry()
        self.entry.connect("activate", self.click)
        self.entry.set_text(default_text)
        box.pack_start(self.entry)
        self.entry.show()
        self.entry.grab_focus()
        button = gtk.Button("OK")
        button.connect("clicked", self.click)
        button.set_flags(gtk.CAN_DEFAULT)
        self.action_area.pack_start(button)
        button.show()
        button.grab_default()
        button = gtk.Button("Cancel")
        button.connect("clicked", self.quit)
        button.set_flags(gtk.CAN_DEFAULT)
        self.action_area.pack_start(button)
        button.show()
        self.ret = None

    def quit(self, *_):
        self.hide()
        self.destroy()
        gtk.main_quit()

    def click(self, *_):
        self.ret = self.entry.get_text()
        self.quit()


def input_box(title="Input Box", message="", default_text='', modal=True):
    win = InputBoxDialog(message, default_text, modal=modal)
    win.set_title(title)
    win.show()
    gtk.main()

    return win.ret
