from oya.apps.asgi import Application


_app = Application()

# Some Stuff here


app = _app.get_asgi_application()

