class Config:
    SECRET_KEY = 'your-secret-key'
    SQLALCHEMY_DATABASE_URI = 'postgresql://postgres:1234@localhost:5432/messenger'
    SQLALCHEMY_TRACK_MODIFICATIONS = False