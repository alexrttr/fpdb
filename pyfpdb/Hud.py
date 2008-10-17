#!/usr/bin/env python
"""Hud.py

Create and manage the hud overlays.
"""
#    Copyright 2008, Ray E. Barker

#    
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#    
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#    GNU General Public License for more details.
#    
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA

########################################################################
#    Standard Library modules
import os

#    pyGTK modules
import pygtk
import gtk
import pango
import gobject

#    win32 modules -- only imported on windows systems
if os.name == 'nt':
    import win32gui
    import win32con

#    FreePokerTools modules
import Tables # needed for testing only
import Configuration
import Stats
import Mucked
import Database
import HUD_main

class Hud:
    
    def __init__(self, table, max, poker_game, config, db_name):
        self.table         = table
        self.config        = config
        self.poker_game    = poker_game
        self.max           = max
        self.db_name       = db_name
        self.deleted       = False

        self.stat_windows = {}
        self.popup_windows = {}
        self.font = pango.FontDescription("Sans 8")

#    Set up a main window for this this instance of the HUD
        self.main_window = gtk.Window()
#        self.window.set_decorated(0)
        self.main_window.set_gravity(gtk.gdk.GRAVITY_STATIC)
        self.main_window.set_keep_above(1)
        self.main_window.set_title(table.name)
        self.main_window.connect("destroy", self.kill_hud)

        self.ebox = gtk.EventBox()
        self.label = gtk.Label("Close this window to\nkill the HUD for\n %s" % (table.name))
        self.main_window.add(self.ebox)
        self.ebox.add(self.label)
        self.main_window.move(self.table.x, self.table.y)

#    A popup window for the main window
        self.menu = gtk.Menu()
        self.item1 = gtk.MenuItem('Kill this HUD')
        self.menu.append(self.item1)
        self.item1.connect("activate", self.kill_hud)
        self.item1.show()
        self.item2 = gtk.MenuItem('Save Layout')
        self.menu.append(self.item2)
        self.item2.connect("activate", self.save_layout)
        self.item2.show()
        self.ebox.connect_object("button-press-event", self.on_button_press, self.menu)

        self.main_window.show_all()
#    set_keep_above(1) for windows
        if os.name == 'nt': self.topify_window(self.main_window)

    def on_button_press(self, widget, event):
        if event.button == 3:
            widget.popup(None, None, None, event.button, event.time)
            return True
        return False

    def kill_hud(self, args):
        for k in self.stat_windows.keys():
            self.stat_windows[k].window.destroy()
        self.main_window.destroy()
        self.deleted = True

    def save_layout(self, *args):
        new_layout = []
        for sw in self.stat_windows:
            loc = self.stat_windows[sw].window.get_position()
            new_loc = (loc[0] - self.table.x, loc[1] - self.table.y)
            new_layout.append(new_loc)
#        print new_layout
        self.config.edit_layout(self.table.site, self.max, locations = new_layout)
        self.config.save()

    def adj_seats(self, hand, config):
        adj = range(0, self.max + 1) # default seat adjustments = no adjustment
#    does the user have a fav_seat?
        try:
            if int(config.supported_sites[self.table.site].layout[self.max].fav_seat) > 0:
                fav_seat = config.supported_sites[self.table.site].layout[self.max].fav_seat
                db_connection = Database.Database(config, self.db_name, 'temp')
                actual_seat = db_connection.get_actual_seat(hand, config.supported_sites[self.table.site].screen_name)
                db_connection.close_connection()
                for i in range(0, self.max + 1):
                    j = actual_seat + i
                    if j > self.max: j = j - self.max
                    adj[j] = fav_seat + i
                    if adj[j] > self.max: adj[j] = adj[j] - self.max
        except:
            pass
        return adj

    def create(self, hand, config):
#    update this hud, to the stats and players as of "hand"
#    hand is the hand id of the most recent hand played at this table
#
#    this method also manages the creating and destruction of stat
#    windows via calls to the Stat_Window class

        adj = self.adj_seats(hand, config)
#    create the stat windows
        for i in range(1, self.max + 1):
            (x, y) = config.supported_sites[self.table.site].layout[self.max].location[adj[i]]
            self.stat_windows[i] = Stat_Window(game = config.supported_games[self.poker_game],
                                               parent = self,
                                               table = self.table, 
                                               x = x,
                                               y = y,
                                               seat = i,
                                               player_id = 'fake',
                                               font = self.font)

        self.stats = []
        for i in range(0, config.supported_games[self.poker_game].rows + 1):
            row_list = [''] * config.supported_games[self.poker_game].cols
            self.stats.append(row_list)
        for stat in config.supported_games[self.poker_game].stats.keys():
            self.stats[config.supported_games[self.poker_game].stats[stat].row] \
                      [config.supported_games[self.poker_game].stats[stat].col] = \
                      config.supported_games[self.poker_game].stats[stat].stat_name

#        self.mucked_window = gtk.Window()
#        self.m = Mucked.Mucked(self.mucked_window, self.db_connection)
#        self.mucked_window.show_all() 
            
    def update(self, hand, db, config):
        self.hand = hand   # this is the last hand, so it is available later
        stat_dict = db.get_stats_from_hand(hand)
        for s in stat_dict.keys():
            self.stat_windows[stat_dict[s]['seat']].player_id = stat_dict[s]['player_id']
            for r in range(0, config.supported_games[self.poker_game].rows):
                for c in range(0, config.supported_games[self.poker_game].cols):
                    number = Stats.do_stat(stat_dict, player = stat_dict[s]['player_id'], stat = self.stats[r][c])
                    self.stat_windows[stat_dict[s]['seat']].label[r][c].set_text(number[1])
                    tip = stat_dict[s]['screen_name'] + "\n" + number[5] + "\n" + \
                          number[3] + ", " + number[4]
                    Stats.do_tip(self.stat_windows[stat_dict[s]['seat']].e_box[r][c], tip)
#        self.m.update(hand)

    def topify_window(self, window):
        """Set the specified gtk window to stayontop in MS Windows."""

        def windowEnumerationHandler(hwnd, resultList):
            '''Callback for win32gui.EnumWindows() to generate list of window handles.'''
            resultList.append((hwnd, win32gui.GetWindowText(hwnd)))

        unique_name = 'unique name for finding this window'
        real_name = window.get_title()
        window.set_title(unique_name)
        tl_windows = []
        win32gui.EnumWindows(windowEnumerationHandler, tl_windows)
        
        for w in tl_windows:
            if w[1] == unique_name:
                win32gui.SetWindowPos(w[0], win32con.HWND_TOPMOST, 0, 0, 0, 0, win32con.SWP_NOMOVE|win32con.SWP_NOSIZE) 
#                notify_id = (w[0],
#                             0,
#                             win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP,
#                             win32con.WM_USER+20,
#                             0,
#                             '')
#                win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, notify_id)
#
        window.set_title(real_name)

class Stat_Window:

    def button_press_cb(self, widget, event, *args):
#    This handles all callbacks from button presses on the event boxes in 
#    the stat windows.  There is a bit of an ugly kludge to separate single-
#    and double-clicks.
        if event.button == 1:   # left button event
            if event.type == gtk.gdk.BUTTON_PRESS: # left button single click
                if self.sb_click > 0: return
                self.sb_click = gobject.timeout_add(250, self.single_click, widget)
            elif event.type == gtk.gdk._2BUTTON_PRESS: # left button double click
                if self.sb_click > 0:
                    gobject.source_remove(self.sb_click)
                    self.sb_click = 0
                    self.double_click(widget, event, *args)

        if event.button == 2:   # middle button event
            pass
#            print "middle button clicked"

        if event.button == 3:   # right button event
            pass
#            print "right button clicked"

    def single_click(self, widget):
#    Callback from the timeout in the single-click finding part of the
#    button press call back.  This needs to be modified to get all the 
#    arguments from the call.
#        print "left button clicked"
        self.sb_click = 0
        Popup_window(widget, self)
        return False

    def double_click(self, widget, event, *args):
        self.toggle_decorated(widget)

    def toggle_decorated(self, widget):
        top = widget.get_toplevel()
        (x, y) = top.get_position()
                    
        if top.get_decorated():
            top.set_decorated(0)
            top.move(x, y)
        else:
            top.set_decorated(1)
            top.move(x, y)

    def __init__(self, parent, game, table, seat, x, y, player_id, font):
        self.parent = parent        # Hud object that this stat window belongs to
        self.game = game            # Configuration object for the curren
        self.table = table          # Table object where this is going
        self.x = x + table.x        # table.x and y are the location of the table
        self.y = y + table.y        # x and y are the location relative to table.x & y
        self.player_id = player_id  # looks like this isn't used ;)
        self.sb_click = 0           # used to figure out button clicks

        self.window = gtk.Window()
        self.window.set_decorated(0)
        self.window.set_gravity(gtk.gdk.GRAVITY_STATIC)
        self.window.set_keep_above(1)
        self.window.set_title("%s" % seat)
        self.window.set_property("skip-taskbar-hint", True)

        self.grid = gtk.Table(rows = self.game.rows, columns = self.game.cols, homogeneous = False)
        self.window.add(self.grid)
        
        self.e_box = []
        self.frame = []
        self.label = []
        for r in range(self.game.rows):
            self.e_box.append([])
            self.label.append([])
            for c in range(self.game.cols):
                self.e_box[r].append( gtk.EventBox() )
                Stats.do_tip(self.e_box[r][c], 'farts')
                self.grid.attach(self.e_box[r][c], c, c+1, r, r+1, xpadding = 0, ypadding = 0)
                self.label[r].append( gtk.Label('xxx') )
                self.e_box[r][c].add(self.label[r][c])
                self.e_box[r][c].connect("button_press_event", self.button_press_cb)
#                font = pango.FontDescription("Sans 8")
                self.label[r][c].modify_font(font)
        self.window.realize
        self.window.move(self.x, self.y)
        self.window.show_all()
#    set_keep_above(1) for windows
        if os.name == 'nt': self.topify_window(self.window)

    def topify_window(self, window):
        """Set the specified gtk window to stayontop in MS Windows."""

        def windowEnumerationHandler(hwnd, resultList):
            '''Callback for win32gui.EnumWindows() to generate list of window handles.'''
            resultList.append((hwnd, win32gui.GetWindowText(hwnd)))

        unique_name = 'unique name for finding this window'
        real_name = window.get_title()
        window.set_title(unique_name)
        tl_windows = []
        win32gui.EnumWindows(windowEnumerationHandler, tl_windows)
        
        for w in tl_windows:
            if w[1] == unique_name:
                win32gui.SetWindowPos(w[0], win32con.HWND_TOPMOST, 0, 0, 0, 0, win32con.SWP_NOMOVE|win32con.SWP_NOSIZE) 
#                notify_id = (w[0],
#                             0,
#                             win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP,
#                             win32con.WM_USER+20,
#                             0,
#                             '')
#                win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, notify_id)
#
        window.set_title(real_name)

def destroy(*args):             # call back for terminating the main eventloop
    gtk.main_quit()

class Popup_window:
    def __init__(self, parent, stat_window):
        self.sb_click = 0

#    create the popup window
        self.window = gtk.Window()
        self.window.set_decorated(0)
        self.window.set_gravity(gtk.gdk.GRAVITY_STATIC)
        self.window.set_keep_above(1)
        self.window.set_title("popup")
        self.window.set_property("skip-taskbar-hint", True)
        self.window.set_transient_for(parent.get_toplevel())
        self.window.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
        
        self.ebox = gtk.EventBox()
        self.ebox.connect("button_press_event", self.button_press_cb)
        self.lab  = gtk.Label("stuff\nstuff\nstuff")

#    need an event box so we can respond to clicks
        self.window.add(self.ebox)
        self.ebox.add(self.lab)
        self.window.realize

#    figure out the row, col address of the click that activated the popup
        row = 0
        col = 0
        for r in range(0, stat_window.game.rows):
            for c in range(0, stat_window.game.cols):
                if stat_window.e_box[r][c] == parent:
                    row = r
                    col = c
                    break

#    figure out what popup format we're using
        popup_format = "default"
        for stat in stat_window.game.stats.keys():
            if stat_window.game.stats[stat].row == row and stat_window.game.stats[stat].col == col:
                popup_format = stat_window.game.stats[stat].popup
                break

#    get the list of stats to be presented from the config
        stat_list = []
        for w in stat_window.parent.config.popup_windows.keys():
            if w == popup_format:
                stat_list = stat_window.parent.config.popup_windows[w].pu_stats
                break

#    get a database connection
        db_connection = Database.Database(stat_window.parent.config, stat_window.parent.db_name, 'temp')
    
#    calculate the stat_dict and then create the text for the pu
#        stat_dict = db_connection.get_stats_from_hand(stat_window.parent.hand, stat_window.player_id)
        stat_dict = db_connection.get_stats_from_hand(stat_window.parent.hand)
        db_connection.close_connection()

        pu_text = ""
        for s in stat_list:
            number = Stats.do_stat(stat_dict, player = int(stat_window.player_id), stat = s)
            pu_text += number[3] + "\n"

        self.lab.set_text(pu_text)        
        self.window.show_all()
#    set_keep_above(1) for windows
        if os.name == 'nt': self.topify_window(self.window)

    def button_press_cb(self, widget, event, *args):
#    This handles all callbacks from button presses on the event boxes in 
#    the popup windows.  There is a bit of an ugly kludge to separate single-
#    and double-clicks.  This is the same code as in the Stat_window class
        if event.button == 1:   # left button event
            if event.type == gtk.gdk.BUTTON_PRESS: # left button single click
                if self.sb_click > 0: return
                self.sb_click = gobject.timeout_add(250, self.single_click, widget)
            elif event.type == gtk.gdk._2BUTTON_PRESS: # left button double click
                if self.sb_click > 0:
                    gobject.source_remove(self.sb_click)
                    self.sb_click = 0
                    self.double_click(widget, event, *args)

        if event.button == 2:   # middle button event
            pass
#            print "middle button clicked"

        if event.button == 3:   # right button event
            pass
#            print "right button clicked"

    def single_click(self, widget):
#    Callback from the timeout in the single-click finding part of the
#    button press call back.  This needs to be modified to get all the 
#    arguments from the call.
        self.sb_click = 0
        self.window.destroy()
        return False

    def double_click(self, widget, event, *args):
        self.toggle_decorated(widget)

    def toggle_decorated(self, widget):
        top = widget.get_toplevel()
        (x, y) = top.get_position()
                    
        if top.get_decorated():
            top.set_decorated(0)
            top.move(x, y)
        else:
            top.set_decorated(1)
            top.move(x, y)

    def topify_window(self, window):
        """Set the specified gtk window to stayontop in MS Windows."""

        def windowEnumerationHandler(hwnd, resultList):
            '''Callback for win32gui.EnumWindows() to generate list of window handles.'''
            resultList.append((hwnd, win32gui.GetWindowText(hwnd)))

        unique_name = 'unique name for finding this window'
        real_name = window.get_title()
        window.set_title(unique_name)
        tl_windows = []
        win32gui.EnumWindows(windowEnumerationHandler, tl_windows)
        
        for w in tl_windows:
            if w[1] == unique_name:
                win32gui.SetWindowPos(w[0], win32con.HWND_TOPMOST, 0, 0, 0, 0, win32con.SWP_NOMOVE|win32con.SWP_NOSIZE) 
#                notify_id = (w[0],
#                             0,
#                             win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP,
#                             win32con.WM_USER+20,
#                             0,
#                             '')
#                win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, notify_id)
#
        window.set_title(real_name)

if __name__== "__main__":
    main_window = gtk.Window()
    main_window.connect("destroy", destroy)
    label = gtk.Label('Fake main window, blah blah, blah\nblah, blah')
    main_window.add(label)
    main_window.show_all()
    
    c = Configuration.Config()
    tables = Tables.discover(c)
    db = Database.Database(c, 'fpdb', 'holdem')

    for t in tables:
        win = Hud(t, 8, c, db)
#        t.get_details()
        win.update(8300, db, c)

    gtk.main()