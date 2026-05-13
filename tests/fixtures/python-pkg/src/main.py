from . import App

def create_app(config=None):
    app = App(config or {})
    return app

VERSION = "1.0.0"
