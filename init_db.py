# init_db.py - ACTUALIZADO FASE 1 & 2
from app import app, db
from models import Usuario, Producto, Insumo, Sabor, ComboItem

def cargar_datos_completos():
    with app.app_context():
        # 1. BORRÓN Y CUENTA NUEVA
        print("🗑️ Borrando base de datos antigua...")
        db.drop_all()
        print("🏗️ Creando nuevas tablas con Stock Separado...")
        db.create_all()

        # 2. CREAR USUARIOS (Uno para cada Rol/Sucursal)
        print("👤 Creando Usuarios...")
        # Admin Global (Ve todo)
        u1 = Usuario(username="admin", password="123", rol="admin", sucursal="General")
        # Vendedor Máximo Paz
        u2 = Usuario(username="maximo", password="123", rol="vendedor", sucursal="Máximo Paz")
        # Vendedor Tristán Suárez
        u3 = Usuario(username="tristan", password="123", rol="vendedor", sucursal="Tristán Suárez")
        
        db.session.add_all([u1, u2, u3])

        # 3. CREAR INSUMOS (Con stock separado)
        print("📦 Creando Insumos...")
        insumos_data = [
            # Nombre, Stock Inicial MP, Stock Inicial TS
            ("Cucurucho Chico", 200, 200),
            ("Cucurucho Grande", 150, 150),
            ("Vaso Térmico 1kg", 50, 50),
            ("Vaso Térmico 1/2kg", 60, 60),
            ("Vaso Térmico 1/4kg", 80, 80),
            ("Vasito Colegial", 300, 300),
        ]

        # Guardamos referencia para usar los IDs en los productos
        insumos_objs = {} 

        for nombre, stock_mp, stock_ts in insumos_data:
            insumo = Insumo(nombre=nombre, stock_maximo=stock_mp, stock_tristan=stock_ts)
            db.session.add(insumo)
            # Hacemos flush para que se genere el ID sin commitear todavía
            db.session.flush() 
            insumos_objs[nombre] = insumo.id

        # 4. CREAR LISTA DE PRECIOS (PRODUCTOS)
        print("💲 Creando Lista de Precios...")
        productos = [
            # HELADOS (Asociados a sus insumos)
            {"nombre": "1 kg", "precio": 12000, "es_helado": True, "peso": 1000, "insumo": "Vaso Térmico 1kg"},
            {"nombre": "1/2 kg", "precio": 7000, "es_helado": True, "peso": 500, "insumo": "Vaso Térmico 1/2kg"},
            {"nombre": "1/4 kg", "precio": 4000, "es_helado": True, "peso": 250, "insumo": "Vaso Térmico 1/4kg"},
            {"nombre": "Cucurucho Grande", "precio": 3500, "es_helado": True, "peso": 180, "insumo": "Cucurucho Grande"},
            {"nombre": "Cucurucho Chico", "precio": 2500, "es_helado": True, "peso": 120, "insumo": "Cucurucho Chico"},
            {"nombre": "Vasito", "precio": 2000, "es_helado": True, "peso": 100, "insumo": "Vasito Colegial"},
            
            # EXTRAS / OTROS
            {"nombre": "Baño de Chocolate", "precio": 1500, "es_helado": False, "peso": 0, "insumo": None},
            
            # COMBOS (Promociones)
            {"nombre": "Promo 2 Kilos", "precio": 22000, "es_helado": False, "es_combo": True, "peso": 0, "insumo": None},
        ]

        prod_objs = {}

        for p in productos:
            insumo_id = insumos_objs.get(p["insumo"]) if p["insumo"] else None
            nuevo_prod = Producto(
                nombre=p["nombre"],
                precio=p["precio"],
                es_helado=p.get("es_helado", False),
                peso_helado=p.get("peso", 0),
                es_combo=p.get("es_combo", False),
                insumo_id=insumo_id
            )
            db.session.add(nuevo_prod)
            db.session.flush()
            prod_objs[p["nombre"]] = nuevo_prod.id

        # 5. CONFIGURAR COMBOS (Relacionar items)
        # Ejemplo: La Promo 2 Kilos está hecha de dos "1 kg"
        id_promo = prod_objs["Promo 2 Kilos"]
        id_item = prod_objs["1 kg"]
        
        # Agregamos 2 items de "1 kg" a la promo
        db.session.add(ComboItem(promo_id=id_promo, item_id=id_item, cantidad=2))

        # 6. CREAR SABORES (Con stock separado en 0)
        print("🍦 Creando Sabores...")
        sabores_lista = [
            "Chocolate", "Chocolate con Almendras", "Chocolate Blanco",
            "Dulce de Leche", "Dulce de Leche Granizado", "Super Dulce de Leche",
            "Frutilla a la Crema", "Frutilla al Agua", "Limon",
            "Americana", "Vainilla", "Tramontana", "Sambayon", "Menta Granizada"
        ]

        for s in sabores_lista:
            # Aquí está el CAMBIO CLAVE: stock_maximo y stock_tristan en vez de stock_gramos
            db.session.add(Sabor(nombre=s, stock_maximo=0, stock_tristan=0, activo=True))

        # GUARDAR TODO
        db.session.commit()
        print("✅ Base de datos restaurada COMPLETAMENTE (Usuarios + Productos + Sabores + Stocks Separados)")

if __name__ == "__main__":
    cargar_datos_completos()