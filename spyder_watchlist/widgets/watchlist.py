# -*- coding: utf-8 -*-
#
# Copyright © PROCITEC GmbH
# Licensed under the terms of the MIT License

import contextlib
import itertools
import math
from typing import Collection, Final, Iterator, List, Optional, Tuple

from qtpy.QtCore import QMimeData, QModelIndex, QObject, Qt
from qtpy.QtGui import (
    QContextMenuEvent,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QFont,
    QKeyEvent,
    QMouseEvent,
    QPalette,
)
from qtpy.QtWidgets import (
    QAbstractItemView,
    QAction,
    QApplication,
    QMenu,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)
from spyder.config.base import get_translation
from spyder.utils.icon_manager import ima
from spyder.utils.qthelpers import create_action

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
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)

        # Drag and Drop
        # NOTE: We completely override QTableWidget’s handling of drag’n’drop
        # because it’s impossible (?) to make it do what we want to do. See
        # notes below (dragEnterEvent(), dragMoveEvent(), dropEvent()).
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.viewport().setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDropIndicatorShown(True)

        self.copyValueAction = create_action(
            self,
            _("Copy value"),
            icon=ima.icon("editcopy"),
            triggered=self.onCopyValueAction,
        )

        self.contextMenu = QMenu(self)
        self.contextMenu.addAction(self.copyValueAction)
        self.contextMenu.addAction(self.addAction)
        self.contextMenu.addAction(self.removeAction)
        self.contextMenu.addAction(self.removeAllAction)

        # We do not use QTableWidget’s cellChanged() signal as it is triggered
        # by too many actions.
        itemDelegate = self.itemDelegate()
        itemDelegate.closeEditor.connect(self.onExpressionChanged)

        self.itemSelectionChanged.connect(self._updateRemoveAction)

        self.shellWidget.executed.connect(lambda: self._refresh(send_expressions=False))

    # --- helpers ---
    def _updateRemoveAction(self):
        if self.selectionModel().hasSelection():
            self.removeAction.setEnabled(True)
        else:
            self.removeAction.setEnabled(False)

    def _insertRow(
        self, insertAt: int, exprText: Optional[str] = None
    ) -> Tuple[QTableWidgetItem, QTableWidgetItem]:
        self.insertRow(insertAt)

        exprItem = QTableWidgetItem()
        exprItem.setFlags(
            Qt.ItemIsEnabled
            | Qt.ItemIsSelectable
            | Qt.ItemIsEditable
            | Qt.ItemIsDragEnabled
        )
        exprItem.setFont(self.tableFont)
        # Set text *after* setting the font, otherwise the font doesn’t take effect.
        if exprText is not None:
            exprItem.setText(exprText)
        self.setItem(insertAt, 0, exprItem)

        valueItem = QTableWidgetItem()
        valueItem.setFlags(
            Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsDragEnabled
        )
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

    def _singleRowSelected(self) -> bool:
        ranges = self.selectedRanges()
        if len(ranges) != 1:
            return False
        if ranges[0].rowCount() != 1:
            return False
        return True

    # overrides Qt method which does nothing by default
    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        index = self.indexAt(event.pos())
        if index.isValid():
            self.copyValueAction.setEnabled(True)
        else:
            self.copyValueAction.setEnabled(False)
            self.clearSelection()
            # This makes sure that onAddAction() appends new entries at the end
            # of the table after the user has clicked in “empty space”.
            self.setCurrentIndex(QModelIndex())
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
            self.onAddAction()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        super().mousePressEvent(event)
        index = self.indexAt(event.pos())
        if not index.isValid():
            # This makes sure that onAddAction() appends new entries at the end
            # of the table after the user has clicked in “empty space”.
            self.setCurrentIndex(QModelIndex())

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key_Delete and self.selectionModel().hasSelection():
            self.onRemoveAction()
            event.accept()
        else:
            super().keyPressEvent(event)

    # We completely override QTableWidget’s handling of drag’n’drop because it’s
    # impossible (?) to make it do what we want to do.
    #
    # The drag event handlers below overwrite event.proposedAction() by
    # explicitly requesting a copy action. This is required because the drag
    # event may start as a move action. The move action (if accepted) cuts (!)
    # the source text.
    #
    # Overwriting the proposed action in dragEnterEvent() only is not sufficient
    # as dragMoveEvent() and dropEvent() from QAbstractItemView() overwrite that
    # value.

    def mimeTypes(self) -> list[str]:
        # NOTE Ordering matters (possibly due to default imlementation of
        # QAbstractItemModel::mimeData(), see Qt documentation thereof)
        #
        #   - "application/x-qabstractitemmodeldatalist" is the value returned
        #   by the default implementation. It must be present. It must be the
        #   first entry, otherwise something breaks.
        #
        #   - "text/plain" must be present for the drop indicator to be drawn
        #   when external text is dragged into the table.
        return ["application/x-qabstractitemmodeldatalist", "text/plain"]

    def dropMimeData(
        self, row: int, column: int, data: QMimeData, action: Qt.DropAction
    ) -> bool:
        # QAbstractItemView::dropEvent() called from within our implementation
        # of dropEvent() calls dropMimeData(). Do nothing as our dropEvent()
        # takes care of everything.
        return False

    # overrides Qt method QAbstractItemView.dropEvent()
    def dropEvent(self, event: QDropEvent):
        insertAt = self.indexAt(event.pos()).row()
        indicatorPos: Final = self.dropIndicatorPosition()

        if insertAt < 0:
            # Invalid index: mouse is in “empty space” of table => append at
            # end of table
            insertAt = self.rowCount()
        else:
            if indicatorPos == QAbstractItemView.BelowItem:
                insertAt += 1
            elif indicatorPos == QAbstractItemView.AboveItem:
                pass
            elif indicatorPos == QAbstractItemView.OnItem:
                pass
            elif indicatorPos == QAbstractItemView.OnViewport:
                pass

        # QAbstractItemView::dropEvent() must be called. It performs some
        # actions we cannot replicate.
        mime = event.mimeData()
        if mime.hasText():
            for line in reversed(event.mimeData().text().splitlines()):
                if not line:
                    continue
                exprItem, valueItem = self._insertRow(insertAt)
                exprItem.setText(line.strip())

            super().dropEvent(event)
            # Explicitly set copy action. Otherwise the source text will be cut
            # if the proposedAction() is a move action.
            event.setDropAction(Qt.CopyAction)
            event.accept()

            self._refresh()
        elif (
            event.source() == self
            and mime.hasFormat("application/x-qabstractitemmodeldatalist")
            and self._singleRowSelected()
        ):
            selectedRow: Final = self.selectedRanges()[0].topRow()

            if selectedRow < insertAt:
                # row is moved down: account for removeRow() below
                insertAt -= 1

            if insertAt == selectedRow:
                event.ignore()
                return

            exprItem = self.takeItem(selectedRow, 0)
            valueItem = self.takeItem(selectedRow, 1)
            self.removeRow(selectedRow)
            assert insertAt >= 0 and insertAt <= self.rowCount()
            self.insertRow(insertAt)
            self.setItem(insertAt, 0, exprItem)
            self.setItem(insertAt, 1, valueItem)

            super().dropEvent(event)
            event.setDropAction(Qt.MoveAction)
            event.accept()

            self._refresh()
        else:
            # The assert should’t fail because dragEnterEvent() filters drag
            # events we are not interested in (see Qt documentation of
            # QWidget::dragEnterEvent()).
            assert False

    # overrides Qt method QAbstractItemView.dragMoveEvent()
    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        # QAbstractItemView.dragMoveEvent() must be called in order to draw drop
        # indicator and to update dropIndicatorPosition() used in dropEvent().
        mime = event.mimeData()
        if mime.hasText():
            super().dragMoveEvent(event)
            event.setDropAction(Qt.CopyAction)
            event.accept()
        elif (
            event.source() == self
            and mime.hasFormat("application/x-qabstractitemmodeldatalist")
            and self._singleRowSelected()
        ):
            super().dragMoveEvent(event)
            event.setDropAction(Qt.MoveAction)
            event.accept()
        else:
            # The assert should’t fail because dragEnterEvent() filters drag
            # events we are not interested in (see Qt documentation of
            # QWidget::dragEnterEvent()).
            assert False

    # overrides Qt method QAbstractItemView.dragEnterEvent()
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        # QAbstractItemView.setState(DraggingState) must be called, just as in
        # QAbstractItemView::dragEnterEvent(). Otherwise drawing of the drop
        # indicator is broken (however, only for the mime.hasText() case?!).
        mime = event.mimeData()
        if mime.hasText():
            self.setState(QAbstractItemView.DraggingState)
            event.setDropAction(Qt.CopyAction)
            event.accept()
        elif (
            event.source() == self
            and mime.hasFormat("application/x-qabstractitemmodeldatalist")
            and self._singleRowSelected()
        ):
            self.setState(QAbstractItemView.DraggingState)
            event.setDropAction(Qt.MoveAction)
            event.accept()
        else:
            # Prevents further drag move events (see Qt documentation of
            # QWidget::dragEnterEvent())
            event.ignore()

    # --- signal handlers ---
    def onExpressionChanged(self, editor: QWidget, hint) -> None:
        currentItem = self.currentItem()
        assert currentItem is not None

        strippedText = currentItem.text().strip()
        if not strippedText:
            # remove empty entries
            self.removeRow(self.currentRow())
            return

        assert len(strippedText)
        # set new (and stripped) expression string
        currentItem.setText(strippedText)

        # reset expression value
        currentRow = self.row(currentItem)
        valueItem = self.item(currentRow, 1)
        valueItem.setText("")

        self._refresh()

    def onAddAction(self):
        insertAt = self.currentRow()
        if insertAt < 0:
            # Invalid index: mouse is in “empty space” of table => append at
            # end of table
            insertAt = self.rowCount()

        exprItem, valueItem = self._insertRow(insertAt)
        self.setCurrentItem(exprItem)
        self.editItem(exprItem)
        # calling _refresh() is handled by onExpressionChanged() when editing is
        # finised

    def onRemoveAction(self):
        # A selected range may contain a single item (item selected using
        # CTRL+mouse) or multiple items (item range selected using SHIFT+mouse)
        for row in sorted(
            (
                i
                for r in self.selectedRanges()
                for i in range(r.topRow(), r.bottomRow() + 1)
            ),
            reverse=True,
        ):
            self.removeRow(row)

        # QTableView.selectRow() also sets the current item
        if row == self.rowCount():
            # The last row has been removed. Select the new last row.
            self.selectRow(self.rowCount() - 1)
        else:
            # Select the row following the removed one.
            assert row < self.rowCount()
            self.selectRow(row)

        self._refresh()

    def onRemoveAllAction(self, *, refresh):
        self.clearContents()
        self.setRowCount(0)
        # disable remove action as table is empty now
        self.removeAction.setEnabled(False)
        if refresh:
            self._refresh()

    def onCopyValueAction(self):
        currentRow: Final = self.currentRow()
        clipboard = QApplication.clipboard()
        clipboard.setText(self.item(currentRow, 1).text())

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
