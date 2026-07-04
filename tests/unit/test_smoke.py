import soteria
from soteria.core.config import get_settings
from soteria.worker.celery_app import app as celery_app


def test_import_soteria_package() -> None:
    assert isinstance(soteria.__version__, str)
    assert soteria.__version__


def test_settings_defaults() -> None:
    settings = get_settings()
    assert settings.database_url
    assert settings.celery_broker_url


def test_celery_app_constructs() -> None:
    assert celery_app.main == "soteria"
