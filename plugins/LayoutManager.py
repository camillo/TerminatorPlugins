'''
Created on Feb 25, 2011

@author: Daniel Marohn
'''

import gtk

import terminatorlib.plugin as plugin
from terminatorlib.translation import _

from terminatorlib.util import dbg
from terminatorlib.util import err
from terminatorlib.util import get_top_window
from terminatorlib.util import get_config_dir

from terminatorlib.paned import Paned
from terminatorlib.paned import HPaned
from terminatorlib.paned import VPaned
from terminatorlib.window import Window
from terminatorlib.terminal import Terminal

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

ROOT_ELEMENT = "root"
CHILD_ELEMENT = "child"
SPLIT_ELEMENT = "split"
TERMINAL_ELEMENT = "terminal"
COMMAND_ATTRIBUTE = "command"
ORIENTATION_ATTRIBUTE = "orientation"
POSITION_ATTRIBUTE = "position"
EXPORT_TERMINAL_NUMBER_ATTRIBUTE = "exportTerminalNumber"
ROOT_DEFAULT_COMMAND = ""
HORIZONTAL_VALUE = "0"
VERTICAL_VALUE = "1"

WRONG_EXTENSION_MESSAGE = "wrong extension"
FILE_NOT_FOUND_MESSAGE = "file not found"

SAVE_BOX_TITLE = 'name the config'
SAVE_BOX_MESSAGE = 'Enter a name:'

TERMINAL_NUMBER_VARIABLE = "terminalNumber"
EXPORT_TERMINAL_COMMAND = "export %s=%d"

EVENT_ACTIVATE = "activate"

AVAILABLE = [LAYOUTMANAGER_NAME]
#older versions of terminator require available instead of AVAILABLE
available = [LAYOUTMANAGER_NAME]

class LayoutManager(plugin.MenuItem):
    
    capabilities = LAYOUTMANAGER_CAPABILITIES
    configDir = None
    nextTerminalNumber = 0
    rootCommand = None
    exportVariable = None

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
        (mainItem, submenu) = self.createMainItems()

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
        (isLayout, shortname) = self.tryGetLayoutShortName(name)
        if isLayout:
            layoutItem = gtk.MenuItem(_(shortname))
            layoutItem.connect(EVENT_ACTIVATE, self.loadCallback, terminal)
            menu.append(layoutItem)
            return True
        else:
            dbg("ignoring [%s] : %s" % (name, shortname))
            return False               

    def tryGetLayoutShortName(self,name):
        if isfile(join(self.configDir, name)):
            (shortname, extension) = splitext(name)
            if extension == LAYOUT_EXTENSION:
                return True, shortname
            else:
                return False, WRONG_EXTENSION_MESSAGE
        else:
            return False, FILE_NOT_FOUND_MESSAGE

    def saveCallback(self, saveMenuItem, terminal):
        window = get_top_window(terminal)
        rootElement = self.createRootElement()
        self.saveRecursive(window, rootElement)
        self.indentXmlElement(rootElement)
        self.writeXmlToFile(rootElement)

    def createRootElement(self, name = ROOT_ELEMENT):
        rootElement = ET.Element(name)
        rootElement.attrib[COMMAND_ATTRIBUTE] = ROOT_DEFAULT_COMMAND
        rootElement.attrib[EXPORT_TERMINAL_NUMBER_ATTRIBUTE] = TERMINAL_NUMBER_VARIABLE
        return rootElement
                   
    def saveRecursive(self, container, element):       
        if isinstance(container, Terminal):
            self.saveTerminal(container, element)
        elif isinstance(container, Paned):
            self.savePanedRecursive(container, element)
        elif isinstance(container, Window):
            self.saveWindowRecursiv(container, element)
        else:
            err("ignoring unknown container type")

    def saveTerminal(self,container, element):
        ET.SubElement(element, TERMINAL_ELEMENT)

    def savePanedRecursive(self,container, element):
        splitElement = self.createSplitElement(element, container)
        children = container.get_children()
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
                err("unknown Paned type; use %s" % HORIZONTAL_VALUE)           
            orientation = HORIZONTAL_VALUE
            
        return orientation

    def saveSplitChildRecursive(self, splitElement, child):
        childElement = ET.SubElement(splitElement, CHILD_ELEMENT)           
        self.saveRecursive(child, childElement)       
        
    def saveWindowRecursiv(self, window, element):
        childElement = ET.SubElement(element, CHILD_ELEMENT)
        child = window.get_children()[0]
        self.saveRecursive(child,childElement)
 
    def writeXmlToFile (self, element, filename = None):
        if filename is None:
            newFilename = inputBox(title=SAVE_BOX_TITLE, message=SAVE_BOX_MESSAGE, default_text="")
            if not (newFilename is None or newFilename == ""):
                self.writeXmlToFile(element, newFilename)
            else:
                dbg("no filename provided; abort saving")
        else:           
            targetFileName = join(self.configDir,filename)
            targetFileName = targetFileName + LAYOUT_EXTENSION
            ET.ElementTree(element).write(targetFileName)

    def loadCallback(self, layoutMenuItem, terminal):
        fileName = layoutMenuItem.props.label + LAYOUT_EXTENSION
        fileName = join(self.configDir, fileName)
        dbg("loading Layout config [%s]" % fileName)
         
        tree = parse(fileName)
        rootElement = tree.getroot()
        self.initRoot(rootElement)

        self.loadLayout(terminal, rootElement)

    def initRoot(self,rootElement):
        self.rootCommand = self.tryGetXmlAttribute(rootElement, COMMAND_ATTRIBUTE)
        self.exportVariable = self.tryGetXmlAttribute(rootElement, EXPORT_TERMINAL_NUMBER_ATTRIBUTE)       
        self.nextTerminalNumber = 1

    def loadLayout(self, terminal, rootElement):
        childElement = rootElement.find(CHILD_ELEMENT)
        if not childElement is None:
            self.loadChildRecursive(terminal, childElement)
        else:
            err("rootElement has no child childElement; abort loading")
        
    def loadChildRecursive(self,terminal,childElement):
        targetElement = childElement.find(SPLIT_ELEMENT)
        handled = self.tryLoadSplitRecursive(terminal, targetElement)
        
        if not handled:
            targetElement = childElement.find(TERMINAL_ELEMENT)
            handled = self.tryLoadTerminal(terminal, targetElement)
        
        if not handled:
            err("neither split, nor terminal found.")
                
    def tryLoadSplitRecursive(self, terminal, splitElement):
        if splitElement == None:
            return False
        #TODO: pass the position to terminator's pane
        #position = self.tryGetXmlAttribute(splitElement, POSITION_ATTRIBUTE)
        splitChildren = list(splitElement.findall(CHILD_ELEMENT))
        if len(splitChildren) == 2:
            orientation = self.tryGetXmlAttribute(splitElement, ORIENTATION_ATTRIBUTE) 
            self.SplitAndLoadAxisRecursive(terminal, orientation, splitChildren[0], splitChildren[1])
            return True
        else:
            err("split element does not have exactly 2 child elements as children")

        return False

    def SplitAndLoadAxisRecursive(self, terminal, orientation, child1, child2):
        isVertical = self.isVerticalOrientation(orientation)
        terminal.parent.split_axis(terminal, isVertical)

        newTerminal = terminal.parent.get_children()[1]
        
        self.loadChildRecursive(terminal, child1)
        self.loadChildRecursive(newTerminal, child2)
    
    def isVerticalOrientation(self, orientation):
        if orientation == HORIZONTAL_VALUE:
            return False
        elif not orientation == VERTICAL_VALUE:
            err("unknown orientation [%s]; use default" % orientation)
            
        return True

    def tryLoadTerminal(self, terminal, terminalElement):
        if terminalElement is None:
            return False
        
        if not self.exportVariable is None:
            self.exportTerminalNumber(terminal)
        
        command = self.getCommandForTerminal(terminalElement)
        if not command is None:
            terminal.feed(command + NEWLINE)

        return True   

    def exportTerminalNumber(self, terminal):
        terminal.feed(EXPORT_TERMINAL_COMMAND % (self.exportVariable, self.nextTerminalNumber) + NEWLINE)
        self.nextTerminalNumber += 1

    def getCommandForTerminal(self,terminalElement):
        command = self.tryGetXmlAttribute(terminalElement, COMMAND_ATTRIBUTE)
        if command is None:
            command = self.rootCommand
        if command == "":
            command = None
        return command

    def tryGetXmlAttribute(self,element, attributeName):
        if attributeName in element.attrib:
            return element.attrib[attributeName]
        else:
            return None

    def indentXmlElement(self, element, level = 0):
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

    def __init__(self, message="", default_text='', modal= True):
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

def inputBox(title = "Input Box", message = "", default_text = '', modal= True):
    win = InputBoxDialog(message, default_text, modal=modal)
    win.set_title(title)
    win.show()
    gtk.main()

    return win.ret
