# init_db.py - CARGA COMPLETA DE DATOS
from flask import Flask
from models import db, Usuario, Sabor, Insumo, Producto, ComboItem

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///heladeria.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

def cargar_datos_completos():
    with app.app_context():
        db.create_all()
        
        # ---------------------------------------------------------
        # 1. CREAR USUARIOS
        # ---------------------------------------------------------
        if not Usuario.query.first():
            print("👤 Creando Usuarios...")
            usuarios = [
                Usuario(username="admin", password="123", rol="admin", sucursal="General"),
                Usuario(username="tristan", password="123", rol="vendedor", sucursal="Tristán Suárez"),
                Usuario(username="maximo", password="123", rol="vendedor", sucursal="Máximo Paz"),
            ]
            db.session.add_all(usuarios)
            db.session.commit()

        # ---------------------------------------------------------
        # 2. CREAR INSUMOS (Los envases físicos)
        # ---------------------------------------------------------
        if not Insumo.query.first():
            print("📦 Creando Insumos...")
            # Definimos nombre y stock inicial
            lista_insumos = [
                ("Pote 1/4", 200),
                ("Pote 1/2", 100),
                ("Pote 1kg", 100),
                ("Cucurucho Pasta", 300),  # Para Cucuruchón
                ("Cucurucho Grande", 300),
                ("Cucurucho Chico", 300),
                ("Tacita Plastico", 500),
                ("Vaso Batido", 100),
                ("Vaso Cafeteria", 100),
                ("Vaso Plastico", 500),    # Para item "Vasos"
                ("Paq. Cucuruchos x3", 50),
                ("Paq. Cucuruchos x5", 50),
                ("Sin Insumo", 999999)     # Para promos o cosas sin envase
            ]
            
            for nombre, stock in lista_insumos:
                db.session.add(Insumo(nombre=nombre, stock=stock))
            db.session.commit()

        # Helper para buscar insumo rápido por nombre
        def get_ins(nombre):
            return Insumo.query.filter_by(nombre=nombre).first()

        # ---------------------------------------------------------
        # 3. CREAR PRODUCTOS (Lista de Precios)
        # ---------------------------------------------------------
        if not Producto.query.first():
            print("💲 Creando Lista de Precios...")
            # Formato: (Nombre, Precio, EsHelado, PesoGr, MaxGustos, NombreInsumo)
            productos = [
                ("1/4 S/tapa", 4000, True, 250, 3, "Pote 1/4"),
                ("1/4 C/tapa", 4000, True, 250, 3, "Pote 1/4"),
                ("1/2 kg", 8000, True, 500, 3, "Pote 1/2"),
                ("1 kg", 16000, True, 1000, 4, "Pote 1kg"),
                ("Cucuruchon", 7000, True, 150, 2, "Cucurucho Pasta"),
                ("Cucurucho Gran", 6000, True, 120, 2, "Cucurucho Grande"),
                ("Cucurucho Chi", 5000, True, 80, 1, "Cucurucho Chico"),
                ("Tacita", 4000, True, 80, 1, "Tacita Plastico"),
                ("Batitos", 4500, True, 300, 2, "Vaso Batido"),
                ("Cafeteria", 5000, False, 0, 0, "Vaso Cafeteria"),
                ("Vasos", 4000, False, 0, 0, "Vaso Plastico"),
                ("Paq. x 3", 5000, False, 0, 0, "Paq. Cucuruchos x3"),
                ("Paq. x 5", 6500, False, 0, 0, "Paq. Cucuruchos x5"),
            ]

            for p in productos:
                insumo_obj = get_ins(p[5])
                nuevo = Producto(
                    nombre=p[0], precio=p[1], es_helado=p[2], 
                    peso_helado=p[3], max_gustos=p[4], insumo=insumo_obj
                )
                db.session.add(nuevo)
            
            # --- PROMOS (COMBOS) ---
            # Promo 1: $20.000
            promo1 = Producto(nombre="Promo 1", precio=20000, es_combo=True)
            # Promo 2: $18.000
            promo2 = Producto(nombre="Promo 2", precio=18000, es_combo=True)
            # Promo 3: $21.000 (Patagonico)
            promo3 = Producto(nombre="Promo 3 (Patagonico)", precio=21000, es_combo=True)
            
            db.session.add_all([promo1, promo2, promo3])
            db.session.commit()

        # ---------------------------------------------------------
        # 4. CREAR SABORES (Lista completa de la imagen)
        # ---------------------------------------------------------
        if not Sabor.query.first():
            print("🍦 Creando Sabores...")
            lista_sabores = [
                # Dulces de Leche
                "Dulce de Leche", "Dulce de Leche Granizado", "Super Dulce de Leche",
                "Dulce de Leche Brownie", "Dulce de Leche Tecio",
                # Chocolates
                "Chocolate", "Chocolate Blanco", "Chocolate Granizado", 
                "Chocolate Marroc", "Chocolate Tecio", "Chocolate con Almendras", 
                "Chocolate Patagonico", "Chocolate Dubai", "Chocolate Kinder", 
                "Chocolate Nutella",
                # Cremas
                "Almendrado", "Banana", "Bananita Dolca", "Cereza a la Crema",
                "Crema Americana", "Crema Del Cielo", "Crema Oreo", "Crema Rusa",
                "Crema Baileys", "Mouse de Limon Tecio", "Bonobon", "Pistacho",
                "Sambayón", "Chocotorta", "Capitan del Espacio", "Flan con dulce de Leche",
                "Granizado", "Mantecol", "Tiramisu", "Tramontana", "Vainilla Al oreo",
                # Frutales
                "Frutilla Cadbury", "Frutilla A la reina", "Frutilla a la Crema", 
                "Tecio Frauni", "Frutos del bosque", "Maracuya", "Menta Granizada",
                "Lemon Pie", "Anana", "Durazno", "Frutilla al Agua", "Limon"
            ]

            for nombre in lista_sabores:
                # 10kg iniciales por sabor (10000g)
                db.session.add(Sabor(nombre=nombre, stock_gramos=10000))
            
            db.session.commit()

        print("✅ Base de datos restaurada COMPLETAMENTE (Usuarios + Productos + Sabores)")

if __name__ == "__main__":
    cargar_datos_completos()