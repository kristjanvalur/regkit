def test_import():
    from winregkit.registry import handle_to_str, join_names

    assert callable(join_names)
    assert callable(handle_to_str)
