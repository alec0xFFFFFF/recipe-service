import os
from sqlalchemy import text

from api.api import create_api
from data.models import db

app = create_api()

with app.app_context():
    db.create_all()
    try:
        db.session.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        db.session.commit()
        print("pg_similarity extension created successfully.")
    except Exception as e:
        db.session.rollback()
        print(f"Error creating pg_similarity extension: {str(e)}")

if __name__ == '__main__':
    app.run(debug=True, port=os.getenv("PORT", default=5000))
