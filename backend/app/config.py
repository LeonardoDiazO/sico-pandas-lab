import os


class Config:
    """12-factor config: every setting is sourced from the environment."""

    ENV = os.environ.get("FLASK_ENV", "production")
    DEBUG = ENV == "development"
