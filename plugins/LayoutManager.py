'''
Created on Feb 25, 2011

@author: Daniel Marohn
'''

import gtk

import terminatorlib.plugin as plugin
from terminatorlib.translation import _

from terminatorlib.util import dbg
from terminatorlib.util import err
from terminatorlib.util import get_config_dir

from terminatorlib.paned import Paned
from terminatorlib.paned import HPaned
from terminatorlib.paned import VPaned
from terminatorlib.window import Window
from terminatorlib.terminal import Terminal
from terminatorlib.notebook import Notebook

from xml.etree.ElementTree import parse
import xml.etree.ElementTree as ET

from os.path import splitext
from os.path import isfile
from os.path import exists
from os.path import join

from os import listdir
from os import makedirs

LAYOUTMANAGER_NAME = "LayoutManager"
LAYOUTMANAGER_DISPLAY_NAME = "Layout Manager"
LAYOUTMANAGER_CAPABILITIES = ['terminal_menu']

LAYOUT_EXTENSION = ".layout"
SAVE_COMMAND_CAPTION = "save"
NEWLINE = "\n"
INDENT_SPACE = "  "
DEFAULT_PARAMETER_PLACEHOLDER = "{}"
DEFAULT_PARAMETER_SEPARATOR = ","

ROOT_ELEMENT = "root"
CHILD_ELEMENT = "child"
SPLIT_ELEMENT = "split"
TERMINAL_ELEMENT = "terminal"
CAPTION_ATTRIBUTE = "caption"
COMMAND_ATTRIBUTE = "command"
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

DEFAULT_EXECUTION_ORDER = [DIRECTORY_ATTRIBUTE,
                           EXPORT_TERMINAL_NUMBER_ATTRIBUTE, COMMAND_ATTRIBUTE]

WRONG_EXTENSION_MESSAGE = "wrong extension"
FILE_NOT_FOUND_MESSAGE = "file not found"

SAVE_BOX_TITLE = 'name the config'
SAVE_BOX_MESSAGE = 'Enter a name:'

TERMINAL_NUMBER_VARIABLE = "terminalNumber"
CHANGE_DIRECTORY_COMMAND = 'cd "%s"'
EXPORT_TERMINAL_COMMAND = "export %s=%d"

EVENT_ACTIVATE = "activate"

AVAILABLE = [LAYOUTMANAGER_NAME]
#older versions of terminator require available instead of AVAILABLE
available = AVAILABLE


def get_top_window(widget):
    """ Return the Window instance a widget belongs to. """
    parent = widget.get_parent()
    while parent:
        widget = parent
        parent = widget.get_parent()
    return(widget)


class LayoutManager(plugin.MenuItem):

    capabilities = LAYOUTMANAGER_CAPABILITIES
    configDir = None
    nextTerminalNumber = 0
    rootCommand = None
    rootDirectory = None
    exportVariable = None
    tab = None
    parameter = None
    parameterPlaceholder = DEFAULT_PARAMETER_PLACEHOLDER
    parameterSeparator = DEFAULT_PARAMETER_SEPARATOR
    useParameter = False
    executionOrder = DEFAULT_EXECUTION_ORDER

    def __init__(self):
        plugin.MenuItem.__init__(self)
        self.setConfigDir()

    def setConfigDir(self):
        if self.configDir is None:
            configDir = join(get_config_dir(), LAYOUTMANAGER_NAME)
            if not exists(configDir):
                makedirs(configDir)
            self.configDir = configDir

    def callback(self, menuitems, menu, terminal):
        mainItem = self.createMainItem(terminal)
        menuitems.append(mainItem)

    def createMainItem(self, terminal):
        mainItem, submenu = self.createMainItems()

        submenu.append(self.createSaveItem(terminal))
        submenu.append(gtk.SeparatorMenuItem())

        for currentFile in listdir(self.configDir):
            self.tryAddLayoutMenuItem(currentFile, terminal, submenu)

        return mainItem

    def createMainItems(self):
        mainItem = gtk.MenuItem(_(LAYOUTMANAGER_DISPLAY_NAME))
        submenu = gtk.Menu()
        mainItem.set_submenu(submenu)
        return mainItem, submenu

    def createSaveItem(self, terminal):
        saveItem = gtk.ImageMenuItem(SAVE_COMMAND_CAPTION)
        image = gtk.Image()
        image.set_from_icon_name(gtk.STOCK_FLOPPY, gtk.ICON_SIZE_MENU)
        saveItem.set_image(image)
        saveItem.connect(EVENT_ACTIVATE, self.saveCallback, terminal)
        return saveItem

    def tryAddLayoutMenuItem(self, name, terminal, menu):
        isLayout, shortname = self.tryGetLayoutShortName(name)
        if isLayout:
            layoutItem = gtk.MenuItem(_(shortname))
            layoutItem.connect(EVENT_ACTIVATE, self.loadCallback, terminal)
            menu.append(layoutItem)
            return True
        else:
            dbg("ignoring [%s] : %s" % (name, shortname))
            return False

    def tryGetLayoutShortName(self, name):
        if isfile(join(self.configDir, name)):
            shortname, extension = splitext(name)
            if extension == LAYOUT_EXTENSION:
                return True, shortname
            else:
                return False, WRONG_EXTENSION_MESSAGE
        else:
            return False, FILE_NOT_FOUND_MESSAGE

    def saveCallback(self, saveMenuItem, terminal):
        window = get_top_window(terminal)
        rootElement = self.createRootElement()
        self.saveRecursive(window, rootElement, terminal)
        self.indentXmlElement(rootElement)
        self.writeXmlToFile(rootElement)

    def createRootElement(self, name=ROOT_ELEMENT):
        rootElement = ET.Element(name)
        rootElement.attrib[COMMAND_ATTRIBUTE] = ROOT_DEFAULT_COMMAND
        rootElement.attrib[EXPORT_TERMINAL_NUMBER_ATTRIBUTE] = TERMINAL_NUMBER_VARIABLE

        return rootElement

    def saveRecursive(self, target, element, terminal=None):
        if isinstance(target, Terminal):
            self.saveTerminal(target, element)
        elif isinstance(target, Paned):
            self.savePanedRecursive(target, element)
        elif isinstance(target, Window):
            self.saveWindowRecursiv(target, element, terminal)
        elif isinstance(target, Notebook):
            self.saveNotebookRecursiv(target, element, terminal)
        else:
            err("ignoring unknown target type")

    def saveTerminal(self, terminal, element):
        terminalElement = ET.SubElement(element, TERMINAL_ELEMENT)
        terminalElement.attrib[DIRECTORY_ATTRIBUTE] = terminal.get_cwd()
        caption = terminal.titlebar.get_custom_string()
        if caption:
            terminalElement.attrib[CAPTION_ATTRIBUTE] = caption

    def savePanedRecursive(self, paned, element):
        splitElement = self.createSplitElement(element, paned)
        children = paned.get_children()

        self.saveSplitChildRecursive(splitElement, children[0])
        self.saveSplitChildRecursive(splitElement, children[1])

    def createSplitElement(self, element, paned):
        splitElement = ET.SubElement(element, SPLIT_ELEMENT)
        #the position is not used yet.
        splitElement.attrib[POSITION_ATTRIBUTE] = str(paned.get_position())
        splitElement.attrib[ORIENTATION_ATTRIBUTE] = self.getOrientation(paned)
        return splitElement

    def getOrientation(self, paned):
        if isinstance(paned, VPaned):
            orientation = VERTICAL_VALUE
        else:
            if not isinstance(paned, HPaned):
                err("unknown Paned type; will use: %s" % HORIZONTAL_VALUE)
            orientation = HORIZONTAL_VALUE

        return orientation

    def saveSplitChildRecursive(self, splitElement, child):
        childElement = ET.SubElement(splitElement, CHILD_ELEMENT)
        self.saveRecursive(child, childElement)

    def saveWindowRecursiv(self, window, element, terminal):
        childElement = ET.SubElement(element, CHILD_ELEMENT)
        child = window.get_children()[0]
        self.saveRecursive(child, childElement, terminal)

    def saveNotebookRecursiv(self, notebook, element, terminal):
        child = notebook.find_tab_root(terminal)
        self.saveRecursive(child, element)

    def writeXmlToFile(self, element, filename=None):
        if filename is None:
            newFilename = inputBox(title=SAVE_BOX_TITLE,
                                   message=SAVE_BOX_MESSAGE, default_text="")
            if not (newFilename is None or newFilename == ""):
                self.writeXmlToFile(element, newFilename)
            else:
                dbg("no filename provided; abort saving")
        else:
            targetFileName = join(self.configDir, filename)
            targetFileName = targetFileName + LAYOUT_EXTENSION
            ET.ElementTree(element).write(targetFileName)

    def loadCallback(self, layoutMenuItem, terminal):
        tree = self.loadXmlTree(layoutMenuItem)
        rootElement = tree.getroot()

        self.initRoot(rootElement)

        self.setTargetTab(terminal)

        self.loadLayout(terminal, rootElement)

    def loadXmlTree(self, layoutMenuItem):
        fileName = layoutMenuItem.props.label + LAYOUT_EXTENSION
        fileName = join(self.configDir, fileName)
        dbg("loading Layout config [%s]" % fileName)

        return parse(fileName)

    def initRoot(self, rootElement):
        self.rootCommand = self.tryGetXmlAttribute(
            rootElement, COMMAND_ATTRIBUTE)
        self.rootDirectory = self.tryGetXmlAttribute(
            rootElement, DIRECTORY_ATTRIBUTE)
        self.exportVariable = self.tryGetXmlAttribute(
            rootElement, EXPORT_TERMINAL_NUMBER_ATTRIBUTE)
        self.executionOrder = self.parseExecutionOrder(rootElement)
        self.tab = self.tryGetXmlAttribute(rootElement, TAB_ATTRIBUTE)
        self.setParameter(rootElement)
        self.nextTerminalNumber = 1

    def parseExecutionOrder(self, rootElement):
        executionOrder = self.tryGetXmlAttribute(
            rootElement, EXECUTION_ORDER_ATTRIBUTE)
        if executionOrder:
            executionOrder = executionOrder.split(DEFAULT_PARAMETER_SEPARATOR)
            executionOrder = self.normalizeExecutionOrder(executionOrder)
            self.addMissingExecutionSteps(executionOrder)
        else:
            executionOrder = DEFAULT_EXECUTION_ORDER

        return executionOrder

    def normalizeExecutionOrder(self, executionOrder):
        normalizedExecutionOrder = []
        for step in executionOrder:
            normalizedExecutionOrder.append(step.strip())

        return normalizedExecutionOrder

    def addMissingExecutionSteps(self, executionOrder):
        for step in DEFAULT_EXECUTION_ORDER:
            if not step in executionOrder:
                executionOrder.append(step)

    def setParameter(self, rootElement):
        self.parameterPlaceholder = self.getParameterPlaceholder(rootElement)
        self.parameterSeparator = self.getParameterSeparator(rootElement)
        self.useParameter, self.parameter = self.tryParseParameter(rootElement)

    def getParameterPlaceholder(self, rootElement):
        return self.tryGetXmlAttribute(
            rootElement, PARAMETER_PLACEHOLDER_ATTRIBUTE,
            DEFAULT_PARAMETER_PLACEHOLDER)

    def getParameterSeparator(self, rootElement):
        return self.tryGetXmlAttribute(
            rootElement, PARAMETER_SEPARATOR_ATTRIBUTE,
            DEFAULT_PARAMETER_SEPARATOR)

    def tryParseParameter(self, rootElement):
        parameter = self.tryGetXmlAttribute(rootElement, PARAMETER_ATTRIBUTE)

        if parameter:
            parameter = parameter.split(self.parameterSeparator)
            parameter.reverse()

        return (not parameter is None, parameter)

    def setTargetTab(self, terminal):
        if self.tab:
            window = get_top_window(terminal)
            window.tab_new()

    def loadLayout(self, terminal, rootElement):
        childElement = rootElement.find(CHILD_ELEMENT)
        if not childElement is None:
            self.loadChildRecursive(terminal, childElement)
        else:
            err("rootElement has no child childElement; abort loading")

    def loadChildRecursive(self, terminal, childElement):
        targetElement = childElement.find(SPLIT_ELEMENT)
        handled = self.tryLoadSplitRecursive(terminal, targetElement)

        if not handled:
            targetElement = childElement.find(TERMINAL_ELEMENT)
            handled = self.tryLoadTerminal(terminal, targetElement)

        if not handled:
            err("neither split, nor terminal found.")

    def tryLoadSplitRecursive(self, terminal, splitElement):
        if splitElement is None:
            return False
        #TODO: pass the position to terminator's pane
        #position = self.tryGetXmlAttribute(splitElement, POSITION_ATTRIBUTE)
        splitChildren = list(splitElement.findall(CHILD_ELEMENT))
        if len(splitChildren) == 2:
            orientation = self.tryGetXmlAttribute(
                splitElement, ORIENTATION_ATTRIBUTE)
            self.splitAndLoadAxisRecursive(terminal, orientation,
                                           splitChildren[0], splitChildren[1])
        else:
            err("split element needs excatly two chiled elements.")

        return True

    def splitAndLoadAxisRecursive(self, terminal, orientation, child1, child2):
        isVertical = self.isVerticalOrientation(orientation)
        terminal.parent.split_axis(terminal, isVertical)

        newTerminal = terminal.parent.get_children()[1]

        self.loadChildRecursive(terminal, child1)
        self.loadChildRecursive(newTerminal, child2)

    def isVerticalOrientation(self, orientation):
        if orientation is None:
            err("orientation is None; use default")
        elif orientation == HORIZONTAL_VALUE:
            return False
        elif not orientation == VERTICAL_VALUE:
            err("unknown orientation [%s]; use default" % orientation)

        return True

    def tryLoadTerminal(self, terminal, terminalElement):
        if terminalElement is None:
            return False

        self.setTerminalCaption(terminal, terminalElement)

        for step in self.executionOrder:
            self.executeStep(step, terminal, terminalElement)

        return True

    def setTerminalCaption(self, terminal, terminalElement):
        caption = self.tryGetXmlAttribute(terminalElement, CAPTION_ATTRIBUTE)
        if caption:
            terminal.titlebar.set_custom_string(caption)

    def executeStep(self, step, terminal, terminalElement):
        if step == DIRECTORY_ATTRIBUTE:
            self.setDirectory(terminal, terminalElement)
        elif step == EXPORT_TERMINAL_NUMBER_ATTRIBUTE:
            self.exportTerminalNumber(terminal, self.exportVariable)
        elif step == COMMAND_ATTRIBUTE:
            self.executeTerminalCommand(terminal, terminalElement)
        else:
            err("ignoring unknown step [%s]" % step)

    def setDirectory(self, terminal, terminalElement):
        directory = self.tryGetXmlAttribute(
            terminalElement, DIRECTORY_ATTRIBUTE, self.rootDirectory)

        if directory:
            self.writeCommand(terminal, CHANGE_DIRECTORY_COMMAND % directory)

    def exportTerminalNumber(self, terminal, variable):
        if not variable is None:
            self.writeCommand(
                terminal, EXPORT_TERMINAL_COMMAND %
                (variable, self.nextTerminalNumber))
            self.nextTerminalNumber += 1

    def executeTerminalCommand(self, terminal, terminalElement):
        command = self.getTerminalCommand(terminalElement)
        self.writeCommand(terminal, command)

    def getTerminalCommand(self, terminalElement):
        command = self.tryGetXmlAttribute(terminalElement, COMMAND_ATTRIBUTE)
        if command is None:
            command = self.rootCommand
            if self.useParameter:
                command = self.insertCommandParameter(command)
        if command == "":
            command = None
        return command

    def insertCommandParameter(self, command):
        if not command:
            return None

        if not self.parameter:
            err("no parameter left for terminal; ignoring command")
            return None

        parameter = self.parameter.pop()

        return command.replace(self.parameterPlaceholder, parameter)

    def writeCommand(self, terminal, command):
        if command:
            terminal.feed(command + NEWLINE)

    def tryGetXmlAttribute(self, element, attributeName, default=None):
        if attributeName in element.attrib:
            return element.attrib[attributeName]
        else:
            return default

    def indentXmlElement(self, element, level=0):
        indentSpace = NEWLINE + level * INDENT_SPACE
        if len(element):
            if not element.text or not element.text.strip():
                element.text = indentSpace + INDENT_SPACE
            if not element.tail or not element.tail.strip():
                element.tail = indentSpace
            for element in element:
                self.indentXmlElement(element, level + 1)
            if not element.tail or not element.tail.strip():
                element.tail = indentSpace
        else:
            if level and (not element.tail or not element.tail.strip()):
                element.tail = indentSpace


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

    def quit(self, w=None, event=None):
        self.hide()
        self.destroy()
        gtk.main_quit()

    def click(self, button):
        self.ret = self.entry.get_text()
        self.quit()


def inputBox(title="Input Box", message="", default_text='', modal=True):
    win = InputBoxDialog(message, default_text, modal=modal)
    win.set_title(title)
    win.show()
    gtk.main()

    return win.ret
