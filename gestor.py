# gestor.py
# ---------------------------------------------------------
# IMPORTANTE: Aquí agregamos 'Usuario' al final de la lista
# ---------------------------------------------------------
from models import db, Sabor, Insumo, Producto, Venta, ComboItem, Usuario
from datetime import datetime
import pandas as pd
import io

class HeladeriaManager:
    # --- CONSULTAS DE DATOS (READ) ---
    def obtener_sabores(self):
        # Devuelve solo los activos
        return Sabor.query.filter_by(activo=True).all()

    def obtener_productos(self):
        return Producto.query.all()
    
    def obtener_insumos(self):
        return Insumo.query.all()

    def obtener_ventas(self):
        # Devuelve todas las ventas (para el admin)
        return Venta.query.all()

    # --- (NUEVO) GESTIÓN DE USUARIOS ---
    def obtener_usuarios(self):
        return Usuario.query.all()

    def crear_usuario(self, username, password, rol, sucursal):
        # Validar que no exista
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

    # --- LÓGICA DE VENTA (CORE) ---
    def procesar_carrito(self, datos_carrito, sucursal="General"):
        """
        Procesa la venta, descuenta stock (insumos y helado) y guarda el registro.
        Recibe 'sucursal' para identificar desde dónde se vende.
        """
        items = datos_carrito.get('items', [])
        medio_pago = datos_carrito.get('medio_pago')
        
        if not items:
            return False, "El carrito está vacío."

        total_a_pagar = 0
        descripcion_venta = []

        try:
            for item in items:
                nombre_prod = item['formato']
                sabores_elegidos = item['sabores'] # Lista de nombres de sabores
                
                producto = Producto.query.filter_by(nombre=nombre_prod).first()
                if not producto:
                    raise Exception(f"Producto {nombre_prod} no existe")

                total_a_pagar += producto.precio
                
                # Construir detalle legible: "1 kg (Choco, Vainilla)"
                detalle_item = f"{producto.nombre}"
                if sabores_elegidos:
                    detalle_item += f" ({', '.join(sabores_elegidos)})"
                descripcion_venta.append(detalle_item)

                # Descontar stock (Maneja combos, insumos y gramos)
                self._descontar_producto_recursivo(producto, sabores_elegidos)

            # Crear el registro de venta
            nueva_venta = Venta(
                fecha=datetime.now(),
                total=total_a_pagar,
                medio_pago=medio_pago,
                detalle="; ".join(descripcion_venta),
                sucursal=sucursal  # Guardamos la sucursal del usuario
            )
            db.session.add(nueva_venta)
            db.session.commit()
            
            return True, f"Venta registrada correctamente. Total: ${total_a_pagar}"

        except Exception as e:
            db.session.rollback() # Si algo falla (ej: falta stock), no se guarda nada
            return False, f"Error: {str(e)}"

    def _descontar_producto_recursivo(self, producto, lista_sabores_elegidos):
        """
        Función auxiliar recursiva.
        1. Si es Combo: Busca sus componentes y se llama a sí misma para cada uno.
        2. Si es Simple: Descuenta el insumo (envase) y los gramos de helado.
        """
        
        # CASO A: ES UNA PROMO (COMBO)
        if producto.es_combo:
            items_combo = ComboItem.query.filter_by(promo_id=producto.id).all()
            for comp in items_combo:
                hijo = Producto.query.get(comp.item_id)
                # Recursividad: Si el combo tiene helado, usamos los sabores elegidos para descontar
                self._descontar_producto_recursivo(hijo, lista_sabores_elegidos)
            return

        # CASO B: ES UN PRODUCTO SIMPLE
        
        # 1. Descontar Insumo (Envase)
        if producto.insumo_id:
            insumo = Insumo.query.get(producto.insumo_id)
            if insumo.stock <= 0:
                raise Exception(f"Sin stock de envases: {insumo.nombre}")
            insumo.stock -= 1

        # 2. Descontar Helado (Gramos)
        if producto.es_helado and producto.peso_helado > 0:
            if not lista_sabores_elegidos:
                # Si es un producto de helado pero viene sin gustos, no descontamos gramos
                pass 
            else:
                peso_por_gusto = producto.peso_helado / len(lista_sabores_elegidos)
                
                for nombre_sabor in lista_sabores_elegidos:
                    sabor_obj = Sabor.query.filter_by(nombre=nombre_sabor).first()
                    if not sabor_obj:
                        continue 
                    
                    if sabor_obj.stock_gramos < peso_por_gusto:
                        raise Exception(f"Stock insuficiente de {sabor_obj.nombre}. Faltan {peso_por_gusto - sabor_obj.stock_gramos:.0f}g")
                    
                    sabor_obj.stock_gramos -= peso_por_gusto

    # --- GENERADOR DE REPORTES (EXCEL) ---
    def generar_reporte_excel(self, fecha_inicio, fecha_fin):
        # 1. Obtener ventas filtradas por fecha
        ventas = Venta.query.filter(Venta.fecha >= fecha_inicio, Venta.fecha <= fecha_fin).all()
        
        if not ventas:
            return None

        data_ventas = []
        todos_sabores = []
        total_gramos_vendidos = 0
        
        # Mapa para saber cuánto pesa cada producto y sumar kilos totales
        mapa_pesos = {p.nombre: p.peso_helado for p in Producto.query.all()}

        for v in ventas:
            # Analizar el detalle de texto para extraer estadísticas
            items_texto = v.detalle.split(";")
            
            for item in items_texto:
                item = item.strip()
                nombre_prod = item.split("(")[0].strip()
                
                # Sumar Kilos
                if nombre_prod in mapa_pesos:
                    total_gramos_vendidos += mapa_pesos[nombre_prod]

                # Extraer Sabores para el Ranking
                if "(" in item and ")" in item:
                    contenido = item.split("(")[1].split(")")[0]
                    sabores = [s.strip() for s in contenido.split(",")]
                    todos_sabores.extend(sabores)

            # Fila para la hoja "Detalle"
            data_ventas.append({
                "Fecha": v.fecha.strftime("%d/%m/%Y"),
                "Hora": v.fecha.strftime("%H:%M"),
                "Sucursal": v.sucursal if v.sucursal else "General",
                "Detalle Completo": v.detalle,
                "Medio Pago": v.medio_pago,
                "Total ($)": v.total
            })

        # 2. Calcular Top 3 Sabores con Pandas
        df_sabores = pd.Series(todos_sabores)
        top_sabores = df_sabores.value_counts().head(3)
        
        # 3. Crear DataFrames
        df_detalle = pd.DataFrame(data_ventas)

        # --- GESTIÓN DE PROMOS (NUEVO) ---
    def obtener_items_de_promo(self, promo_id):
        # Devuelve una lista de tuplas: (ObjetoComboItem, NombreProductoHijo)
        # Esto es necesario para mostrar el nombre en la pantalla
        items = ComboItem.query.filter_by(promo_id=promo_id).all()
        resultado = []
        for item in items:
            prod_hijo = Producto.query.get(item.item_id)
            if prod_hijo:
                resultado.append((item, prod_hijo.nombre))
        return resultado

    def agregar_item_a_promo(self, promo_id, item_id, cantidad):
        # Evitar meter la promo dentro de sí misma (bucle infinito)
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
        
        # Hoja Resumen
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