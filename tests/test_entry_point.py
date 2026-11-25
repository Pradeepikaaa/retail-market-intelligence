import main


def test_main_imports_dashboard_inside_streamlit_runtime(monkeypatch):
    imported = []
    cli_calls = []

    monkeypatch.setattr(
        main,
        "get_script_run_ctx",
        lambda **kwargs: object(),
    )
    monkeypatch.setattr(main, "import_module", imported.append)
    monkeypatch.setattr(main.stcli, "main", lambda: cli_calls.append(True))

    main.main()

    assert imported == ["app"]
    assert cli_calls == []


def test_main_starts_streamlit_cli_outside_runtime(monkeypatch):
    cli_calls = []
    monkeypatch.setattr(main, "get_script_run_ctx", lambda **kwargs: None)
    monkeypatch.setattr(main.stcli, "main", lambda: cli_calls.append(True))
    monkeypatch.setattr(main.sys, "argv", ["python", "main.py"])

    main.main()

    assert main.sys.argv == ["streamlit", "run", "app.py"]
    assert cli_calls == [True]
