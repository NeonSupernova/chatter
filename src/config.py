# config.py

import os

class Config:
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.environ.get('SECRET_KEY', 'default_secret_key')
    CORS_HEADERS = 'Content-Type'
    SOCKETIO_MESSAGE_QUEUE = os.environ.get('SOCKETIO_MESSAGE_QUEUE', None) # For production use

class DevelopmentConfig(Config):
    SQLALCHEMY_DATABASE_URI = 'sqlite:///dev_chatrooms.db'
    DEBUG = True
    TESTING = False
    LIMITER_DEFAULTS = ["200 per day", "50 per hour"]
    STORAGE_URI = "redis://default:aJXuXHO2nmuqKptnWVP9o8jiQ5887HRr@redis-19209.c283.us-east-1-4.ec2.redns.redis-cloud.com:19209"

class ProductionConfig(Config):
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///prod_chatrooms.db')
    DEBUG = False
    TESTING = False
    LIMITER_DEFAULTS = ["1000 per day", "200 per hour"]
    STORAGE_URI = os.environ.get('STORAGE_URI', 'redis://default:aJXuXHO2nmuqKptnWVP9o8jiQ5887HRr@redis-19209.c283.us-east-1-4.ec2.redns.redis-cloud.com:19209')