from btui import config


def test_default_sin_config(tmp_path):
    assert config.DEFAULT_RECEIVE_DIR == "/tmp/recibidos"
    assert config.get_receive_dir(tmp_path / "no-existe") == "/tmp/recibidos"


def test_set_y_get(tmp_path):
    cfg = tmp_path / "btui"
    config.set_receive_dir("~/Recibidos", cfg)
    assert config.get_receive_dir(cfg) == "~/Recibidos"
    assert (cfg / "receive.txt").exists()


def test_set_vacio_vuelve_default(tmp_path):
    cfg = tmp_path / "btui"
    config.set_receive_dir("  ", cfg)
    assert config.get_receive_dir(cfg) == "/tmp/recibidos"


def test_archivo_corrupto_default(tmp_path):
    cfg = tmp_path / "btui"
    cfg.mkdir()
    (cfg / "receive.txt").write_text("")
    assert config.get_receive_dir(cfg) == "/tmp/recibidos"
