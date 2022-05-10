def register_watchlist():
    kernel = get_ipython().kernel
    kernel.watchlist_expressions = []
    kernel.watchlist_debugger_only = True

    def set_watchlist_expressions(expressions, debugger_only=True):
        kernel.watchlist_expressions = expressions
        kernel.watchlist_debugger_only = debugger_only

    def eval_watchlist_expressions():
        if kernel.watchlist_debugger_only and not kernel.shell.is_debugging():
            return None

        ns = kernel._get_current_namespace()

        data = []
        for expr in kernel.watchlist_expressions:
            # Strictly speaking we need NOT to send back 'expr'; see comment in
            # displayData() in Watchlist plugin.
            try:
                value = str(eval(expr, ns))
                if len(value) > 512:
                    value = value[:512] + "…"
                data.append((expr, value, None))
            except Exception as e:
                data.append((expr, str(e), e.__class__.__name__))

        return data

    kernel.frontend_comm.register_call_handler(
        "set_watchlist_expressions", set_watchlist_expressions
    )
    kernel.frontend_comm.register_call_handler(
        "eval_watchlist_expressions", eval_watchlist_expressions
    )
