# models.py - FASE 1 (STOCK TOTALMENTE SEPARADO)
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

# --- TABLAS DE PRODUCTOS Y SABORES ---
class Sabor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), unique=True, nullable=False)
    # STOCK SEPARADO POR SUCURSAL
    stock_maximo = db.Column(db.Float, default=0.0)  # Gramos en MP
    stock_tristan = db.Column(db.Float, default=0.0) # Gramos en TS
    activo = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f"<Sabor {self.nombre}>"

class Insumo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), unique=True, nullable=False)
    # STOCK SEPARADO POR SUCURSAL (CORREGIDO)
    stock_maximo = db.Column(db.Integer, default=0) # Unidades en MP
    stock_tristan = db.Column(db.Integer, default=0) # Unidades en TS

class Producto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    precio = db.Column(db.Float, nullable=False)
    es_helado = db.Column(db.Boolean, default=False) 
    peso_helado = db.Column(db.Float, default=0.0)   
    es_combo = db.Column(db.Boolean, default=False)
    insumo_id = db.Column(db.Integer, db.ForeignKey('insumo.id'), nullable=True)

class ComboItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    promo_id = db.Column(db.Integer, db.ForeignKey('producto.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('producto.id'), nullable=False)
    cantidad = db.Column(db.Integer, default=1)

# --- TABLAS DE VENTAS Y USUARIOS ---
class Venta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.DateTime, nullable=False)
    total = db.Column(db.Float, nullable=False)
    medio_pago = db.Column(db.String(50), nullable=False) 
    detalle = db.Column(db.Text, nullable=False)
    sucursal = db.Column(db.String(50)) # Fundamental para los reportes

class Usuario(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    rol = db.Column(db.String(20), nullable=False) 
    sucursal = db.Column(db.String(50)) # Define de qué stock descuenta

class CierreCaja(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sucursal = db.Column(db.String(50), nullable=False)
    fecha_cierre = db.Column(db.DateTime, nullable=False)
    monto_total = db.Column(db.Float, nullable=False)
    cantidad_ventas = db.Column(db.Integer, nullable=False)
    
def __repr__(self):
    return f"<Cierre {self.sucursal} - {self.fecha_cierre}>"