# models.py
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin # Necesario para el login

db = SQLAlchemy()

# 1. TABLA DE USUARIOS (NUEVA)
class Usuario(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(50), nullable=False) # En prod usaríamos hash
    rol = db.Column(db.String(20), nullable=False) # 'admin' o 'vendedor'
    sucursal = db.Column(db.String(50), nullable=True) # 'Tristan Suarez', 'Maximo Paz'

    def __repr__(self):
        return f"<User {self.username}>"

class Insumo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    stock = db.Column(db.Integer, default=0)

class Sabor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    stock_gramos = db.Column(db.Float, default=0)
    activo = db.Column(db.Boolean, default=True)

class Producto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    precio = db.Column(db.Integer, default=0)
    es_helado = db.Column(db.Boolean, default=False)
    peso_helado = db.Column(db.Integer, default=0)
    max_gustos = db.Column(db.Integer, default=0)
    insumo_id = db.Column(db.Integer, db.ForeignKey('insumo.id'), nullable=True)
    insumo = db.relationship('Insumo', backref='productos')
    es_combo = db.Column(db.Boolean, default=False)

class ComboItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    promo_id = db.Column(db.Integer, db.ForeignKey('producto.id'))
    item_id = db.Column(db.Integer, db.ForeignKey('producto.id'))
    cantidad = db.Column(db.Integer, default=1)

class Venta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.DateTime, nullable=False)
    total = db.Column(db.Integer, default=0)
    medio_pago = db.Column(db.String(50))
    detalle = db.Column(db.Text)
    sucursal = db.Column(db.String(50)) # NUEVO CAMPO