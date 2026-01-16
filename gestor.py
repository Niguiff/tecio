# gestor.py - VERSIÓN FINAL (SISTEMA TECIO)
# Incluye: Recaudación Mensual, Contador Diario y Reporte Excel Estilizado

from models import db, Sabor, Insumo, Producto, Venta, ComboItem, Usuario
from datetime import datetime
from sqlalchemy import extract, func # NECESARIO PARA FILTRAR FECHAS (MES/DÍA)
import pandas as pd
import io
# IMPORTS PARA ESTILO VISUAL DE EXCEL
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

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

    # --- ESTADÍSTICAS INTELIGENTES (NUEVO) ---
    def obtener_recaudacion_mensual(self):
        """Calcula el total vendido SOLO en el mes y año actual."""
        hoy = datetime.now()
        total = db.session.query(db.func.sum(Venta.total)).filter(
            extract('year', Venta.fecha) == hoy.year,
            extract('month', Venta.fecha) == hoy.month
        ).scalar()
        return total if total else 0

    def obtener_cantidad_ventas_hoy(self):
        """Cuenta cuántas ventas se hicieron hoy (ignora la hora, solo fecha)."""
        hoy = datetime.now().date()
        cantidad = Venta.query.filter(func.date(Venta.fecha) == hoy).count()
        return cantidad

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

    def obtener_recaudacion_total_historica(self):
        # Esta función queda por si alguna vez quieres ver el histórico total
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
                
                # Construir detalle simple para la base de datos
                detalle_item = f"{producto.nombre}"
                if sabores_elegidos:
                    detalle_item += f" ({', '.join(sabores_elegidos)})"
                descripcion_venta.append(detalle_item)

                # Descontar stock
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

    # --- REPORTE EXCEL AVANZADO (TIPO FACTURA DETALLADA) ---
    def generar_reporte_excel(self, fecha_inicio, fecha_fin):
        print(f"Generando reporte detallado entre {fecha_inicio} y {fecha_fin}")
        
        # 1. Obtener ventas filtradas
        ventas = Venta.query.filter(Venta.fecha >= fecha_inicio).filter(Venta.fecha <= fecha_fin).all()

        if not ventas:
            return None

        # 2. Mapa de Precios
        mapa_precios = {p.nombre: p.precio for p in Producto.query.all()}
        
        data_detalle = []
        gran_total = 0

        for v in ventas:
            items_texto = v.detalle.split(";")
            
            # --- FILAS DE ITEMS ---
            for item_raw in items_texto:
                item_raw = item_raw.strip()
                if not item_raw: continue

                # Separar "Nombre Producto" de "Sabores"
                if "(" in item_raw and ")" in item_raw:
                    parts = item_raw.split("(")
                    nombre_prod = parts[0].strip()
                    gustos = parts[1].replace(")", "").strip()
                else:
                    nombre_prod = item_raw
                    gustos = "-"

                precio_unitario = mapa_precios.get(nombre_prod, 0)
                
                fila_item = {
                    "Fecha": v.fecha.strftime("%d/%m/%Y"),
                    "Hora": v.fecha.strftime("%H:%M"),
                    "Sucursal": v.sucursal if v.sucursal else "General",
                    "Envases (Item)": nombre_prod,
                    "Sabores / Detalle": gustos,
                    "Medio Pago": v.medio_pago,
                    "Total ($)": precio_unitario,
                    "Tipo Fila": "Item"
                }
                data_detalle.append(fila_item)
            
            # --- FILA DE SUBTOTAL ---
            fila_subtotal = {
                "Fecha": "",
                "Hora": "",
                "Sucursal": "",
                "Envases (Item)": "SUBTOTAL VENTA",
                "Sabores / Detalle": "",
                "Medio Pago": "",
                "Total ($)": v.total,
                "Tipo Fila": "Subtotal"
            }
            data_detalle.append(fila_subtotal)
            gran_total += v.total

        # --- FILA FINAL DE GRAN TOTAL ---
        fila_final = {
            "Fecha": "", "Hora": "", "Sucursal": "",
            "Envases (Item)": "TOTAL RECAUDADO", "Sabores / Detalle": "",
            "Medio Pago": "", "Total ($)": gran_total,
            "Tipo Fila": "GranTotal"
        }
        data_detalle.append(fila_final)

        # 3. Crear DataFrame y Estilizar con OpenPyXL
        df = pd.DataFrame(data_detalle)
        
        tipos_fila = df["Tipo Fila"].tolist() 
        df = df.drop(columns=["Tipo Fila"])

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Detalle Caja', index=False)
            
            workbook = writer.book
            ws = writer.sheets['Detalle Caja']

            # --- ESTILOS VISUALES ---
            borde_fino = Side(border_style="thin", color="000000")
            borde_cuadro = Border(left=borde_fino, right=borde_fino, top=borde_fino, bottom=borde_fino)
            
            fill_header = PatternFill(start_color="FFC000", end_color="FFC000", fill_type="solid") # Naranja
            fill_subtotal = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid") # Verde Claro
            fill_total = PatternFill(start_color="A9D08E", end_color="A9D08E", fill_type="solid") # Verde Oscuro
            
            font_header = Font(bold=True, color="000000")
            font_bold = Font(bold=True)

            # 1. Formatear Encabezados
            for cell in ws[1]:
                cell.fill = fill_header
                cell.font = font_header
                cell.alignment = Alignment(horizontal='center')
                cell.border = borde_cuadro

            # 2. Formatear Filas
            for i, tipo in enumerate(tipos_fila):
                row_idx = i + 2 
                
                for col in range(1, 8):
                    cell = ws.cell(row=row_idx, column=col)
                    cell.border = borde_cuadro
                    if col == 7: 
                        cell.number_format = '$ #,##0'

                if tipo == "Subtotal":
                    for col in range(1, 8):
                        ws.cell(row=row_idx, column=col).fill = fill_subtotal
                        ws.cell(row=row_idx, column=col).font = font_bold
                    ws.cell(row=row_idx, column=4).alignment = Alignment(horizontal='right')

                elif tipo == "GranTotal":
                    for col in range(1, 8):
                        celda = ws.cell(row=row_idx, column=col)
                        celda.fill = fill_total
                        celda.font = Font(bold=True, size=12)
                    ws.cell(row=row_idx, column=4).alignment = Alignment(horizontal='right')

            # 3. Anchos de columna
            ws.column_dimensions['A'].width = 12
            ws.column_dimensions['B'].width = 8
            ws.column_dimensions['C'].width = 15
            ws.column_dimensions['D'].width = 25
            ws.column_dimensions['E'].width = 40
            ws.column_dimensions['F'].width = 12
            ws.column_dimensions['G'].width = 15

        output.seek(0)
        return output