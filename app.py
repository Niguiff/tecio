# app.py - VERSIÓN COMPLETA CON DIAGNÓSTICO DE ERRORES
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, Usuario, Sabor, Insumo, Producto, Venta
from gestor import HeladeriaManager
from datetime import datetime
import io
import pandas as pd

app = Flask(__name__)
app.secret_key = 'helado_secreto_super_seguro'

# --- CONFIGURACIÓN BASE DE DATOS ---
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///heladeria.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
gestor = HeladeriaManager()

# --- CONFIGURACIÓN LOGIN ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

# --- HELPER: Función para agrupar sabores (Diseño Móvil) ---
def clasificar_sabores(lista_sabores):
    grupos = {
        "🍫 Chocolates": [],
        "🍯 Dulces de Leche": [],
        "🍓 Frutales": [],
        "🍦 Cremas y Otros": []
    }
    
    for s in lista_sabores:
        nombre = s.nombre.lower()
        if "chocolate" in nombre or "cacao" in nombre:
            grupos["🍫 Chocolates"].append(s)
        elif "dulce de leche" in nombre:
            grupos["🍯 Dulces de Leche"].append(s)
        elif any(x in nombre for x in ["fruti", "limon", "anana", "durazno", "cereza", "banana", "manzana", "maracuya", "naranja", "melon"]):
            grupos["🍓 Frutales"].append(s)
        else:
            grupos["🍦 Cremas y Otros"].append(s)
    return grupos

# --- RUTAS DE ACCESO ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form.get('username')
        pwd = request.form.get('password')
        usuario_db = Usuario.query.filter_by(username=user).first()
        
        if usuario_db and usuario_db.password == pwd:
            login_user(usuario_db)
            if usuario_db.rol == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('vender'))
        else:
            flash("Usuario o contraseña incorrectos")
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
def index():
    return redirect(url_for('login'))

# --- RUTA DE VENTA (SUCURSALES) ---
@app.route('/vender', methods=['GET', 'POST'])
@login_required
def vender():
    if request.is_json:
        datos = request.get_json()
        # Inyectamos la sucursal del usuario actual
        exito, mensaje = gestor.procesar_carrito(datos, sucursal=current_user.sucursal)
        
        if exito:
            return jsonify({"status": "ok", "msg": mensaje})
        else:
            return jsonify({"status": "error", "msg": mensaje}), 400

    lista_sabores = gestor.obtener_sabores()
    sabores_agrupados = clasificar_sabores(lista_sabores)
    return render_template('vender.html', 
                           productos=gestor.obtener_productos(), 
                           sabores_agrupados=sabores_agrupados,
                           sucursal=current_user.sucursal)

# --- RUTAS DE ADMINISTRADOR ---

# EN APP.PY, BUSCA ESTA FUNCIÓN Y REEMPLÁZALA
@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin_dashboard():
    if current_user.rol != 'admin': return redirect(url_for('vender'))
    
    # 1. Obtener Recaudación del Mes actual
    total_mes = gestor.obtener_recaudacion_mensual()
    
    # 2. Obtener Cantidad de ventas de HOY
    ventas_hoy_count = gestor.obtener_cantidad_ventas_hoy()
    
    # 3. Calcular nombre del mes en español
    nombres_meses = {
        1: "ENERO", 2: "FEBRERO", 3: "MARZO", 4: "ABRIL",
        5: "MAYO", 6: "JUNIO", 7: "JULIO", 8: "AGOSTO",
        9: "SEPTIEMBRE", 10: "OCTUBRE", 11: "NOVIEMBRE", 12: "DICIEMBRE"
    }
    mes_actual_nombre = nombres_meses[datetime.now().month]
    titulo_recaudacion = f"RECAUDACIÓN {mes_actual_nombre}"

    # Últimas ventas para tabla
    ventas = Venta.query.order_by(Venta.fecha.desc()).limit(50).all() 
    
    return render_template('admin_dashboard.html', 
                           recaudacion=total_mes,
                           titulo_recaudacion=titulo_recaudacion, # Enviamos el título dinámico
                           cantidad_ventas_hoy=ventas_hoy_count, # Enviamos el contador arreglado
                           ventas=ventas)

# RUTA ESPECIAL PARA DESCARGAR REPORTE (MODIFICADA CON MODO DETECTIVE)
@app.route('/admin/reporte', methods=['POST'])
@login_required
def descargar_reporte():
    if current_user.rol != 'admin': return redirect(url_for('vender'))
    
    try:
        print("--- INICIANDO DESCARGA DE REPORTE ---")
        fecha_inicio_str = request.form.get('fecha_inicio')
        fecha_fin_str = request.form.get('fecha_fin')
        
        print(f"Fechas recibidas: {fecha_inicio_str} al {fecha_fin_str}")

        # Convertir texto a fecha
        inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d')
        # Al fin del día le ponemos 23:59:59
        fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59)

        print("Generando Excel en gestor...")
        archivo_excel = gestor.generar_reporte_excel(inicio, fin)
        
        if archivo_excel:
            print("Excel generado OK. Enviando archivo...")
            nombre_archivo = f"Reporte_{fecha_inicio_str}.xlsx"
            return send_file(
                archivo_excel,
                as_attachment=True,
                download_name=nombre_archivo,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
        else:
            print("Gestor devolvió None (Sin datos)")
            flash("⚠️ No se encontraron ventas en ese rango de fechas.")
            return redirect(url_for('admin_dashboard'))

    except Exception as e:
        # AQUÍ CAPTURAMOS EL ERROR REAL
        error_msg = f"❌ ERROR AL DESCARGAR: {str(e)}"
        print(error_msg)
        flash(error_msg) # Esto saldrá en rojo en tu pantalla
        return redirect(url_for('admin_dashboard'))

# GESTIÓN DE SABORES
@app.route('/admin/sabores', methods=['GET', 'POST'])
@login_required
def gestion_sabores():
    if current_user.rol != 'admin': return redirect(url_for('vender'))
    
    if request.method == 'POST':
        accion = request.form.get('accion')
        
        if accion == 'agregar_stock':
            nombre = request.form.get('sabor_nombre')
            baldes = float(request.form.get('cant_baldes'))
            gramos = baldes * 6000 # 1 Balde = 6kg
            gestor.reponer_stock_sabor(nombre, gramos)
            flash(f"Se agregaron {baldes} baldes a {nombre}")
            
        elif accion == 'crear_sabor':
            nuevo = request.form.get('nuevo_nombre')
            db.session.add(Sabor(nombre=nuevo, stock_gramos=0))
            db.session.commit()
            flash(f"Sabor {nuevo} creado.")

        elif accion == 'eliminar_sabor':
            id_borrar = request.form.get('id_sabor')
            Sabor.query.filter_by(id=id_borrar).delete()
            db.session.commit()
            flash("Sabor eliminado.")

    return render_template('admin_sabores.html', sabores=gestor.obtener_sabores())

# GESTIÓN DE INSUMOS
@app.route('/admin/insumos', methods=['GET', 'POST'])
@login_required
def gestion_insumos():
    if current_user.rol != 'admin': return redirect(url_for('vender'))
    
    if request.method == 'POST':
        accion = request.form.get('accion')
        if accion == 'reponer':
            id_ins = int(request.form.get('id_insumo'))
            cant = int(request.form.get('cantidad'))
            gestor.reponer_stock_insumo(id_ins, cant)
            flash("Stock actualizado")
        elif accion == 'crear':
            nombre = request.form.get('nuevo_nombre')
            db.session.add(Insumo(nombre=nombre, stock=0))
            db.session.commit()
            flash("Insumo creado")

    return render_template('admin_insumos.html', insumos=gestor.obtener_insumos())

# GESTIÓN DE PRECIOS
@app.route('/admin/precios', methods=['GET', 'POST'])
@login_required
def gestion_precios():
    if current_user.rol != 'admin': return redirect(url_for('vender'))
    
    if request.method == 'POST':
        id_prod = int(request.form.get('id_producto'))
        precio_nuevo = float(request.form.get('nuevo_precio'))
        gestor.actualizar_precio(id_prod, precio_nuevo)
        flash("Precio actualizado")

    return render_template('admin_precios.html', productos=gestor.obtener_productos())

# GESTIÓN DE USUARIOS
@app.route('/admin/usuarios', methods=['GET', 'POST'])
@login_required
def gestion_usuarios():
    if current_user.rol != 'admin': return redirect(url_for('vender'))
    
    if request.method == 'POST':
        accion = request.form.get('accion')
        
        if accion == 'crear_usuario':
            user = request.form.get('username')
            pwd = request.form.get('password')
            rol = request.form.get('rol')
            sucursal = request.form.get('sucursal')
            exito, msg = gestor.crear_usuario(user, pwd, rol, sucursal)
            flash(msg)

        elif accion == 'eliminar_usuario':
            id_borrar = int(request.form.get('user_id'))
            if id_borrar == current_user.id:
                flash("⚠️ No puedes eliminarte a ti mismo.")
            else:
                exito, msg = gestor.eliminar_usuario(id_borrar)
                flash(msg)

    return render_template('admin_usuarios.html', usuarios=gestor.obtener_usuarios())

# GESTIÓN DE PROMOS (CONFIGURADOR)
@app.route('/admin/promos', methods=['GET', 'POST'])
@login_required
def gestion_promos():
    if current_user.rol != 'admin': return redirect(url_for('vender'))
    
    promos_disponibles = Producto.query.filter_by(es_combo=True).all()
    productos_disponibles = Producto.query.all()
    
    promo_seleccionada = None
    items_actuales = []

    id_seleccionado = request.args.get('id_promo')
    
    if request.method == 'POST':
        accion = request.form.get('accion')
        id_promo_form = request.form.get('id_promo_actual')
        
        if accion == 'agregar_item':
            id_prod_hijo = request.form.get('id_producto_hijo')
            cantidad = request.form.get('cantidad')
            exito, msg = gestor.agregar_item_a_promo(id_promo_form, id_prod_hijo, cantidad)
            flash(msg)
            return redirect(url_for('gestion_promos', id_promo=id_promo_form))

        elif accion == 'eliminar_item':
            id_combo_item = request.form.get('id_combo_item')
            exito, msg = gestor.eliminar_item_de_promo(id_combo_item)
            flash(msg)
            return redirect(url_for('gestion_promos', id_promo=id_promo_form))

    if id_seleccionado:
        promo_seleccionada = Producto.query.get(id_seleccionado)
        items_actuales = gestor.obtener_items_de_promo(id_seleccionado)

    return render_template('admin_promos.html', 
                           promos=promos_disponibles,
                           productos=productos_disponibles,
                           promo_actual=promo_seleccionada,
                           items=items_actuales)

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)