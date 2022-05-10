# -*- coding: utf-8 -*-
#
# Copyright © PROCITEC GmbH
# Licensed under the terms of the MIT License

import contextlib
import itertools
import math
from typing import Collection, Tuple, Optional, List

from qtpy.QtCore import Qt, QObject
from qtpy.QtGui import (
    QContextMenuEvent,
    QDragMoveEvent,
    QDropEvent,
    QFont,
    QMouseEvent,
    QPalette,
)
from qtpy.QtWidgets import (
    QAbstractItemView,
    QAction,
    QMenu,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from spyder.config.base import get_translation

_ = get_translation("spyder_watchlist")

# see eval_watchlist_expressions() in spyder_kernels/console/kernel.py
# (expression, evaluation result or exception message, None or name of exception)
WatchlisDataType = Optional[List[Tuple[str, str, Optional[str]]]]


@contextlib.contextmanager
def block_signals(obj: QObject):
    oldValue = obj.blockSignals(True)
    try:
        yield None
    finally:
        obj.blockSignals(oldValue)


class WatchlistTableWidget(QTableWidget):
    def __init__(
        self,
        *,
        shellWidget,
        addAction: QAction,
        removeAction: QAction,
        removeAllAction: QAction,
        parent: QWidget = None,
    ):
        super().__init__(parent)

        self.shellWidget = shellWidget

        # actions are connected in WatchlistMainWidget from watchlist/widgets/main_widget.py
        self.addAction = addAction
        self.removeAction = removeAction
        self.removeAllAction = removeAllAction

        # disable remove action as table is empty at startup
        self.removeAction.setEnabled(False)

        # config columns
        self.setColumnCount(2)
        self.setHorizontalHeaderLabels([_("Expression"), _("Value")])
        self.horizontalHeader().setStretchLastSection(True)

        width = self.fontMetrics().width("QAbstractItemView")
        self.setColumnWidth(0, math.ceil(width * 1.1))

        # config rows
        self.setRowCount(0)
        self.verticalHeader().setVisible(False)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)

        # selection mode
        self.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.setSelectionMode(QAbstractItemView.SingleSelection)

        # drag and drop
        # We completely override QTableWidget’s handling of drag’n’drop because
        # it’s impossible (?) to make it do what we want to do. See notes below
        # (dragEnterEvent(), dragMoveEvent(), dropEvent()).
        self.setAcceptDrops(True)
        self.setDragEnabled(False)
        # self.viewport().setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DropOnly)

        # The drop indicator setting enables an indicator showing in which
        # row/column the drop will occur. Disable this indicator because we
        # always append at end end of the table. The mouse cursor is changed to
        # a hand regardless of the setting.
        self.setDropIndicatorShown(False)

        self.contextMenu = QMenu(self)
        self.contextMenu.addAction(self.addAction)
        self.contextMenu.addAction(self.removeAction)
        self.contextMenu.addAction(self.removeAllAction)

        # We do not use QTableWidget’s cellChanged() signal as it is triggered
        # by too many actions.
        itemDelegate = self.itemDelegate()
        itemDelegate.closeEditor.connect(self.onExpressionChanged)

        self.currentItemChanged.connect(self.onCurrentItemChanged)

        self.shellWidget.executed.connect(lambda: self._refresh(send_expressions=False))

    # --- helpers ---
    def _updateRemoveAction(self):
        if self.currentRow() == -1 or self.rowCount() == 0:
            self.removeAction.setEnabled(False)
        else:
            self.removeAction.setEnabled(True)

    def _insertRow(
        self, insertAt: int, exprText: Optional[str] = None
    ) -> Tuple[QTableWidgetItem, QTableWidgetItem]:
        self.insertRow(insertAt)

        exprItem = QTableWidgetItem()
        exprItem.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable)
        exprItem.setFont(self.tableFont)
        # Set text *after* setting the font, otherwise the font doesn’t take effect.
        if exprText is not None:
            exprItem.setText(exprText)
        self.setItem(insertAt, 0, exprItem)

        valueItem = QTableWidgetItem()
        valueItem.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        self.setItem(insertAt, 1, valueItem)

        return exprItem, valueItem

    def _refresh(self, *, send_expressions: bool = True) -> None:
        if self.shellWidget.kernel_client is None:
            return

        # We use interrupt=True because this is what the Variable Explorer does
        # by default (see refresh_namespacebrowser() in ipythonconsole/widgets/namespacebrowser.py)
        if send_expressions:
            expressions = self.getExpressions()
            self.shellWidget.call_kernel(interrupt=True).set_watchlist_expressions(
                expressions
            )
        self.shellWidget.call_kernel(
            interrupt=True, callback=self.displayValues
        ).eval_watchlist_expressions()

    # overrides Qt method which does nothing by default
    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        self._updateRemoveAction()
        self.contextMenu.popup(event.globalPos())
        event.accept()

    # overrides Qt method QAbstractItemView.mouseDoubleClickEvent()
    # QTableWidget and its base classes do not provide a way detect a double
    # click on “empty space”. Note that the default implementation invokes a
    # mousePressEvent() under certain circumstances if the index is not valid
    # (as of Qt 5.15.2), i.e. our code might change behaviour.
    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        index = self.indexAt(event.pos())
        if index.isValid():
            super().mouseDoubleClickEvent(event)
        else:
            # Argument does not matter and is only present due to QAction’s
            # optional argument in the triggered() signal.
            self.onAddAction()

    # We completely override QTableWidget’s handling of drag’n’drop because it’s
    # impossible (?) to make it do what we want to do.
    #
    # The drag event handlers below overwrite event.proposedAction() by
    # explicitly requesting a copy action. This is required because the drag
    # event may start as a move action. The move action (if accepted) cuts (!)
    # the source text.
    #
    # The drag event handlers of the base class QTableWidget are not called. The
    # main issue is that a request for a copy action is ignored/overwritten in
    # QTableWidget.dropEvent()

    # overrides Qt method QAbstractItemView.dropEvent()
    def dropEvent(self, event: QDropEvent):
        if not event.mimeData().hasText():
            return

        for line in event.mimeData().text().splitlines():
            if not line:
                continue
            exprItem, valueItem = self._insertRow(self.rowCount())
            exprItem.setText(line.strip())

        # Explicitly set copy action. Otherwise the source text will be cut
        # if the proposedAction() is a move action.
        event.setDropAction(Qt.CopyAction)
        event.accept()

        self._refresh()

    # overrides Qt method QAbstractItemView.dragMoveEvent()
    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        if event.mimeData().hasText():
            event.setDropAction(Qt.CopyAction)
            event.accept()

    # overrides Qt method QAbstractItemView.dragEnterEvent()
    def dragEnterEvent(self, event: QDragMoveEvent) -> None:
        if event.mimeData().hasText():
            event.setDropAction(Qt.CopyAction)
            event.accept()

    # The following three methods are required if QTableWidget’s handling of
    # drag’n’drop is used.

    # overrides Qt method
    # def mimeTypes(self):
    #    return ["text/plain"] # supported types for drag’n’drop

    # overrides Qt method
    # def mimeData(self, items):
    #    # TODO: serialize items for drag’n’drop (not required if only dropping
    #    # is enabled?)
    #    assert False

    # overrides Qt method which crashes (and probobaly doesn’t do what we need)
    # def dropMimeData(self, row: int, column: int, data: QMimeData, action: Qt.DropAction):
    #    if data.hasText():
    #        exprItem, valueItem = self._insertRow(self.rowCount())
    #        exprItem.setText(data.text().strip())
    #        return True
    #    else:
    #        return False

    # --- signal handlers ---
    def onExpressionChanged(self, editor: QWidget, hint) -> None:
        currentItem = self.currentItem()
        assert currentItem is not None

        strippedText = currentItem.text().strip()
        if not strippedText:
            # remove empty entries
            self.removeRow(self.currentRow())
            self._updateRemoveAction()
            return

        assert len(strippedText)
        # set new (and stripped) expression string
        currentItem.setText(strippedText)

        # reset expression value
        currentRow = self.row(currentItem)
        valueItem = self.item(currentRow, 1)
        valueItem.setText("")

        self._updateRemoveAction()
        self._refresh()

    def onCurrentItemChanged(
        self, current: Optional[QTableWidgetItem], previous: Optional[QTableWidgetItem]
    ) -> None:
        if current is None:
            self.removeAction.setEnabled(False)
        else:
            self.removeAction.setEnabled(True)

    def onAddAction(self):
        insertAt = self.rowCount()
        exprItem, valueItem = self._insertRow(insertAt)

        self.setCurrentItem(exprItem)
        self.editItem(exprItem)
        # calling _refresh() is handled by onExpressionChanged() when editing is
        # finised

    def onRemoveAction(self):
        assert self.currentRow() != -1
        self.removeRow(self.currentRow())
        self._updateRemoveAction()
        self._refresh()

    def onRemoveAllAction(self, *, refresh):
        self.clearContents()
        self.setRowCount(0)
        # disable remove action as table is empty now
        self.removeAction.setEnabled(False)
        if refresh:
            self._refresh()

    # --- public API ---
    def setTableFont(self, font: QFont) -> None:
        self.tableFont = font
        boldFont = QFont(self.tableFont)
        boldFont.setBold(True)
        for (row, column) in itertools.product(
            range(self.rowCount()), range(self.columnCount())
        ):
            item = self.item(row, column)
            if item.font().bold():
                item.setFont(boldFont)
            else:
                item.setFont(self.tableFont)

    def getExpressions(self) -> List[str]:
        expressions = []
        for row in range(self.rowCount()):
            text = self.item(row, 0).text()
            if text:
                expressions.append(text)

        return expressions

    def setExpressions(self, expressions: Collection[str]) -> None:
        self.onRemoveAllAction(refresh=False)  # refresh is triggered below

        for row, expr in enumerate(expressions):
            self._insertRow(row, expr)

        self._refresh()

    def clearValues(self):
        for row in range(self.rowCount()):
            item = self.item(row, 1)
            item.setText("")
        self.resizeRowsToContents()

    def displayValues(self, data: WatchlisDataType) -> None:
        if data is None:
            self.clearValues()
            return

        assert len(data) == self.rowCount()

        boldFont = QFont(self.tableFont)
        boldFont.setBold(True)
        disabledTextBrush = self.palette().brush(QPalette.Disabled, QPalette.Text)
        defaultTextBrush = self.palette().brush(QPalette.Active, QPalette.Text)

        for row, (expr, exprVal, exception) in enumerate(data):
            # TODO The kernel does not reorder, i.e. the kernel need not to send
            # the expression back. However, that requires the kernel and the
            # Spyder GUI to be in sync at all times. Can we trust this to be
            # true?
            assert self.item(row, 0).text() == expr

            item = self.item(row, 1)

            if exception is None:
                text = exprVal  # evaluation result
                tooltip = ""
            else:
                text = f"<{exception}>"  # name of exception
                tooltip = exprVal  # exception message

            # set bold font if entry changed
            if item.text() == text:
                item.setFont(self.tableFont)
            else:
                item.setFont(boldFont)

            if exception is None:
                item.setForeground(defaultTextBrush)
            elif exception == "SyntaxError":
                item.setForeground(Qt.red)
            elif exception == "NameError":
                # A disabled ItemIsEnabled flag disables user interactions,
                # including a selection; modify text color instead.
                # item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
                item.setForeground(disabledTextBrush)
            else:
                item.setForeground(disabledTextBrush)

            item.setToolTip(tooltip)
            # Set text *after* setting the font, otherwise the font doesn’t take effect.
            item.setText(text)

        self.resizeRowsToContents()
