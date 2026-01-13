# app.py
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, Usuario, Sabor, Insumo, Producto, Venta
from gestor import HeladeriaManager
from datetime import datetime
import io
import pandas as pd

app = Flask(__name__)
app.secret_key = 'helado_secreto_super_seguro'

# DB Config
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///heladeria.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
gestor = HeladeriaManager()

# --- CONFIGURACIÓN LOGIN ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' # Si no estás logueado, te manda acá

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

# --- HELPERS ---
def clasificar_sabores(lista_sabores):
    # (Tu función de clasificar sabores igual que antes...)
    grupos = {"🍫 Chocolates": [], "🍯 Dulces de Leche": [], "🍓 Frutales": [], "🍦 Cremas y Otros": []}
    for s in lista_sabores:
        nombre = s.nombre.lower()
        if "chocolate" in nombre or "cacao" in nombre: grupos["🍫 Chocolates"].append(s)
        elif "dulce de leche" in nombre: grupos["🍯 Dulces de Leche"].append(s)
        elif any(x in nombre for x in ["fruti", "limon", "anana", "durazno", "cereza"]): grupos["🍓 Frutales"].append(s)
        else: grupos["🍦 Cremas y Otros"].append(s)
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
        # Inyectamos la sucursal del usuario actual al gestor
        exito, mensaje = gestor.procesar_carrito(datos, sucursal=current_user.sucursal)
        if exito: return jsonify({"status": "ok", "msg": mensaje})
        else: return jsonify({"status": "error", "msg": mensaje}), 400

    sabores_agrupados = clasificar_sabores(gestor.obtener_sabores())
    return render_template('vender.html', productos=gestor.obtener_productos(), sabores_agrupados=sabores_agrupados, sucursal=current_user.sucursal)

# --- RUTAS DE ADMINISTRADOR ---

@app.route('/admin')
@login_required
def admin_dashboard():
    if current_user.rol != 'admin': return redirect(url_for('vender'))
    
    # Calcular totales
    total_gral = gestor.obtener_recaudacion_total()
    ventas = Venta.query.order_by(Venta.fecha.desc()).limit(50).all() # Últimas 50
    
    return render_template('admin_dashboard.html', 
                           recaudacion=total_gral, 
                           ventas=ventas)

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
            # LÓGICA DE 1 BALDE = 6 KG
            gramos = baldes * 6000 
            gestor.reponer_stock_sabor(nombre, gramos)
            flash(f"Se agregaron {baldes} baldes ({gramos/1000}kg) a {nombre}")
            
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
            flash("Stock de insumo actualizado")
            
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
    # Seguridad: Solo admin puede entrar aquí
    if current_user.rol != 'admin': 
        return redirect(url_for('vender'))
    
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
            
            # Evitar que el admin se borre a sí mismo por error
            if id_borrar == current_user.id:
                flash("⚠️ No puedes eliminar tu propio usuario mientras estás logueado.")
            else:
                exito, msg = gestor.eliminar_usuario(id_borrar)
                flash(msg)

    return render_template('admin_usuarios.html', usuarios=gestor.obtener_usuarios())

# REPORTE EXCEL (Ruta dedicada)
@app.route('/admin/reporte', methods=['POST'])
@login_required
def descargar_reporte():
    if current_user.rol != 'admin': return redirect(url_for('vender'))
    
    inicio = datetime.strptime(request.form.get('fecha_inicio'), '%Y-%m-%d')
    fin = datetime.strptime(request.form.get('fecha_fin'), '%Y-%m-%d').replace(hour=23, minute=59)
    
    archivo = gestor.generar_reporte_excel(inicio, fin)
    if archivo:
        return send_file(archivo, as_attachment=True, download_name=f"Reporte_{inicio.date()}.xlsx", mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    flash("No hay ventas en esas fechas")
    return redirect(url_for('admin_dashboard'))

# GESTIÓN DE PROMOS (CONFIGURADOR)
@app.route('/admin/promos', methods=['GET', 'POST'])
@login_required
def gestion_promos():
    if current_user.rol != 'admin': return redirect(url_for('vender'))
    
    # 1. Obtener lista de PROMOS para el selector
    promos_disponibles = Producto.query.filter_by(es_combo=True).all()
    # 2. Obtener lista de PRODUCTOS para agregar (Hijos)
    productos_disponibles = Producto.query.all() # Podrías filtrar para no mostrar otras promos
    
    promo_seleccionada = None
    items_actuales = []

    # Si seleccionaron una promo para editar (viene por URL ?id=...)
    id_seleccionado = request.args.get('id_promo')
    
    if request.method == 'POST':
        accion = request.form.get('accion')
        id_promo_form = request.form.get('id_promo_actual')
        
        if accion == 'agregar_item':
            id_prod_hijo = request.form.get('id_producto_hijo')
            cantidad = request.form.get('cantidad')
            exito, msg = gestor.agregar_item_a_promo(id_promo_form, id_prod_hijo, cantidad)
            flash(msg)
            return redirect(url_for('gestion_promos', id_promo=id_promo_form)) # Recargar misma promo

        elif accion == 'eliminar_item':
            id_combo_item = request.form.get('id_combo_item')
            exito, msg = gestor.eliminar_item_de_promo(id_combo_item)
            flash(msg)
            return redirect(url_for('gestion_promos', id_promo=id_promo_form))

    # Si hay una promo seleccionada, cargamos sus datos
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