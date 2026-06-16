@@
     monkeypatch.setattr(
         "api.graph_lifecycle_providers.get_graph_lifecycle_settings",
         lambda: base_settings,
     )
 
     # Force an exception
-    def _raise_reconciliation_failure(*_args, **_kwargs) -> None:
-        """Raise a simulated runtime error to represent reconciliation failure."""
-        raise ValueError("simulated unexpected startup error")
+    # We patch the thread-executed function _run_startup_reconciliation
+    # (instead of the higher-level _perform_startup_reconciliation) to ensure the
+    # test exercises the real thread handoff path:
+    #   _perform_startup_reconciliation -> asyncio.to_thread(_run_startup_reconciliation, ...)
+    # This validates exception propagation from the worker thread back into the
+    # async caller where logging with the startup trace context occurs.
+    def _raise_reconciliation_failure(*_args, **_kwargs) -> None:
+        """Raise a simulated runtime error to represent reconciliation failure."""
+        raise ValueError("simulated unexpected startup error")
@@
-    monkeypatch.setattr(
-        app_factory,
-        "_run_startup_reconciliation",
-        _raise_reconciliation_failure,
-    )
+    monkeypatch.setattr(app_factory, "_run_startup_reconciliation", _raise_reconciliation_failure)
@@
-    def fake_log_event(logger: Any, level: Any, event: Any) -> None:
-        """Append logged events to a local list for assertion."""
-        logged_events.append(event)
+    def fake_log_event(logger: Any, level: Any, event: Any) -> None:
+        """Append logged events to a local list for assertion."""
+        logged_events.append(event)
