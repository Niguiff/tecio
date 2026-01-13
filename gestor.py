# gestor.py - VERSIÓN CORREGIDA Y CON DIAGNÓSTICO
from models import db, Sabor, Insumo, Producto, Venta, ComboItem, Usuario
from datetime import datetime
import pandas as pd
import io

class HeladeriaManager:
    # --- CONSULTAS DE DATOS (READ) ---
    def obtener_sabores(self):
        return Sabor.query.filter_by(activo=True).all()

    def obtener_productos(self):
        return Producto.query.all()
    
    def obtener_insumos(self):
        return Insumo.query.all()

    def obtener_ventas(self):
        return Venta.query.all()

    def obtener_usuarios(self):
        return Usuario.query.all()

    # --- GESTIÓN DE USUARIOS ---
    def crear_usuario(self, username, password, rol, sucursal):
        if Usuario.query.filter_by(username=username).first():
            return False, f"El usuario '{username}' ya existe."
        nuevo_usuario = Usuario(username=username, password=password, rol=rol, sucursal=sucursal)
        db.session.add(nuevo_usuario)
        db.session.commit()
        return True, f"Usuario {username} creado exitosamente."

    def eliminar_usuario(self, user_id):
        usuario = Usuario.query.get(user_id)
        if usuario:
            nombre = usuario.username
            db.session.delete(usuario)
            db.session.commit()
            return True, f"Usuario {nombre} eliminado."
        return False, "Usuario no encontrado."

    def obtener_recaudacion_total(self):
        resultado = db.session.query(db.func.sum(Venta.total)).scalar()
        return resultado if resultado else 0

    # --- GESTIÓN DE STOCK Y PRECIOS (WRITE) ---
    def reponer_stock_sabor(self, nombre_sabor, cantidad_gramos):
        sabor = Sabor.query.filter_by(nombre=nombre_sabor).first()
        if sabor:
            sabor.stock_gramos += cantidad_gramos
            db.session.commit()
            return True, f"Stock actualizado. {sabor.nombre}: {sabor.stock_gramos:.0f}g"
        return False, "Sabor no encontrado"

    def reponer_stock_insumo(self, id_insumo, cantidad_unidades):
        insumo = Insumo.query.get(id_insumo)
        if insumo:
            insumo.stock += cantidad_unidades
            db.session.commit()
            return True, f"Stock actualizado. {insumo.nombre}: {insumo.stock} u."
        return False, "Insumo no encontrado"

    def actualizar_precio(self, id_producto, nuevo_precio):
        prod = Producto.query.get(id_producto)
        if prod:
            prod.precio = nuevo_precio
            db.session.commit()
            return True, f"Precio de {prod.nombre} actualizado a ${nuevo_precio}"
        return False, "Producto no encontrado"

    # --- GESTIÓN DE PROMOS ---
    def obtener_items_de_promo(self, promo_id):
        items = ComboItem.query.filter_by(promo_id=promo_id).all()
        resultado = []
        for item in items:
            prod_hijo = Producto.query.get(item.item_id)
            if prod_hijo:
                resultado.append((item, prod_hijo.nombre))
        return resultado

    def agregar_item_a_promo(self, promo_id, item_id, cantidad):
        if int(promo_id) == int(item_id):
            return False, "No puedes agregar la promo dentro de sí misma."
        nuevo_item = ComboItem(promo_id=promo_id, item_id=item_id, cantidad=cantidad)
        db.session.add(nuevo_item)
        db.session.commit()
        return True, "Item agregado a la receta."

    def eliminar_item_de_promo(self, combo_item_id):
        item = ComboItem.query.get(combo_item_id)
        if item:
            db.session.delete(item)
            db.session.commit()
            return True, "Item quitado de la promo."
        return False, "Item no encontrado."

    # --- LÓGICA DE VENTA (CORE) ---
    def procesar_carrito(self, datos_carrito, sucursal="General"):
        items = datos_carrito.get('items', [])
        medio_pago = datos_carrito.get('medio_pago')
        
        if not items:
            return False, "El carrito está vacío."

        total_a_pagar = 0
        descripcion_venta = []

        try:
            for item in items:
                nombre_prod = item['formato']
                sabores_elegidos = item['sabores'] 
                
                producto = Producto.query.filter_by(nombre=nombre_prod).first()
                if not producto:
                    raise Exception(f"Producto {nombre_prod} no existe")

                total_a_pagar += producto.precio
                
                detalle_item = f"{producto.nombre}"
                if sabores_elegidos:
                    detalle_item += f" ({', '.join(sabores_elegidos)})"
                descripcion_venta.append(detalle_item)

                self._descontar_producto_recursivo(producto, sabores_elegidos)

            nueva_venta = Venta(
                fecha=datetime.now(),
                total=total_a_pagar,
                medio_pago=medio_pago,
                detalle="; ".join(descripcion_venta),
                sucursal=sucursal
            )
            db.session.add(nueva_venta)
            db.session.commit()
            
            return True, f"Venta registrada correctamente. Total: ${total_a_pagar}"

        except Exception as e:
            db.session.rollback()
            return False, f"Error: {str(e)}"

    def _descontar_producto_recursivo(self, producto, lista_sabores_elegidos):
        if producto.es_combo:
            items_combo = ComboItem.query.filter_by(promo_id=producto.id).all()
            for comp in items_combo:
                hijo = Producto.query.get(comp.item_id)
                self._descontar_producto_recursivo(hijo, lista_sabores_elegidos)
            return

        if producto.insumo_id:
            insumo = Insumo.query.get(producto.insumo_id)
            if insumo.stock <= 0:
                raise Exception(f"Sin stock de envases: {insumo.nombre}")
            insumo.stock -= 1

        if producto.es_helado and producto.peso_helado > 0:
            if lista_sabores_elegidos:
                peso_por_gusto = producto.peso_helado / len(lista_sabores_elegidos)
                for nombre_sabor in lista_sabores_elegidos:
                    sabor_obj = Sabor.query.filter_by(nombre=nombre_sabor).first()
                    if sabor_obj:
                        if sabor_obj.stock_gramos < peso_por_gusto:
                            raise Exception(f"Stock insuficiente: {sabor_obj.nombre}")
                        sabor_obj.stock_gramos -= peso_por_gusto

    # --- GENERADOR DE REPORTES (CORREGIDO) ---
    def generar_reporte_excel(self, fecha_inicio, fecha_fin):
        print(f"DEBUG EXCEL: Buscando ventas entre {fecha_inicio} y {fecha_fin}")
        
        # 1. DIAGNÓSTICO: Imprimimos qué hay realmente en la base de datos
        todas = Venta.query.all()
        print(f"DEBUG EXCEL: Total de ventas en la DB: {len(todas)}")
        for v in todas:
            print(f" --> Venta ID: {v.id} | Fecha guardada: {v.fecha} | Total: {v.total}")

        # 2. FILTRO SEGURO: Usamos el método 'between' que suele fallar menos
        # Aseguramos que se filtren ventas incluso si la hora difiere un poco
        ventas = Venta.query.filter(Venta.fecha >= fecha_inicio).filter(Venta.fecha <= fecha_fin).all()
        
        print(f"DEBUG EXCEL: Ventas encontradas tras filtrar: {len(ventas)}")

        if not ventas:
            return None

        data_ventas = []
        todos_sabores = []
        total_gramos_vendidos = 0
        mapa_pesos = {p.nombre: p.peso_helado for p in Producto.query.all()}

        for v in ventas:
            items_texto = v.detalle.split(";")
            for item in items_texto:
                item = item.strip()
                nombre_prod = item.split("(")[0].strip()
                if nombre_prod in mapa_pesos:
                    total_gramos_vendidos += mapa_pesos[nombre_prod]
                if "(" in item and ")" in item:
                    contenido = item.split("(")[1].split(")")[0]
                    sabores = [s.strip() for s in contenido.split(",")]
                    todos_sabores.extend(sabores)

            data_ventas.append({
                "Fecha": v.fecha.strftime("%d/%m/%Y"),
                "Hora": v.fecha.strftime("%H:%M"),
                "Sucursal": v.sucursal if v.sucursal else "General",
                "Detalle Completo": v.detalle,
                "Medio Pago": v.medio_pago,
                "Total ($)": v.total
            })

        df_sabores = pd.Series(todos_sabores)
        top_sabores = df_sabores.value_counts().head(3)
        
        df_detalle = pd.DataFrame(data_ventas)
        df_resumen = pd.DataFrame({
            "Métrica": ["Total Recaudado", "Total Kilos Vendidos", "Cant. Ventas", "Top 1 Sabor", "Top 2 Sabor", "Top 3 Sabor"],
            "Valor": [
                f"${sum(v.total for v in ventas)}",
                f"{total_gramos_vendidos / 1000:.2f} kg",
                len(ventas),
                f"{top_sabores.index[0]} ({top_sabores.values[0]})" if len(top_sabores) > 0 else "-",
                f"{top_sabores.index[1]} ({top_sabores.values[1]})" if len(top_sabores) > 1 else "-",
                f"{top_sabores.index[2]} ({top_sabores.values[2]})" if len(top_sabores) > 2 else "-"
            ]
        })

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_resumen.to_excel(writer, sheet_name='Resumen General', index=False)
            df_detalle.to_excel(writer, sheet_name='Detalle Ventas', index=False)
            worksheet = writer.sheets['Detalle Ventas']
            worksheet.column_dimensions['D'].width = 50 
            
        output.seek(0)
        return output