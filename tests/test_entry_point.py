import main


def test_main_runs_dashboard_inside_streamlit_runtime(monkeypatch):
    executed = []
    cli_calls = []

    monkeypatch.setattr(
        main,
        "get_script_run_ctx",
        lambda **kwargs: object(),
    )
    monkeypatch.setattr(main.runpy, "run_path", executed.append)
    monkeypatch.setattr(main.stcli, "main", lambda: cli_calls.append(True))

    main.main()
    main.main()

    assert executed == [str(main.APP_PATH), str(main.APP_PATH)]
    assert cli_calls == []


def test_main_starts_streamlit_cli_outside_runtime(monkeypatch):
    cli_calls = []
    monkeypatch.setattr(main, "get_script_run_ctx", lambda **kwargs: None)
    monkeypatch.setattr(main.stcli, "main", lambda: cli_calls.append(True))
    monkeypatch.setattr(main.sys, "argv", ["python", "main.py"])

    main.main()

    assert main.sys.argv == ["streamlit", "run", "app.py"]
    assert cli_calls == [True]
