from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from datetime import datetime
from sqlalchemy import func

# Importamos nuestros modelos (Incluida la nueva CierreCaja) y el gestor
from models import db, Usuario, Venta, Producto, Insumo, Sabor, ComboItem, CierreCaja
from gestor import HeladeriaManager

# --- CONFIGURACIÓN INICIAL ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'tu_clave_secreta_super_segura' 
# Timeout agregado para evitar bloqueos en Google Drive/OneDrive
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///heladeria.db?timeout=15' 
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inicializar Extensiones
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Instancia del Gestor
gestor = HeladeriaManager()

# --- GESTIÓN DE SESIÓN ---
@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.rol == 'admin':
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('vender'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = Usuario.query.filter_by(username=username).first()
        
        if user and user.password == password:
            login_user(user)
            if user.rol == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('vender'))
        else:
            flash('Usuario o contraseña incorrectos')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- ÁREA DE VENTAS (POS) ---
@app.route('/vender', methods=['GET', 'POST'])
@login_required
def vender():
    if request.method == 'POST':
        data = request.get_json()
        sucursal_actual = current_user.sucursal 
        if not sucursal_actual: sucursal_actual = "General"

        exito, mensaje = gestor.procesar_carrito(data, sucursal=sucursal_actual)
        
        if exito:
            return jsonify({'success': True, 'msg': mensaje})
        else:
            return jsonify({'success': False, 'msg': mensaje}), 400

    sabores = gestor.obtener_sabores_venta()
    productos = gestor.obtener_productos()
    return render_template('vender.html', sabores=sabores, productos=productos, vendedor=current_user)

# --- PANEL DEL VENDEDOR (MI CAJA) ---
@app.route('/mi_caja')
@login_required
def panel_vendedor():
    if current_user.rol != 'vendedor': return redirect(url_for('admin_dashboard'))
    
    mi_sucursal = current_user.sucursal
    
    # Usamos la lógica de turnos para que coincida con el cierre del admin
    ventas_turno = gestor.obtener_ventas_turno_actual(mi_sucursal)
    
    # Ordenamos visualmente: lo más reciente arriba
    ventas_turno.sort(key=lambda x: x.fecha, reverse=True)
    
    # Cálculos sobre ese turno específico
    total_recaudado = sum(v.total for v in ventas_turno)
    cantidad_ventas = len(ventas_turno)
    
    ventas_efectivo = [v for v in ventas_turno if v.medio_pago == 'Efectivo']
    total_efectivo = sum(v.total for v in ventas_efectivo)
    cantidad_efectivo = len(ventas_efectivo)
    
    return render_template('panel_vendedor.html', sucursal=mi_sucursal, ventas=ventas_turno, total_recaudado=total_recaudado, cantidad_ventas=cantidad_ventas, total_efectivo=total_efectivo, cantidad_efectivo=cantidad_efectivo)

# --- DASHBOARD ADMIN (ACTUALIZADO CON DESGLOSE PARA MODAL) ---
@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin_dashboard():
    if current_user.rol != 'admin': return redirect(url_for('vender'))
    
    # 1. MÁXIMO PAZ: Ventas y Desglose
    ventas_mp = gestor.obtener_ventas_turno_actual("Máximo Paz")
    total_mp = sum(v.total for v in ventas_mp)
    count_mp = len(ventas_mp)
    # Calculamos desglose para el modal (Efectivo vs Digital)
    efectivo_mp = sum(v.total for v in ventas_mp if v.medio_pago == 'Efectivo')
    digital_mp = total_mp - efectivo_mp 

    # 2. TRISTÁN SUÁREZ: Ventas y Desglose
    ventas_ts = gestor.obtener_ventas_turno_actual("Tristán Suárez")
    total_ts = sum(v.total for v in ventas_ts)
    count_ts = len(ventas_ts)
    # Calculamos desglose para el modal
    efectivo_ts = sum(v.total for v in ventas_ts if v.medio_pago == 'Efectivo')
    digital_ts = total_ts - efectivo_ts

    # Globales
    total_global_turno = total_mp + total_ts
    count_global_turno = count_mp + count_ts

    # Historial reciente
    ultimas_ventas = Venta.query.order_by(Venta.fecha.desc()).limit(10).all()

    # Mes actual
    nombres_meses = {1:"ENERO", 2:"FEBRERO", 3:"MARZO", 4:"ABRIL", 5:"MAYO", 6:"JUNIO", 7:"JULIO", 8:"AGOSTO", 9:"SEPTIEMBRE", 10:"OCTUBRE", 11:"NOVIEMBRE", 12:"DICIEMBRE"}
    mes_actual = nombres_meses[datetime.now().month]

    return render_template('admin_dashboard.html',
                           mes_actual=mes_actual,
                           total_global=total_global_turno,
                           count_global=count_global_turno,
                           # Datos MP
                           total_mp=total_mp, count_mp=count_mp,
                           efectivo_mp=efectivo_mp, digital_mp=digital_mp,
                           # Datos TS
                           total_ts=total_ts, count_ts=count_ts,
                           efectivo_ts=efectivo_ts, digital_ts=digital_ts,
                           # Extras
                           ventas=ultimas_ventas)

# --- PROCESAR CIERRE DE CAJA (BOTONES ROJOS) ---
@app.route('/admin/cerrar-caja', methods=['POST'])
@login_required
def procesar_cierre():
    if current_user.rol != 'admin': return redirect(url_for('vender'))
    
    sucursal = request.form.get('sucursal')
    if sucursal:
        exito, msg = gestor.cerrar_caja_sucursal(sucursal)
        flash(msg)
    
    return redirect(url_for('admin_dashboard'))

# --- GESTIÓN SABORES ---
@app.route('/admin/sabores', methods=['GET', 'POST'])
@login_required
def gestion_sabores():
    if current_user.rol != 'admin': return redirect(url_for('vender'))
    
    if request.method == 'POST':
        accion = request.form.get('accion')
        
        if accion == 'crear':
            nombre = request.form.get('nombre')
            nuevo_sabor = Sabor(nombre=nombre, stock_maximo=0, stock_tristan=0)
            db.session.add(nuevo_sabor)
            db.session.commit()
            flash(f"Sabor {nombre} creado.")

        elif accion == 'agregar_stock':
            nombre = request.form.get('sabor_nombre')
            baldes = float(request.form.get('cant_baldes'))
            sucursal = request.form.get('sucursal_destino') 
            gramos = baldes * 6000 
            exito, msg = gestor.reponer_stock_sabor(nombre, gramos, sucursal)
            flash(msg if exito else "Error al reponer stock.")

        elif accion == 'corregir_stock':
            nombre = request.form.get('sabor_nombre')
            baldes_reales = float(request.form.get('cant_baldes_real'))
            sucursal = request.form.get('sucursal_destino')
            exito, msg = gestor.corregir_stock_manual(nombre, baldes_reales, sucursal)
            flash(msg)

        elif accion == 'cambiar_estado':
            nombre = request.form.get('sabor_nombre')
            sabor = Sabor.query.filter_by(nombre=nombre).first()
            if sabor:
                sabor.activo = not sabor.activo
                db.session.commit()
    
    sabores = gestor.obtener_todos_sabores()
    return render_template('admin_sabores.html', sabores=sabores)

# --- GESTIÓN INSUMOS ---
@app.route('/admin/insumos', methods=['GET', 'POST'])
@login_required
def gestion_insumos():
    if current_user.rol != 'admin': return redirect(url_for('vender'))

    if request.method == 'POST':
        accion = request.form.get('accion')

        if accion == 'reponer':
            id_insumo = request.form.get('id_insumo')
            cantidad = int(request.form.get('cantidad'))
            sucursal = request.form.get('sucursal_destino')
            exito, msg = gestor.reponer_stock_insumo(id_insumo, cantidad, sucursal)
            flash(msg)
        
        elif accion == 'crear':
            nombre = request.form.get('nombre')
            nuevo_insumo = Insumo(nombre=nombre, stock_maximo=0, stock_tristan=0)
            db.session.add(nuevo_insumo)
            db.session.commit()
            flash(f"Insumo '{nombre}' creado.")

        elif accion == 'eliminar':
            id_insumo = request.form.get('id_insumo')
            insumo = Insumo.query.get(id_insumo)
            if insumo:
                try:
                    db.session.delete(insumo)
                    db.session.commit()
                    flash(f"Insumo '{insumo.nombre}' eliminado.")
                except Exception as e:
                    db.session.rollback()
                    flash("No se puede eliminar: está asociado a un producto activo.")

    insumos = gestor.obtener_insumos()
    return render_template('admin_insumos.html', insumos=insumos)

# --- GESTIÓN PRECIOS (ABM + COMBOS) ---
@app.route('/admin/precios', methods=['GET', 'POST'])
@login_required
def gestion_precios():
    if current_user.rol != 'admin': return redirect(url_for('vender'))
    insumos = gestor.obtener_insumos()
    
    todos_los_productos = Producto.query.filter_by(es_combo=False).all()

    if request.method == 'POST':
        accion = request.form.get('accion')
        
        if accion == 'actualizar_precio':
            id_prod = request.form.get('id_producto')
            nuevo_precio = float(request.form.get('nuevo_precio'))
            gestor.actualizar_precio(id_prod, nuevo_precio)
            flash("Precio actualizado.")

        elif accion == 'eliminar':
            id_prod = request.form.get('id_producto')
            prod = Producto.query.get(id_prod)
            
            if prod and prod.es_combo:
                ComboItem.query.filter_by(promo_id=prod.id).delete()
                
            if prod:
                db.session.delete(prod)
                db.session.commit()
                flash(f"Producto '{prod.nombre}' eliminado.")
        
        elif accion == 'crear':
            nombre = request.form.get('nombre')
            precio = float(request.form.get('precio'))
            tipo = request.form.get('tipo') 
            
            if tipo == 'combo':
                nuevo_prod = Producto(
                    nombre=nombre, 
                    precio=precio, 
                    es_helado=True, 
                    es_combo=True, 
                    peso_helado=0 
                )
                db.session.add(nuevo_prod)
                db.session.flush()

                componentes = request.form.getlist('componentes') 
                for item_id in componentes:
                    cantidad = int(request.form.get(f'cantidad_{item_id}', 1))
                    if cantidad > 0:
                        db.session.add(ComboItem(promo_id=nuevo_prod.id, item_id=item_id, cantidad=cantidad))
                
                db.session.commit()
                flash(f"Combo '{nombre}' creado con éxito.")

            else:
                insumo_id = request.form.get('insumo_id') 
                es_helado = False
                peso = 0
                if tipo == 'helado':
                    es_helado = True
                    peso = float(request.form.get('peso', 0))
                
                id_insumo_final = int(insumo_id) if insumo_id else None

                nuevo_prod = Producto(
                    nombre=nombre, 
                    precio=precio, 
                    es_helado=es_helado, 
                    peso_helado=peso, 
                    es_combo=False, 
                    insumo_id=id_insumo_final
                )
                db.session.add(nuevo_prod)
                db.session.commit()
                flash(f"Producto '{nombre}' creado.")

        return redirect(url_for('gestion_precios'))
        
    productos = gestor.obtener_productos()
    return render_template('admin_precios.html', productos=productos, insumos=insumos, productos_para_combo=todos_los_productos)

# --- REPORTES EXCEL (GESTOR MULTI-HOJA) ---
@app.route('/admin/reporte', methods=['POST'])
@login_required
def descargar_reporte():
    if current_user.rol != 'admin': return redirect(url_for('vender'))
    
    fecha_inicio_str = request.form.get('fecha_inicio')
    fecha_fin_str = request.form.get('fecha_fin')

    try:
        fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d')
        fecha_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
        
        excel_file = gestor.generar_reporte_excel(fecha_inicio, fecha_fin)

        if not excel_file:
            flash("No hay ventas en ese rango.")
            return redirect(url_for('admin_dashboard'))

        return send_file(excel_file, as_attachment=True, download_name=f"Reporte_{fecha_inicio_str}.xlsx", mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    except Exception as e:
        print(f"Error reporte: {e}")
        flash("Error fechas.")
        return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    app.run(debug=True)