import os

from app import app

if __name__ == '__main__':
    app.run(debug=True, port=os.getos.environ.get("PORT", default=5000))
