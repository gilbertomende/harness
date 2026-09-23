def test_import():
    import app.main
    assert app.main.app.version == "0.2.0"
