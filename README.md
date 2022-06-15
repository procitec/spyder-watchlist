# Spyder Watchlist plugin

Watchlist plugin for the debugger in the Spyder IDE

A Watchlist is a functionality some IDEs offer while debugging code. It is
related to the display of all variables accessible in the current scope (aka
Variable Explorer in Spyder). But there is an important distinction: A Watchlist
consists of a user-definable list of expressions. These expressions are
evaluated after a debugger step and the result of the evaluation is displayed.
See the screencast in
[spyder/#16384](https://github.com/spyder-ide/spyder/issues/16438)
for a demonstration.

## Features

* The list of expressions can be edited at any time; see [Usage](#usage) for
  details.
* The value of an expression is shown with bold font if its value changed (e.g.
  after a debugger step).
* The value of an invalid expression is show as `<exception name>`. Hover the
  mouse over the value to show the full exception message in a tooltip.

## Usage

* Changing an existing expression: Double click
* Adding a new expression
  * Toolbar `+` button
  * Menu entry in right-click menu (anywhere in the table)
  * Double click at the end of the table (only possible if there is no
    scrollbar)
  * Drag & drop of text. If the text consists of multiple lines, each line is
    added as an expression.
* Removing an expression
  * Toolbar `-` button. The currently selected expression is removed.
  * Menu entry in right-click menu. The selected expression is removed.
* There is also a “Remove all expression” action in the toolbar and right-click
  menu
