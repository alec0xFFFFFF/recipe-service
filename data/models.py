from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Boolean, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import ARRAY
from datetime import datetime

db = SQLAlchemy()


class Recipe(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(DateTime, default=datetime.utcnow)
    ingredients = db.Column(db.Text, nullable=True)
    steps = db.Column(db.Text, nullable=True)
    equipment = db.Column(db.Text, nullable=True)
    time = db.Column(db.Text, nullable=True)
    description = db.Column(db.Text, nullable=True)
    title = db.Column(db.Text, nullable=True)
    author = db.Column(db.Text, nullable=True)
    submission_md5 = db.Column(db.Text, nullable=True)
    deleted = db.Column(Boolean, nullable=False, default=False)

    def to_dict(self):
        return {
            'id': self.id,
            "ingredients": self.ingredients,
            "submission_md5": self.submission_md5,
            "steps": self.steps,
            "equipment": self.equipment,
            "time": self.time,
            "description": self.description,
            "title": self.title,
            "author": self.author,
            'created_at': self.created_at,
            'deleted': self.deleted
        }


class DescriptionEmbeddings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(db.Integer, ForeignKey('recipe.id'))
    embeddings = db.Column(ARRAY(db.Float))  # Use ARRAY to store embeddings

    def to_dict(self):
        return {
            'id': self.id,
            'embeddings': self.embeddings,
            'recipe_id': self.recipe_id,
        }
