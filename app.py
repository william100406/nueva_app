import os
from datetime import datetime
from decimal import Decimal
from functools import wraps

from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for
)
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from werkzeug.security import check_password_hash, generate_password_hash


load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv(
    "SECRET_KEY",
    "cambia-esta-clave-secreta"
)


database_url = os.getenv("DATABASE_URL")

if database_url:
    # Compatibilidad con URLs antiguas
    if database_url.startswith("postgres://"):
        database_url = database_url.replace(
            "postgres://",
            "postgresql://",
            1
        )

    if "sslmode=" not in database_url:
        separator = "&" if "?" in database_url else "?"
        database_url = f"{database_url}{separator}sslmode=require"

    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///facturacion.db"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


def wants_json_response():
    return (
        request.is_json
        or request.path.startswith("/api/")
        or request.accept_mimetypes.best == "application/json"
    )


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not session.get("user_id"):
            if not wants_json_response():
                return redirect(url_for("login"))

            return jsonify({
                "error": "Debes iniciar sesion."
            }), 401

        return view(*args, **kwargs)

    return wrapped_view


def get_current_user():
    user_id = session.get("user_id")

    if not user_id:
        return None

    return User.query.get(user_id)


def verify_password(user, password):
    try:
        valid_password = check_password_hash(
            user.password_hash,
            password
        )
    except ValueError:
        valid_password = False

    if valid_password:
        return True

    # Compatibilidad con usuarios creados antes de usar hash.
    if user.password_hash == password:
        user.password_hash = generate_password_hash(password)
        db.session.commit()
        return True

    return False


def user_to_dict(user):
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active
    }


def get_nav_items():
    return [
        {"label": "Inicio", "endpoint": "dashboard", "section": None},
        {"label": "Clientes", "endpoint": "section_page", "section": "clientes"},
        {"label": "Inventario", "endpoint": "section_page", "section": "productos"},
        {"label": "Servicios", "endpoint": "section_page", "section": "servicios"},
        {"label": "Cotizaciones", "endpoint": "section_page", "section": "cotizaciones"},
        {"label": "Ventas", "endpoint": "section_page", "section": "ventas"},
        {"label": "Movimientos", "endpoint": "section_page", "section": "movimientos"},
        {"label": "Perfil", "endpoint": "section_page", "section": "usuarios"}
    ]


def decimal_to_money(value):
    return f"RD$ {value or Decimal('0.00')}"


def parse_decimal(value, default="0.00"):
    raw_value = str(value or "").strip()

    if not raw_value:
        raw_value = default

    return Decimal(raw_value)


def get_action_for_section(section):
    actions = {
        "clientes": {
            "label": "Nuevo cliente",
            "endpoint": "new_customer"
        },
        "productos": {
            "label": "Nuevo producto",
            "endpoint": "new_product"
        },
        "servicios": {
            "label": "Nuevo servicio",
            "endpoint": "new_service"
        }
    }

    return actions.get(section)


def get_section_data(section):
    sections = {
        "clientes": {
            "title": "Clientes",
            "subtitle": "Consulta los clientes registrados en el sistema.",
            "tag": "CRM",
            "action": get_action_for_section("clientes"),
            "columns": ["Nombre", "Email", "Telefono", "RNC/Cedula"],
            "rows": [
                [
                    customer.name,
                    customer.email or "Sin email",
                    customer.phone or "Sin telefono",
                    customer.tax_id or "Sin documento"
                ]
                for customer in Customer.query.order_by(
                    Customer.created_at.desc()
                ).all()
            ]
        },
        "productos": {
            "title": "Inventario",
            "subtitle": "Revisa productos, codigos, precios y stock.",
            "tag": "Inventario",
            "action": get_action_for_section("productos"),
            "columns": ["Codigo", "Producto", "Precio", "Stock"],
            "rows": [
                [
                    product.code,
                    product.name,
                    decimal_to_money(product.sale_price),
                    product.stock
                ]
                for product in Product.query.order_by(
                    Product.created_at.desc()
                ).all()
            ]
        },
        "servicios": {
            "title": "Servicios",
            "subtitle": "Lista de servicios disponibles para cotizar o vender.",
            "tag": "Catalogo",
            "action": get_action_for_section("servicios"),
            "columns": ["Codigo", "Servicio", "Precio base", "Estado"],
            "rows": [
                [
                    service.code,
                    service.name,
                    decimal_to_money(service.base_price),
                    "Activo" if service.is_active else "Inactivo"
                ]
                for service in Service.query.order_by(
                    Service.created_at.desc()
                ).all()
            ]
        },
        "cotizaciones": {
            "title": "Cotizaciones",
            "subtitle": "Seguimiento de cotizaciones creadas.",
            "tag": "Preventa",
            "columns": ["Numero", "Cliente", "Estado", "Total"],
            "rows": [
                [
                    quote.quote_number,
                    quote.customer.name if quote.customer else "Sin cliente",
                    quote.status,
                    decimal_to_money(quote.total)
                ]
                for quote in Quote.query.order_by(
                    Quote.created_at.desc()
                ).all()
            ]
        },
        "ventas": {
            "title": "Ventas",
            "subtitle": "Historial de ventas y pagos registrados.",
            "tag": "Facturacion",
            "columns": ["Numero", "Cliente", "Metodo", "Total"],
            "rows": [
                [
                    sale.sale_number,
                    sale.customer.name if sale.customer else "Sin cliente",
                    sale.payment_method,
                    decimal_to_money(sale.total)
                ]
                for sale in Sale.query.order_by(
                    Sale.created_at.desc()
                ).all()
            ]
        },
        "usuarios": {
            "title": "Perfil",
            "subtitle": "Informacion de acceso y configuracion de cuenta.",
            "tag": "Seguridad",
            "columns": ["Nombre", "Email", "Rol", "Estado"],
            "rows": [
                [
                    user.name,
                    user.email,
                    user.role,
                    "Activo" if user.is_active else "Inactivo"
                ]
                for user in User.query.order_by(
                    User.created_at.desc()
                ).all()
            ]
        },
        "movimientos": {
            "title": "Movimientos de stock",
            "subtitle": "Entradas y salidas de inventario.",
            "tag": "Almacen",
            "columns": ["Producto", "Tipo", "Cantidad", "Notas"],
            "rows": [
                [
                    movement.product.name if movement.product else "Sin producto",
                    movement.movement_type,
                    movement.quantity,
                    movement.notes or "Sin notas"
                ]
                for movement in StockMovement.query.order_by(
                    StockMovement.created_at.desc()
                ).all()
            ]
        }
    }

    return sections.get(section)


class TimestampMixin:
    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )


class User(db.Model, TimestampMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), default="admin")
    is_active = db.Column(db.Boolean, default=True)


class Customer(db.Model, TimestampMixin):
    __tablename__ = "customers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(30))
    email = db.Column(db.String(120))
    address = db.Column(db.Text)
    tax_id = db.Column(db.String(30))  # RNC o cédula


class Product(db.Model, TimestampMixin):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)

    purchase_price = db.Column(
        db.Numeric(12, 2),
        default=Decimal("0.00")
    )

    sale_price = db.Column(
        db.Numeric(12, 2),
        nullable=False
    )

    stock = db.Column(
        db.Numeric(12, 2),
        default=Decimal("0.00")
    )

    min_stock = db.Column(
        db.Numeric(12, 2),
        default=Decimal("0.00")
    )

    is_active = db.Column(db.Boolean, default=True)


class Service(db.Model, TimestampMixin):
    __tablename__ = "services"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)

    base_price = db.Column(
        db.Numeric(12, 2),
        nullable=False
    )

    is_active = db.Column(db.Boolean, default=True)


class Quote(db.Model, TimestampMixin):
    __tablename__ = "quotes"

    id = db.Column(db.Integer, primary_key=True)
    quote_number = db.Column(
        db.String(50),
        unique=True,
        nullable=False
    )

    customer_id = db.Column(
        db.Integer,
        db.ForeignKey("customers.id")
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id")
    )

    status = db.Column(
        db.String(30),
        default="draft"
    )

    subtotal = db.Column(
        db.Numeric(12, 2),
        default=Decimal("0.00")
    )

    discount = db.Column(
        db.Numeric(12, 2),
        default=Decimal("0.00")
    )

    tax = db.Column(
        db.Numeric(12, 2),
        default=Decimal("0.00")
    )

    total = db.Column(
        db.Numeric(12, 2),
        default=Decimal("0.00")
    )

    valid_until = db.Column(db.Date)
    notes = db.Column(db.Text)

    customer = db.relationship("Customer")
    user = db.relationship("User")


class QuoteItem(db.Model):
    __tablename__ = "quote_items"

    id = db.Column(db.Integer, primary_key=True)

    quote_id = db.Column(
        db.Integer,
        db.ForeignKey("quotes.id"),
        nullable=False
    )

    item_type = db.Column(
        db.String(20),
        nullable=False
    )  # product | service

    item_id = db.Column(
        db.Integer,
        nullable=False
    )

    description = db.Column(db.String(255))

    quantity = db.Column(
        db.Numeric(12, 2),
        default=Decimal("1.00")
    )

    unit_price = db.Column(
        db.Numeric(12, 2),
        default=Decimal("0.00")
    )

    discount = db.Column(
        db.Numeric(12, 2),
        default=Decimal("0.00")
    )

    total = db.Column(
        db.Numeric(12, 2),
        default=Decimal("0.00")
    )


class Sale(db.Model, TimestampMixin):
    __tablename__ = "sales"

    id = db.Column(db.Integer, primary_key=True)

    sale_number = db.Column(
        db.String(50),
        unique=True,
        nullable=False
    )

    customer_id = db.Column(
        db.Integer,
        db.ForeignKey("customers.id")
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id")
    )

    quote_id = db.Column(
        db.Integer,
        db.ForeignKey("quotes.id")
    )

    status = db.Column(
        db.String(30),
        default="paid"
    )

    payment_method = db.Column(
        db.String(50),
        default="cash"
    )

    subtotal = db.Column(
        db.Numeric(12, 2),
        default=Decimal("0.00")
    )

    discount = db.Column(
        db.Numeric(12, 2),
        default=Decimal("0.00")
    )

    tax = db.Column(
        db.Numeric(12, 2),
        default=Decimal("0.00")
    )

    total = db.Column(
        db.Numeric(12, 2),
        default=Decimal("0.00")
    )

    paid_amount = db.Column(
        db.Numeric(12, 2),
        default=Decimal("0.00")
    )

    change_amount = db.Column(
        db.Numeric(12, 2),
        default=Decimal("0.00")
    )

    customer = db.relationship("Customer")
    user = db.relationship("User")
    quote = db.relationship("Quote")


class SaleItem(db.Model):
    __tablename__ = "sale_items"

    id = db.Column(db.Integer, primary_key=True)

    sale_id = db.Column(
        db.Integer,
        db.ForeignKey("sales.id"),
        nullable=False
    )

    item_type = db.Column(
        db.String(20),
        nullable=False
    )  # product | service

    item_id = db.Column(
        db.Integer,
        nullable=False
    )

    description = db.Column(db.String(255))

    quantity = db.Column(
        db.Numeric(12, 2),
        default=Decimal("1.00")
    )

    unit_price = db.Column(
        db.Numeric(12, 2),
        default=Decimal("0.00")
    )

    discount = db.Column(
        db.Numeric(12, 2),
        default=Decimal("0.00")
    )

    total = db.Column(
        db.Numeric(12, 2),
        default=Decimal("0.00")
    )


class StockMovement(db.Model, TimestampMixin):
    __tablename__ = "stock_movements"

    id = db.Column(db.Integer, primary_key=True)

    product_id = db.Column(
        db.Integer,
        db.ForeignKey("products.id"),
        nullable=False
    )

    movement_type = db.Column(
        db.String(20),
        nullable=False
    ) 

    quantity = db.Column(
        db.Numeric(12, 2),
        nullable=False
    )

    reference_type = db.Column(db.String(20))
    reference_id = db.Column(db.Integer)
    notes = db.Column(db.Text)

    product = db.relationship("Product")


class Payment(db.Model, TimestampMixin):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)

    sale_id = db.Column(
        db.Integer,
        db.ForeignKey("sales.id"),
        nullable=False
    )

    amount = db.Column(
        db.Numeric(12, 2),
        nullable=False
    )

    method = db.Column(
        db.String(50),
        nullable=False
    )

    reference = db.Column(db.String(100))

    paid_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    sale = db.relationship("Sale")


@app.route("/")
def home():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))

    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    user = get_current_user()
    db_type = (
        "postgresql"
        if "postgresql" in app.config["SQLALCHEMY_DATABASE_URI"]
        else "sqlite"
    )

    totals = {
        "usuarios": User.query.count(),
        "clientes": Customer.query.count(),
        "productos": Product.query.count(),
        "servicios": Service.query.count(),
        "cotizaciones": Quote.query.count(),
        "ventas": Sale.query.count(),
        "movimientos": StockMovement.query.count()
    }

    recent_products = Product.query.order_by(
        Product.created_at.desc()
    ).limit(5).all()

    recent_customers = Customer.query.order_by(
        Customer.created_at.desc()
    ).limit(5).all()

    return render_template(
        "dashboard.html",
        user=user,
        db_type=db_type,
        totals=totals,
        recent_products=recent_products,
        recent_customers=recent_customers,
        nav_items=get_nav_items(),
        active_page="dashboard"
    )


@app.route("/panel/<section>")
@login_required
def section_page(section):
    section_data = get_section_data(section)

    if not section_data:
        return redirect(url_for("dashboard"))

    return render_template(
        "section.html",
        user=get_current_user(),
        nav_items=get_nav_items(),
        active_page=section,
        section_key=section,
        section_data=section_data
    )


@app.route("/clientes/nuevo", methods=["GET", "POST"])
@login_required
def new_customer():
    if request.method == "GET":
        return render_template(
            "form.html",
            user=get_current_user(),
            nav_items=get_nav_items(),
            active_page="clientes",
            title="Nuevo cliente",
            subtitle="Registra los datos principales del cliente.",
            back_url=url_for("section_page", section="clientes"),
            fields=[
                {"name": "name", "label": "Nombre", "type": "text", "required": True},
                {"name": "email", "label": "Email", "type": "email"},
                {"name": "phone", "label": "Telefono", "type": "text"},
                {"name": "tax_id", "label": "RNC/Cedula", "type": "text"},
                {"name": "address", "label": "Direccion", "type": "textarea"}
            ]
        )

    customer = Customer(
        name=request.form.get("name", "").strip(),
        email=request.form.get("email", "").strip() or None,
        phone=request.form.get("phone", "").strip() or None,
        tax_id=request.form.get("tax_id", "").strip() or None,
        address=request.form.get("address", "").strip() or None
    )

    if not customer.name:
        return redirect(url_for("new_customer"))

    db.session.add(customer)
    db.session.commit()
    return redirect(url_for("section_page", section="clientes"))


@app.route("/inventario/nuevo", methods=["GET", "POST"])
@login_required
def new_product():
    if request.method == "GET":
        return render_template(
            "form.html",
            user=get_current_user(),
            nav_items=get_nav_items(),
            active_page="productos",
            title="Nuevo producto",
            subtitle="Agrega un producto al inventario.",
            back_url=url_for("section_page", section="productos"),
            fields=[
                {"name": "code", "label": "Codigo", "type": "text", "required": True},
                {"name": "name", "label": "Producto", "type": "text", "required": True},
                {"name": "description", "label": "Descripcion", "type": "textarea"},
                {"name": "purchase_price", "label": "Precio de compra", "type": "number", "step": "0.01"},
                {"name": "sale_price", "label": "Precio de venta", "type": "number", "step": "0.01", "required": True},
                {"name": "stock", "label": "Stock", "type": "number", "step": "0.01"},
                {"name": "min_stock", "label": "Stock minimo", "type": "number", "step": "0.01"}
            ]
        )

    product = Product(
        code=request.form.get("code", "").strip(),
        name=request.form.get("name", "").strip(),
        description=request.form.get("description", "").strip() or None,
        purchase_price=parse_decimal(request.form.get("purchase_price")),
        sale_price=parse_decimal(request.form.get("sale_price")),
        stock=parse_decimal(request.form.get("stock")),
        min_stock=parse_decimal(request.form.get("min_stock"))
    )

    if not product.code or not product.name:
        return redirect(url_for("new_product"))

    db.session.add(product)
    db.session.commit()
    return redirect(url_for("section_page", section="productos"))


@app.route("/servicios/nuevo", methods=["GET", "POST"])
@login_required
def new_service():
    if request.method == "GET":
        return render_template(
            "form.html",
            user=get_current_user(),
            nav_items=get_nav_items(),
            active_page="servicios",
            title="Nuevo servicio",
            subtitle="Crea un servicio para cotizar o vender.",
            back_url=url_for("section_page", section="servicios"),
            fields=[
                {"name": "code", "label": "Codigo", "type": "text", "required": True},
                {"name": "name", "label": "Servicio", "type": "text", "required": True},
                {"name": "description", "label": "Descripcion", "type": "textarea"},
                {"name": "base_price", "label": "Precio base", "type": "number", "step": "0.01", "required": True}
            ]
        )

    service = Service(
        code=request.form.get("code", "").strip(),
        name=request.form.get("name", "").strip(),
        description=request.form.get("description", "").strip() or None,
        base_price=parse_decimal(request.form.get("base_price"))
    )

    if not service.code or not service.name:
        return redirect(url_for("new_service"))

    db.session.add(service)
    db.session.commit()
    return redirect(url_for("section_page", section="servicios"))


@app.route("/health")
def health():
    try:
        db.session.execute(db.text("SELECT 1"))
        return jsonify({
            "status": "healthy",
            "database": "connected"
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        if session.get("user_id"):
            return redirect(url_for("dashboard"))

        return render_template("login.html")

    data = request.get_json(silent=True) or request.form
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        if not wants_json_response():
            return render_template(
                "login.html",
                error="Email y password son requeridos.",
                email=email
            ), 400

        return jsonify({
            "error": "Email y password son requeridos."
        }), 400

    user = User.query.filter_by(email=email).first()

    if not user or not verify_password(user, password):
        if not wants_json_response():
            return render_template(
                "login.html",
                error="Credenciales incorrectas.",
                email=email
            ), 401

        return jsonify({
            "error": "Credenciales incorrectas."
        }), 401

    if not user.is_active:
        if not wants_json_response():
            return render_template(
                "login.html",
                error="Usuario inactivo.",
                email=email
            ), 403

        return jsonify({
            "error": "Usuario inactivo."
        }), 403

    session.clear()
    session["user_id"] = user.id

    if not wants_json_response():
        return redirect(url_for("dashboard"))

    return jsonify({
        "message": "Login correcto.",
        "user": user_to_dict(user)
    })


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()

    if not wants_json_response():
        return redirect(url_for("login"))

    return jsonify({
        "message": "Sesion cerrada."
    })


@app.route("/me")
@login_required
def me():
    user = get_current_user()

    if not user:
        session.clear()
        return jsonify({
            "error": "Sesion invalida."
        }), 401

    return jsonify({
        "user": user_to_dict(user)
    })


@app.route("/init-db")
def init_db():
    try:
        db.create_all()
        return jsonify({
            "message": "Base de datos creada correctamente."
        })
    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500


@app.route("/seed")
def seed():
    """
    Crea un usuario admin y algunos datos de ejemplo.
    """
    try:
        db.create_all()

        admin = User.query.filter_by(
            email="admin@facturacion.com"
        ).first()

        if not admin:
            admin = User(
                name="Administrador",
                email="admin@facturacion.com",
                password_hash=generate_password_hash("admin123"),
                role="admin"
            )
            db.session.add(admin)

        customer = Customer.query.filter_by(
            name="Cliente General"
        ).first()

        if not customer:
            customer = Customer(
                name="Cliente General"
            )
            db.session.add(customer)

        product = Product.query.filter_by(
            code="P001"
        ).first()

        if not product:
            product = Product(
                code="P001",
                name="Producto de Prueba",
                purchase_price=Decimal("50.00"),
                sale_price=Decimal("100.00"),
                stock=Decimal("10.00"),
                min_stock=Decimal("2.00")
            )
            db.session.add(product)

        service = Service.query.filter_by(
            code="S001"
        ).first()

        if not service:
            service = Service(
                code="S001",
                name="Servicio de Prueba",
                base_price=Decimal("1500.00")
            )
            db.session.add(service)

        db.session.commit()

        return jsonify({
            "message": "Datos de ejemplo creados.",
            "admin_email": "admin@facturacion.com",
            "admin_password": "admin123"
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "error": str(e)
        }), 500


@app.route("/stats")
@login_required
def stats():
    return jsonify({
        "users": User.query.count(),
        "customers": Customer.query.count(),
        "products": Product.query.count(),
        "services": Service.query.count(),
        "quotes": Quote.query.count(),
        "sales": Sale.query.count(),
        "stock_movements": StockMovement.query.count()
    })

if __name__ == "__main__":
    if "sqlite" in app.config["SQLALCHEMY_DATABASE_URI"]:
        with app.app_context():
            db.create_all()
    else:
        print("Base PostgreSQL configurada. Usa /init-db para crear tablas.")

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True,
        use_reloader=False
    )
