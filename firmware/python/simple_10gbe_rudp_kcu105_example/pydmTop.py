#-----------------------------------------------------------------------------
# Title      : PyRogue PyDM Top Level GUI
#-----------------------------------------------------------------------------
# This file is part of the rogue software platform. It is subject to
# the license terms in the LICENSE.txt file found in the top-level directory
# of this distribution and at:
#    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part of the rogue software platform, including this file, may be
# copied, modified, propagated, or distributed except according to the terms
# contained in the LICENSE.txt file.
#-----------------------------------------------------------------------------

import os
import pyrogue as pr
import pyrogue.pydm
from pydm import Display

from qtpy.QtWidgets import (QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QLineEdit, QPushButton, QScrollArea, QFrame,
    QApplication, QWidget, QTabWidget, QListView)
from pydm.utilities import connection


from pyrogue.pydm.widgets import DebugTree, SystemWindow

from pydm.widgets import PyDMEmbeddedDisplay
import pydm.widgets.timeplot as pwt

from PyQt5 import QtGui
from PyQt5.QtWidgets import QSplitter
import sys
from PyQt5.QtCore import Qt


from qtpy import QtCore
from PyQt5.QtCore import Qt
import PyQt5.QtCore as qtcore

import random

#new tree class
from selectiontree import SelectionTree, ToggleButton


Channel = 'rogue://0/root'

def runGui(root):
    pyrogue.pydm.runPyDM(
            root  = root,
            sizeX = 800,
            sizeY = 800,
            ui = os.path.abspath(__file__))

class DefaultTop(Display):
    def __init__(self, parent=None, args=[], macros=None):
        super(DefaultTop, self).__init__(parent=parent, args=args, macros=None)

        self.sizeX  = None
        self.sizeY  = None
        self.title  = None

        self._addColor = '#dddddd'
        self._colorSelector = ColorSelector()

        for a in args:
            if 'sizeX=' in a:
                self.sizeX = int(a.split('=')[1])
            if 'sizeY=' in a:
                self.sizeY = int(a.split('=')[1])
            if 'title=' in a:
                self.title = a.split('=')[1]

        if self.title is None:
            self.title = "Rogue Server: {}".format(os.getenv('ROGUE_SERVERS'))

        if self.sizeX is None:
            self.sizeX = 2200
        if self.sizeY is None:
            self.sizeY = 1000

        self.setup_ui()


    def setup_ui(self):

        self.setWindowTitle(self.title)

        vb = QVBoxLayout()
        self.setLayout(vb)

        self.tab = QTabWidget()
        vb.addWidget(self.tab)

        sys = SystemWindow(parent=None, init_channel=Channel)
        self.tab.addTab(sys,'System')


        var = DebugTree(parent=self, init_channel=Channel)
        self.tab.addTab(var,'Debug Tree')


        main_layout = QHBoxLayout()
        main_box = QGroupBox(parent=self)
        main_box.setLayout(main_layout)

        buttons_layout = QHBoxLayout()

        buttons_box = QGroupBox(parent=self)
        buttons_box.setLayout(buttons_layout)

        self.width_edit = QLineEdit()
        apply_btn = QPushButton()
        apply_btn.setText("Set width")
        apply_btn.clicked.connect(self.do_setwidth)





        # Create the Results Layout
        self.legend_layout = QVBoxLayout()
        self.legend_layout.setContentsMargins(10, 10, 10, 10)

        # Create a Frame to host the results of search
        self.frm_legend = QFrame(parent=self)
        self.frm_legend.setLayout(self.legend_layout)


        # Create a ScrollArea so we can properly handle
        # many entries
        self.scroll_area = QScrollArea(parent=self)
        self.scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)
        self.scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.scroll_area.setWidgetResizable(True)


        # Add the Frame to the scroll area
        self.scroll_area.setWidget(self.frm_legend)



        buttons_layout.addWidget(self.scroll_area)
        buttons_layout.addWidget(self.width_edit)
        buttons_layout.addWidget(apply_btn)




        plots_layout = QHBoxLayout()


        plots_box = QGroupBox(parent=self)
        plots_box.setLayout(plots_layout)


        self.plots = pwt.PyDMTimePlot(parent=None, background = '#f6f6f6', plot_by_timestamps = True)
        self.plots.setTitle('Plots')
        self.plots.setTimeSpan(100)


        plots_layout.addWidget(self.plots)
        plots_layout.addWidget(buttons_box)

                
        selection_layout = QVBoxLayout()
        self.selection_tree = SelectionTree(main=self,parent=None,init_channel=Channel)
        selection_layout.addWidget(self.selection_tree)
        selection_layout.addWidget(self.scroll_area)
        selection_box = QGroupBox()
        selection_box.setLayout(selection_layout)

        selection_splitter = QSplitter(Qt.Vertical)
        selection_splitter.addWidget(self.selection_tree)
        selection_splitter.addWidget(self.scroll_area)

        graphs_layout = QVBoxLayout()
        graphs_layout.addWidget(self.plots)
        graphs_layout.addWidget(buttons_box)
        graphs_box = QGroupBox()
        graphs_box.setLayout(graphs_layout)

        main_splitter = QSplitter(Qt.Horizontal)

        main_splitter.addWidget(selection_splitter)
        main_splitter.addWidget(graphs_box)
        main_layout.addWidget(main_splitter)

 
        self.tab.addTab(main_box,'Plots')

        self.resize(self.sizeX, self.sizeY)


    def do_add(self,path):
        self.plots.addYChannel(y_channel=path,
                color = self._colorSelector.take_color(path),
                lineWidth = 5)

        # disp = QLabel(path)
        disp = LegendRow(parent = self,path=path,main = self)
        self.legend_layout.addWidget(disp)


    def do_remove(self,path):
        curve = self.plots.findCurve(path)
        self.plots.removeYChannel(curve)
        for widget in self.frm_legend.findChildren(QWidget):
            # print(widget)
            if isinstance(widget,LegendRow) and widget._path == path:
                widget.setParent(None)
                widget.deleteLater()
        


    def do_setwidth(self):
        text = self.width_edit.text()

        try:
            val = float(text)
            print(val)
            self.plots.setTimeSpan(val)
        except:
            pass

    def minimumSizeHint(self):

        return QtCore.QSize(1500, 1000)

    def ui_filepath(self):
        # No UI file is being used
        return None

class LegendRow(Display):
    def __init__(self, parent=None, args=[], macros=None,path=None,main=None):
        super(LegendRow, self).__init__(parent=parent, args=args, macros=None)

        self._path = path
        self.sizeX = 40
        self.sizeY = 40
        self.setMaximumHeight(50)
        self._main = main

        self.setup_ui()


    def setup_ui(self):

        #setup main layout
        main_layout = QHBoxLayout()
        main_box = QGroupBox(parent=self)
        main_box.setLayout(main_layout)


        #Add widgets to layout
        main_layout.addWidget(QLabel(self._path))
        button = ToggleButton(main=self._main, state = True, path = self._path)
        button.setStyle(self._main._colorSelector.current_color())
        button.setMaximumWidth(150)
        button.setMaximumHeight(50)
        button.setText('Remove')

        def legendbuttonfuncgen(path):
            def f():
                self._main.do_remove(path)
                for widget in self._main.selection_tree.findChildren(QWidget):
                    if isinstance(widget,ToggleButton) and widget._path == path:
                        widget.toggle()
            return f

        button.clicked.connect(legendbuttonfuncgen(self._path))
        main_layout.addWidget(button)

        self.setLayout(main_layout)


    def ui_filepath(self):
        # No UI file is being used
        return None


class ColorSelector():
    
    def __init__(self):
        self._colorList = ['#F94144', '#F3722C', '#F8961E', '#F9844A', '#F9C74F', '#90BE6D', '#43AA8B', '#4D908E', '#577590', '#277DA1','#f70a0a','#f75d0a','#f7a00a','#f7f30a','#98f70a','#1af70a','#0af7c0','#0accf7','#0a75f7','#0a1ef7','#710af7','#e70af7','#f70a71','#8a2d06','#838a06''#188a06','#188a06','#188a06']
        self._currentDict = {}
        self._currentColor = None

    def take_color(self,channel):

        if len(self._colorList) == 0:
            self._colorList.append(self.generate_new_color())

        random.shuffle(self._colorList)
        color = self._colorList.pop()
        self._currentDict[channel] = color
        self._currentColor = color
        return color

    def give_back_color(self,channel):

        color = self.currentDict.pop(channel)
        self._colorList.append(color)
        random.shuffle(self._colorList)

    def current_color(self):

        return self._currentColor

    def generate_new_color(self):

        return '#' + hex(random.randint(0x100000,0xffffff))[2:] #<----------Change this


