# Spyder Watchlist plugin

Watchlist plugin for the debugger in the Spyder IDE

A watchlist is a functionality some IDEs offer while debugging code. It is
related to the display of all variables accessible in the current scope (aka
Variable Explorer in Spyder). But there is an important distinction: A Watchlist
consists of a user-definable list of expressions. These expressions are
evaluated after each debugger step and the result of the evaluation is
displayed. See [here](https://github.com/spyder-ide/spyder/issues/16438) for a
screencast which demonstrates the plugin.


## Installation

    pip install spyder-watchlist

## Features

* Any Python expression can be entered. The Watchlist displays the stringified
  result of the evaluation. In terms of Python code `value =
  str(eval(expression, globals, locals))`.

  > **Warning**
  > This makes the Watchlist a very powerful tool, but this comes at a cost: Any
  > side effects of an expression will affect your execution environment.

* The values of expressions are refreshed whenever they might have changed
  (after executing commands in the IPython Console and after debugger commands).
* The list of expressions can be modified at any time; see [Usage](#usage) for
  details.
* The value of an expression is shown with bold font if it has changed
* The value of an invalid expression is show as `<exception name>`. Hover the
  mouse over the value to show the full exception message in a tooltip.

## Usage

* Changing an existing expression: Double click on expression (first column)
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

## Known Issues

* The value of variables in the current scope can be changed in Spyder’s
  Variable Explorer plugin. Expressions in the Watchlist depending on any
  variable changed in the Variable Explorer will display an outdated value. The
  new expression value is displayed after a refresh of the Watchlist. A
  refresh is trigged by:
  * Executing commands in the IPython Console. Pressing Enter with an empty
    input prompt is sufficient.
  * Modifying the list of expressions in some way (add, remove or edit an
    expression)
