from flask import Flask
from flask_mysqldb import MySQL
from flask_login import LoginManager
from config.linux import LinuxConfig
import os

mysql = MySQL()
login_manager = LoginManager()

def create_app():

    app = Flask(__name__)
    app.secret_key = 'your_secret_key'

    app.config.from_object(LinuxConfig)
    app.config["MYSQL_PASSWORD"] = "alvienged."

    mysql.init_app(app)
    login_manager.init_app(app)

    from .routes import main
    app.register_blueprint(main)

    return app

