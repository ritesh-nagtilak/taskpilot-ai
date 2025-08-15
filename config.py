import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-change-in-production'
    
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    DATABASE_URL = os.environ.get('DATABASE_URL') or os.path.join(BASE_DIR, 'taskpilot.db')

class DevelopmentConfig(Config):
    DEBUG = True
    DATABASE_URL = os.path.join(Config.BASE_DIR, 'taskpilot.db')

class ProductionConfig(Config):
    DEBUG = False
    DATABASE_URL = os.environ.get('DATABASE_URL') or '/var/data/taskpilot.db'

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
