import os

from api.api import create_api
from data.models import db

app = create_api()

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True, port=os.getos.environ.get("PORT", default=5000))
