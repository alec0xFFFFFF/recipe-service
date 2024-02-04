from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Boolean, ForeignKey, DateTime, event, text
from sqlalchemy.dialects.postgresql import ARRAY, INT4RANGE
from datetime import datetime

db = SQLAlchemy()


class Record:
    id = db.Column(db.Integer, primary_key=True)

    def to_dict(self):
        raise NotImplementedError


class Recipe(db.Model, Record):
    created_at = db.Column(DateTime, default=datetime.utcnow)
    ingredients = db.Column(db.Text, nullable=True)
    servings = db.Column(INT4RANGE, nullable=True)
    steps = db.Column(db.Text, nullable=True)
    equipment = db.Column(db.Text, nullable=True)
    time = db.Column(db.Integer, nullable=True)
    description = db.Column(db.Text, nullable=True)
    title = db.Column(db.Text, nullable=True)
    author = db.Column(db.Text, nullable=True)
    submission_md5 = db.Column(db.Text, unique=True)
    deleted = db.Column(Boolean, nullable=False, default=False)

    def to_dict(self):
        return {
            'id': self.id,
            "ingredients": self.ingredients,
            "servings": self.servings,
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


class DescriptionEmbeddings(db.Model, Record):
    recipe_id = db.Column(db.Integer, ForeignKey('recipe.id'), unique=True)
    embeddings = db.Column(ARRAY(db.Float))  # 1536

    def to_dict(self):
        return {
            'id': self.id,
            'embeddings': self.embeddings,
            'recipe_id': self.recipe_id,
        }


class IngredientsEmbeddings(db.Model, Record):
    recipe_id = db.Column(db.Integer, ForeignKey('recipe.id'), unique=True)
    embeddings = db.Column(ARRAY(db.Float))  # 1536

    def to_dict(self):
        return {
            'id': self.id,
            'embeddings': self.embeddings,
            'recipe_id': self.recipe_id,
        }


class PantryItem(db.Model, Record):
    created_at = db.Column(DateTime, default=datetime.utcnow)
    expiration = db.Column(DateTime, nullable=True)
    name = db.Column(db.Text, nullable=True)
    image = db.Column(db.Text, nullable=True)
    description = db.Column(db.Text, nullable=True)
    user_id = db.Column(db.Integer, nullable=True)
    deleted = db.Column(Boolean, nullable=False, default=False)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'description': self.description,
            'name': self.name,
            'expiration': self.expiration,
            'image': self.image,
            'deleted': self.deleted,
            'created_at': self.created_at,
        }


class PantryItemEmbeddings(db.Model, Record):
    pantry_item_id = db.Column(db.Integer, ForeignKey('pantry_item.id'), unique=True)
    embeddings = db.Column(ARRAY(db.Float))  # 1536

    def to_dict(self):
        return {
            'id': self.id,
            'embeddings': self.embeddings,
            'pantry_item_id': self.pantry_item_id,
        }


def after_description_create_listener(target, connection, **kw):
    connection.execute(text(
        "ALTER TABLE description_embeddings ALTER COLUMN embeddings TYPE vector(3072) USING embeddings::vector(3072);"))


@event.listens_for(DescriptionEmbeddings.__table__, 'after_create')
def after_description_create(target, connection, **kw):
    after_description_create_listener(target, connection, **kw)


def after_ingredient_create_listener(target, connection, **kw):
    connection.execute(text(
        "ALTER TABLE ingredients_embeddings ALTER COLUMN embeddings TYPE vector(3072) USING embeddings::vector(3072);"))


@event.listens_for(IngredientsEmbeddings.__table__, 'after_create')
def after_ingredient_create(target, connection, **kw):
    after_ingredient_create_listener(target, connection, **kw)


def after_pantry_create_listener(target, connection, **kw):
    connection.execute(text(
        "ALTER TABLE pantry_items_embeddings ALTER COLUMN embeddings TYPE vector(3072) USING embeddings::vector(3072);"))


@event.listens_for(PantryItemEmbeddings.__table__, 'after_create')
def after_pantry_create(target, connection, **kw):
    after_pantry_create_listener(target, connection, **kw)
