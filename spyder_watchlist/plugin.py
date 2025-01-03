# -*- coding: utf-8 -*-
#
# Copyright © PROCITEC GmbH
# Licensed under the terms of the MIT License

from spyder.api.fonts import SpyderFontType
from spyder.api.plugins import Plugins, SpyderDockablePlugin
from spyder.api.shellconnect.mixins import ShellConnectPluginMixin

from .widgets.main_widget import WatchlistMainWidget


class Watchlist(SpyderDockablePlugin, ShellConnectPluginMixin):
    # --- SpyderPluginV2 API ---
    NAME = "watchlist"
    REQUIRES = [Plugins.IPythonConsole]
    CONF_SECTION = NAME
    # CONF_FILE = True  # use separate configuration file (default)
    CONF_VERSION = "0.1.0"
    CONF_DEFAULTS = [(NAME, {"expressions": []})]

    # -- SpyderDockablePlugin API ---
    # TABIFY seems to be ignored if the plugin is added to a layout in
    # plugins/layout/layout.py. However, it seems to be respected when the plugin
    # is not in a layout and the user “manually” enables it using the Panes
    # menu.
    TABIFY = [Plugins.VariableExplorer]
    WIDGET_CLASS = WatchlistMainWidget

    # --- SpyderPluginV2 API ---
    @staticmethod
    def get_name():
        return "Watchlist"

    @staticmethod
    def get_description():
        return "Execute Python statements in the current namesapce and view the results"

    @classmethod
    def get_icon(cls):
        return cls.create_icon("debug")

    def on_initialize(self):
        font = self.get_font(SpyderFontType.Monospace)
        self.get_widget().set_table_font(font)

    def update_font(self):
        font = self.get_font(SpyderFontType.Monospace)
        self.get_widget().set_table_font(font)

    def on_close(self, cancelable=False):
        expressions = self.get_widget().all_expressions()
        self.set_conf("expressions", expressions, recursive_notification=False)
